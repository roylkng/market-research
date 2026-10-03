from __future__ import annotations

import copy
import math
import statistics
from collections import defaultdict
from typing import Any

import numpy as np

from marketlab.ab001 import validate_alpha_library
from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_diagnostics import paired_report_difference_inference
from marketlab.alpha_model import evaluate_cross_sectional_predictions

PILOT_ID = "AB001-P004-v1"
HORIZON = 5
RIDGE_L2 = 1.0
MIN_TRAINING_SESSIONS = 40
NW_LAG = 4

ALPHA_CORE = "AB001-P003-CORE27"
ALPHA_DELTA = "AB001-P003-FUTURES-DELTA"

EXPECTED_P003_REPORT_SHA = (
    "0d833a280dcc741ebba13bfe8b753689b7ff1ad41f0b2c13181fd8b0c37552c6"
)
EXPECTED_P003_LIBRARY_SHA = (
    "4e04142bb3b33ca9f1c86de456bed1e5479d7d6c89bd72e59bff14b5c713ec36"
)
EXPECTED_P003_MARKET_SHA = (
    "9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e"
)

CONTEXT_VARIABLES = (
    "nifty500_return_20",
    "nifty500_realized_vol_20",
    "breadth_positive_momentum20_fraction",
)


def _verify_hash(payload: dict[str, Any], *, field: str, label: str) -> None:
    stored = str(payload.get(field) or "")
    unsigned = copy.deepcopy(payload)
    unsigned.pop(field, None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError(f"AB001 P004 {label} hash mismatch")


def _verify_sources(
    p003_report: dict[str, Any],
    regime_panel: dict[str, Any],
) -> dict[str, Any]:
    _verify_hash(p003_report, field="report_sha256", label="P003 report")
    if p003_report.get("pilot_id") != "AB001-P003-v1":
        raise AlphaContractError("AB001 P004 unexpected P003 pilot id")
    if p003_report.get("report_sha256") != EXPECTED_P003_REPORT_SHA:
        raise AlphaContractError("AB001 P004 P003 report differs from frozen source")
    if int(p003_report.get("horizon_sessions") or 0) != HORIZON:
        raise AlphaContractError("AB001 P004 source horizon differs from frozen 5D")
    library = p003_report.get("library")
    if not isinstance(library, dict):
        raise AlphaContractError("AB001 P004 P003 alpha library is missing")
    validate_alpha_library(library)
    if library.get("library_sha256") != EXPECTED_P003_LIBRARY_SHA:
        raise AlphaContractError("AB001 P004 P003 library differs from frozen source")

    _verify_hash(regime_panel, field="panel_sha256", label="RG001 panel")
    if regime_panel.get("panel_id") != "AE001-RG001-v1":
        raise AlphaContractError("AB001 P004 unexpected RG001 panel id")
    if regime_panel.get("market_panel_sha256") != EXPECTED_P003_MARKET_SHA:
        raise AlphaContractError(
            "AB001 P004 RG001 market source differs from frozen P003 panel"
        )
    if regime_panel.get("stock_level_alpha") is not False:
        raise AlphaContractError("AB001 P004 RG001 must not be stock-level alpha")
    if regime_panel.get("outcomes_attached") is not False:
        raise AlphaContractError("AB001 P004 RG001 must be outcome-free")
    observed = set(regime_panel.get("variable_names") or [])
    if not set(CONTEXT_VARIABLES).issubset(observed):
        raise AlphaContractError("AB001 P004 frozen context variables are missing")
    return library


def _session_rows(
    library: dict[str, Any],
) -> dict[str, dict[str, dict[tuple[str, str], dict[str, Any]]]]:
    by_alpha: dict[
        str, dict[str, dict[tuple[str, str], dict[str, Any]]]
    ] = {
        ALPHA_CORE: defaultdict(dict),
        ALPHA_DELTA: defaultdict(dict),
    }
    for row in library["records"]:
        alpha = str(row["alpha_id"])
        if alpha not in by_alpha:
            continue
        if int(row["horizon_sessions"]) != HORIZON:
            continue
        if row["outcome_status"] != "COMPLETE":
            continue
        if row["target_excess_return"] is None:
            raise AlphaContractError("AB001 P004 complete source row lacks target")
        session = str(row["feature_session"])
        identity = (str(row["symbol"]), str(row["isin"]))
        if identity in by_alpha[alpha][session]:
            raise AlphaContractError("AB001 P004 duplicate alpha/session identity")
        by_alpha[alpha][session][identity] = row
    return {
        alpha: dict(sessions)
        for alpha, sessions in by_alpha.items()
    }


def _session_prediction_report(
    rows: dict[tuple[str, str], dict[str, Any]],
    *,
    session: str,
) -> dict[str, Any]:
    predictions = [
        {
            "symbol": identity[0],
            "isin": identity[1],
            "feature_session": session,
            "prediction": float(row["normalized_score"]),
            "target_excess_return": float(row["target_excess_return"]),
        }
        for identity, row in sorted(rows.items())
    ]
    if len(predictions) < 5:
        raise AlphaContractError("AB001 P004 session has too few stock rows")
    report = evaluate_cross_sectional_predictions(predictions)
    if report["session_count"] != 1:
        raise AlphaContractError("AB001 P004 expected one-session report")
    metric = report["session_metrics"][0]
    if metric["rank_ic"] is None:
        raise AlphaContractError("AB001 P004 session rank IC is undefined")
    return metric


def _build_session_table(
    library: dict[str, Any],
    regime_panel: dict[str, Any],
) -> list[dict[str, Any]]:
    sources = _session_rows(library)
    context_by_session = {
        str(row["session_date"]): row
        for row in regime_panel["rows"]
    }
    common_sessions = sorted(
        set(sources[ALPHA_CORE])
        & set(sources[ALPHA_DELTA])
        & set(context_by_session)
    )
    if not common_sessions:
        raise AlphaContractError("AB001 P004 has no common alpha/context sessions")

    table = []
    for session in common_sessions:
        core_map = sources[ALPHA_CORE][session]
        delta_map = sources[ALPHA_DELTA][session]
        common_ids = sorted(set(core_map) & set(delta_map))
        if len(common_ids) < 5:
            continue
        core_rows = {identity: core_map[identity] for identity in common_ids}
        delta_rows = {identity: delta_map[identity] for identity in common_ids}

        exit_sessions = {
            str(row["exit_session"])
            for row in [*core_rows.values(), *delta_rows.values()]
        }
        if len(exit_sessions) != 1:
            raise AlphaContractError("AB001 P004 aligned session exit dates disagree")
        targets_core = {
            identity: float(core_rows[identity]["target_excess_return"])
            for identity in common_ids
        }
        targets_delta = {
            identity: float(delta_rows[identity]["target_excess_return"])
            for identity in common_ids
        }
        if targets_core != targets_delta:
            raise AlphaContractError("AB001 P004 aligned alpha targets disagree")

        core_metric = _session_prediction_report(core_rows, session=session)
        delta_metric = _session_prediction_report(delta_rows, session=session)
        context_values = context_by_session[session].get("values")
        if not isinstance(context_values, dict):
            raise AlphaContractError("AB001 P004 RG001 context values are missing")
        context = {}
        for variable in CONTEXT_VARIABLES:
            value = float(context_values[variable])
            if not math.isfinite(value):
                raise AlphaContractError("AB001 P004 context contains nonfinite value")
            context[variable] = value

        table.append(
            {
                "feature_session": session,
                "exit_session": exit_sessions.pop(),
                "context": context,
                "core_rank_ic": float(core_metric["rank_ic"]),
                "delta_rank_ic": float(delta_metric["rank_ic"]),
                "relative_ic": (
                    float(delta_metric["rank_ic"])
                    - float(core_metric["rank_ic"])
                ),
                "common_identity_count": len(common_ids),
                "core_rows": core_rows,
                "delta_rows": delta_rows,
            }
        )
    return table


def _fit_context_ridge(
    training: list[dict[str, Any]],
    current_context: dict[str, float],
) -> dict[str, Any]:
    if len(training) < MIN_TRAINING_SESSIONS:
        raise AlphaContractError("AB001 P004 insufficient matured training sessions")

    means = {}
    stds = {}
    columns = []
    current = []
    for variable in CONTEXT_VARIABLES:
        values = [float(row["context"][variable]) for row in training]
        mean = statistics.mean(values)
        std = statistics.pstdev(values)
        means[variable] = mean
        stds[variable] = std
        if std == 0.0:
            columns.append([0.0 for _ in values])
            current.append(0.0)
        else:
            columns.append([(value - mean) / std for value in values])
            current.append((float(current_context[variable]) - mean) / std)

    matrix = np.asarray(columns, dtype=float).T
    target = np.asarray(
        [float(row["relative_ic"]) for row in training],
        dtype=float,
    )
    target_mean = float(target.mean())
    centered = target - target_mean
    penalty = np.eye(len(CONTEXT_VARIABLES), dtype=float) * RIDGE_L2
    gram = matrix.T @ matrix + penalty
    rhs = matrix.T @ centered
    try:
        coefficients = np.linalg.solve(gram, rhs)
    except np.linalg.LinAlgError as exc:
        raise AlphaContractError("AB001 P004 ridge system is singular") from exc

    predicted = target_mean + float(
        np.asarray(current, dtype=float) @ coefficients
    )
    if not math.isfinite(predicted):
        raise AlphaContractError("AB001 P004 predicted relative IC is nonfinite")

    return {
        "intercept": target_mean,
        "coefficients": {
            variable: float(coefficients[index])
            for index, variable in enumerate(CONTEXT_VARIABLES)
        },
        "training_context_mean": means,
        "training_context_std": stds,
        "predicted_relative_ic": predicted,
        "training_session_count": len(training),
    }


def _rows_to_predictions(
    session_row: dict[str, Any],
    *,
    prediction_source: str,
) -> list[dict[str, Any]]:
    session = str(session_row["feature_session"])
    core_rows = session_row["core_rows"]
    delta_rows = session_row["delta_rows"]
    common = sorted(set(core_rows) & set(delta_rows))
    predictions = []
    for identity in common:
        core = core_rows[identity]
        delta = delta_rows[identity]
        if prediction_source == "CORE27":
            score = float(core["normalized_score"])
        elif prediction_source == "FUTURES_DELTA":
            score = float(delta["normalized_score"])
        elif prediction_source == "STATIC_EQUAL_BLEND":
            score = (
                float(core["normalized_score"])
                + float(delta["normalized_score"])
            ) / 2.0
        else:
            raise AlphaContractError(
                f"AB001 P004 unsupported prediction source: {prediction_source}"
            )
        predictions.append(
            {
                "symbol": identity[0],
                "isin": identity[1],
                "feature_session": session,
                "prediction": score,
                "target_excess_return": float(core["target_excess_return"]),
            }
        )
    return predictions


def run_ab001_p004(
    *,
    p003_report: dict[str, Any],
    regime_panel: dict[str, Any],
) -> dict[str, Any]:
    library = _verify_sources(p003_report, regime_panel)
    table = _build_session_table(library, regime_panel)

    selector_predictions = []
    futures_predictions = []
    equal_predictions = []
    decisions = []

    for current in table:
        session = str(current["feature_session"])
        training = [
            row for row in table
            if str(row["exit_session"]) < session
        ]
        if len(training) < MIN_TRAINING_SESSIONS:
            continue

        fit = _fit_context_ridge(training, current["context"])
        choose_futures = float(fit["predicted_relative_ic"]) > 0.0
        choice = "FUTURES_DELTA" if choose_futures else "CORE27"

        selector_predictions.extend(
            _rows_to_predictions(current, prediction_source=choice)
        )
        futures_predictions.extend(
            _rows_to_predictions(
                current,
                prediction_source="FUTURES_DELTA",
            )
        )
        equal_predictions.extend(
            _rows_to_predictions(
                current,
                prediction_source="STATIC_EQUAL_BLEND",
            )
        )
        realized_relative = float(current["relative_ic"])
        decisions.append(
            {
                "feature_session": session,
                "exit_session": current["exit_session"],
                "training_session_count": fit["training_session_count"],
                "context": current["context"],
                "training_context_mean": fit["training_context_mean"],
                "training_context_std": fit["training_context_std"],
                "intercept": fit["intercept"],
                "coefficients": fit["coefficients"],
                "predicted_relative_ic": fit["predicted_relative_ic"],
                "realized_relative_ic": realized_relative,
                "choice": choice,
                "directionally_correct": (
                    choose_futures == (realized_relative > 0.0)
                ),
                "common_identity_count": current["common_identity_count"],
            }
        )

    if not decisions:
        raise AlphaContractError("AB001 P004 produced no eligible selector sessions")

    selector_report = evaluate_cross_sectional_predictions(
        selector_predictions
    )
    futures_report = evaluate_cross_sectional_predictions(
        futures_predictions
    )
    equal_report = evaluate_cross_sectional_predictions(
        equal_predictions
    )
    selector_vs_futures = paired_report_difference_inference(
        selector_report,
        futures_report,
        max_lag=NW_LAG,
    )
    selector_vs_equal = paired_report_difference_inference(
        selector_report,
        equal_report,
        max_lag=NW_LAG,
    )

    choice_counts = {
        "CORE27": sum(row["choice"] == "CORE27" for row in decisions),
        "FUTURES_DELTA": sum(
            row["choice"] == "FUTURES_DELTA" for row in decisions
        ),
    }
    directional_accuracy = statistics.mean(
        1.0 if row["directionally_correct"] else 0.0
        for row in decisions
    )
    rank_delta = selector_vs_futures["metrics"]["rank_ic"]
    primary_supported = (
        float(rank_delta["mean"]) > 0.0
        and float(rank_delta["p_value_two_sided"]) < 0.05
    )

    report: dict[str, Any] = {
        "schema_version": 1,
        "pilot_id": PILOT_ID,
        "evidence_class": (
            "HISTORICAL_KNOWN_OUTCOME_REGIME_EFFICACY_DIAGNOSTIC"
        ),
        "horizon_sessions": HORIZON,
        "source": {
            "p003_report_sha256": p003_report["report_sha256"],
            "p003_library_sha256": library["library_sha256"],
            "rg001_panel_sha256": regime_panel["panel_sha256"],
            "context_variables": list(CONTEXT_VARIABLES),
        },
        "training_contract": {
            "maturity_rule": "EXIT_SESSION_LT_DECISION_SESSION",
            "minimum_matured_sessions": MIN_TRAINING_SESSIONS,
            "normalization": "TRAINING_ONLY_ZSCORE",
            "ridge_lambda": RIDGE_L2,
            "selector_threshold": 0.0,
        },
        "eligible_selector_session_count": len(decisions),
        "selector": selector_report,
        "always_futures_delta": futures_report,
        "static_equal_blend": equal_report,
        "selector_minus_always_futures_inference": selector_vs_futures,
        "selector_minus_static_equal_inference": selector_vs_equal,
        "selector_choice_counts": choice_counts,
        "selector_directional_accuracy": directional_accuracy,
        "decisions": decisions,
        "primary_endpoint": {
            "metric": "PAIRED_DAILY_MEAN_RANK_IC_DELTA_VS_ALWAYS_FUTURES_DELTA",
            "mean_delta": rank_delta["mean"],
            "p_value_two_sided": rank_delta["p_value_two_sided"],
            "supported": primary_supported,
        },
        "secondary_may_rescue_primary": False,
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
