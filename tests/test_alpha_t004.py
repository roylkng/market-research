from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_model import ModelExample
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_t004 import freeze_t004_models, validate_frozen_t004_models
from marketlab.alpha_trials import append_trial_event, new_trial_ledger


def _trial_ledger():
    ledger = append_trial_event(
        new_trial_ledger(),
        event_type="TRIAL_REGISTERED",
        trial_id="AE001-T004",
        recorded_at_utc="2026-09-29T10:08:48+00:00",
        payload={"status": "FROZEN_BEFORE_FIRST_ELIGIBLE_DECISION_SESSION"},
    )
    return append_trial_event(
        ledger,
        event_type="TRIAL_PROTOCOL_AMENDED",
        trial_id="AE001-T004",
        recorded_at_utc="2026-09-29T10:12:41+00:00",
        payload={
            "protocol_id": "AE001-T004-P1",
            "source_end_date": "2026-09-25",
            "primary_training_horizon_sessions": 5,
            "ridge_l2": 1.0,
            "base_feature_count": 18,
            "augmented_feature_count": 27,
        },
    )


def _examples():
    names = [
        definition.name
        for definition in [*PRICE_VOLUME_DEFINITIONS, *DELIVERY_DEFINITIONS]
    ]
    start = date(2026, 1, 1)
    rows = []
    for day_index in range(12):
        feature_day = start + timedelta(days=day_index)
        exit_day = feature_day + timedelta(days=5)
        for stock_index in range(12):
            rows.append(
                ModelExample(
                    symbol=f"S{stock_index:02d}",
                    isin=f"INE{stock_index:09d}",
                    feature_session=feature_day.isoformat(),
                    entry_session=(feature_day + timedelta(days=1)).isoformat(),
                    exit_session=exit_day.isoformat(),
                    horizon_sessions=5,
                    features={
                        name: (
                            stock_index / 11.0
                            + feature_index * 0.001
                            + day_index * 0.0001
                        )
                        for feature_index, name in enumerate(names)
                    },
                    target_excess_return=(
                        stock_index / 1000.0 + day_index / 10000.0
                    ),
                )
            )
    return rows


def _feature_panel():
    definitions = [
        {
            "name": definition.name,
            "family": definition.family,
            "version": definition.version,
            "description": definition.description,
            "lookback_sessions": definition.lookback_sessions,
            "availability_lag_sessions": definition.availability_lag_sessions,
        }
        for definition in [*PRICE_VOLUME_DEFINITIONS, *DELIVERY_DEFINITIONS]
    ]
    return {
        "panel_sha256": "f" * 64,
        "transform": "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1",
        "corporate_action_ledger_sha256": "a" * 64,
        "feature_definitions": definitions,
    }


def test_t004_freezes_base_and_augmented_on_identical_rows(monkeypatch):
    examples = _examples()

    def fake_examples(**kwargs):
        return {5: examples}, {"H5:CORPORATE_ACTION_BLOCKED": 0}

    monkeypatch.setattr(
        "marketlab.alpha_t004.build_action_safe_horizon_examples",
        fake_examples,
    )
    artifact = freeze_t004_models(
        feature_panel=_feature_panel(),
        market_panel={"panel_sha256": "m" * 64},
        action_ledger={"ledger_sha256": "a" * 64},
        trial_ledger=_trial_ledger(),
    )
    validate_frozen_t004_models(artifact)
    assert artifact["training_example_count"] == len(examples)
    assert artifact["base_model"]["training_example_count"] == len(examples)
    assert artifact["augmented_model"]["training_example_count"] == len(examples)
    assert len(artifact["base_feature_names"]) == 18
    assert len(artifact["augmented_feature_names"]) == 27
    assert artifact["retraining_during_primary_trial_allowed"] is False


def test_t004_filters_post_cutoff_labels_before_fit(monkeypatch):
    examples = _examples()
    late = ModelExample(
        **{
            **examples[0].__dict__,
            "feature_session": "2026-09-24",
            "entry_session": "2026-09-25",
            "exit_session": "2026-10-01",
        }
    )

    def fake_examples(**kwargs):
        return {5: [*examples, late]}, {}

    monkeypatch.setattr(
        "marketlab.alpha_t004.build_action_safe_horizon_examples",
        fake_examples,
    )
    artifact = freeze_t004_models(
        feature_panel=_feature_panel(),
        market_panel={"panel_sha256": "m" * 64},
        action_ledger={"ledger_sha256": "a" * 64},
        trial_ledger=_trial_ledger(),
    )
    assert artifact["training_example_count"] == len(examples)
    assert artifact["training_last_exit_session"] <= "2026-09-25"


def test_t004_model_artifact_hash_fails_closed_on_tamper(monkeypatch):
    examples = _examples()

    monkeypatch.setattr(
        "marketlab.alpha_t004.build_action_safe_horizon_examples",
        lambda **kwargs: ({5: examples}, {}),
    )
    artifact = freeze_t004_models(
        feature_panel=_feature_panel(),
        market_panel={"panel_sha256": "m" * 64},
        action_ledger={"ledger_sha256": "a" * 64},
        trial_ledger=_trial_ledger(),
    )
    artifact["base_model"]["intercept"] += 1.0
    with pytest.raises(AlphaContractError, match="artifact hash mismatch"):
        validate_frozen_t004_models(artifact)
