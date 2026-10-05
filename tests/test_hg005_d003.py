from __future__ import annotations

from marketlab.hg005_d003 import build_payoff_frameworks


def F(symbol,name,value,unit="X",date="2026-06-30"):
    return {
        "source_id":f"{symbol}-SRC-{name}",
        "symbol":symbol,
        "input_raw_sha256":"a"*64,
        "facts":[{
            "fact_id":f"{symbol}::{name}",
            "fact_name":name,
            "status":"EXPLICIT",
            "value":value,
            "unit":unit,
            "effective_or_reporting_date":date,
            "evidence_segment_ids":["s1"],
        }],
    }


def market():
    return {
        "context_id":"HG005-D001-v1",
        "context_sha256":"f8cb5079e266f451013d964b67b38dd833c7212bdffa4ffe23bd4fcef28fa48b",
        "price_session":"2026-10-01",
        "key_mechanical_context":{
            "ANANTRAJ":{"reported_fd_market_cap_inr_crore":20000.0},
            "DEVX":{"reported_fd_market_cap_inr_crore":400.0},
            "NPST":{"reported_fd_market_cap_inr_crore":4000.0},
            "SAMBHV":{
                "reported_fd_market_cap_inr_crore":5000.0,
                "lanes":{"DILUTION_FINANCING":{"event_adjusted_fd_shares":300_000_000}},
            },
        },
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }


def synthesis():
    facts=[]
    facts += [F("ANANTRAJ","demerged_business_fy26_revenue_inr_crore",150.0)]
    facts += [F("ANANTRAJ","operating_data_center_capacity_mw",30.0)]
    facts += [F("DEVX","winston_area_sqft",450000)]
    facts += [F("DEVX","security_deposit_required_inr_crore",35.1)]
    facts += [F("DEVX","security_deposit_utilized_inr_crore",23.75)]
    facts += [F("NPST","q1fy27_revenue_inr_crore",56.48)]
    facts += [F("NPST","q1fy27_ebitda_inr_crore",18.79)]
    facts += [F("NPST","raise_amount_inr_crore",300.0)]
    facts += [F("NPST","cumulative_deployed_inr_crore",35.64)]
    facts += [F("NPST","unutilized_proceeds_inr_crore",264.36)]
    facts += [F("SAMBHV","phase1_stainless_capacity_addition_mmtpa",0.36)]
    facts += [F("SAMBHV","phase1_capex_inr_million",8100.0)]
    facts += [F("SAMBHV","financing_stage_text","IN_PRINCIPLE_APPLICATION_FILED",date="2026-09-17")]
    return {
        "synthesis_id":"HG005-D002B-SYNTHESIS-v1",
        "synthesis_sha256":"beee365eb088e22b52e1827e0c1d6e2b68e842d36015c8ac988b8f5380f07287",
        "companies":{
            "ANANTRAJ":{"lanes":[{"lane":"DEMERGER_ENTITLEMENT","source_state":"SOURCE_READY"}]},
            "DEVX":{"lanes":[
                {"lane":"DILUTION_FINANCING","source_state":"SOURCE_READY"},
                {"lane":"CAPITAL_DEPLOYMENT_MONITOR","source_state":"SOURCE_READY"},
            ]},
            "NPST":{"lanes":[{"lane":"CAPITAL_DEPLOYMENT_MONITOR","source_state":"SOURCE_READY"}]},
            "SAMBHV":{"lanes":[{"lane":"DILUTION_FINANCING","source_state":"SOURCE_READY"}]},
            "INOXGREEN":{"lanes":[
                {"lane":"ACQUISITION_ECONOMICS","source_state":"SOURCE_PARTIAL"},
                {"lane":"DEMERGER_ENTITLEMENT","source_state":"SOURCE_PARTIAL"},
            ]},
        },
        "extractions":facts,
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }


def test_d003_builds_hurdles_without_expected_return():
    out=build_payoff_frameworks(
        market_context=market(),
        d002b_synthesis=synthesis(),
    )
    assert out["framework_id"]=="HG005-D003-v1"
    assert out["expected_returns_calculated"] is False
    assert out["completion_probabilities_assigned"] is False
    assert len(out["companies"]["DEVX"]["hurdles"])==9
    assert len(out["companies"]["NPST"]["hurdles"])==9
    assert len(out["companies"]["SAMBHV"]["surface"])==27
    assert out["companies"]["INOXGREEN"]["state"]=="PAYOFF_FRAMEWORK_BLOCKED_SOURCE_PARTIAL"


def test_sambhv_capex_conversion_is_deterministic():
    out=build_payoff_frameworks(
        market_context=market(),
        d002b_synthesis=synthesis(),
    )
    row=out["companies"]["SAMBHV"]
    assert row["phase1_capex_inr_crore_deterministic_conversion"]==810.0
    assert row["surface"][0]["conservative_net_incremental_equity_value_inr_crore"] < row["surface"][0]["gross_incremental_ev_inr_crore"]
