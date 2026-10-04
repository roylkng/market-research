from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ei001_inflection import build_inflection_router, derive_inflection


def _family(current: float, prior: float) -> dict:
    return {
        "status": "COMPARABLE_READY",
        "current_value": current,
        "prior_value": prior,
        "unit_ref": "INR",
    }


def test_broad_growth_leverage_and_strong_growth_flags() -> None:
    result = derive_inflection(
        {
            "revenue": _family(130.0, 100.0),
            "pat": _family(18.0, 10.0),
            "pbt": _family(24.0, 16.0),
            "basic_eps": _family(18.0, 10.0),
        }
    )
    assert "BROAD_GROWTH_LEVERAGE" in result["opportunity_flags"]
    assert "STRONG_GROWTH" in result["opportunity_flags"]
    assert result["metrics"]["revenue_growth_pct"] == pytest.approx(30.0)
    assert result["metrics"]["pat_growth_pct"] == pytest.approx(80.0)
    assert result["metrics"]["pat_margin_delta_bps"] > 300


def test_profit_turnaround_does_not_fake_growth_from_negative_pat() -> None:
    result = derive_inflection(
        {
            "revenue": _family(105.0, 100.0),
            "pat": _family(4.0, -3.0),
            "pbt": _family(5.0, -2.0),
            "basic_eps": _family(0.4, -0.3),
        }
    )
    assert result["metrics"]["pat_growth_pct"] is None
    assert result["opportunity_flags"] == ["PROFIT_TURNAROUND"]


def test_low_base_pat_is_explicit_caution() -> None:
    result = derive_inflection(
        {
            "revenue": _family(110.0, 100.0),
            "pat": _family(5.0, 0.5),
            "pbt": _family(7.0, 1.0),
            "basic_eps": _family(5.0, 0.5),
        }
    )
    assert "LOW_BASE_PAT" in result["caution_flags"]


def _panel() -> dict:
    rows = []
    for index in range(2319):
        comparable = None
        status = "CURRENT_UNAVAILABLE"
        if index == 0:
            status = "PAIR_READY"
            comparable = {
                "revenue": _family(130.0, 100.0),
                "pat": _family(18.0, 10.0),
                "pbt": _family(24.0, 16.0),
                "basic_eps": _family(18.0, 10.0),
            }
        rows.append(
            {
                "symbol": f"S{index:04d}",
                "isin": f"INE{index:09d}",
                "company_name": f"Company {index}",
                "in_existing_u001": False,
                "status": status,
                "reason": None,
                "current": None,
                "prior": None,
                "comparable": comparable,
            }
        )
    return {
        "panel_id": "EI001-D002-v1",
        "panel_sha256": (
            "14fdc99444ff8c1c62cbef58db91e51cb4cb6730c1259bccb98df979366272cd"
        ),
        "rows": rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_full_router_keeps_research_only_boundaries() -> None:
    output = build_inflection_router(_panel())
    assert output["identity_count"] == 2319
    assert output["pair_ready_count"] == 1
    assert output["any_opportunity_flag_count"] == 1
    assert output["portfolio_eligibility_allowed"] is False
    assert output["live_capital_allowed"] is False


def test_router_fails_closed_on_source_hash_mismatch() -> None:
    panel = _panel()
    panel["panel_sha256"] = "wrong"
    with pytest.raises(AlphaContractError, match="panel SHA mismatch"):
        build_inflection_router(panel)
