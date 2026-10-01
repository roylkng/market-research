from __future__ import annotations

from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_diagnostics import paired_report_difference_inference
from marketlab.alpha_futures import FUTURES_DEFINITIONS
from marketlab.alpha_multihorizon import run_action_safe_horizon_walkforward
from marketlab.alpha_options import OPTIONS_DEFINITIONS
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_trials import (
    require_protocol_amendment,
    require_unopened_registered_trial,
)

TRIAL_ID = "AE001-T009"
TRIAL_STATUS = "FROZEN_BEFORE_OUTCOME_MATERIALIZATION"
SOURCE_PROTOCOL_ID = "AE001-T009-P1"

EXPECTED_MARKET_PANEL_SHA256 = (
    "9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e"
)
EXPECTED_ACTION_LEDGER_SHA256 = (
    "1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1"
)
EXPECTED_T005_FULL37_PANEL_SHA256 = (
    "62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f"
)
EXPECTED_D006_SOURCE_HASHES_SHA256 = (
    "edf21ed30ea4021a82118c8699f1a7470442bcee29155810772a09c4b24bc6dc"
)


def _names(definitions) -> list[str]:
    return [definition.name for definition in definitions]


def _folds(payload: dict[str, Any], key: str) -> list[dict[str, str]]:
    pairs = payload[key]["folds"]
    return [
        {"start": str(start), "end": str(end)}
        for start, end in pairs
    ]


def _source_contract(payload: dict[str, Any]) -> None:
    required = {
        "protocol_id": SOURCE_PROTOCOL_ID,
        "market_panel_sha256": EXPECTED_MARKET_PANEL_SHA256,
        "corporate_action_ledger_sha256": EXPECTED_ACTION_LEDGER_SHA256,
        "base_37_feature_panel_sha256": EXPECTED_T005_FULL37_PANEL_SHA256,
        "options_source_hashes_sha256": EXPECTED_D006_SOURCE_HASHES_SHA256,
        "options_ready_session_count": 266,
        "options_unavailable_session_count": 0,
        "options_parser_rejected_session_count": 0,
        "outcomes_opened_before_amendment": False,
        "model_fit_started_before_amendment": False,
        "live_capital_allowed": False,
    }
    for field, expected in required.items():
        if payload.get(field) != expected:
            raise AlphaContractError(
                f"T009 P1 source contract differs: {field}"
            )
    for field in (
        "options_panel_sha256",
        "augmented_47_feature_panel_sha256",
    ):
        value = str(payload.get(field) or "")
        if len(value) != 64:
            raise AlphaContractError(f"T009 P1 missing {field}")
    if int(payload.get("option_complete_feature_row_count") or 0) <= 0:
        raise AlphaContractError(
            "T009 P1 option-complete feature row count is invalid"
        )
    if int(payload.get("option_complete_session_count") or 0) <= 0:
        raise AlphaContractError(
            "T009 P1 option-complete session count is invalid"
        )


