from __future__ import annotations

import math
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_history import cross_sectionalize_panel
from marketlab.alpha_market import DailyEquityObservation
from marketlab.alpha_model import (
    ModelExample,
    evaluate_cross_sectional_predictions,
    fit_ridge,
    predict_ridge,
    purge_training_examples,
)
from marketlab.marketdata import IndexDailyPrice

AE001_WALKFORWARD_ID = "AE001-WF-RIDGE-1D-v1"


def build_one_session_examples(
    *,
    feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
) -> tuple[list[ModelExample], dict[str, int]]:
    """Join AE001 features to next-session open-to-close excess returns.

    The 1-session label enters and exits on the same subsequent session. This
    avoids cross-session share-basis discontinuity from splits/bonus/rights.
    Longer horizons require the corporate-action blocker and are intentionally
    out of scope for this v1 pilot.
    """

    if feature_panel.get("outcomes_attached") is not False:
        raise AlphaContractError("feature panel must not contain outcomes")
    sessions = market_panel.get("sessions")
    if not isinstance(sessions, list) or len(sessions) < 2:
        raise AlphaContractError("market panel requires at least two sessions")

    session_dates = [str(row["session_date"]) for row in sessions]
    if session_dates != sorted(session_dates) or len(session_dates) != len(set(session_dates)):
        raise AlphaContractError("market panel sessions must be unique and chronological")

    stock_by_session: dict[
        str, dict[tuple[str, str], DailyEquityObservation]
    ] = {}
    benchmark_by_session: dict[str, IndexDailyPrice] = {}
    for session in sessions:
        session_date = str(session["session_date"])
        equities = session.get("equities")
        benchmark_raw = session.get("benchmark")
        if not isinstance(equities, list) or not isinstance(
            benchmark_raw, (dict, IndexDailyPrice)
        ):
            raise AlphaContractError(f"{session_date}: malformed market session")
        identities: dict[tuple[str, str], DailyEquityObservation] = {}
        for raw in equities:
            observation = (
                raw
                if isinstance(raw, DailyEquityObservation)
                else DailyEquityObservation(**raw)
            )
            key = (observation.symbol, observation.isin)
            if key in identities:
                raise AlphaContractError(
                    f"{session_date}: duplicate identity in market panel {key}"
                )
            identities[key] = observation
        stock_by_session[session_date] = identities
        benchmark_by_session[session_date] = (
            benchmark_raw
            if isinstance(benchmark_raw, IndexDailyPrice)
            else IndexDailyPrice(**benchmark_raw)
        )

    index_by_session = {session: index for index, session in enumerate(session_dates)}
    exclusions = {
        "NO_NEXT_SESSION": 0,
        "MISSING_NEXT_SESSION_IDENTITY": 0,
        "NONFINITE_TARGET": 0,
    }
    examples: list[ModelExample] = []
    rows = feature_panel.get("rows")
    if not isinstance(rows, list):
        raise AlphaContractError("feature panel rows must be a list")

    for row in rows:
        feature_session = str(row["feature_session"])
        session_index = index_by_session.get(feature_session)
        if session_index is None:
            raise AlphaContractError(
                f"feature session is absent from market panel: {feature_session}"
            )
        if session_index + 1 >= len(session_dates):
            exclusions["NO_NEXT_SESSION"] += 1
            continue
        next_session = session_dates[session_index + 1]
        identity = (str(row["symbol"]), str(row["isin"]))
        stock = stock_by_session[next_session].get(identity)
        if stock is None:
            exclusions["MISSING_NEXT_SESSION_IDENTITY"] += 1
            continue
        benchmark = benchmark_by_session[next_session]
        stock_return = stock.close_price / stock.open_price - 1.0
        benchmark_return = benchmark.close_price / benchmark.open_price - 1.0
        target = stock_return - benchmark_return
        if not math.isfinite(target):
            exclusions["NONFINITE_TARGET"] += 1
            continue
        values = row.get("values")
        if not isinstance(values, dict):
            raise AlphaContractError("feature row values must be an object")
        examples.append(
            ModelExample(
                symbol=identity[0],
                isin=identity[1],
                feature_session=feature_session,
                entry_session=next_session,
                exit_session=next_session,
                horizon_sessions=1,
                features={
                    str(name): (None if value is None else float(value))
                    for name, value in values.items()
                },
                target_excess_return=target,
            )
        )

    examples.sort(key=lambda row: (row.feature_session, row.symbol, row.isin))
    return examples, exclusions


