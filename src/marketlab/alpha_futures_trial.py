from __future__ import annotations

from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_diagnostics import paired_report_difference_inference
from marketlab.alpha_futures import FUTURES_DEFINITIONS
from marketlab.alpha_multihorizon import run_action_safe_horizon_walkforward
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_trials import (
    require_protocol_amendment,
    require_unopened_registered_trial,
)

TRIAL_ID = "AE001-T005"
TRIAL_STATUS = "FROZEN_BEFORE_OUTCOME_MATERIALIZATION"
PROTOCOL_ID = "AE001-T005-P1"


def _names(definitions) -> list[str]:
    return [definition.name for definition in definitions]


def _folds(payload: dict[str, Any], key: str) -> list[dict[str, str]]:
    pairs = payload[key]["folds"]
    return [
        {"start": str(start), "end": str(end)}
        for start, end in pairs
    ]


def run_futures_incremental_trial(
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
        protocol_id=PROTOCOL_ID,
    )
    frozen = registration["payload"]
    if p1["payload"].get("selection_rule") != (
        "FEATURE_CONSTRUCTION_USES_ONLY_STF_CONTRACTS_WITH_"
        "EXPIRY_STRICTLY_GREATER_THAN_TRADE_DATE"
    ):
        raise AlphaContractError(
            "T005 expiry-selection rule differs from frozen P1"
        )

    base_names = [
        *_names(PRICE_VOLUME_DEFINITIONS),
        *_names(DELIVERY_DEFINITIONS),
    ]
    futures_names = _names(FUTURES_DEFINITIONS)
    all_names = [*base_names, *futures_names]

    if (
        len(base_names) != int(frozen["base_feature_count"])
        or len(futures_names) != int(frozen["derivative_feature_count"])
        or len(all_names)
        != int(frozen["base_feature_count"])
        + int(frozen["derivative_feature_count"])
    ):
        raise AlphaContractError("T005 frozen feature counts disagree")

    definitions = feature_panel.get("feature_definitions")
    if not isinstance(definitions, list):
        raise AlphaContractError("T005 feature definitions are missing")
    observed_names = {str(row["name"]) for row in definitions}
    if observed_names != set(all_names):
        raise AlphaContractError(
            "T005 feature panel differs from frozen 37-feature set"
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
        (
            5,
            "primary_5d",
            int(frozen["primary"]["newey_west_lag"]),
        ),
        (
            1,
            "secondary_1d",
            int(frozen["secondary"]["newey_west_lag"]),
        ),
        (
            20,
            "diagnostic_20d",
            int(frozen["diagnostic"]["newey_west_lag"]),
        ),
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
                f"T005 H{horizon}: base/augmented comparison rows differ"
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
        "base_feature_panel_sha256": feature_panel.get(
            "base_feature_panel_sha256"
        ),
        "futures_panel_sha256": feature_panel.get("futures_panel_sha256"),
        "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
        "base_feature_names": base_names,
        "futures_feature_names": futures_names,
        "augmented_feature_names": all_names,
        "comparison_contract": (
            "BASE_27_VS_AUGMENTED_37_ON_IDENTICAL_FUTURES_COMPLETE_ROWS"
        ),
        "l2": l2,
        "primary_5d": comparisons["primary_5d"],
        "secondary_1d": comparisons["secondary_1d"],
        "diagnostic_20d": comparisons["diagnostic_20d"],
        "historical_fo_publication_timestamp_verified": False,
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
