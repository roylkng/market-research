import pytest

from marketlab.alpha import digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.po001_i001 import (
    _capped_proportional,
    run_po001_i001,
)
from marketlab.rm001 import FACTOR_NAMES


def test_capped_proportional_fully_invests_without_breaking_cap():
    values = [
        ((f"S{index:02d}", f"INE{index:09d}"), float(index + 1))
        for index in range(25)
    ]
    weights = _capped_proportional(values, cap=0.05)
    assert sum(weights.values()) == pytest.approx(1.0)
    assert max(weights.values()) <= 0.05 + 1e-12
    assert all(weight > 0 for weight in weights.values())


def _feature_panel(count=20):
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
    rows = []
    for index in range(count):
        rows.append(
            {
                "feature_session": "2026-09-25",
                "symbol": f"S{index:03d}",
                "isin": f"INE{index:09d}",
                "values": {
                    definition["name"]: (index + 1) / (count + 1)
                    for definition in definitions
                },
            }
        )
    panel = {
        "schema_version": 1,
        "panel_id": "TEST-DELIVERY",
        "transform": "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1",
        "feature_definitions": definitions,
        "rows": rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _risk_state(count=20):
    rows = []
    for index in range(count):
        percentile = (index + 1) / (count + 1)
        centered = 2.0 * percentile - 1.0
        rows.append(
            {
                "symbol": f"S{index:03d}",
                "isin": f"INE{index:09d}",
                "exposures": {
                    "MARKET_COMMON": 1.0,
                    "BETA60_RELATIVE": centered * 0.2,
                    "MOMENTUM20": centered,
                    "VOLATILITY60": -centered * 0.5,
                    "LIQUIDITY": centered * 0.3,
                },
                "idiosyncratic_variance_daily": 0.00001,
                "idiosyncratic_status": "OBSERVED",
            }
        )
    state = {
        "schema_version": 1,
        "model_id": "RM001-v1-DEVELOPMENT",
        "as_of_session": "2026-09-25",
        "factor_names": list(FACTOR_NAMES),
        "factor_covariance_daily": [
            [0.000001 if i == j else 0.0 for j in range(len(FACTOR_NAMES))]
            for i in range(len(FACTOR_NAMES))
        ],
        "rows": rows,
        "deferred_factors": {
            "SIZE": "POINT_IN_TIME_MARKET_CAP_SOURCE_NOT_FROZEN",
            "SECTOR": "POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN",
        },
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def _models():
    names = [
        definition.name
        for definition in [*PRICE_VOLUME_DEFINITIONS, *DELIVERY_DEFINITIONS]
    ]
    return {
        "artifact_id": "AE001-T004-FROZEN-MODELS-v1",
        "artifact_sha256": "a" * 64,
        "augmented_feature_names": names,
        "augmented_model": {
            "model_id": "AE001-T004-AUGMENTED-RIDGE-v1",
            "model_sha256": "b" * 64,
        },
    }


def test_i001_integrates_alpha_risk_cost_without_opening_outcome(monkeypatch):
    monkeypatch.setattr(
        "marketlab.po001_i001.validate_frozen_t004_models",
        lambda artifact: None,
    )
    monkeypatch.setattr(
        "marketlab.po001_i001.MIN_COMMON_IDENTITIES",
        20,
    )
    monkeypatch.setattr(
        "marketlab.po001_i001.TOP_DECILE_SHARE",
        1.0,
    )

    def fake_score(model, rows):
        return [
            {
                "symbol": row["symbol"],
                "isin": row["isin"],
                "prediction": 0.010 + index * 0.0005,
            }
            for index, row in enumerate(rows)
        ]

    monkeypatch.setattr(
        "marketlab.po001_i001._score_model",
        fake_score,
    )

    artifact = run_po001_i001(
        delivery_feature_panel=_feature_panel(),
        risk_state=_risk_state(),
        frozen_models=_models(),
    )
    assert artifact["common_identity_count"] == 20
    assert artifact["realized_outcome_opened"] is False
    assert artifact["interpretation_limits"]["no_realized_5d_outcome"] is True
    assert set(artifact["portfolios"]) == {
        "equal_weight_top_decile",
        "positive_alpha_proportional_top_decile",
        "risk_aware_zero_cost",
        "full_po001_observable_cost_floor",
    }
    assert artifact["portfolios"]["equal_weight_top_decile"][
        "invested_weight"
    ] == pytest.approx(1.0)
    assert artifact["portfolios"]["full_po001_observable_cost_floor"][
        "total_round_trip_cost_fraction"
    ] >= 0.0
    assert artifact["portfolios"]["risk_aware_zero_cost"][
        "total_round_trip_cost_fraction"
    ] == pytest.approx(0.0)
    assert len(artifact["artifact_sha256"]) == 64
