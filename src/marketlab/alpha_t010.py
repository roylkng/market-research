from __future__ import annotations

import copy
import math
from collections import defaultdict
from dataclasses import asdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_d010_p4 import D010_DEFINITIONS
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_diagnostics import paired_report_difference_inference
from marketlab.alpha_futures import FUTURES_DEFINITIONS
from marketlab.alpha_multihorizon import run_action_safe_horizon_walkforward
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_trials import (
    require_protocol_amendment,
    require_unopened_registered_trial,
)

TRIAL_ID = "AE001-T010"
TRIAL_STATUS = "FROZEN_BEFORE_RETURN_OUTCOMES"
SOURCE_PROTOCOL_ID = "AE001-T010-P1"

EXPECTED_T005_PANEL_SHA256 = (
    "62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f"
)
EXPECTED_D010_P4A_PANEL_SHA256 = (
    "1b629fee85e7430466d81e5c8e5a3497cca77221ab7d38633b23c7db5b49f4b0"
)
EXPECTED_MARKET_PANEL_SHA256 = (
    "9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e"
)
EXPECTED_ACTION_LEDGER_SHA256 = (
    "1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1"
)
OVERLAP_TOLERANCE = 1e-15


def _names(definitions) -> list[str]:
    return [definition.name for definition in definitions]


BASE18_NAMES = _names(PRICE_VOLUME_DEFINITIONS)
BASE37_NAMES = [
    *BASE18_NAMES,
    *_names(DELIVERY_DEFINITIONS),
    *_names(FUTURES_DEFINITIONS),
]
D010_NAMES = _names(D010_DEFINITIONS)
AUGMENTED44_NAMES = [*BASE37_NAMES, *D010_NAMES]


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


def _row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("feature_session") or ""),
        str(row.get("symbol") or ""),
        str(row.get("isin") or ""),
    )


def _equal_feature_value(left: object, right: object) -> tuple[bool, float]:
    if left is None or right is None:
        return left is None and right is None, 0.0
    a = float(left)
    b = float(right)
    if not math.isfinite(a) or not math.isfinite(b):
        raise AlphaContractError("T010 overlapping base feature is nonfinite")
    diff = abs(a - b)
    return diff <= OVERLAP_TOLERANCE, diff


