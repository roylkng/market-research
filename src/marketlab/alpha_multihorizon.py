from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_corporate_actions import (
    action_index,
    blocked_actions,
    validate_action_ledger,
)
from marketlab.alpha_diagnostics import (
    report_time_series_inference,
    signed_single_feature_walkforward,
)
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

SUPPORTED_HORIZONS = (1, 5, 20, 60)


def build_action_safe_horizon_examples(
    *,
    feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    action_ledger: dict[str, Any],
    horizons: tuple[int, ...] = SUPPORTED_HORIZONS,
) -> tuple[dict[int, list[ModelExample]], dict[str, int]]:
    validate_action_ledger(action_ledger)
    if not horizons or any(horizon not in SUPPORTED_HORIZONS for horizon in horizons):
        raise AlphaContractError(
            f"horizons must be a non-empty subset of {SUPPORTED_HORIZONS}"
        )
    if feature_panel.get("corporate_action_ledger_sha256") != action_ledger.get(
        "ledger_sha256"
    ):
        raise AlphaContractError(
            "feature panel is not bound to the supplied corporate-action ledger"
        )

    sessions = market_panel.get("sessions")
    if not isinstance(sessions, list) or len(sessions) < 2:
        raise AlphaContractError("market panel requires completed sessions")
    session_dates = [str(row["session_date"]) for row in sessions]
    if session_dates != sorted(session_dates) or len(session_dates) != len(set(session_dates)):
        raise AlphaContractError("market sessions must be unique and chronological")
    session_index = {value: index for index, value in enumerate(session_dates)}

    stock_by_session: dict[
        str, dict[tuple[str, str], DailyEquityObservation]
    ] = {}
    benchmark_by_session: dict[str, IndexDailyPrice] = {}
    for session in sessions:
        day = str(session["session_date"])
        equities = session.get("equities")
        benchmark_raw = session.get("benchmark")
        if not isinstance(equities, list) or not isinstance(
            benchmark_raw, (dict, IndexDailyPrice)
        ):
            raise AlphaContractError(f"{day}: malformed market session")
        identity_map = {}
        for raw in equities:
            row = (
                raw
                if isinstance(raw, DailyEquityObservation)
                else DailyEquityObservation(**raw)
            )
            key = (row.symbol, row.isin)
            if key in identity_map:
                raise AlphaContractError(f"{day}: duplicate stock identity {key}")
            identity_map[key] = row
        stock_by_session[day] = identity_map
        benchmark_by_session[day] = (
            benchmark_raw
            if isinstance(benchmark_raw, IndexDailyPrice)
            else IndexDailyPrice(**benchmark_raw)
        )

    actions = action_index(action_ledger)
    examples = {horizon: [] for horizon in sorted(set(horizons))}
    exclusions: dict[str, int] = defaultdict(int)
    rows = feature_panel.get("rows")
    if not isinstance(rows, list):
        raise AlphaContractError("feature panel rows must be a list")

    for row in rows:
        feature_session = str(row["feature_session"])
        feature_index = session_index.get(feature_session)
        if feature_index is None:
            raise AlphaContractError(
                f"{feature_session}: feature session absent from market panel"
            )
        entry_index = feature_index + 1
        if entry_index >= len(session_dates):
            for horizon in examples:
                exclusions[f"H{horizon}:NOT_MATURE"] += 1
            continue
        entry_session = session_dates[entry_index]
        identity = (str(row["symbol"]), str(row["isin"]))
        entry_stock = stock_by_session[entry_session].get(identity)
        if entry_stock is None:
            for horizon in examples:
                exclusions[f"H{horizon}:MISSING_ENTRY_IDENTITY"] += 1
            continue
        values = row.get("values")
        if not isinstance(values, dict):
            raise AlphaContractError("feature row values must be an object")

        action_state = actions.get(identity[0].upper())
        if action_state is not None and action_state.get("status") != "READY":
            for horizon in examples:
                exclusions[f"H{horizon}:ACTION_AUDIT_UNRESOLVED"] += 1
            continue

        for horizon, horizon_examples in examples.items():
            exit_index = entry_index + horizon - 1
            if exit_index >= len(session_dates):
                exclusions[f"H{horizon}:NOT_MATURE"] += 1
                continue
            exit_session = session_dates[exit_index]
            exit_stock = stock_by_session[exit_session].get(identity)
            if exit_stock is None:
                exclusions[f"H{horizon}:MISSING_EXIT_IDENTITY"] += 1
                continue
            relevant = blocked_actions(
                actions,
                symbol=identity[0],
                start_exclusive=entry_session,
                end_inclusive=exit_session,
            )
            if relevant:
                exclusions[f"H{horizon}:CORPORATE_ACTION_BLOCKED"] += 1
                continue

            benchmark_entry = benchmark_by_session[entry_session]
            benchmark_exit = benchmark_by_session[exit_session]
            stock_return = exit_stock.close_price / entry_stock.open_price - 1.0
            benchmark_return = (
                benchmark_exit.close_price / benchmark_entry.open_price - 1.0
            )
            target = stock_return - benchmark_return
            if not math.isfinite(target):
                exclusions[f"H{horizon}:NONFINITE_TARGET"] += 1
                continue
            horizon_examples.append(
                ModelExample(
                    symbol=identity[0],
                    isin=identity[1],
                    feature_session=feature_session,
                    entry_session=entry_session,
                    exit_session=exit_session,
                    horizon_sessions=horizon,
                    features={
                        str(name): (None if value is None else float(value))
                        for name, value in values.items()
                    },
                    target_excess_return=target,
                )
            )

    for horizon_examples in examples.values():
        horizon_examples.sort(
            key=lambda item: (item.feature_session, item.symbol, item.isin)
        )
    return examples, dict(sorted(exclusions.items()))


