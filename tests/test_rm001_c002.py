from datetime import UTC, datetime

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001_c002 import (
    CALIBRATION_SCALE,
    append_forecast_entry,
    append_outcome_entry,
    build_forecast_artifact,
    build_outcome_artifact,
    build_probe_library_v1,
    forecast_seal_cutoff_utc,
    new_forecast_ledger,
    new_outcome_ledger,
    prospective_summary,
    validate_forecast_ledger,
    validate_outcome_ledger,
)
from marketlab.rm001_calibration import calibrate_v1_risk_state


def _raw_state(count=520):
    rows = []
    for index in range(count):
        centered = 2.0 * (index + 1) / (count + 1) - 1.0
        rows.append(
            {
                "symbol": f"S{index:04d}",
                "isin": f"INE{index:09d}",
                "exposures": {
                    "MARKET_COMMON": 1.0,
                    "BETA60_RELATIVE": centered,
                    "MOMENTUM20": -centered,
                    "VOLATILITY60": centered * 0.5,
                    "LIQUIDITY": centered * 0.25,
                },
                "idiosyncratic_variance_daily": 0.0004 + index * 1e-8,
                "idiosyncratic_status": "OBSERVED",
            }
        )
    state = {
        "schema_version": 1,
        "model_id": "RM001-v1-DEVELOPMENT",
        "as_of_session": "2026-10-05",
        "factor_names": [
            "MARKET_COMMON",
            "BETA60_RELATIVE",
            "MOMENTUM20",
            "VOLATILITY60",
            "LIQUIDITY",
        ],
        "factor_covariance_window": 60,
        "factor_covariance_first_realized_session": "2026-07-01",
        "factor_covariance_last_realized_session": "2026-10-05",
        "factor_covariance_daily": [
            [0.00001 if i == j else 0.0 for j in range(5)]
            for i in range(5)
        ],
        "idiosyncratic_window": 60,
        "minimum_idiosyncratic_observations": 20,
        "idiosyncratic_fallback_p75": 0.0007,
        "exposure_panel_sha256": "a" * 64,
        "factor_history_sha256": "b" * 64,
        "security_count": count,
        "rows": rows,
        "deferred_factors": {
            "SIZE": "POINT_IN_TIME_MARKET_CAP_SOURCE_NOT_FROZEN",
            "SECTOR": "POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN",
        },
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def _attempt():
    return {
        "session_date": "2026-10-05",
        "eligible_before_cutoff": True,
        "attempt_sha256": "c" * 64,
        "captured_at_utc": "2026-10-05T12:30:00+00:00",
        "market": {"raw_sha256": "d" * 64},
    }


def test_c002_probe_library_has_16_fixed_probes():
    probes = build_probe_library_v1(_raw_state())
    assert len(probes) == 16
    assert all(len(members) == 30 for members in probes.values())
    assert {name for name in probes if name.startswith("HASH")} == {
        f"HASH{index:02d}" for index in range(8)
    }


def test_c002_forecast_is_outcome_free_and_sealed_before_cutoff():
    raw = _raw_state()
    calibrated = calibrate_v1_risk_state(raw)
    artifact = build_forecast_artifact(
        target_session_date="2026-10-05",
        sc001_attempt=_attempt(),
        raw_risk_state=raw,
        calibrated_risk_state=calibrated,
        sealed_at_utc="2026-10-05T14:00:00+00:00",
    )
    assert artifact["probe_count"] == 16
    assert artifact["outcomes_attached"] is False
    assert artifact["calibration_scale"] == CALIBRATION_SCALE
    assert forecast_seal_cutoff_utc("2026-10-05") == datetime(
        2026, 10, 6, 3, 35, tzinfo=UTC
    )


def test_c002_late_forecast_fails_closed():
    raw = _raw_state()
    calibrated = calibrate_v1_risk_state(raw)
    with pytest.raises(AlphaContractError, match="missed 09:05"):
        build_forecast_artifact(
            target_session_date="2026-10-05",
            sc001_attempt=_attempt(),
            raw_risk_state=raw,
            calibrated_risk_state=calibrated,
            sealed_at_utc="2026-10-06T03:35:01+00:00",
        )


def test_c002_ledgers_are_append_only_and_hash_verified():
    forecast = append_forecast_entry(
        new_forecast_ledger(),
        target_session_date="2026-10-05",
        status="SEALED",
        sc001_attempt_sha256="a" * 64,
        observed_at_utc="2026-10-05T14:00:00+00:00",
        forecast_artifact_path="forecast.json.gz",
        forecast_artifact_sha256="b" * 64,
        raw_risk_state_sha256="c" * 64,
        calibrated_risk_state_sha256="d" * 64,
    )
    validate_forecast_ledger(forecast)
    assert forecast["entry_count"] == 1

    outcome_artifact = {
        "target_session_date": "2026-10-05",
        "realized_session_date": "2026-10-06",
        "status": "SCORED",
        "artifact_sha256": "e" * 64,
        "valid_probe_count": 16,
        "cal1_minus_raw_mean_qlike": -0.1,
    }
    outcome = append_outcome_entry(
        new_outcome_ledger(),
        forecast_entry_sha256=forecast["entries"][0]["entry_sha256"],
        outcome_artifact=outcome_artifact,
        outcome_artifact_path="outcome.json.gz",
    )
    validate_outcome_ledger(outcome)
    assert outcome["entry_count"] == 1


def test_c002_outcome_and_summary_compare_raw_vs_cal1_only():
    raw = _raw_state()
    calibrated = calibrate_v1_risk_state(raw)
    forecast = build_forecast_artifact(
        target_session_date="2026-10-05",
        sc001_attempt=_attempt(),
        raw_risk_state=raw,
        calibrated_risk_state=calibrated,
        sealed_at_utc="2026-10-05T14:00:00+00:00",
    )
    returns = {
        (row["symbol"], row["isin"]): 0.001
        for row in raw["rows"]
    }
    outcome = build_outcome_artifact(
        forecast_artifact=forecast,
        realized_session_date="2026-10-06",
        realized_returns=returns,
    )
    assert outcome["status"] == "SCORED"
    assert outcome["valid_probe_count"] == 16
    summary = prospective_summary([outcome])
    assert summary["status"] == "INSUFFICIENT_PROSPECTIVE_SAMPLE"
    assert summary["evaluated_date_count"] == 1
