from __future__ import annotations

from marketlab.ei001_inflection import evaluate_inflection_row
from marketlab.hg001_router import build_hidden_gem_router


def _family(current: float, prior: float) -> dict:
    return {
        "status": "COMPARABLE_READY",
        "current_value": current,
        "prior_value": prior,
    }


def _ei_source(symbol: str, *, revenue=(115.0,100.0), pat=(130.0,100.0), pbt=(25.0,20.0), eps=(13.0,10.0), fin=(8.0,10.0)) -> dict:
    return {
        "symbol": symbol,
        "company_name": symbol,
        "isin": f"ISIN-{symbol}",
        "status": "PAIR_READY",
        "in_existing_u001": False,
        "comparable": {
            "revenue": _family(*revenue),
            "pat": _family(*pat),
            "pbt": _family(*pbt),
            "basic_eps": _family(*eps),
            "finance_costs": _family(*fin),
        },
    }


def test_inflection_strong_on_revenue_and_pat_growth() -> None:
    row=evaluate_inflection_row(_ei_source("AAA"))
    assert row["inflection_state"]=="STRONG_INFLECTION"
    assert "REVENUE_GROWTH_15" in row["positive_flags"]
    assert "PAT_GROWTH_25" in row["positive_flags"]


def test_inflection_detects_loss_to_profit_turnaround() -> None:
    row=evaluate_inflection_row(_ei_source("AAA",pat=(10.0,-5.0),eps=(1.0,-0.5)))
    assert row["inflection_state"]=="STRONG_INFLECTION"
    assert "LOSS_TO_PROFIT_TURNAROUND" in row["positive_flags"]


def test_inflection_negative_diagnostics_do_not_create_positive_state() -> None:
    row=evaluate_inflection_row(
        _ei_source("AAA",revenue=(80.0,100.0),pat=(60.0,100.0),pbt=(10.0,20.0),eps=(6.0,10.0),fin=(12.0,10.0))
    )
    assert row["inflection_state"]=="NO_POSITIVE_INFLECTION"
    assert "REVENUE_CONTRACTION_10" in row["negative_flags"]
    assert "PROFIT_BREAKDOWN" in row["negative_flags"]


def _hg_inputs() -> tuple[dict,dict,dict,dict,dict]:
    symbols=[f"S{i:04d}" for i in range(2319)]
    ei_rows=[]
    ha_rows=[]
    gf_rows=[]
    inv_rows=[]
    for i,symbol in enumerate(symbols):
        state="STRONG_INFLECTION" if i in {0,1} else "NO_POSITIVE_INFLECTION"
        ei_rows.append({
            "symbol":symbol,
            "inflection_state":state,
            "positive_flags":["PAT_GROWTH_25"] if state!="NO_POSITIVE_INFLECTION" else [],
            "negative_flags":[],
            "metrics":{},
        })
        ha_rows.append({
            "symbol":symbol,
            "opportunity_flags":["LIQUID_ASSET_HEAVY"] if i in {0,2} else [],
            "caution_flags":[],
        })
        gf_rows.append({
            "symbol":symbol,
            "governance_state":"CORE_READY",
            "latest":{
                "promoter_percentage":50.0,
                "promoter_encumbrance":{
                    "pledge": i==0,
                    "non_disposal_undertaking":False,
                    "other_encumbrance":False,
                },
            },
            "ownership_delta_pp":{"promoter_percentage_points":0.0},
        })
        inv_rows.append({
            "symbol":symbol,
            "isin":f"ISIN-{symbol}",
            "in_existing_u001":False,
            "liquidity_band":"L3_2_TO_5CR",
            "median_daily_turnover_inr":30_000_000.0,
            "research_capacity_state":"RESEARCH_AND_CAPACITY_CONTEXT_AVAILABLE",
        })

    ei={
        "router_id":"EI001-S001-v1","rows":ei_rows,
        "return_outcomes_opened":False,"portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    ha={
        "panel_id":"HA001-D001-v1",
        "panel_sha256":"81651ebbac5a3102bb2dda9f2931dc10157583bfe2753cc610585811204f5bb3",
        "rows":ha_rows,"return_outcomes_opened":False,
        "portfolio_eligibility_allowed":False,"live_capital_allowed":False,
    }
    gf={
        "panel_id":"GF001-D002-v1",
        "panel_sha256":"dd338cd91f44396278300e27e8cdac1506dae11b63dd31ce827505fe62e8abe7",
        "rows":gf_rows,"return_outcomes_opened":False,
        "portfolio_eligibility_allowed":False,"live_capital_allowed":False,
    }
    inv={
        "context_id":"SS001-I001-v1",
        "context_sha256":"5f7cda9e8eb41954d5cb944b2fd06da9c888fe3513bd7d3acd294a33c93293d4",
        "rows":inv_rows,"return_outcomes_opened":False,
        "portfolio_eligibility_allowed":False,"live_capital_allowed":False,
    }
    special={
        "census_id":"SS002-D001-P2-v1",
        "census_sha256":"ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071",
        "events":[{
            "symbol":"S0001",
            "mapping_state":"CURRENT_INVESTABLE_IDENTITY",
            "special_situation_categories":["BUYBACK"],
        }],
        "return_outcomes_opened":False,"portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    return ei,ha,gf,inv,special


def test_hidden_gem_router_keeps_planes_independent() -> None:
    ei,ha,gf,inv,special=_hg_inputs()
    result=build_hidden_gem_router(
        ei=ei,ha=ha,gf=gf,investability=inv,special=special
    )
    rows={row["symbol"]:row for row in result["rows"]}
    assert rows["S0000"]["research_route"]=="CONVERGENT_DEEP_DIVE"
    assert rows["S0000"]["active_opportunity_lane_count"]==2
    assert "PROMOTER_PLEDGE_PRESENT" in rows["S0000"]["governance_caution_flags"]
    assert rows["S0001"]["research_route"]=="CONVERGENT_DEEP_DIVE"
    assert rows["S0001"]["special_situation_categories"]==["BUYBACK"]
    assert rows["S0002"]["research_route"]=="ASSET_ANOMALY_DEEP_DIVE"
    assert rows["S0003"]["research_route"]=="BACKLOG_NO_ACTIVE_LANE"
    assert result["portfolio_eligibility_allowed"] is False
