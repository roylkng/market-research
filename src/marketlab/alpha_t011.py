from __future__ import annotations

import copy
import math
from collections import defaultdict
from dataclasses import asdict
from typing import Any

from marketlab.alpha import AlphaContractError, FeatureDefinition, digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_diagnostics import paired_report_difference_inference
from marketlab.alpha_futures import FUTURES_DEFINITIONS
from marketlab.alpha_multihorizon import run_action_safe_horizon_walkforward
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_trials import (
    require_protocol_amendment,
    require_unopened_registered_trial,
)

TRIAL_ID = "AE001-T011"
TRIAL_STATUS = "FROZEN_BEFORE_RETURN_OUTCOMES"
SOURCE_PROTOCOL_ID = "AE001-T011-P1"

EXPECTED_MARKET_PANEL_SHA256 = (
    "9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e"
)
EXPECTED_ACTION_LEDGER_SHA256 = (
    "1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1"
)
EXPECTED_CURRENT27_PANEL_SHA256 = (
    "99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90"
)
EXPECTED_T005_PANEL_SHA256 = (
    "62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f"
)
MIN_FEATURE_SESSIONS = 150
MIN_FEATURE_ROWS = 30_000
COPY_TOLERANCE = 0.0


def _names(definitions) -> list[str]:
    return [definition.name for definition in definitions]


BASE27_NAMES = [
    *_names(PRICE_VOLUME_DEFINITIONS),
    *_names(DELIVERY_DEFINITIONS),
]
T005_FUTURES_NAMES = _names(FUTURES_DEFINITIONS)
LAGGED_FUTURES_MAP = {
    name: f"lag1_{name}" for name in T005_FUTURES_NAMES
}
LAGGED_FUTURES_NAMES = [
    LAGGED_FUTURES_MAP[name] for name in T005_FUTURES_NAMES
]
AUGMENTED37_NAMES = [*BASE27_NAMES, *LAGGED_FUTURES_NAMES]

LAGGED_FUTURES_DEFINITIONS = [
    FeatureDefinition(
        LAGGED_FUTURES_MAP[definition.name],
        definition.family,
        "lag1-v1",
        (
            f"Previous completed NSE session value of {definition.name}; "
            "copied without recomputation for current-session decision use."
        ),
        definition.lookback_sessions,
        1,
    )
    for definition in FUTURES_DEFINITIONS
]


def _verify_panel(
    panel: dict[str, Any],
    *,
    expected_sha256: str,
    name: str,
) -> None:
    stored = str(panel.get("panel_sha256") or "")
    unsigned = copy.deepcopy(panel)
    unsigned.pop("panel_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError(f"{name} panel hash mismatch")
    if stored != expected_sha256:
        raise AlphaContractError(
            f"{name} panel differs from frozen upstream artifact"
        )


def _key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("feature_session") or ""),
        str(row.get("symbol") or ""),
        str(row.get("isin") or ""),
    )