def run_options_incremental_trial(
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
    _source_contract(source)

    if market_panel.get("panel_sha256") != EXPECTED_MARKET_PANEL_SHA256:
        raise AlphaContractError(
            "T009 market panel differs from frozen lineage"
        )
    if action_ledger.get("ledger_sha256") != EXPECTED_ACTION_LEDGER_SHA256:
        raise AlphaContractError(
            "T009 corporate-action ledger differs from frozen lineage"
        )
    if feature_panel.get("panel_sha256") != source[
        "augmented_47_feature_panel_sha256"
    ]:
        raise AlphaContractError(
            "T009 47-feature panel differs from frozen P1"
        )
    if feature_panel.get("base_feature_panel_sha256") != (
        EXPECTED_T005_FULL37_PANEL_SHA256
    ):
        raise AlphaContractError(
            "T009 panel is not based on frozen T005 37-feature panel"
        )
    if feature_panel.get("options_panel_sha256") != source[
        "options_panel_sha256"
    ]:
        raise AlphaContractError(
            "T009 options panel differs from frozen P1"
        )
    if feature_panel.get("options_source_hashes_sha256") != (
        EXPECTED_D006_SOURCE_HASHES_SHA256
    ):
        raise AlphaContractError(
            "T009 option source hash chain differs from D006"
        )
    if feature_panel.get("corporate_action_ledger_sha256") != (
        EXPECTED_ACTION_LEDGER_SHA256
    ):
        raise AlphaContractError(
            "T009 feature/action ledger binding mismatch"
        )

    base_names = [
        *_names(PRICE_VOLUME_DEFINITIONS),
        *_names(DELIVERY_DEFINITIONS),
        *_names(FUTURES_DEFINITIONS),
    ]
    option_names = _names(OPTIONS_DEFINITIONS)
    all_names = [*base_names, *option_names]

    if (
        len(base_names) != int(frozen["base_feature_count"])
        or len(option_names) != int(frozen["option_feature_count"])
        or len(all_names) != int(frozen["augmented_feature_count"])
    ):
        raise AlphaContractError("T009 frozen feature counts disagree")

    definitions = feature_panel.get("feature_definitions")
    if not isinstance(definitions, list):
        raise AlphaContractError("T009 feature definitions are missing")
    observed = {str(row["name"]) for row in definitions}
    if observed != set(all_names):
        raise AlphaContractError(
            "T009 feature panel differs from frozen 47-feature set"
        )

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
        feature_names=base_names,
        l2=l2,
    )
    augmented = run_action_safe_horizon_walkforward(
        feature_panel=feature_panel,
        market_panel=market_panel,
        action_ledger=action_ledger,
        folds_by_horizon=folds_by_horizon,
        feature_names=all_names,
        l2=l2,
    )

    comparisons = {}
    for horizon, label, lag in (
        (5, "primary_5d", int(frozen["primary"]["newey_west_lag"])),
        (1, "secondary_1d", int(frozen["secondary"]["newey_west_lag"])),
        (20, "diagnostic_20d", int(frozen["diagnostic"]["newey_west_lag"])),
    ):
        key = str(horizon)
        base_report = base["horizons"][key]["ridge"]
        augmented_report = augmented["horizons"][key]["ridge"]
        if (
            base_report["prediction_count"]
            != augmented_report["prediction_count"]
            or base_report["session_count"]
            != augmented_report["session_count"]
        ):
            raise AlphaContractError(
                f"T009 H{horizon}: base/augmented comparison rows differ"
            )
        comparisons[label] = {
            "horizon_sessions": horizon,
            "base": base["horizons"][key],
            "augmented": augmented["horizons"][key],
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
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "trial_registration_event_sha256": registration["event_sha256"],
        "trial_protocol_p1_event_sha256": p1["event_sha256"],
        "trial_ledger_sha256": trial_ledger["ledger_sha256"],
        "market_panel_sha256": market_panel["panel_sha256"],
        "feature_panel_sha256": feature_panel["panel_sha256"],
        "base_37_feature_panel_sha256": feature_panel[
            "base_feature_panel_sha256"
        ],
        "options_panel_sha256": feature_panel["options_panel_sha256"],
        "options_source_hashes_sha256": feature_panel[
            "options_source_hashes_sha256"
        ],
        "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
        "base_feature_names": base_names,
        "option_feature_names": option_names,
        "augmented_feature_names": all_names,
        "comparison_contract": (
            "BASE_37_VS_AUGMENTED_47_ON_IDENTICAL_OPTION_COMPLETE_ROWS"
        ),
        "l2": l2,
        "source_materialization": {
            "option_complete_feature_row_count": source[
                "option_complete_feature_row_count"
            ],
            "option_complete_session_count": source[
                "option_complete_session_count"
            ],
            "exclusion_counts": source.get("exclusion_counts", {}),
        },
        "primary_5d": comparisons["primary_5d"],
        "secondary_1d": comparisons["secondary_1d"],
        "diagnostic_20d": comparisons["diagnostic_20d"],
        "historical_fo_publication_timestamp_verified": False,
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
