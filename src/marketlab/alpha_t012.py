from __future__ import annotations

from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_announcement_semantics import (
    EXPECTED_ANNOUNCEMENT_PANEL_SHA256,
    HASH_DIMENSIONS,
    SEMANTIC_DEFINITIONS,
    SEMANTIC_DEFINITION_SHA256,
)
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_diagnostics import paired_report_difference_inference
from marketlab.alpha_multihorizon import run_action_safe_horizon_walkforward
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_trials import (
    require_protocol_amendment,
    require_unopened_registered_trial,
)

TRIAL_ID = "AE001-T012"
TRIAL_STATUS = "FROZEN_BEFORE_RETURN_OUTCOMES"
PROTOCOL_ID = "AE001-T012-P1"
RIDGE_L2 = 1.0
PRIMARY_FOLDS = (
    ("2026-04-01", "2026-06-30"),
    ("2026-07-01", "2026-09-24"),
)
SECONDARY_FOLDS = (
    ("2026-04-01", "2026-06-30"),
    ("2026-07-01", "2026-09-18"),
)
PRIMARY_LAG = 5
SECONDARY_LAG = 4
D003_REPORT_SHA256 = (
    "7f402beecaf90f054c93ca2ceeaa01f38fcc5cd8f7f8f6391f60791768f8a91f"
)


def _names(definitions) -> list[str]:
    return [definition.name for definition in definitions]


def _fold_rows(folds: tuple[tuple[str, str], ...]) -> list[dict[str, str]]:
    return [{"start": start, "end": end} for start, end in folds]


def _frozen_fold_lists(
    folds: tuple[tuple[str, str], ...],
) -> list[list[str]]:
    return [[start, end] for start, end in folds]


def _validate_trial_contract(
    registration: dict[str, Any],
    protocol: dict[str, Any],
) -> None:
    frozen = registration["payload"]
    p1 = protocol["payload"]

    if frozen.get("status") != TRIAL_STATUS:
        raise AlphaContractError("T012 registration status changed")
    if frozen.get("model") != {"type": "ridge", "l2": RIDGE_L2}:
        raise AlphaContractError("T012 model differs from frozen registration")
    if frozen.get("primary") != {
        "horizon_sessions": 1,
        "folds": _frozen_fold_lists(PRIMARY_FOLDS),
        "newey_west_lag": PRIMARY_LAG,
    }:
        raise AlphaContractError("T012 primary endpoint differs from registration")
    if frozen.get("secondary") != {
        "horizon_sessions": 5,
        "folds": _frozen_fold_lists(SECONDARY_FOLDS),
        "newey_west_lag": SECONDARY_LAG,
        "rescues_primary": False,
    }:
        raise AlphaContractError(
            "T012 secondary endpoint differs from registration"
        )

    expected_p1 = {
        "protocol_id": PROTOCOL_ID,
        "announcement_panel_sha256": EXPECTED_ANNOUNCEMENT_PANEL_SHA256,
        "d003_report_sha256": D003_REPORT_SHA256,
        "semantic_feature_definition_sha256": SEMANTIC_DEFINITION_SHA256,
        "semantic_hash_dimensions": HASH_DIMENSIONS,
        "same_day_postclose_window": "GT_15_30_AND_LTE_18_30_IST",
        "tokenization": "UNICODE_NFKC_LOWER_ASCII_ALNUM_UNIGRAM_BIGRAM",
        "distinct_ngrams_per_announcement": True,
        "per_announcement_l2_normalization": True,
        "session_aggregation": "SUM",
        "fitted_vocabulary": False,
        "llm_used": False,
        "sentiment_dictionary": False,
        "manual_direction_labels": False,
    }
    for key, value in expected_p1.items():
        if p1.get(key) != value:
            raise AlphaContractError(
                f"T012 protocol P1 differs at {key}"
            )