def build_t011_lagged_feature_panel(
    *,
    market_panel: dict[str, Any],
    current27_panel: dict[str, Any],
    t005_panel: dict[str, Any],
) -> dict[str, Any]:
    """Build current-D base27 plus exact D-1 T005 futures values."""

    _verify_panel(
        market_panel,
        expected_sha256=EXPECTED_MARKET_PANEL_SHA256,
        name="T011 market",
    )
    _verify_panel(
        current27_panel,
        expected_sha256=EXPECTED_CURRENT27_PANEL_SHA256,
        name="T011 current27",
    )
    _verify_panel(
        t005_panel,
        expected_sha256=EXPECTED_T005_PANEL_SHA256,
        name="T011 T005",
    )
    if (
        current27_panel.get("outcomes_attached") is not False
        or t005_panel.get("outcomes_attached") is not False
    ):
        raise AlphaContractError("T011 source panels must be outcome-free")

    current_defs = current27_panel.get("feature_definitions")
    t005_defs = t005_panel.get("feature_definitions")
    if not isinstance(current_defs, list) or not isinstance(t005_defs, list):
        raise AlphaContractError("T011 feature definitions are missing")
    if {str(row["name"]) for row in current_defs} != set(BASE27_NAMES):
        raise AlphaContractError("T011 current panel is not the frozen 27-feature set")
    if {str(row["name"]) for row in t005_defs} != set(
        [*BASE27_NAMES, *T005_FUTURES_NAMES]
    ):
        raise AlphaContractError("T011 T005 panel is not the frozen 37-feature set")

    sessions = market_panel.get("sessions")
    if not isinstance(sessions, list) or len(sessions) < 2:
        raise AlphaContractError("T011 ordered market sessions are required")
    dates = [str(row["session_date"]) for row in sessions]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise AlphaContractError("T011 market sessions must be unique and ordered")
    previous_date = {
        dates[index]: dates[index - 1]
        for index in range(1, len(dates))
    }

    t005_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in t005_panel.get("rows", []):
        key = _key(row)
        if not all(key) or key in t005_rows:
            raise AlphaContractError("T011 T005 row identity is missing or duplicated")
        t005_rows[key] = row

    definitions = list(current_defs) + [
        asdict(definition) for definition in LAGGED_FUTURES_DEFINITIONS
    ]
    definitions.sort(key=lambda row: str(row["name"]))
    if len(definitions) != 37 or len(
        {str(row["name"]) for row in definitions}
    ) != 37:
        raise AlphaContractError("T011 definitions are not exact 37 unique fields")
    feature_set_sha256 = digest(definitions)

    rows = []
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    excluded_no_previous_market_session = 0
    excluded_missing_lagged_futures = 0
    copied_value_count = 0
    max_copy_abs_diff = 0.0

    seen_current: set[tuple[str, str, str]] = set()
    for current in current27_panel.get("rows", []):
        key = _key(current)
        if not all(key) or key in seen_current:
            raise AlphaContractError("T011 current row identity is missing or duplicated")
        seen_current.add(key)
        current_day, symbol, isin = key
        lag_day = previous_date.get(current_day)
        if lag_day is None:
            excluded_no_previous_market_session += 1
            continue
        source = t005_rows.get((lag_day, symbol, isin))
        if source is None:
            excluded_missing_lagged_futures += 1
            continue

        current_values = current.get("values")
        source_values = source.get("values")
        if not isinstance(current_values, dict) or not isinstance(source_values, dict):
            raise AlphaContractError("T011 source row values are malformed")
        if set(current_values) != set(BASE27_NAMES):
            raise AlphaContractError("T011 current row has unexpected base feature set")

        lagged_values = {}
        for source_name in T005_FUTURES_NAMES:
            raw = source_values.get(source_name)
            if raw is None:
                raise AlphaContractError(
                    f"T011 lagged futures source is missing {source_name}"
                )
            value = float(raw)
            if not math.isfinite(value):
                raise AlphaContractError("T011 lagged futures source is nonfinite")
            copied = float(value)
            diff = abs(copied - value)
            max_copy_abs_diff = max(max_copy_abs_diff, diff)
            if diff > COPY_TOLERANCE:
                raise AlphaContractError("T011 futures copy changed source value")
            lagged_values[LAGGED_FUTURES_MAP[source_name]] = copied
            copied_value_count += 1

        values = {**current_values, **lagged_values}
        if set(values) != set(AUGMENTED37_NAMES):
            raise AlphaContractError("T011 row does not contain exact 37 features")
        updated = {
            **current,
            "feature_set_sha256": feature_set_sha256,
            "values": values,
            "lagged_futures_source_session": lag_day,
            "lagged_futures_source_row_sha256": digest(
                {
                    "feature_session": lag_day,
                    "symbol": symbol,
                    "isin": isin,
                    "futures_values": {
                        name: source_values[name]
                        for name in T005_FUTURES_NAMES
                    },
                }
            ),
        }
        rows.append(updated)
        by_session[current_day].append(updated)

    session_summaries = []
    for session in sorted(by_session):
        session_rows = sorted(
            by_session[session],
            key=lambda row: (str(row["symbol"]), str(row["isin"])),
        )
        universe_sha = digest(
            [
                {"symbol": row["symbol"], "isin": row["isin"]}
                for row in session_rows
            ]
        )
        for row in session_rows:
            row["universe_sha256"] = universe_sha
        lag_sessions = {
            str(row["lagged_futures_source_session"])
            for row in session_rows
        }
        if len(lag_sessions) != 1:
            raise AlphaContractError(
                f"T011 {session}: multiple lagged futures sessions observed"
            )
        session_summaries.append(
            {
                "session_date": session,
                "lagged_futures_source_session": next(iter(lag_sessions)),
                "eligible_count": len(session_rows),
                "universe_sha256": universe_sha,
            }
        )

    panel: dict[str, Any] = {
        **{
            key: value
            for key, value in current27_panel.items()
            if key
            not in {
                "panel_sha256",
                "feature_definitions",
                "feature_set_sha256",
                "rows",
                "sessions",
                "feature_row_count",
                "session_count",
            }
        },
        "panel_id": "AE001-T011-LAGGED-FUTURES-37-FEATURE-PANEL-v1",
        "evidence_class": (
            "HISTORICAL_RECONSTRUCTION_DEVELOPMENT_"
            "SOURCE_TIMING_UNVERIFIED"
        ),
        "market_panel_sha256": market_panel["panel_sha256"],
        "current27_feature_panel_sha256": current27_panel["panel_sha256"],
        "t005_same_session37_feature_panel_sha256": t005_panel["panel_sha256"],
        "feature_definitions": definitions,
        "feature_set_sha256": feature_set_sha256,
        "lag_contract": (
            "PREVIOUS_COMPLETED_MARKET_SESSION_T005_FUTURES_"
            "EXACT_SYMBOL_PLUS_ISIN"
        ),
        "copy_tolerance": COPY_TOLERANCE,
        "max_copied_futures_abs_diff": max_copy_abs_diff,
        "copied_futures_value_count": copied_value_count,
        "excluded_no_previous_market_session_row_count": (
            excluded_no_previous_market_session
        ),
        "excluded_missing_lagged_futures_row_count": (
            excluded_missing_lagged_futures
        ),
        "session_count": len(session_summaries),
        "feature_row_count": len(rows),
        "sessions": session_summaries,
        "rows": sorted(
            rows,
            key=lambda row: (
                str(row["feature_session"]),
                str(row["symbol"]),
                str(row["isin"]),
            ),
        ),
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def summarize_t011_source(panel: dict[str, Any]) -> dict[str, Any]:
    stored = str(panel.get("panel_sha256") or "")
    unsigned = copy.deepcopy(panel)
    unsigned.pop("panel_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("T011 panel hash mismatch")
    passes = (
        int(panel["session_count"]) >= MIN_FEATURE_SESSIONS
        and int(panel["feature_row_count"]) >= MIN_FEATURE_ROWS
        and float(panel["max_copied_futures_abs_diff"]) == 0.0
        and panel.get("outcomes_attached") is False
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "trial_id": TRIAL_ID,
        "stage": "SOURCE_ONLY_PRE_OUTCOME",
        "status": (
            "READY_FOR_P1_SOURCE_FREEZE"
            if passes
            else "SOURCE_SAMPLE_GATE_FAILED"
        ),
        "evidence_class": panel["evidence_class"],
        "market_panel_sha256": panel["market_panel_sha256"],
        "current27_feature_panel_sha256": panel[
            "current27_feature_panel_sha256"
        ],
        "t005_same_session37_feature_panel_sha256": panel[
            "t005_same_session37_feature_panel_sha256"
        ],
        "lagged37_feature_panel_sha256": panel["panel_sha256"],
        "feature_set_sha256": panel["feature_set_sha256"],
        "feature_count": len(panel["feature_definitions"]),
        "feature_session_count": panel["session_count"],
        "feature_row_count": panel["feature_row_count"],
        "excluded_missing_lagged_futures_row_count": panel[
            "excluded_missing_lagged_futures_row_count"
        ],
        "max_copied_futures_abs_diff": panel[
            "max_copied_futures_abs_diff"
        ],
        "return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report


def _folds(payload: dict[str, Any], key: str) -> list[dict[str, str]]:
    return [
        {"start": str(start), "end": str(end)}
        for start, end in payload[key]["folds"]
    ]


def run_t011_incremental_trial(
    *,
    market_panel: dict[str, Any],
    feature_panel: dict[str, Any],
    action_ledger: dict[str, Any],
    trial_ledger: dict[str, Any],
) -> dict[str, Any]:
    registration = require_unopened_registered_trial(
        trial_ledger,
        trial_id=TRIAL_ID,
        required_status=TRIAL_STATUS,
    )
    p1 = require_protocol_amendment(
        trial_ledger,
        trial_id=TRIAL_ID,
        protocol_id=SOURCE_PROTOCOL_ID,
    )
    frozen = registration["payload"]
    source = p1["payload"]

    if market_panel.get("panel_sha256") != source["market_panel_sha256"]:
        raise AlphaContractError("T011 market panel differs from frozen P1")
    if action_ledger.get("ledger_sha256") != source[
        "corporate_action_ledger_sha256"
    ]:
        raise AlphaContractError("T011 action ledger differs from frozen P1")
    if feature_panel.get("panel_sha256") != source[
        "lagged37_feature_panel_sha256"
    ]:
        raise AlphaContractError("T011 lagged panel differs from frozen P1")
    if feature_panel.get("current27_feature_panel_sha256") != source[
        "current27_feature_panel_sha256"
    ]:
        raise AlphaContractError("T011 current27 lineage differs from frozen P1")
    if feature_panel.get("t005_same_session37_feature_panel_sha256") != source[
        "t005_same_session37_feature_panel_sha256"
    ]:
        raise AlphaContractError("T011 T005 lineage differs from frozen P1")

    definitions = feature_panel.get("feature_definitions")
    if not isinstance(definitions, list) or {
        str(row["name"]) for row in definitions
    } != set(AUGMENTED37_NAMES):
        raise AlphaContractError("T011 feature set differs from frozen 37 features")

    l2 = float(frozen["model"]["l2"])
    folds_by_horizon = {
        1: _folds(frozen, "secondary"),
        5: _folds(frozen, "primary"),
    }
    base = run_action_safe_horizon_walkforward(
        feature_panel=feature_panel,
        market_panel=market_panel,
        action_ledger=action_ledger,
        folds_by_horizon=folds_by_horizon,
        feature_names=BASE27_NAMES,
        l2=l2,
    )
    augmented = run_action_safe_horizon_walkforward(
        feature_panel=feature_panel,
        market_panel=market_panel,
        action_ledger=action_ledger,
        folds_by_horizon=folds_by_horizon,
        feature_names=AUGMENTED37_NAMES,
        l2=l2,
    )

    comparisons = {}
    for horizon, key, lag in (
        (5, "primary_5d", int(frozen["primary"]["newey_west_lag"])),
        (1, "secondary_1d", int(frozen["secondary"]["newey_west_lag"])),
    ):
        base_report = base["horizons"][str(horizon)]["ridge"]
        augmented_report = augmented["horizons"][str(horizon)]["ridge"]
        if (
            base_report["prediction_count"]
            != augmented_report["prediction_count"]
            or base_report["session_count"]
            != augmented_report["session_count"]
        ):
            raise AlphaContractError(
                f"T011 H{horizon}: base/augmented comparison rows differ"
            )
        comparisons[key] = {
            "horizon_sessions": horizon,
            "base": base["horizons"][str(horizon)],
            "augmented": augmented["horizons"][str(horizon)],
            "augmented_minus_base_inference": (
                paired_report_difference_inference(
                    augmented_report,
                    base_report,
                    max_lag=lag,
                )
            ),
        }

    report: dict[str, Any] = {
        "schema_version": 1,
        "trial_id": TRIAL_ID,
        "engine_id": "AE001-v1-DEVELOPMENT",
        "evidence_class": (
            "HISTORICAL_RECONSTRUCTION_DEVELOPMENT_"
            "SOURCE_TIMING_UNVERIFIED"
        ),
        "trial_registration_event_sha256": registration["event_sha256"],
        "trial_protocol_p1_event_sha256": p1["event_sha256"],
        "trial_ledger_sha256": trial_ledger["ledger_sha256"],
        "market_panel_sha256": market_panel["panel_sha256"],
        "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
        "feature_panel_sha256": feature_panel["panel_sha256"],
        "current27_feature_panel_sha256": feature_panel[
            "current27_feature_panel_sha256"
        ],
        "t005_same_session37_feature_panel_sha256": feature_panel[
            "t005_same_session37_feature_panel_sha256"
        ],
        "base_feature_names": BASE27_NAMES,
        "lagged_futures_feature_names": LAGGED_FUTURES_NAMES,
        "augmented_feature_names": AUGMENTED37_NAMES,
        "comparison_contract": (
            "CURRENT_BASE27_VS_BASE27_PLUS_PREVIOUS_SESSION_FUTURES_"
            "ON_IDENTICAL_ROWS"
        ),
        "l2": l2,
        "primary_5d": comparisons["primary_5d"],
        "secondary_1d": comparisons["secondary_1d"],
        "medium_horizon_tested": False,
        "historical_previous_session_fo_preopen_timing_verified": False,
        "future_source_timing_gate": "AE001-SC003",
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
