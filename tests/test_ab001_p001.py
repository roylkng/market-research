from datetime import date, timedelta

import pytest

from marketlab.ab001_p001 import run_ab001_p001
from marketlab.alpha import AlphaContractError
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_model import ModelExample
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS


def _examples():
    names = [
        definition.name
        for definition in [*PRICE_VOLUME_DEFINITIONS, *DELIVERY_DEFINITIONS]
    ]
    sessions = [
        "2026-01-05",
        "2026-01-12",
        "2026-01-19",
        "2026-01-26",
        "2026-02-02",
        "2026-04-01",
        "2026-04-02",
        "2026-04-03",
        "2026-07-01",
        "2026-07-02",
        "2026-07-03",
    ]
    rows = []
    for session_index, session in enumerate(sessions):
        day = date.fromisoformat(session)
        for stock_index in range(30):
            centered = stock_index - 14.5
            features = {
                name: (
                    centered * (feature_index + 1) / 1000.0
                    + session_index * 0.0001
                )
                for feature_index, name in enumerate(names)
            }
            target = centered / 1000.0
            rows.append(
                ModelExample(
                    symbol=f"S{stock_index:03d}",
                    isin=f"INE{stock_index:09d}",
                    feature_session=session,
                    entry_session=(day + timedelta(days=1)).isoformat(),
                    exit_session=(day + timedelta(days=5)).isoformat(),
                    horizon_sessions=5,
                    features=features,
                    target_excess_return=target,
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
        "schema_version": 1,
        "panel_id": "SYNTHETIC",
        "panel_sha256": "f" * 64,
        "base_feature_panel_sha256": "b" * 64,
        "corporate_action_ledger_sha256": "a" * 64,
        "transform": "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1",
        "feature_definitions": definitions,
        "rows": [],
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }


def test_p001_reconstructs_three_frozen_oos_sources(monkeypatch):
    monkeypatch.setattr(
        "marketlab.ab001_p001.EXPECTED_MARKET_SHA",
        "m" * 64,
    )
    monkeypatch.setattr(
        "marketlab.ab001_p001.EXPECTED_BASE_FEATURE_SHA",
        "b" * 64,
    )
    monkeypatch.setattr(
        "marketlab.ab001_p001.EXPECTED_ACTION_SHA",
        "a" * 64,
    )
    monkeypatch.setattr(
        "marketlab.ab001_p001.EXPECTED_AUGMENTED_FEATURE_SHA",
        "f" * 64,
    )
    monkeypatch.setattr(
        "marketlab.ab001_p001.build_action_safe_horizon_examples",
        lambda **kwargs: ({5: _examples()}, {}),
    )

    result = run_ab001_p001(
        market_panel={"panel_sha256": "m" * 64},
        augmented_feature_panel=_feature_panel(),
        action_ledger={"ledger_sha256": "a" * 64},
    )

    assert result["pilot_id"] == "AB001-P001-v1"
    assert result["horizon_sessions"] == 5
    assert result["library"]["alpha_count"] == 3
    assert result["library"]["record_count"] > 0
    assert set(result["standalone"]) == {
        "AB001-P001-A1",
        "AB001-P001-A2",
        "AB001-P001-A3",
    }
    assert len(result["pairwise"]) == 3
    assert result["incremental_augmented_candidate"][
        "candidate_alpha_id"
    ] == "AB001-P001-A1"
    assert result["dynamic_blend"]["prediction_count"] > 0
    assert result["dynamic_vs_augmented"][
        "dynamic_minus_augmented_inference"
    ]["common_session_count"] == 6
    assert result["prospective_claim_allowed"] is False
    assert len(result["report_sha256"]) == 64


def test_p001_fails_closed_on_upstream_hash_drift(monkeypatch):
    monkeypatch.setattr(
        "marketlab.ab001_p001.EXPECTED_MARKET_SHA",
        "m" * 64,
    )
    with pytest.raises(AlphaContractError, match="market panel"):
        run_ab001_p001(
            market_panel={"panel_sha256": "x" * 64},
            augmented_feature_panel=_feature_panel(),
            action_ledger={"ledger_sha256": "a" * 64},
        )