def build_t010_feature_panel(
    *,
    t005_feature_panel: dict[str, Any],
    d010_feature_panel: dict[str, Any],
) -> dict[str, Any]:
    """Join sealed T005 and D010-P4A rows without opening outcomes."""

    _verify_panel(
        t005_feature_panel,
        expected_sha256=EXPECTED_T005_PANEL_SHA256,
        name="T010 T005 base37",
    )
    _verify_panel(
        d010_feature_panel,
        expected_sha256=EXPECTED_D010_P4A_PANEL_SHA256,
        name="T010 D010 P4A",
    )
    if (
        t005_feature_panel.get("outcomes_attached") is not False
        or d010_feature_panel.get("outcomes_attached") is not False
    ):
        raise AlphaContractError("T010 source panels must be outcome-free")

    t005_defs = t005_feature_panel.get("feature_definitions")
    d010_defs = d010_feature_panel.get("feature_definitions")
    if not isinstance(t005_defs, list) or not isinstance(d010_defs, list):
        raise AlphaContractError("T010 feature definitions are missing")
    if {str(row["name"]) for row in t005_defs} != set(BASE37_NAMES):
        raise AlphaContractError("T010 T005 panel is not the frozen 37-feature set")
    if {str(row["name"]) for row in d010_defs} != {
        *BASE18_NAMES,
        *D010_NAMES,
    }:
        raise AlphaContractError("T010 D010 panel is not the frozen P4A set")

    d010_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in d010_feature_panel.get("rows", []):
        key = _row_key(row)
        if not all(key) or key in d010_rows:
            raise AlphaContractError("T010 D010 row identity is missing or duplicated")
        d010_rows[key] = row

    definitions = list(t005_defs) + [
        asdict(definition) for definition in D010_DEFINITIONS
    ]
    definitions.sort(key=lambda row: str(row["name"]))
    if len(definitions) != 44 or len(
        {str(row["name"]) for row in definitions}
    ) != 44:
        raise AlphaContractError("T010 combined feature definitions are not 44 unique fields")
    feature_set_sha256 = digest(definitions)

    result_rows = []
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    excluded_no_d010 = 0
    max_overlap_abs_diff = 0.0

    seen_base_keys: set[tuple[str, str, str]] = set()
    for base_row in t005_feature_panel.get("rows", []):
        key = _row_key(base_row)
        if not all(key) or key in seen_base_keys:
            raise AlphaContractError("T010 T005 row identity is missing or duplicated")
        seen_base_keys.add(key)
        d010_row = d010_rows.get(key)
        if d010_row is None:
            excluded_no_d010 += 1
            continue
        base_values = base_row.get("values")
        d010_values = d010_row.get("values")
        if not isinstance(base_values, dict) or not isinstance(d010_values, dict):
            raise AlphaContractError("T010 row values are malformed")

        for name in BASE18_NAMES:
            same, diff = _equal_feature_value(
                base_values.get(name),
                d010_values.get(name),
            )
            max_overlap_abs_diff = max(max_overlap_abs_diff, diff)
            if not same:
                raise AlphaContractError(
                    f"T010 overlapping base feature differs for {key}/{name}"
                )

        new_values = {
            **base_values,
            **{name: d010_values.get(name) for name in D010_NAMES},
        }
        if set(new_values) != set(AUGMENTED44_NAMES):
            raise AlphaContractError("T010 row does not contain exact 44 features")
        if any(
            value is not None and not math.isfinite(float(value))
            for value in new_values.values()
        ):
            raise AlphaContractError("T010 combined row contains nonfinite value")

        updated = {
            **base_row,
            "feature_set_sha256": feature_set_sha256,
            "values": new_values,
            "d010_source_window_sha256": d010_row.get(
                "d010_source_window_sha256"
            ),
        }
        result_rows.append(updated)
        by_session[key[0]].append(updated)

    session_rows = []
    for session in sorted(by_session):
        rows = sorted(
            by_session[session],
            key=lambda row: (str(row["symbol"]), str(row["isin"])),
        )
        universe_sha = digest(
            [
                {"symbol": row["symbol"], "isin": row["isin"]}
                for row in rows
            ]
        )
        for row in rows:
            row["universe_sha256"] = universe_sha
        session_rows.append(
            {
                "session_date": session,
                "eligible_count": len(rows),
                "universe_sha256": universe_sha,
            }
        )

    panel: dict[str, Any] = {
        **{
            key: value
            for key, value in t005_feature_panel.items()
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
        "panel_id": "AE001-T010-COMBINED-44-FEATURE-PANEL-v1",
        "evidence_class": (
            "HISTORICAL_RECONSTRUCTION_DEVELOPMENT_"
            "SOURCE_TIMING_UNVERIFIED"
        ),
        "base37_feature_panel_sha256": t005_feature_panel["panel_sha256"],
        "d010_p4a_feature_panel_sha256": d010_feature_panel["panel_sha256"],
        "feature_definitions": definitions,
        "feature_set_sha256": feature_set_sha256,
        "join_contract": "FEATURE_SESSION_PLUS_SYMBOL_PLUS_ISIN_INNER_JOIN",
        "overlapping_base_feature_tolerance": OVERLAP_TOLERANCE,
        "max_overlapping_base_feature_abs_diff": max_overlap_abs_diff,
        "excluded_no_d010_row_count": excluded_no_d010,
        "session_count": len(session_rows),
        "feature_row_count": len(result_rows),
        "sessions": session_rows,
        "rows": sorted(
            result_rows,
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


def summarize_t010_source(panel: dict[str, Any]) -> dict[str, Any]:
    stored = str(panel.get("panel_sha256") or "")
    unsigned = copy.deepcopy(panel)
    unsigned.pop("panel_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("T010 combined panel hash mismatch")
    report: dict[str, Any] = {
        "schema_version": 1,
        "trial_id": TRIAL_ID,
        "stage": "SOURCE_ONLY_PRE_OUTCOME",
        "status": "READY_FOR_P1_SOURCE_FREEZE",
        "evidence_class": panel["evidence_class"],
        "base37_feature_panel_sha256": panel[
            "base37_feature_panel_sha256"
        ],
        "d010_p4a_feature_panel_sha256": panel[
            "d010_p4a_feature_panel_sha256"
        ],
        "combined44_feature_panel_sha256": panel["panel_sha256"],
        "feature_set_sha256": panel["feature_set_sha256"],
        "feature_count": len(panel["feature_definitions"]),
        "feature_session_count": panel["session_count"],
        "feature_row_count": panel["feature_row_count"],
        "excluded_no_d010_row_count": panel["excluded_no_d010_row_count"],
        "max_overlapping_base_feature_abs_diff": panel[
            "max_overlapping_base_feature_abs_diff"
        ],
        "return_labels_opened": False,
        "model_fit_performed": False,
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report


def _folds(payload: dict[str, Any], key: str) -> list[dict[str, str]]:
    return [
        {"start": str(start), "end": str(end)}
        for start, end in payload[key]["folds"]
    ]


def run_t010_incremental_trial(
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
        raise AlphaContractError("T010 market panel differs from frozen P1")
    if action_ledger.get("ledger_sha256") != source[
        "corporate_action_ledger_sha256"
    ]:
        raise AlphaContractError("T010 action ledger differs from frozen P1")
    if feature_panel.get("panel_sha256") != source[
        "combined44_feature_panel_sha256"
    ]:
        raise AlphaContractError("T010 combined panel differs from frozen P1")
    if feature_panel.get("base37_feature_panel_sha256") != source[
        "base37_feature_panel_sha256"
    ]:
        raise AlphaContractError("T010 base37 lineage differs from frozen P1")
    if feature_panel.get("d010_p4a_feature_panel_sha256") != source[
        "d010_p4a_feature_panel_sha256"
    ]:
        raise AlphaContractError("T010 P4A lineage differs from frozen P1")

    definitions = feature_panel.get("feature_definitions")
    if not isinstance(definitions, list) or {
        str(row["name"]) for row in definitions
    } != set(AUGMENTED44_NAMES):
        raise AlphaContractError("T010 feature set differs from frozen 44 features")

    l2 = float(frozen["model"]["l2"])
    folds_by_horizon = {
        1: _folds(frozen, "secondary"),
        5: _folds(frozen, "primary"),
        20: _folds(frozen, "diagnostic"),
    }
    base = run_action_safe_horizon_walkforward(
        feature_panel=feature_panel,
        market_panel=market_panel,
        action_ledger=action_ledger,
        folds_by_horizon=folds_by_horizon,
        feature_names=BASE37_NAMES,
        l2=l2,
    )
    augmented = run_action_safe_horizon_walkforward(
        feature_panel=feature_panel,
        market_panel=market_panel,
        action_ledger=action_ledger,
        folds_by_horizon=folds_by_horizon,
        feature_names=AUGMENTED44_NAMES,
        l2=l2,
    )

    comparisons = {}
    for horizon, key, lag in (
        (5, "primary_5d", int(frozen["primary"]["newey_west_lag"])),
        (1, "secondary_1d", int(frozen["secondary"]["newey_west_lag"])),
        (20, "diagnostic_20d", int(frozen["diagnostic"]["newey_west_lag"])),
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
                f"T010 H{horizon}: base/augmented comparison rows differ"
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
        "base37_feature_panel_sha256": feature_panel[
            "base37_feature_panel_sha256"
        ],
        "d010_p4a_feature_panel_sha256": feature_panel[
            "d010_p4a_feature_panel_sha256"
        ],
        "base_feature_names": BASE37_NAMES,
        "d010_feature_names": D010_NAMES,
        "augmented_feature_names": AUGMENTED44_NAMES,
        "comparison_contract": (
            "BASE_37_VS_AUGMENTED_44_ON_IDENTICAL_D010_COMPLETE_ROWS"
        ),
        "l2": l2,
        "primary_5d": comparisons["primary_5d"],
        "secondary_1d": comparisons["secondary_1d"],
        "diagnostic_20d": comparisons["diagnostic_20d"],
        "historical_short_slb_publication_timestamp_verified": False,
        "future_source_timing_gate": "AE001-SC004",
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
