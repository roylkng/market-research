from __future__ import annotations

from dataclasses import asdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_futures import FUTURES_DEFINITIONS
from marketlab.alpha_history import cross_sectionalize_panel
from marketlab.alpha_model import fit_ridge, project_examples
from marketlab.alpha_multihorizon import build_action_safe_horizon_examples
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_trials import (
    require_protocol_amendment,
    require_unopened_registered_trial,
)

TRIAL_ID = "AE001-T006"
TRIAL_STATUS = "FROZEN_BEFORE_FIRST_ELIGIBLE_DECISION_SESSION"
MODEL_PROTOCOL_ID = "AE001-T006-P1"
TRAINING_END_DATE = "2026-09-25"
TRAINING_HORIZON = 5
RIDGE_L2 = 1.0

EXPECTED_MARKET_SHA = (
    "9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e"
)
EXPECTED_ACTION_SHA = (
    "1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1"
)
EXPECTED_DELIVERY_SHA = (
    "99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90"
)
EXPECTED_FUTURES_SHA = (
    "02656c828a1d5fe22660c154a445ebd69a7492b56f1807da0d8c959a6f0c11d5"
)
EXPECTED_FUTURES_FEATURE_SHA = (
    "62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f"
)


def _names(definitions) -> list[str]:
    return [definition.name for definition in definitions]


