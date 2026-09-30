from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_model import RidgeModel
from marketlab.po001_i003 import (
    _execution_inputs,
    _validate_alpha_diagnostic,
    _validate_i003_risk_inputs,
    _validate_pinned_alpha_model,
    _validate_pinned_i002_control,
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
        "factor_names": ["MARKET_COMMON"],
        "factor_covariance_window": 60,
        "factor_covariance_first_realized_session": "2026-06-08",
        "factor_covariance_last_realized_session": "2026-08-31",
        "factor_covariance_daily": [[0.00001]],
        "idiosyncratic_window": 60,
        "minimum_idiosyncratic_observations": 20,
        "idiosyncratic_fallback_p75": 0.001,
        "security_count": 1,
        "deferred_factors": {
            "SIZE": "POINT_IN_TIME_MARKET_CAP_SOURCE_NOT_FROZEN",
            "SECTOR": "POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN",
        },
        "rows": [
            {
                "symbol": symbol,
                "isin": isin,
                "exposures": {"MARKET_COMMON": 1.0},
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
    diagnostics = _validate_i003_risk_inputs(legacy, canonical)
    assert diagnostics["economic_equivalence_passed"] is True
    assert diagnostics["max_exposure_abs_diff"] == pytest.approx(0.0)


def test_i003_rejects_legacy_canonical_identity_drift(monkeypatch):
    legacy = _risk_state()
    canonical = _risk_state(symbol="OTHER", isin="INE999999999")
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_LEGACY_RISK_STATE_SHA256",
        legacy["state_sha256"],
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



def test_i003_accepts_rm001_subprecision_drift_under_frozen_p5(monkeypatch):
    legacy = _risk_state()
    canonical = _risk_state()
    canonical["rows"][0]["exposures"]["MARKET_COMMON"] += 1e-15
    unsigned = dict(canonical)
    unsigned.pop("state_sha256", None)
    canonical["state_sha256"] = digest(unsigned)
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_LEGACY_RISK_STATE_SHA256",
        legacy["state_sha256"],
    )
    diagnostics = _validate_i003_risk_inputs(legacy, canonical)
    assert diagnostics["max_exposure_abs_diff"] == pytest.approx(1e-15)


def test_i003_rejects_rm001_drift_above_frozen_p5(monkeypatch):
    legacy = _risk_state()
    canonical = _risk_state()
    canonical["rows"][0]["exposures"]["MARKET_COMMON"] += 1e-12
    unsigned = dict(canonical)
    unsigned.pop("state_sha256", None)
    canonical["state_sha256"] = digest(unsigned)
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_LEGACY_RISK_STATE_SHA256",
        legacy["state_sha256"],
    )
    with pytest.raises(AlphaContractError, match="exposure drift"):
        _validate_i003_risk_inputs(legacy, canonical)



def test_i003_alpha_diagnostic_accepts_exact_pinned_predictions(monkeypatch):
    pinned = _alpha_model()
    diagnostic = RidgeModel(
        model_id=pinned["model_id"],
        feature_names=tuple(pinned["feature_names"]),
        feature_medians=tuple(pinned["feature_medians"]),
        feature_means=tuple(pinned["feature_means"]),
        feature_scales=tuple(pinned["feature_scales"]),
        coefficients=tuple(pinned["coefficients"]),
        intercept=pinned["intercept"],
        l2=pinned["l2"],
        training_example_count=pinned["training_example_count"],
        training_last_exit_session=pinned["training_last_exit_session"],
        model_sha256=pinned["model_sha256"],
    )
    rows = [
        {
            "symbol": f"S{index:03d}",
            "isin": f"INE{index:09d}",
            "values": {"x": index / 100.0},
        }
        for index in range(20)
    ]
    diagnostics = _validate_alpha_diagnostic(
        pinned,
        diagnostic,
        rows,
    )
    assert diagnostics["economic_equivalence_passed"] is True
    assert diagnostics["max_prediction_abs_diff"] == pytest.approx(0.0)
    assert diagnostics["top_decile_symmetric_diff_count"] == 0


def test_i003_alpha_diagnostic_rejects_prediction_drift(monkeypatch):
    pinned = _alpha_model()
    drifted = dict(pinned)
    drifted["coefficients"] = [pinned["coefficients"][0] + 1e-8]
    unsigned = dict(drifted)
    unsigned.pop("model_sha256", None)
    drifted["model_sha256"] = digest(unsigned)
    diagnostic = RidgeModel(
        model_id=drifted["model_id"],
        feature_names=tuple(drifted["feature_names"]),
        feature_medians=tuple(drifted["feature_medians"]),
        feature_means=tuple(drifted["feature_means"]),
        feature_scales=tuple(drifted["feature_scales"]),
        coefficients=tuple(drifted["coefficients"]),
        intercept=drifted["intercept"],
        l2=drifted["l2"],
        training_example_count=drifted["training_example_count"],
        training_last_exit_session=drifted["training_last_exit_session"],
        model_sha256=drifted["model_sha256"],
    )
    rows = [
        {
            "symbol": f"S{index:03d}",
            "isin": f"INE{index:09d}",
            "values": {"x": index / 100.0},
        }
        for index in range(20)
    ]
    with pytest.raises(AlphaContractError, match="alpha drift"):
        _validate_alpha_diagnostic(
            pinned,
            diagnostic,
            rows,
        )



def _i002_control_artifact():
    control = {
        "name": "FULL_PO001_OBSERVABLE_COST_FLOOR",
        "holding_count": 39,
        "invested_weight": 1.0,
        "cash_weight": 0.0,
        "expected_5d_excess_return": 0.01056267666652251,
        "annualized_volatility": 0.13713480625195076,
        "factor_variance_daily": 0.00001,
        "idiosyncratic_variance_daily": 0.00002,
        "total_variance_daily": 0.00003,
        "portfolio_factor_exposures": {},
        "buy_cost_fraction": 0.001,
        "terminal_sell_cost_fraction": 0.001224812,
        "total_round_trip_cost_fraction": 0.002224812,
        "risk_penalty_at_i001_lambda": 0.0018656701473968324,
        "utility_at_i001_lambda": 0.006472194519125673,
        "max_name_weight": 0.05,
        "weight_hhi": 0.03,
        "effective_number_of_names": 33.0,
        "top_holdings": [],
        "positions": [],
        "optimizer_artifact_sha256": "o" * 64,
        "solver": {"success": True},
    }
    artifact = {
        "schema_version": 1,
        "study_id": "PO001-I002-v1",
        "decision_session": "2026-08-31",
        "realized_outcome_opened": False,
        "common_identity_count": 1307,
        "alpha_source": {"model_sha256": "m" * 64},
        "risk_source": {"risk_state_sha256": "r" * 64},
        "portfolios": {
            "full_po001_observable_cost_floor": control,
        },
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def test_i003_accepts_exact_pinned_i002_control(monkeypatch):
    artifact = _i002_control_artifact()
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_MODEL_SHA256",
        "m" * 64,
    )
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_LEGACY_RISK_STATE_SHA256",
        "r" * 64,
    )
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_V1_OPTIMIZER_SHA256",
        "o" * 64,
    )
    control = _validate_pinned_i002_control(artifact)
    assert control["holding_count"] == 39
    assert control["expected_5d_excess_return"] == pytest.approx(
        0.01056267666652251
    )


def test_i003_rejects_pinned_i002_control_tamper(monkeypatch):
    artifact = _i002_control_artifact()
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_MODEL_SHA256",
        "m" * 64,
    )
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_LEGACY_RISK_STATE_SHA256",
        "r" * 64,
    )
    monkeypatch.setattr(
        "marketlab.po001_i003.EXPECTED_V1_OPTIMIZER_SHA256",
        "o" * 64,
    )
    artifact["portfolios"]["full_po001_observable_cost_floor"][
        "holding_count"
    ] = 40
    with pytest.raises(AlphaContractError, match="hash mismatch"):
        _validate_pinned_i002_control(artifact)
