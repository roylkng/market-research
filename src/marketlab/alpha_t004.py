from __future__ import annotations

from dataclasses import asdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_history import cross_sectionalize_panel
from marketlab.alpha_model import fit_ridge, project_examples
from marketlab.alpha_multihorizon import build_action_safe_horizon_examples
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_trials import (
    require_protocol_amendment,
    require_unopened_registered_trial,
)

TRIAL_ID = "AE001-T004"
TRIAL_STATUS = "FROZEN_BEFORE_FIRST_ELIGIBLE_DECISION_SESSION"
MODEL_PROTOCOL_ID = "AE001-T004-P1"
TRAINING_END_DATE = "2026-09-25"
TRAINING_HORIZON = 5
RIDGE_L2 = 1.0


def _names(definitions) -> list[str]:
    return [definition.name for definition in definitions]


def freeze_t004_models(
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
        raise AlphaContractError("T004 training end date differs from P1")
    if int(frozen.get("primary_training_horizon_sessions")) != TRAINING_HORIZON:
        raise AlphaContractError("T004 training horizon differs from P1")
    if float(frozen.get("ridge_l2")) != RIDGE_L2:
        raise AlphaContractError("T004 ridge l2 differs from P1")

    ranked = (
        feature_panel
        if feature_panel.get("transform")
        == "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1"
        else cross_sectionalize_panel(feature_panel)
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
        raise AlphaContractError("T004 fixed model has insufficient training examples")
    if any(row.exit_session > TRAINING_END_DATE for row in examples):
        raise AlphaContractError("T004 fixed model contains a post-cutoff label")

    base_names = _names(PRICE_VOLUME_DEFINITIONS)
    delivery_names = _names(DELIVERY_DEFINITIONS)
    augmented_names = base_names + delivery_names
    if (
        len(base_names) != int(frozen["base_feature_count"])
        or len(augmented_names) != int(frozen["augmented_feature_count"])
    ):
        raise AlphaContractError("T004 feature counts differ from frozen P1")

    observed_definitions = ranked.get("feature_definitions")
    if not isinstance(observed_definitions, list):
        raise AlphaContractError("T004 training feature definitions are missing")
    observed_names = {str(row["name"]) for row in observed_definitions}
    if set(augmented_names) != observed_names:
        raise AlphaContractError(
            "T004 training panel does not contain exactly frozen 27 features"
        )

    base_examples = project_examples(examples, feature_names=base_names)
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
        raise AlphaContractError("T004 base and augmented training rows differ")

    base_model = fit_ridge(
        base_examples,
        feature_names=base_names,
        l2=RIDGE_L2,
        model_id="AE001-T004-BASE-RIDGE-v1",
    )
    augmented_model = fit_ridge(
        augmented_examples,
        feature_names=augmented_names,
        l2=RIDGE_L2,
        model_id="AE001-T004-AUGMENTED-RIDGE-v1",
    )

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "artifact_id": "AE001-T004-FROZEN-MODELS-v1",
        "trial_id": TRIAL_ID,
        "evidence_class": "PROSPECTIVE_CONFIRMATORY_INPUT",
        "trial_registration_event_sha256": registration["event_sha256"],
        "model_protocol_event_sha256": protocol["event_sha256"],
        "model_protocol_id": MODEL_PROTOCOL_ID,
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
        "corporate_action_ledger_sha256": action_ledger["ledger_sha256"],
        "training_exclusions": exclusions,
        "base_feature_names": base_names,
        "delivery_feature_names": delivery_names,
        "augmented_feature_names": augmented_names,
        "base_model": asdict(base_model),
        "augmented_model": asdict(augmented_model),
        "retraining_during_primary_trial_allowed": False,
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def validate_frozen_t004_models(artifact: dict[str, Any]) -> None:
    if artifact.get("artifact_id") != "AE001-T004-FROZEN-MODELS-v1":
        raise AlphaContractError("unexpected T004 model artifact id")
    if artifact.get("trial_id") != TRIAL_ID:
        raise AlphaContractError("unexpected T004 trial id in model artifact")
    if artifact.get("retraining_during_primary_trial_allowed") is not False:
        raise AlphaContractError("T004 frozen model artifact permits retraining")
    if artifact.get("live_capital_allowed") is not False:
        raise AlphaContractError("T004 frozen model artifact permits live capital")
    unsigned = dict(artifact)
    stored = str(unsigned.pop("artifact_sha256", ""))
    if stored != digest(unsigned):
        raise AlphaContractError("T004 frozen model artifact hash mismatch")
    if artifact.get("training_last_exit_session") > TRAINING_END_DATE:
        raise AlphaContractError("T004 model artifact leaks post-cutoff labels")
