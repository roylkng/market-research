from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.po001_i003 import (
    _execution_inputs,
    _validate_i003_risk_inputs,
    _validate_pinned_alpha_model,
)


def _market_sessions():
    start = date(2026, 8, 12)
    sessions = []
    for index in range(20):
        day = (start + timedelta(days=index)).isoformat()
        sessions.append(
            {
                "session_date": day,
                "equities": [
                    {
                        "session_date": day,
                        "symbol": "TEST",
                        "isin": "INE000000001",
                        "open_price": 100.0,
                        "high_price": 102.0,
                        "low_price": 99.0,
                        "close_price": 101.0,
                        "previous_close": 100.0,
                        "volume": 1000.0,
                        "turnover_inr": float(10_000_000 + index * 1_000_000),
                        "trade_count": 100.0,
                    }
                ],
            }
        )
    return sessions


def _feature_panel():
    return {
        "rows": [
            {
                "feature_session": "2026-08-31",
                "symbol": "TEST",
                "isin": "INE000000001",
                "values": {
                    "realized_vol_20": 0.025,
                },
            }
        ]
    }


def test_i003_execution_inputs_use_exact_identity_and_trailing_20_median():
    result = _execution_inputs(
        market_panel={"sessions": _market_sessions()},
        delivery_feature_panel=_feature_panel(),
        identities=[("TEST", "INE000000001")],
    )
    row = result[("TEST", "INE000000001")]
    assert row["adv20_inr"] == pytest.approx(19_500_000.0)
    assert row["daily_volatility_decimal"] == pytest.approx(0.025)


def test_i003_execution_inputs_fail_on_identity_gap():
    sessions = _market_sessions()
    sessions[10]["equities"] = []
    with pytest.raises(AlphaContractError, match="20 contiguous turnover"):
        _execution_inputs(
            market_panel={"sessions": sessions},
            delivery_feature_panel=_feature_panel(),
            identities=[("TEST", "INE000000001")],
        )



def _risk_state(symbol="TEST", isin="INE000000001"):
    state = {
        "schema_version": 1,
        "model_id": "RM001-v1-DEVELOPMENT",
        "as_of_session": "2026-08-31",
        "factor_names": [],
        "factor_covariance_daily": [],
        "rows": [
            {
                "symbol": symbol,
                "isin": isin,
                "exposures": {},
                "idiosyncratic_variance_daily": 0.001,
                "idiosyncratic_status": "OBSERVED",
            }
        ],
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def test_i003_accepts_frozen_legacy_and_canonical_risk_pair(monkeypatch):
    legacy = _risk_state()
    canonical = _risk_state()
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_LEGACY_RISK_STATE_SHA256",
        legacy["state_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_CANONICAL_RISK_STATE_SHA256",
        canonical["state_sha256"],
    )
    _validate_i003_risk_inputs(legacy, canonical)


def test_i003_rejects_legacy_canonical_identity_drift(monkeypatch):
    legacy = _risk_state()
    canonical = _risk_state(symbol="OTHER", isin="INE999999999")
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_LEGACY_RISK_STATE_SHA256",
        legacy["state_sha256"],
    )
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_CANONICAL_RISK_STATE_SHA256",
        canonical["state_sha256"],
    )
    with pytest.raises(AlphaContractError, match="identity sets differ"):
        _validate_i003_risk_inputs(legacy, canonical)



def _alpha_model():
    model = {
        "model_id": "AE001-T003-H5-F2-AUGMENTED-RIDGE-I002",
        "feature_names": ["x"],
        "feature_medians": [0.5],
        "feature_means": [0.5],
        "feature_scales": [0.25],
        "coefficients": [0.01],
        "intercept": 0.002,
        "l2": 1.0,
        "training_example_count": 169825,
        "training_last_exit_session": "2026-06-30",
    }
    model["model_sha256"] = digest(model)
    return model


def test_i003_accepts_exact_pinned_alpha_model(monkeypatch):
    model = _alpha_model()
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_MODEL_SHA256",
        model["model_sha256"],
    )
    _validate_pinned_alpha_model(model)


def test_i003_rejects_pinned_alpha_model_tamper(monkeypatch):
    model = _alpha_model()
    expected = model["model_sha256"]
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_MODEL_SHA256",
        expected,
    )
    model["coefficients"][0] = 0.02
    with pytest.raises(AlphaContractError, match="hash mismatch"):
        _validate_pinned_alpha_model(model)
