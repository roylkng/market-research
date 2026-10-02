import copy

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001 import portfolio_risk
from marketlab.rm001_calibration import (
    CAL1_MODEL_ID,
    CALIBRATION_SCALE,
    calibrate_v1_risk_state,
    portfolio_risk_cal1,
)


def _raw_state():
    state = {
        "schema_version": 1,
        "model_id": "RM001-v1-DEVELOPMENT",
        "as_of_session": "2026-09-25",
        "factor_names": [
            "MARKET_COMMON",
            "BETA60_RELATIVE",
            "MOMENTUM20",
            "VOLATILITY60",
            "LIQUIDITY",
        ],
        "factor_covariance_window": 60,
        "factor_covariance_first_realized_session": "2026-07-01",
        "factor_covariance_last_realized_session": "2026-09-25",
        "factor_covariance_daily": [
            [0.00001, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.00002, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.00003, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.00004, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.00005],
        ],
        "idiosyncratic_window": 60,
        "minimum_idiosyncratic_observations": 20,
        "idiosyncratic_fallback_p75": 0.0007,
        "exposure_panel_sha256": "a" * 64,
        "factor_history_sha256": "b" * 64,
        "security_count": 2,
        "rows": [
            {
                "symbol": "AAA",
                "isin": "INE000000001",
                "exposures": {
                    "MARKET_COMMON": 1.0,
                    "BETA60_RELATIVE": 0.1,
                    "MOMENTUM20": -0.2,
                    "VOLATILITY60": 0.3,
                    "LIQUIDITY": 0.4,
                },
                "idiosyncratic_variance_daily": 0.0004,
                "idiosyncratic_status": "OBSERVED",
            },
            {
                "symbol": "BBB",
                "isin": "INE000000002",
                "exposures": {
                    "MARKET_COMMON": 1.0,
                    "BETA60_RELATIVE": -0.2,
                    "MOMENTUM20": 0.3,
                    "VOLATILITY60": -0.1,
                    "LIQUIDITY": -0.5,
                },
                "idiosyncratic_variance_daily": 0.0008,
                "idiosyncratic_status": "CONSERVATIVE_IMPUTATION_P75",
            },
        ],
        "deferred_factors": {
            "SIZE": "POINT_IN_TIME_MARKET_CAP_SOURCE_NOT_FROZEN",
            "SECTOR": "POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN",
        },
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def test_cal1_preserves_identity_exposure_and_status_structure():
    raw = _raw_state()
    calibrated = calibrate_v1_risk_state(raw)

    assert calibrated["model_id"] == CAL1_MODEL_ID
    assert calibrated["parent_risk_state_sha256"] == raw["state_sha256"]
    assert calibrated["security_count"] == raw["security_count"]
    assert calibrated["factor_names"] == raw["factor_names"]
    assert calibrated["deferred_factors"] == raw["deferred_factors"]

    for source, target in zip(raw["rows"], calibrated["rows"], strict=True):
        assert (source["symbol"], source["isin"]) == (
            target["symbol"],
            target["isin"],
        )
        assert source["exposures"] == target["exposures"]
        assert (
            source["idiosyncratic_status"]
            == target["idiosyncratic_status"]
        )
        assert target["idiosyncratic_variance_daily"] == pytest.approx(
            source["idiosyncratic_variance_daily"] * CALIBRATION_SCALE,
            abs=1e-15,
        )


def test_cal1_scales_any_portfolio_variance_by_frozen_scalar():
    raw = _raw_state()
    calibrated = calibrate_v1_risk_state(raw)
    positions = [
        {"symbol": "AAA", "isin": "INE000000001", "weight": 0.4},
        {"symbol": "BBB", "isin": "INE000000002", "weight": 0.5},
    ]

    raw_report = portfolio_risk(raw, positions=positions)
    cal_report = portfolio_risk_cal1(
        calibrated,
        positions=positions,
    )

    assert cal_report["model_id"] == CAL1_MODEL_ID
    assert cal_report["total_variance_daily"] == pytest.approx(
        raw_report["total_variance_daily"] * CALIBRATION_SCALE,
        abs=5e-15,
    )
    assert cal_report["factor_variance_daily"] == pytest.approx(
        raw_report["factor_variance_daily"] * CALIBRATION_SCALE,
        abs=5e-15,
    )
    assert cal_report["idiosyncratic_variance_daily"] == pytest.approx(
        raw_report["idiosyncratic_variance_daily"] * CALIBRATION_SCALE,
        abs=5e-15,
    )


def test_cal1_rejects_tampered_or_non_v1_parent():
    raw = _raw_state()
    tampered = copy.deepcopy(raw)
    tampered["rows"][0]["idiosyncratic_variance_daily"] = 0.9
    with pytest.raises(AlphaContractError, match="hash mismatch"):
        calibrate_v1_risk_state(tampered)

    wrong = _raw_state()
    wrong["model_id"] = "RM001-v2-DEVELOPMENT"
    unsigned = copy.deepcopy(wrong)
    unsigned.pop("state_sha256")
    wrong["state_sha256"] = digest(unsigned)
    with pytest.raises(AlphaContractError, match="requires RM001-v1"):
        calibrate_v1_risk_state(wrong)
