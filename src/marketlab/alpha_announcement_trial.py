from __future__ import annotations

from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_announcement_features import (
    ANNOUNCEMENT_DEFINITIONS,
    ANNOUNCEMENT_FEATURE_DEFINITION_SHA256,
    ANNOUNCEMENT_TAXONOMY_SHA256,
)
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_diagnostics import paired_report_difference_inference
from marketlab.alpha_multihorizon import run_action_safe_horizon_walkforward
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_trials import (
    require_protocol_amendment,
    require_unopened_registered_trial,
)

TRIAL_ID = "AE001-T007"
TRIAL_STATUS = "FROZEN_BEFORE_OUTCOME_MATERIALIZATION"
PROTOCOL_ID = "AE001-T007-P1"
D003_REPORT_SHA256 = (
    "7f402beecaf90f054c93ca2ceeaa01f38fcc5cd8f7f8f6391f60791768f8a91f"
)


def _names(definitions) -> list[str]:
    return [definition.name for definition in definitions]


def _folds(payload: dict[str, Any], key: str) -> list[dict[str, str]]:
    return [
        {"start": str(start), "end": str(end)}
        for start, end in payload[key]["folds"]
    ]


def run_announcement_incremental_trial(
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
    protocol = require_protocol_amendment(
        trial_ledger,
        trial_id=TRIAL_ID,
        protocol_id=PROTOCOL_ID,
    )
    frozen = registration["payload"]
    p1 = protocol["payload"]

    if p1.get("announcement_taxonomy_sha256") != ANNOUNCEMENT_TAXONOMY_SHA256:
        raise AlphaContractError("T007 announcement taxonomy differs from frozen P1")
    if (
        p1.get("announcement_feature_definition_sha256")
        != ANNOUNCEMENT_FEATURE_DEFINITION_SHA256
    ):
        raise AlphaContractError(
            "T007 announcement feature definitions differ from frozen P1"
        )
    if p1.get("d003_report_sha256") != D003_REPORT_SHA256:
        raise AlphaContractError("T007 D003 source audit binding differs from P1")
    if p1.get("source_query_granularity") != "ONE_WHOLE_MARKET_QUERY_PER_CALENDAR_DATE":
        raise AlphaContractError("T007 source acquisition strategy differs from P1")
    if p1.get("zero_event_policy") != "VALID_ONLY_WITH_COMPLETE_DAILY_SOURCE_WINDOW":
        raise AlphaContractError("T007 zero-event policy differs from P1")

    base_names = [
        *_names(PRICE_VOLUME_DEFINITIONS),
        *_names(DELIVERY_DEFINITIONS),
    ]
    event_names = _names(ANNOUNCEMENT_DEFINITIONS)
    all_names = [*base_names, *event_names]

    if (
        len(base_names) != 27
        or len(event_names) != int(frozen["new_feature_count"])
        or len(all_names) != 43
    ):
        raise AlphaContractError("T007 frozen feature counts disagree")

    definitions = feature_panel.get("feature_definitions")
    if not isinstance(definitions, list):
        raise AlphaContractError("T007 feature definitions are missing")
    observed = {str(row["name"]) for row in definitions}
    if observed != set(all_names):
        raise AlphaContractError("T007 feature panel differs from frozen CORE43")
    if feature_panel.get("panel_id") != "AE001-T007-CORE43-v1":
        raise AlphaContractError("T007 feature panel identity changed")
    if feature_panel.get("outcomes_attached") is not False:
        raise AlphaContractError("T007 feature panel contains outcomes")

    l2 = float(frozen["model"]["l2"])
    if l2 != 1.0:
        raise AlphaContractError("T007 ridge l2 differs from frozen registration")

    folds_by_horizon = {
        1: _folds(frozen, "primary"),
        5: _folds(frozen, "secondary"),
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

    comparisons: dict[str, Any] = {}
    for horizon, label, lag in (
        (1, "primary_1d", int(frozen["primary"]["newey_west_lag"])),
        (5, "secondary_5d", int(frozen["secondary"]["newey_west_lag"])),
    ):
        key = str(horizon)
        base_report = base["horizons"][key]["ridge"]
        augmented_report = augmented["horizons"][key]["ridge"]
        if (
            base_report["prediction_count"] != augmented_report["prediction_count"]
            or base_report["session_count"] != augmented_report["session_count"]
        ):
            raise AlphaContractError(
                f"T007 H{horizon}: base/augmented comparison rows differ"
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
        "trial_protocol_p1_event_sha256": protocol["event_sha256"],
        "trial_ledger_sha256": trial_ledger["ledger_sha256"],
        "market_panel_sha256": market_panel["panel_sha256"],
        "feature_panel_sha256": feature_panel["panel_sha256"],
        "base_feature_panel_sha256": feature_panel.get("base_feature_panel_sha256"),
        "announcement_panel_sha256": feature_panel.get("announcement_panel_sha256"),
        "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
        "base_feature_names": base_names,
        "announcement_feature_names": event_names,
        "augmented_feature_names": all_names,
        "announcement_taxonomy_sha256": ANNOUNCEMENT_TAXONOMY_SHA256,
        "announcement_feature_definition_sha256": (
            ANNOUNCEMENT_FEATURE_DEFINITION_SHA256
        ),
        "comparison_contract": (
            "CORE27_VS_CORE43_ON_IDENTICAL_ACTION_SAFE_DELIVERY_COMPLETE_ROWS"
        ),
        "l2": l2,
        "primary_1d": comparisons["primary_1d"],
        "secondary_5d": comparisons["secondary_5d"],
        "primary_success_rule": (
            "BOTH_POSITIVE_PAIRED_RANK_IC_AND_TOP_MINUS_BOTTOM_SPREAD_"
            "WITH_TWO_SIDED_P_LT_0_05"
        ),
        "secondary_may_rescue_primary": False,
        "historical_source_completeness_audit_sha256": D003_REPORT_SHA256,
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
