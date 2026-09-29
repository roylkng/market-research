from __future__ import annotations

from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_diagnostics import paired_report_difference_inference
from marketlab.alpha_multihorizon import run_action_safe_horizon_walkforward
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_trials import (
    require_protocol_amendment,
    require_unopened_registered_trial,
)
from marketlab.alpha_walkforward import run_ridge_walkforward

TRIAL_ID = "AE001-T003"
TRIAL_STATUS = "FROZEN_BEFORE_DELIVERY_OUTCOME_RUN"
PROTOCOL_ID = "AE001-T003-P1"
SOURCE_QUALITY_PROTOCOL_ID = "AE001-T003-P3"


def _feature_names(definitions) -> list[str]:
    return [definition.name for definition in definitions]


def run_delivery_incremental_trial(
    *,
    market_panel: dict[str, Any],
    feature_panel: dict[str, Any],
    action_ledger: dict[str, Any],
    trial_ledger: dict[str, Any],
    folds_1d: list[dict[str, str]],
    folds_5d: list[dict[str, str]],
    folds_20d: list[dict[str, str]],
    l2: float = 1.0,
) -> dict[str, Any]:
    registration = require_unopened_registered_trial(
        trial_ledger,
        trial_id=TRIAL_ID,
        required_status=TRIAL_STATUS,
    )
    protocol = require_protocol_amendment(
        trial_ledger,
        trial_id=TRIAL_ID,
        protocol_id=PROTOCOL_ID,
    )
    source_quality_protocol = require_protocol_amendment(
        trial_ledger,
        trial_id=TRIAL_ID,
        protocol_id=SOURCE_QUALITY_PROTOCOL_ID,
    )
    frozen = protocol["payload"]
    source_quality = source_quality_protocol["payload"]
    if not str(source_quality.get("source_quality_rule") or "").startswith(
        "EXCLUDE_WHOLE_DELIVERY_SESSION"
    ):
        raise AlphaContractError(
            "delivery trial source-quality policy differs from frozen protocol"
        )
    if float(frozen["ridge_l2"]) != float(l2):
        raise AlphaContractError("delivery trial l2 differs from frozen protocol")

    def fold_pairs(folds: list[dict[str, str]]) -> list[list[str]]:
        return [[str(row["start"]), str(row["end"])] for row in folds]

    supplied_folds = {
        "1": fold_pairs(folds_1d),
        "5": fold_pairs(folds_5d),
        "20": fold_pairs(folds_20d),
    }
    if supplied_folds != frozen["folds"]:
        raise AlphaContractError("delivery trial folds differ from frozen protocol")

    base_names = _feature_names(PRICE_VOLUME_DEFINITIONS)
    delivery_names = _feature_names(DELIVERY_DEFINITIONS)
    all_names = base_names + delivery_names
    if (
        len(base_names) != int(frozen["feature_count_base"])
        or len(delivery_names) != int(frozen["feature_count_delivery"])
        or len(all_names) != int(frozen["feature_count_augmented"])
    ):
        raise AlphaContractError("delivery trial feature count differs from frozen protocol")
    definitions = feature_panel.get("feature_definitions")
    if not isinstance(definitions, list):
        raise AlphaContractError("delivery trial feature definitions are missing")
    observed = {str(row["name"]) for row in definitions}
    if set(all_names) != observed:
        raise AlphaContractError(
            "delivery trial feature panel must contain exactly frozen base+delivery features"
        )

    base_1d = run_ridge_walkforward(
        feature_panel=feature_panel,
        market_panel=market_panel,
        folds=folds_1d,
        feature_names=base_names,
        l2=l2,
    )
    augmented_1d = run_ridge_walkforward(
        feature_panel=feature_panel,
        market_panel=market_panel,
        folds=folds_1d,
        feature_names=all_names,
        l2=l2,
    )
    primary = {
        "horizon_sessions": 1,
        "base": base_1d,
        "augmented": augmented_1d,
        "augmented_minus_base_inference": paired_report_difference_inference(
            augmented_1d["ridge"],
            base_1d["ridge"],
            max_lag=5,
        ),
    }

    folds_by_horizon = {
        5: folds_5d,
        20: folds_20d,
    }
    base_multi = run_action_safe_horizon_walkforward(
        feature_panel=feature_panel,
        market_panel=market_panel,
        action_ledger=action_ledger,
        folds_by_horizon=folds_by_horizon,
        feature_names=base_names,
        l2=l2,
    )
    augmented_multi = run_action_safe_horizon_walkforward(
        feature_panel=feature_panel,
        market_panel=market_panel,
        action_ledger=action_ledger,
        folds_by_horizon=folds_by_horizon,
        feature_names=all_names,
        l2=l2,
    )

    horizon_comparisons = {}
    for horizon in (5, 20):
        key = str(horizon)
        horizon_comparisons[key] = {
            "horizon_sessions": horizon,
            "base": base_multi["horizons"][key],
            "augmented": augmented_multi["horizons"][key],
            "augmented_minus_base_inference": (
                paired_report_difference_inference(
                    augmented_multi["horizons"][key]["ridge"],
                    base_multi["horizons"][key]["ridge"],
                    max_lag=horizon - 1,
                )
            ),
        }

    report: dict[str, Any] = {
        "schema_version": 1,
        "trial_id": TRIAL_ID,
        "engine_id": "AE001-v1-DEVELOPMENT",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "trial_registration_event_sha256": registration["event_sha256"],
        "trial_protocol_event_sha256": protocol["event_sha256"],
        "trial_protocol_id": PROTOCOL_ID,
        "source_quality_protocol_event_sha256": (
            source_quality_protocol["event_sha256"]
        ),
        "source_quality_protocol_id": SOURCE_QUALITY_PROTOCOL_ID,
        "trial_ledger_sha256": trial_ledger["ledger_sha256"],
        "market_panel_sha256": market_panel["panel_sha256"],
        "feature_panel_sha256": feature_panel["panel_sha256"],
        "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
        "base_feature_names": base_names,
        "delivery_feature_names": delivery_names,
        "augmented_feature_names": all_names,
        "comparison_contract": (
            "BASE_18_VS_AUGMENTED_27_ON_IDENTICAL_DELIVERY_COMPLETE_ROWS"
        ),
        "l2": l2,
        "primary_1d": primary,
        "secondary_5d": horizon_comparisons["5"],
        "diagnostic_20d": horizon_comparisons["20"],
        "horizon_60_excluded_by_frozen_trial": True,
        "cost_model_status": "NOT_IMPLEMENTED_TC001_REQUIRED",
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