def _prediction_baseline(
    examples: list[ModelExample],
    *,
    feature_name: str,
    model_id: str,
) -> list[dict[str, Any]]:
    rows = []
    for example in examples:
        value = example.features.get(feature_name)
        if value is None:
            continue
        rows.append(
            {
                "model_id": model_id,
                "symbol": example.symbol,
                "isin": example.isin,
                "feature_session": example.feature_session,
                "prediction": float(value),
                "target_excess_return": example.target_excess_return,
                "prediction_role": "OOS",
                "oos_only": True,
                "live_capital_allowed": False,
            }
        )
    return rows


def _cost_views(report: dict[str, Any]) -> dict[str, float | None]:
    gross = report.get("mean_top_decile_excess")
    if gross is None:
        return {"0bps": None, "25bps": None, "50bps": None}
    value = float(gross)
    return {
        "0bps": value,
        "25bps": value - 0.0025,
        "50bps": value - 0.0050,
    }


def run_ridge_walkforward(
    *,
    feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    folds: list[dict[str, str]],
    feature_names: list[str] | None = None,
    l2: float = 1.0,
) -> dict[str, Any]:
    if not folds:
        raise AlphaContractError("at least one walk-forward fold is required")
    ranked_panel = (
        feature_panel
        if feature_panel.get("transform") == "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1"
        else cross_sectionalize_panel(feature_panel)
    )
    examples, exclusions = build_one_session_examples(
        feature_panel=ranked_panel,
        market_panel=market_panel,
    )
    if not examples:
        raise AlphaContractError("no complete one-session examples are available")

    definitions = ranked_panel.get("feature_definitions")
    if not isinstance(definitions, list):
        raise AlphaContractError("feature definitions are missing")
    all_features = [str(row["name"]) for row in definitions]
    selected = feature_names or all_features
    if not selected or not set(selected).issubset(set(all_features)):
        raise AlphaContractError("walk-forward feature selection is invalid")

    all_predictions: list[dict[str, Any]] = []
    baseline_predictions: list[dict[str, Any]] = []
    fold_reports = []

    prior_end: str | None = None
    for fold_index, fold in enumerate(folds, start=1):
        start = str(fold.get("start") or "")
        end = str(fold.get("end") or "")
        if not start or not end or start > end:
            raise AlphaContractError("walk-forward fold start/end is invalid")
        if prior_end is not None and start <= prior_end:
            raise AlphaContractError("walk-forward folds must be non-overlapping and ordered")
        prior_end = end

        train = purge_training_examples(
            examples,
            validation_start_session=start,
        )
        validation = [
            row for row in examples if start <= row.feature_session <= end
        ]
        if len(train) < 100:
            raise AlphaContractError(
                f"fold {fold_index}: fewer than 100 purged training examples"
            )
        if not validation:
            raise AlphaContractError(f"fold {fold_index}: validation window is empty")

        model = fit_ridge(
            train,
            feature_names=selected,
            l2=l2,
            model_id=f"AE001-RIDGE-1D-v1-F{fold_index:02d}",
        )
        predictions = predict_ridge(
            model,
            validation,
            prediction_role="OOS",
        )
        baseline = _prediction_baseline(
            validation,
            feature_name="momentum_20",
            model_id=f"AE001-BASE-MOM20-F{fold_index:02d}",
        )
        all_predictions.extend(predictions)
        baseline_predictions.extend(baseline)
        fold_reports.append(
            {
                "fold": fold_index,
                "start": start,
                "end": end,
                "training_example_count": len(train),
                "validation_example_count": len(validation),
                "training_last_exit_session": model.training_last_exit_session,
                "model_sha256": model.model_sha256,
                "ridge": evaluate_cross_sectional_predictions(predictions),
                "momentum_20_baseline": evaluate_cross_sectional_predictions(baseline),
            }
        )

    ridge_report = evaluate_cross_sectional_predictions(all_predictions)
    baseline_report = evaluate_cross_sectional_predictions(baseline_predictions)
    report: dict[str, Any] = {
        "schema_version": 1,
        "walkforward_id": AE001_WALKFORWARD_ID,
        "engine_id": "AE001-v1-DEVELOPMENT",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "horizon_sessions": 1,
        "label_convention": "NEXT_COMPLETED_NSE_SESSION_OPEN_TO_SAME_SESSION_CLOSE_EXCESS_VS_NIFTY500",
        "corporate_action_cross_session_blocker_required": False,
        "feature_transform": "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1",
        "feature_names": selected,
        "l2": l2,
        "folds": fold_reports,
        "exclusions": exclusions,
        "oos_prediction_count": len(all_predictions),
        "ridge": ridge_report,
        "momentum_20_baseline": baseline_report,
        "ridge_top_decile_cost_views": _cost_views(ridge_report),
        "baseline_top_decile_cost_views": _cost_views(baseline_report),
        "oos_predictions": all_predictions,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
