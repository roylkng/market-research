from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_diagnostics import newey_west_mean_inference

STUDY_ID = "PO001-I006-v1"
ALPHA_ID = "AB001-P003-FUTURES-DELTA"
EXPECTED_P003_REPORT_SHA = (
    "0d833a280dcc741ebba13bfe8b753689b7ff1ad41f0b2c13181fd8b0c37552c6"
)
EXPECTED_P003_LIBRARY_SHA = (
    "4e04142bb3b33ca9f1c86de456bed1e5479d7d6c89bd72e59bff14b5c713ec36"
)
EXPECTED_RG001_PANEL_SHA = (
    "7921fb8db899016f73162d33642b916db71c5b65768d530a47d50c7c06a562f6"
)
HORIZON_SESSIONS = 5
TRAILING_REGIME_SESSIONS = 60
UTILITY_GAMMA = 5.0
NEWey_WEST_LAG = 4
TOP_DECILE_SHARE = 0.10


def _verify_embedded_hash(
    payload: dict[str, Any],
    *,
    field: str,
    expected: str,
    name: str,
) -> None:
    observed = str(payload.get(field) or "")
    if observed != expected:
        raise AlphaContractError(
            f"I006 {name} hash mismatch: {observed} != {expected}"
        )


def _verify_rg001(panel: dict[str, Any]) -> None:
    stored = str(panel.get("panel_sha256") or "")
    unsigned = dict(panel)
    unsigned.pop("panel_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("I006 RG001 panel content hash mismatch")
    if stored != EXPECTED_RG001_PANEL_SHA:
        raise AlphaContractError("I006 RG001 panel differs from frozen P004 source")
    if panel.get("outcomes_attached") is not False:
        raise AlphaContractError("I006 RG001 panel unexpectedly contains outcomes")


def _top_decile_session_returns(
    p003_report: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    _verify_embedded_hash(
        p003_report,
        field="report_sha256",
        expected=EXPECTED_P003_REPORT_SHA,
        name="P003 report",
    )
    library = p003_report.get("library")
    if not isinstance(library, dict):
        raise AlphaContractError("I006 P003 alpha library is missing")
    _verify_embedded_hash(
        library,
        field="library_sha256",
        expected=EXPECTED_P003_LIBRARY_SHA,
        name="P003 library",
    )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, str, str]] = set()
    for row in library.get("records", []):
        if row.get("alpha_id") != ALPHA_ID:
            continue
        if int(row.get("horizon_sessions") or 0) != HORIZON_SESSIONS:
            raise AlphaContractError("I006 FUTURES_DELTA horizon changed")
        key = (
            str(row["feature_session"]),
            str(row["symbol"]),
            str(row["isin"]),
        )
        if key in seen:
            raise AlphaContractError("I006 duplicate P003 FUTURES_DELTA row")
        seen.add(key)
        grouped[key[0]].append(row)

    if not grouped:
        raise AlphaContractError("I006 FUTURES_DELTA OOS stream is empty")

    result = {}
    for session in sorted(grouped):
        rows = grouped[session]
        if len(rows) < 10:
            raise AlphaContractError(
                f"I006 {session}: alpha cross-section too small"
            )
        ordered = sorted(
            rows,
            key=lambda row: (
                -float(row["normalized_score"]),
                str(row["symbol"]),
                str(row["isin"]),
            ),
        )
        bucket = max(1, math.ceil(len(ordered) * TOP_DECILE_SHARE))
        top = ordered[:bucket]
        realized = statistics.mean(
            float(row["target_excess_return"])
            for row in top
        )
        result[session] = {
            "feature_session": session,
            "stock_count": len(rows),
            "top_decile_count": len(top),
            "control_realized_5d_excess": realized,
            "top_decile_identity_sha256": digest(
                [
                    {
                        "symbol": str(row["symbol"]),
                        "isin": str(row["isin"]),
                    }
                    for row in top
                ]
            ),
        }
    return result


