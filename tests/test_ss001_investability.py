from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss001_investability import (
    build_investability_context,
    liquidity_band,
)


def test_liquidity_bands_are_frozen_at_operational_boundaries() -> None:
    assert liquidity_band(
        observed_session_count=20,
        median_daily_turnover_inr=100_000_000.0,
    ) == "L1_10CR_PLUS"
    assert liquidity_band(
        observed_session_count=20,
        median_daily_turnover_inr=50_000_000.0,
    ) == "L2_5_TO_10CR"
    assert liquidity_band(
        observed_session_count=20,
        median_daily_turnover_inr=20_000_000.0,
    ) == "L3_2_TO_5CR"
    assert liquidity_band(
        observed_session_count=20,
        median_daily_turnover_inr=10_000_000.0,
    ) == "L4_1_TO_2CR"
    assert liquidity_band(
        observed_session_count=20,
        median_daily_turnover_inr=2_000_000.0,
    ) == "L5_20L_TO_1CR"
    assert liquidity_band(
        observed_session_count=20,
        median_daily_turnover_inr=1_999_999.0,
    ) == "L6_BELOW_20L"
    assert liquidity_band(
        observed_session_count=14,
        median_daily_turnover_inr=100_000_000.0,
    ) == "OBSERVATION_INSUFFICIENT"


def _census() -> dict:
    rows = []
    for idx in range(2319):
        rows.append(
            {
                "symbol": f"S{idx:04d}",
                "isin": f"INE{idx:09d}"[-12:],
                "in_existing_u001": idx < 100,
                "market": {
                    "observed_session_count": 20 if idx != 2318 else 10,
                    "median_daily_turnover_inr": (
                        100_000_000.0 if idx != 2318 else 1_000_000.0
                    ),
                },
            }
        )
    return {
        "census_id": "SS001-D001-v1",
        "census_sha256": (
            "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"
        ),
        "eq_identity_count": 2319,
        "rows": rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_context_retains_all_names_and_adds_capacity_surfaces() -> None:
    result = build_investability_context(_census())
    assert len(result["rows"]) == 2319
    first = result["rows"][0]
    assert first["liquidity_band"] == "L1_10CR_PLUS"
    assert first["one_day_capacity"]["5pct_adv_inr"] == pytest.approx(5_000_000.0)
    assert first["execution_days_at_5pct_adv"]["1_crore"] == pytest.approx(2.0)
    unresolved = next(row for row in result["rows"] if row["symbol"] == "S2318")
    assert unresolved["liquidity_band"] == "OBSERVATION_INSUFFICIENT"
    assert unresolved["research_capacity_state"] == "RESEARCH_ONLY_CAPACITY_UNRESOLVED"
    assert result["portfolio_eligibility_allowed"] is False


def test_wrong_source_hash_fails_closed() -> None:
    census = _census()
    census["census_sha256"] = "wrong"
    with pytest.raises(AlphaContractError, match="census SHA mismatch"):
        build_investability_context(census)