def freeze_t006_models(
    *,
    feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
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
        protocol_id=MODEL_PROTOCOL_ID,
    )
    frozen = protocol["payload"]

    if str(frozen.get("source_end_date")) != TRAINING_END_DATE:
        raise AlphaContractError("T006 training end date differs from P1")
    if int(frozen.get("training_horizon_sessions") or 0) != TRAINING_HORIZON:
        raise AlphaContractError("T006 training horizon differs from P1")
    if float(frozen.get("ridge_l2")) != RIDGE_L2:
        raise AlphaContractError("T006 ridge l2 differs from P1")
    if frozen.get("retraining_during_trial_allowed") is not False:
        raise AlphaContractError("T006 P1 unexpectedly permits retraining")
    if str(frozen.get("earliest_eligible_decision_date")) != "2026-10-01":
        raise AlphaContractError("T006 earliest decision date differs from P1")

    if market_panel.get("panel_sha256") != EXPECTED_MARKET_SHA:
        raise AlphaContractError("T006 market panel differs from frozen source")
    if action_ledger.get("ledger_sha256") != EXPECTED_ACTION_SHA:
        raise AlphaContractError("T006 action ledger differs from frozen source")
    if feature_panel.get("panel_sha256") != EXPECTED_FUTURES_FEATURE_SHA:
        raise AlphaContractError(
            "T006 futures feature panel differs from frozen source"
        )
    if feature_panel.get("base_feature_panel_sha256") != EXPECTED_DELIVERY_SHA:
        raise AlphaContractError(
            "T006 futures feature panel delivery lineage mismatch"
        )
    if feature_panel.get("futures_panel_sha256") != EXPECTED_FUTURES_SHA:
        raise AlphaContractError("T006 futures source panel lineage mismatch")
    if feature_panel.get("corporate_action_ledger_sha256") != EXPECTED_ACTION_SHA:
        raise AlphaContractError("T006 feature/action ledger binding mismatch")

    ranked = (
        feature_panel
        if feature_panel.get("transform")
        == "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1"
        else cross_sectionalize_panel(feature_panel)
    )

    base_names = [
        *_names(PRICE_VOLUME_DEFINITIONS),
        *_names(DELIVERY_DEFINITIONS),
    ]
    futures_names = _names(FUTURES_DEFINITIONS)
    augmented_names = [*base_names, *futures_names]

    if (
        len(base_names) != int(frozen.get("base_feature_count") or 0)
        or len(augmented_names)
        != int(frozen.get("augmented_feature_count") or 0)
        or len(futures_names)
        != int(frozen.get("futures_feature_count") or 0)
    ):
        raise AlphaContractError("T006 frozen feature counts disagree")

    definitions = ranked.get("feature_definitions")
    if not isinstance(definitions, list):
        raise AlphaContractError("T006 training feature definitions are missing")
    observed_names = {str(row["name"]) for row in definitions}
    if observed_names != set(augmented_names):
        raise AlphaContractError(
            "T006 training panel does not contain frozen 37 features"
        )

    examples_by_horizon, exclusions = build_action_safe_horizon_examples(
        feature_panel=ranked,
        market_panel=market_panel,
        action_ledger=action_ledger,
        horizons=(TRAINING_HORIZON,),
    )
    examples = [
        row
        for row in examples_by_horizon[TRAINING_HORIZON]
        if row.exit_session <= TRAINING_END_DATE
    ]
    if len(examples) < 100:
        raise AlphaContractError(
            "T006 fixed model has insufficient training examples"
        )
    if any(row.exit_session > TRAINING_END_DATE for row in examples):
        raise AlphaContractError("T006 fixed model leaks post-cutoff labels")

    base_examples = project_examples(
        examples,
        feature_names=base_names,
    )
    augmented_examples = project_examples(
        examples,
        feature_names=augmented_names,
    )
    base_identity = [
        (row.feature_session, row.symbol, row.isin, row.exit_session)
        for row in base_examples
    ]
    augmented_identity = [
        (row.feature_session, row.symbol, row.isin, row.exit_session)
        for row in augmented_examples
    ]
    if base_identity != augmented_identity:
        raise AlphaContractError("T006 base and augmented training rows differ")

    base_model = fit_ridge(
        base_examples,
        feature_names=base_names,
        l2=RIDGE_L2,
        model_id="AE001-T006-CORE27-RIDGE-v1",
    )
    augmented_model = fit_ridge(
        augmented_examples,
        feature_names=augmented_names,
        l2=RIDGE_L2,
        model_id="AE001-T006-FULL37-RIDGE-v1",
    )

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "artifact_id": "AE001-T006-FROZEN-MODELS-v1",
        "trial_id": TRIAL_ID,
        "evidence_class": "PROSPECTIVE_CONFIRMATORY_INPUT",
        "trial_registration_event_sha256": registration["event_sha256"],
        "model_protocol_event_sha256": protocol["event_sha256"],
        "model_protocol_id": MODEL_PROTOCOL_ID,
        "earliest_eligible_decision_date": "2026-10-01",
        "training_source_end_date": TRAINING_END_DATE,
        "training_horizon_sessions": TRAINING_HORIZON,
        "training_example_count": len(examples),
        "training_first_feature_session": min(
            row.feature_session for row in examples
        ),
        "training_last_feature_session": max(
            row.feature_session for row in examples
        ),
        "training_last_exit_session": max(row.exit_session for row in examples),
        "input_market_panel_sha256": market_panel["panel_sha256"],
        "input_feature_panel_sha256": feature_panel["panel_sha256"],
        "input_ranked_feature_panel_sha256": ranked["panel_sha256"],
        "input_delivery_feature_panel_sha256": EXPECTED_DELIVERY_SHA,
        "input_futures_panel_sha256": EXPECTED_FUTURES_SHA,
        "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
        "training_exclusions": exclusions,
        "base_feature_names": base_names,
        "futures_feature_names": futures_names,
        "augmented_feature_names": augmented_names,
        "base_model": asdict(base_model),
        "augmented_model": asdict(augmented_model),
        "retraining_during_primary_trial_allowed": False,
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def validate_frozen_t006_models(artifact: dict[str, Any]) -> None:
    if artifact.get("artifact_id") != "AE001-T006-FROZEN-MODELS-v1":
        raise AlphaContractError("unexpected T006 model artifact id")
    if artifact.get("trial_id") != TRIAL_ID:
        raise AlphaContractError("unexpected T006 trial id in model artifact")
    if artifact.get("retraining_during_primary_trial_allowed") is not False:
        raise AlphaContractError("T006 frozen model artifact permits retraining")
    if artifact.get("live_capital_allowed") is not False:
        raise AlphaContractError("T006 frozen model artifact permits live capital")
    if artifact.get("earliest_eligible_decision_date") != "2026-10-01":
        raise AlphaContractError("T006 model artifact start date mismatch")
    unsigned = dict(artifact)
    stored = str(unsigned.pop("artifact_sha256", ""))
    if stored != digest(unsigned):
        raise AlphaContractError("T006 frozen model artifact hash mismatch")
    if artifact.get("training_last_exit_session") > TRAINING_END_DATE:
        raise AlphaContractError("T006 model artifact leaks post-cutoff labels")