def _regime_rows(panel: dict[str, Any]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    _verify_rg001(panel)
    rows = panel.get("rows")
    if not isinstance(rows, list) or not rows:
        raise AlphaContractError("I006 RG001 rows are missing")
    dates = [str(row["session_date"]) for row in rows]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise AlphaContractError("I006 RG001 sessions must be unique and ordered")
    return dates, {str(row["session_date"]): row for row in rows}


def _quantile(values: list[float], probability: float) -> float:
    if not values:
        raise AlphaContractError("I006 quantile input is empty")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _paired_inference(values: list[float]) -> dict[str, Any]:
    return newey_west_mean_inference(
        values,
        max_lag=NEWey_WEST_LAG,
    )


def run_po001_i006(
    *,
    p003_report: dict[str, Any],
    rg001_panel: dict[str, Any],
) -> dict[str, Any]:
    session_returns = _top_decile_session_returns(p003_report)
    regime_dates, regime_map = _regime_rows(rg001_panel)
    regime_index = {day: index for index, day in enumerate(regime_dates)}

    observations = []
    for session in sorted(session_returns):
        index = regime_index.get(session)
        if index is None or index < TRAILING_REGIME_SESSIONS:
            continue
        trailing_rows = [
            regime_map[day]
            for day in regime_dates[
                index - TRAILING_REGIME_SESSIONS : index
            ]
        ]
        if len(trailing_rows) != TRAILING_REGIME_SESSIONS:
            raise AlphaContractError("I006 trailing RG001 window is incomplete")

        current_row = regime_map[session]
        current_vol = float(
            current_row["values"]["nifty500_realized_vol_20"]
        )
        prior_vols = [
            float(row["values"]["nifty500_realized_vol_20"])
            for row in trailing_rows
        ]
        if (
            not math.isfinite(current_vol)
            or current_vol <= 0
            or any(not math.isfinite(value) or value <= 0 for value in prior_vols)
        ):
            raise AlphaContractError("I006 RG001 vol20 must be finite and positive")

        reference_vol = statistics.median(prior_vols)
        multiplier = min(1.0, reference_vol / current_vol)
        control_return = float(
            session_returns[session]["control_realized_5d_excess"]
        )
        treatment_return = multiplier * control_return
        control_utility = (
            control_return
            - UTILITY_GAMMA * control_return * control_return
        )
        treatment_utility = (
            treatment_return
            - UTILITY_GAMMA * treatment_return * treatment_return
        )
        observations.append(
            {
                **session_returns[session],
                "current_vol20": current_vol,
                "reference_prior60_median_vol20": reference_vol,
                "active_exposure_multiplier": multiplier,
                "benchmark_sleeve_weight": 1.0 - multiplier,
                "treatment_realized_5d_excess": treatment_return,
                "control_realized_utility": control_utility,
                "treatment_realized_utility": treatment_utility,
                "utility_delta": treatment_utility - control_utility,
                "return_delta": treatment_return - control_return,
                "squared_return_delta": (
                    treatment_return * treatment_return
                    - control_return * control_return
                ),
                "absolute_return_delta": (
                    abs(treatment_return) - abs(control_return)
                ),
            }
        )

    if len(observations) < 40:
        raise AlphaContractError(
            "I006 has fewer than 40 eligible OOS portfolio sessions"
        )

    utility_delta = [float(row["utility_delta"]) for row in observations]
    return_delta = [float(row["return_delta"]) for row in observations]
    squared_delta = [
        float(row["squared_return_delta"]) for row in observations
    ]
    absolute_delta = [
        float(row["absolute_return_delta"]) for row in observations
    ]
    control_returns = [
        float(row["control_realized_5d_excess"]) for row in observations
    ]
    treatment_returns = [
        float(row["treatment_realized_5d_excess"]) for row in observations
    ]
    multipliers = [
        float(row["active_exposure_multiplier"]) for row in observations
    ]

    primary = _paired_inference(utility_delta)
    primary_supported = (
        float(primary["mean"]) > 0.0
        and float(primary["p_value_two_sided"]) < 0.05
    )

    ranked_by_vol = sorted(
        observations,
        key=lambda row: (
            float(row["current_vol20"]),
            str(row["feature_session"]),
        ),
    )
    quartile_rows: list[list[dict[str, Any]]] = [[], [], [], []]
    for index, row in enumerate(ranked_by_vol):
        bucket = min(3, (4 * index) // len(ranked_by_vol))
        quartile_rows[bucket].append(row)

    report: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "status": (
            "COMPLETE_DEVELOPMENT_PRIMARY_SUPPORTED"
            if primary_supported
            else "COMPLETE_DEVELOPMENT_PRIMARY_UNSUPPORTED"
        ),
        "evidence_class": (
            "HISTORICAL_KNOWN_OUTCOME_PORTFOLIO_CONTEXT_DIAGNOSTIC"
        ),
        "horizon_sessions": HORIZON_SESSIONS,
        "source": {
            "p003_report_sha256": p003_report["report_sha256"],
            "p003_library_sha256": p003_report["library"]["library_sha256"],
            "alpha_id": ALPHA_ID,
            "rg001_panel_sha256": rg001_panel["panel_sha256"],
            "rg001_variable": "nifty500_realized_vol_20",
        },
        "eligible_session_count": len(observations),
        "frozen_overlay": {
            "trailing_regime_sessions": TRAILING_REGIME_SESSIONS,
            "utility_gamma": UTILITY_GAMMA,
            "top_decile_share": TOP_DECILE_SHARE,
            "formula": "MIN_1_PRIOR60_MEDIAN_VOL20_DIV_CURRENT_VOL20",
            "residual_allocation": "NIFTY500_BENCHMARK_SLEEVE",
            "leverage_allowed": False,
        },
        "primary_endpoint": {
            "metric": "PAIRED_MEAN_REALIZED_ACTIVE_UTILITY_DELTA",
            **primary,
            "supported": primary_supported,
        },
        "secondary": {
            "mean_5d_excess_return_delta": _paired_inference(return_delta),
            "mean_squared_5d_excess_delta": _paired_inference(
                squared_delta
            ),
            "mean_absolute_5d_excess_delta": _paired_inference(
                absolute_delta
            ),
        },
        "control": {
            "mean_5d_excess_return": statistics.mean(control_returns),
            "median_5d_excess_return": statistics.median(control_returns),
            "std_5d_excess_return": statistics.pstdev(control_returns),
            "p10_5d_excess_return": _quantile(control_returns, 0.10),
            "worst_5d_excess_return": min(control_returns),
            "mean_realized_utility": statistics.mean(
                float(row["control_realized_utility"])
                for row in observations
            ),
        },
        "treatment": {
            "mean_5d_excess_return": statistics.mean(treatment_returns),
            "median_5d_excess_return": statistics.median(treatment_returns),
            "std_5d_excess_return": statistics.pstdev(treatment_returns),
            "p10_5d_excess_return": _quantile(treatment_returns, 0.10),
            "worst_5d_excess_return": min(treatment_returns),
            "mean_realized_utility": statistics.mean(
                float(row["treatment_realized_utility"])
                for row in observations
            ),
        },
        "exposure": {
            "mean": statistics.mean(multipliers),
            "median": statistics.median(multipliers),
            "minimum": min(multipliers),
            "scaled_below_one_session_count": sum(
                value < 1.0 - 1e-15 for value in multipliers
            ),
            "scaled_below_one_fraction": (
                sum(value < 1.0 - 1e-15 for value in multipliers)
                / len(multipliers)
            ),
            "mean_by_current_vol_quartile": {
                f"Q{index + 1}": statistics.mean(
                    float(row["active_exposure_multiplier"])
                    for row in rows
                )
                for index, rows in enumerate(quartile_rows)
                if rows
            },
        },
        "observations": observations,
        "cost_model_status": (
            "NOT_INCLUDED_OVERLAPPING_COHORT_ROLLING_IMPLEMENTATION_NOT_CONSTRUCTED"
        ),
        "interpretation": {
            "primary_supported": primary_supported,
            "p004_alpha_selector_promoted": False,
            "stock_ranking_changed": False,
            "alpha_refit_performed": False,
            "same_i006_retune_allowed": False,
            "prospective_claim_allowed": False,
            "implementable_pnl_claim_allowed": False,
            "next_if_supported": (
                "SEPARATELY_FROZEN_ROLLING_COST_AWARE_ACTIVE_RISK_OVERLAY"
            ),
        },
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
