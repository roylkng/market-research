import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001_c001 import (
    MIN_EVALUATED_DATES,
    _classification,
    build_probe_library,
    qlike_loss,
)


def _state(model_id, *, include_size):
    rows = []
    for index in range(600):
        exposures = {
            "MARKET_COMMON": 1.0,
            "BETA60_RELATIVE": (index - 300) / 300.0,
            "MOMENTUM20": ((index * 7) % 601) / 300.0 - 1.0,
            "VOLATILITY60": ((index * 11) % 607) / 303.0 - 1.0,
            "LIQUIDITY": ((index * 13) % 613) / 306.0 - 1.0,
        }
        if include_size:
            exposures["SIZE"] = ((index * 17) % 617) / 308.0 - 1.0
        rows.append(
            {
                "symbol": f"S{index:03d}",
                "isin": f"INE{index:09d}",
                "exposures": exposures,
                "idiosyncratic_variance_daily": 0.0001,
                "idiosyncratic_status": "OBSERVED",
            }
        )
    state = {
        "schema_version": 1,
        "model_id": model_id,
        "as_of_session": "2026-08-31",
        "rows": rows,
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def test_qlike_prefers_variance_closer_to_realized_square():
    realized = 0.0004
    close = qlike_loss(0.0004, realized)
    too_low = qlike_loss(0.0001, realized)
    too_high = qlike_loss(0.0020, realized)
    assert close < too_low
    assert close < too_high


def test_qlike_rejects_nonpositive_forecast():
    with pytest.raises(AlphaContractError, match="strictly positive"):
        qlike_loss(0.0, 0.001)


def test_probe_library_is_deterministic_and_frozen_size():
    v1 = _state("RM001-v1-DEVELOPMENT", include_size=False)
    v2 = _state("RM001-v2-DEVELOPMENT", include_size=True)
    v3 = _state("RM001-v3-DEVELOPMENT", include_size=True)
    first = build_probe_library(
        v1_state=v1,
        v2_state=v2,
        v3_state=v3,
    )
    second = build_probe_library(
        v1_state=v1,
        v2_state=v2,
        v3_state=v3,
    )
    assert first == second
    assert len(first) == 18
    assert all(len(values) == 30 for values in first.values())
    assert set(first) == {
        *(f"HASH{index:02d}" for index in range(8)),
        "BETA60_RELATIVE_LOW",
        "BETA60_RELATIVE_HIGH",
        "MOMENTUM20_LOW",
        "MOMENTUM20_HIGH",
        "VOLATILITY60_LOW",
        "VOLATILITY60_HIGH",
        "LIQUIDITY_LOW",
        "LIQUIDITY_HIGH",
        "SIZE_LOW",
        "SIZE_HIGH",
    }


def _inference(mean, high):
    return {
        "count": MIN_EVALUATED_DATES,
        "mean": mean,
        "newey_west_lag": 5,
        "standard_error": 0.001,
        "t_stat": None,
        "p_value_two_sided": None,
        "ci95_low": mean - 0.002,
        "ci95_high": high,
    }


def test_classification_requires_v3_to_beat_both_parents_significantly():
    result = _classification(
        included_date_count=MIN_EVALUATED_DATES,
        v3_minus_v1=_inference(-0.01, -0.001),
        v3_minus_v2=_inference(-0.02, -0.002),
    )
    assert result == "V3_SUPERIOR_OOS_RISK_FORECAST"


def test_classification_is_mixed_when_only_one_parent_is_beaten():
    result = _classification(
        included_date_count=MIN_EVALUATED_DATES,
        v3_minus_v1=_inference(-0.01, -0.001),
        v3_minus_v2=_inference(0.001, 0.004),
    )
    assert result == "V3_MIXED_OOS_RISK_FORECAST"


def test_classification_reports_no_superiority_when_v3_losses_are_higher():
    result = _classification(
        included_date_count=MIN_EVALUATED_DATES,
        v3_minus_v1=_inference(0.01, 0.02),
        v3_minus_v2=_inference(0.02, 0.03),
    )
    assert result == "NO_V3_OOS_RISK_SUPERIORITY"


def test_classification_fails_closed_on_small_sample():
    result = _classification(
        included_date_count=MIN_EVALUATED_DATES - 1,
        v3_minus_v1=_inference(-0.01, -0.001),
        v3_minus_v2=_inference(-0.02, -0.002),
    )
    assert result == "INSUFFICIENT_CALIBRATION_SAMPLE"