def run_t012_semantic_trial(
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
    _validate_trial_contract(registration, protocol)

    base_names = [
        *_names(PRICE_VOLUME_DEFINITIONS),
        *_names(DELIVERY_DEFINITIONS),
    ]
    semantic_names = _names(SEMANTIC_DEFINITIONS)
    all_names = [*base_names, *semantic_names]

    if len(base_names) != 27:
        raise AlphaContractError("T012 CORE27 feature count changed")
    if len(semantic_names) != HASH_DIMENSIONS:
        raise AlphaContractError("T012 semantic feature count changed")
    if len(all_names) != 91:
        raise AlphaContractError("T012 CORE91 feature count changed")

    if feature_panel.get("panel_id") != "AE001-T012-CORE91-v1":
        raise AlphaContractError("T012 semantic feature panel identity changed")
    if feature_panel.get("outcomes_attached") is not False:
        raise AlphaContractError("T012 feature panel contains outcomes")
    if (
        feature_panel.get("announcement_panel_sha256")
        != EXPECTED_ANNOUNCEMENT_PANEL_SHA256
    ):
        raise AlphaContractError(
            "T012 feature panel announcement source hash changed"
        )
    if (
        feature_panel.get("semantic_feature_definition_sha256")
        != SEMANTIC_DEFINITION_SHA256
    ):
        raise AlphaContractError(
            "T012 semantic feature definition hash changed"
        )

    definitions = feature_panel.get("feature_definitions")
    if not isinstance(definitions, list):
        raise AlphaContractError("T012 feature definitions are missing")
    observed = {str(row["name"]) for row in definitions}
    if observed != set(all_names):
        raise AlphaContractError("T012 feature panel differs from CORE91")

    folds_by_horizon = {
        1: _fold_rows(PRIMARY_FOLDS),
        5: _fold_rows(SECONDARY_FOLDS),
    }
    base = run_action_safe_horizon_walkforward(
        feature_panel=feature_panel,
        market_panel=market_panel,
        action_ledger=action_ledger,
        folds_by_horizon=folds_by_horizon,
        feature_names=base_names,
        l2=RIDGE_L2,
    )
    challenger = run_action_safe_horizon_walkforward(
        feature_panel=feature_panel,
        market_panel=market_panel,
        action_ledger=action_ledger,
        folds_by_horizon=folds_by_horizon,
        feature_names=all_names,
        l2=RIDGE_L2,
    )

    comparisons: dict[str, Any] = {}
    for horizon, label, lag in (
        (1, "primary_1d", PRIMARY_LAG),
        (5, "secondary_5d", SECONDARY_LAG),
    ):
        key = str(horizon)
        base_report = base["horizons"][key]["ridge"]
        challenger_report = challenger["horizons"][key]["ridge"]
        if (
            base_report["prediction_count"]
            != challenger_report["prediction_count"]
            or base_report["session_count"]
            != challenger_report["session_count"]
        ):
            raise AlphaContractError(
                f"T012 H{horizon}: base/challenger rows differ"
            )
        comparisons[label] = {
            "horizon_sessions": horizon,
            "base": base["horizons"][key],
            "challenger": challenger["horizons"][key],
            "challenger_minus_base_inference": (
                paired_report_difference_inference(
                    challenger_report,
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
        "base_feature_panel_sha256": feature_panel.get(
            "base_feature_panel_sha256"
        ),
        "announcement_panel_sha256": feature_panel[
            "announcement_panel_sha256"
        ],
        "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
        "base_feature_names": base_names,
        "semantic_feature_names": semantic_names,
        "challenger_feature_names": all_names,
        "semantic_feature_definition_sha256": (
            SEMANTIC_DEFINITION_SHA256
        ),
        "comparison_contract": (
            "CORE27_VS_CORE91_ON_IDENTICAL_ACTION_SAFE_DELIVERY_COMPLETE_ROWS"
        ),
        "l2": RIDGE_L2,
        "primary_1d": comparisons["primary_1d"],
        "secondary_5d": comparisons["secondary_5d"],
        "primary_success_rule": (
            "BOTH_POSITIVE_PAIRED_RANK_IC_AND_TOP_MINUS_BOTTOM_SPREAD_"
            "WITH_TWO_SIDED_P_LT_0_05"
        ),
        "secondary_may_rescue_primary": False,
        "retune_same_trial_if_failed": False,
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
