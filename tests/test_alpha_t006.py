from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_futures import FUTURES_DEFINITIONS
from marketlab.alpha_model import ModelExample
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.alpha_t006 import (
    freeze_t006_models,
    validate_frozen_t006_models,
)
from marketlab.alpha_trials import append_trial_event, new_trial_ledger


def _trial_ledger():
    ledger = append_trial_event(
        new_trial_ledger(),
        event_type="TRIAL_REGISTERED",
        trial_id="AE001-T006",
        recorded_at_utc="2026-09-30T10:44:49+00:00",
        payload={
            "status": "FROZEN_BEFORE_FIRST_ELIGIBLE_DECISION_SESSION"
        },
    )
    return append_trial_event(
        ledger,
        event_type="TRIAL_PROTOCOL_AMENDED",
        trial_id="AE001-T006",
        recorded_at_utc="2026-09-30T10:44:50+00:00",
        payload={
            "protocol_id": "AE001-T006-P1",
            "source_end_date": "2026-09-25",
            "training_horizon_sessions": 5,
            "ridge_l2": 1.0,
            "base_feature_count": 27,
            "augmented_feature_count": 37,
            "futures_feature_count": 10,
            "retraining_during_trial_allowed": False,
            "earliest_eligible_decision_date": "2026-10-01",
        },
    )


def _examples():
    names = [
        definition.name
        for definition in [
            *PRICE_VOLUME_DEFINITIONS,
            *DELIVERY_DEFINITIONS,
            *FUTURES_DEFINITIONS,
        ]
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
        for definition in [
            *PRICE_VOLUME_DEFINITIONS,
            *DELIVERY_DEFINITIONS,
            *FUTURES_DEFINITIONS,
        ]
    ]
    return {
        "panel_sha256": (
            "62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f"
        ),
        "transform": "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1",
        "base_feature_panel_sha256": (
            "99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90"
        ),
        "futures_panel_sha256": (
            "02656c828a1d5fe22660c154a445ebd69a7492b56f1807da0d8c959a6f0c11d5"
        ),
        "corporate_action_ledger_sha256": (
            "1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1"
        ),
        "feature_definitions": definitions,
    }


def test_t006_freezes_identical_core_and_full_rows(monkeypatch):
    examples = _examples()
    monkeypatch.setattr(
        "marketlab.alpha_t006.build_action_safe_horizon_examples",
        lambda **kwargs: ({5: examples}, {}),
    )
    artifact = freeze_t006_models(
        feature_panel=_feature_panel(),
        market_panel={
            "panel_sha256": (
                "9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e"
            )
        },
        action_ledger={
            "ledger_sha256": (
                "1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1"
            )
        },
        trial_ledger=_trial_ledger(),
    )
    validate_frozen_t006_models(artifact)
    assert artifact["training_example_count"] == len(examples)
    assert len(artifact["base_feature_names"]) == 27
    assert len(artifact["futures_feature_names"]) == 10
    assert len(artifact["augmented_feature_names"]) == 37
    assert artifact["base_model"]["training_example_count"] == len(examples)
    assert artifact["augmented_model"]["training_example_count"] == len(examples)
    assert artifact["retraining_during_primary_trial_allowed"] is False


def test_t006_filters_post_cutoff_labels(monkeypatch):
    examples = _examples()
    late = ModelExample(
        **{
            **examples[0].__dict__,
            "feature_session": "2026-09-24",
            "entry_session": "2026-09-25",
            "exit_session": "2026-10-01",
        }
    )
    monkeypatch.setattr(
        "marketlab.alpha_t006.build_action_safe_horizon_examples",
        lambda **kwargs: ({5: [*examples, late]}, {}),
    )
    artifact = freeze_t006_models(
        feature_panel=_feature_panel(),
        market_panel={
            "panel_sha256": (
                "9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e"
            )
        },
        action_ledger={
            "ledger_sha256": (
                "1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1"
            )
        },
        trial_ledger=_trial_ledger(),
    )
    assert artifact["training_example_count"] == len(examples)
    assert artifact["training_last_exit_session"] <= "2026-09-25"


def test_t006_model_artifact_fails_closed_on_tamper(monkeypatch):
    examples = _examples()
    monkeypatch.setattr(
        "marketlab.alpha_t006.build_action_safe_horizon_examples",
        lambda **kwargs: ({5: examples}, {}),
    )
    artifact = freeze_t006_models(
        feature_panel=_feature_panel(),
        market_panel={
            "panel_sha256": (
                "9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e"
            )
        },
        action_ledger={
            "ledger_sha256": (
                "1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1"
            )
        },
        trial_ledger=_trial_ledger(),
    )
    artifact["augmented_model"]["intercept"] += 1.0
    with pytest.raises(AlphaContractError, match="artifact hash mismatch"):
        validate_frozen_t006_models(artifact)
