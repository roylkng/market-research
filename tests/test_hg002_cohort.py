from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg002_cohort import build_underwriting_cohort


def _row(index: int) -> dict:
    return {
        "symbol": f"S{index:04d}",
        "isin": f"INE{index:09d}",
        "in_existing_u001": False,
        "active_opportunity_lanes": [
            "EARNINGS_INFLECTION",
            "ASSET_OR_CAPACITY_ANOMALY",
            "CURRENT_SPECIAL_SITUATION",
        ],
        "active_opportunity_lane_count": 3,
        "earnings_inflection_state": "STRONG_INFLECTION",
        "earnings_positive_flags": ["REVENUE_GROWTH_15", "PAT_GROWTH_25"],
        "earnings_negative_flags": [],
        "earnings_metrics": {"revenue_growth_pct": 25.0},
        "asset_opportunity_flags": ["LIQUID_ASSET_HEAVY"],
        "asset_caution_flags": [],
        "governance_caution_flags": [],
        "governance_caution_count": 0,
        "promoter_percentage": 60.0,
        "promoter_delta_pp": 0.0,
        "liquidity_band": "L3_2_TO_5CR",
        "median_daily_turnover_inr": 30_000_000.0,
        "research_capacity_state": "CAPACITY_OBSERVED",
        "special_situation_event_count": 1,
        "special_situation_categories": (
            ["BUYBACK"] if index < 3 else ["SCHEME_REORGANISATION"]
        ),
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _router() -> dict:
    selected = [_row(index) for index in range(28)]
    remaining = []
    for index in range(28, 2319):
        row = _row(index)
        row["active_opportunity_lanes"] = ["EARNINGS_INFLECTION"]
        row["active_opportunity_lane_count"] = 1
        row["asset_opportunity_flags"] = []
        row["special_situation_event_count"] = 0
        row["special_situation_categories"] = []
        remaining.append(row)
    return {
        "router_id": "HG001-D001-v1",
        "router_sha256": (
            "79e6b068f95c890e4ef88be62ffe2e8dfb94fabbf293770804e64aaa82d6e5ff"
        ),
        "identity_count": 2319,
        "rows": selected + remaining,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_cohort_retains_all_28_triple_convergence_clean_names() -> None:
    output = build_underwriting_cohort(_router())
    assert output["cohort_count"] == 28
    assert output["l001_p1_validated_family_ready_count"] == 3
    assert output["l001_p1_unvalidated_family_counts"] == {
        "SCHEME_REORGANISATION": 25
    }
    assert all(
        row["deep_research_workstreams"]
        == [
            "EARNINGS_NORMALIZATION",
            "ASSET_CAPACITY_VERIFICATION",
            "SPECIAL_SITUATION_ECONOMICS",
        ]
        for row in output["rows"]
    )
    assert output["portfolio_eligibility_allowed"] is False


def test_u001_name_is_not_admitted() -> None:
    router = _router()
    router["rows"][0]["in_existing_u001"] = True
    with pytest.raises(AlphaContractError, match="expected 28 qualifying"):
        build_underwriting_cohort(router)


def test_governance_or_asset_caution_is_not_admitted() -> None:
    router = _router()
    router["rows"][0]["governance_caution_count"] = 1
    with pytest.raises(AlphaContractError, match="expected 28 qualifying"):
        build_underwriting_cohort(router)

    router = _router()
    router["rows"][0]["asset_caution_flags"] = ["WORKING_CAPITAL_HEAVY_CAUTION"]
    with pytest.raises(AlphaContractError, match="expected 28 qualifying"):
        build_underwriting_cohort(router)