def _validate_folds(folds: list[dict[str, str]]) -> None:
    if not folds:
        raise AlphaContractError("at least one fold is required")
    prior_end: str | None = None
    for fold in folds:
        start = str(fold.get("start") or "")
        end = str(fold.get("end") or "")
        if not start or not end or start > end:
            raise AlphaContractError("invalid horizon fold")
        if prior_end is not None and start <= prior_end:
            raise AlphaContractError("horizon folds must be ordered and non-overlapping")
        prior_end = end


def run_action_safe_horizon_walkforward(
    *,
    feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    action_ledger: dict[str, Any],
    folds_by_horizon: dict[int, list[dict[str, str]]],
    l2: float = 1.0,
) -> dict[str, Any]:
    ranked = (
        feature_panel
        if feature_panel.get("transform") == "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1"
        else cross_sectionalize_panel(feature_panel)
    )
    definitions = ranked.get("feature_definitions")
    if not isinstance(definitions, list) or not definitions:
        raise AlphaContractError("feature definitions are required")
    feature_names = [str(row["name"]) for row in definitions]

    horizons = tuple(sorted(folds_by_horizon))
    examples_by_horizon, exclusions = build_action_safe_horizon_examples(
        feature_panel=ranked,
        market_panel=market_panel,
        action_ledger=action_ledger,
        horizons=horizons,
    )

    horizon_reports = {}
    for horizon in horizons:
        folds = folds_by_horizon[horizon]
        _validate_folds(folds)
        examples = examples_by_horizon[horizon]
        all_predictions = []
        fold_reports = []
        for fold_index, fold in enumerate(folds, start=1):
            start = str(fold["start"])
            end = str(fold["end"])
            train = purge_training_examples(
                examples,
                validation_start_session=start,
            )
            validation = [
                row for row in examples if start <= row.feature_session <= end
            ]
            if len(train) < 100:
                raise AlphaContractError(
                    f"H{horizon} fold {fold_index}: insufficient purged training data"
                )
            if not validation:
                raise AlphaContractError(
                    f"H{horizon} fold {fold_index}: validation is empty"
                )
            model = fit_ridge(
                train,
                feature_names=feature_names,
                l2=l2,
                model_id=f"AE001-RIDGE-H{horizon}-F{fold_index:02d}",
            )
            oos = predict_ridge(
                model,
                validation,
                prediction_role="OOS",
            )
            all_predictions.extend(oos)
            fold_reports.append(
                {
                    "fold": fold_index,
                    "start": start,
                    "end": end,
                    "training_example_count": len(train),
                    "validation_example_count": len(validation),
                    "training_last_exit_session": model.training_last_exit_session,
                    "model_sha256": model.model_sha256,
                    "oos": evaluate_cross_sectional_predictions(oos),
                }
            )

        ridge_report = evaluate_cross_sectional_predictions(all_predictions)
        singles = signed_single_feature_walkforward(
            examples,
            folds=folds,
            feature_names=feature_names,
        )
        horizon_reports[str(horizon)] = {
            "horizon_sessions": horizon,
            "example_count": len(examples),
            "folds": fold_reports,
            "ridge": ridge_report,
            "ridge_time_series_inference": report_time_series_inference(
                ridge_report,
                max_lag=5,
            ),
            "best_single_feature_train_selected": singles[
                "best_single_feature_train_selected_oos"
            ],
            "best_single_feature_time_series_inference": (
                report_time_series_inference(
                    singles["best_single_feature_train_selected_oos"],
                    max_lag=5,
                )
            ),
            "signed_single_feature_folds": singles["folds"],
            "signed_single_features_oos": singles["per_feature_oos"],
        }

    report = {
        "schema_version": 1,
        "walkforward_id": "AE001-ACTION-SAFE-MULTIHORIZON-v1",
        "engine_id": "AE001-v1-DEVELOPMENT",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "feature_panel_sha256": feature_panel["panel_sha256"],
        "market_panel_sha256": market_panel["panel_sha256"],
        "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
        "l2": l2,
        "horizons": horizon_reports,
        "exclusions": exclusions,
        "cost_model_status": "NOT_IMPLEMENTED_TC001_REQUIRED",
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
