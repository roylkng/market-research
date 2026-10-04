from __future__ import annotations

import math
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest

PANEL_ID="HA001-D001-v1"
EXPECTED_FA_SHA="cb8a408b6904799750a5aa08210f909ae8b285005273b5588fb1f8b7a6019124"
EXPECTED_COUNT=2319

OPPORTUNITY_FLAGS=(
    "LIQUID_ASSET_HEAVY",
    "INVESTMENT_HOLDING_HEAVY",
    "INVESTMENT_PROPERTY_MATERIAL",
    "CWIP_CAPACITY_INFLECTION",
)
CAUTION_FLAGS=(
    "INTANGIBLE_HEAVY_CAUTION",
    "WORKING_CAPITAL_HEAVY_CAUTION",
)


def _ready_inr(facts:dict[str,Any],name:str)->float|None:
    row=facts.get(name)
    if not isinstance(row,dict) or row.get("status")!="READY" or row.get("unit_ref")!="INR":
        return None
    value=row.get("value")
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        return None
    value=float(value)
    return value if math.isfinite(value) else None


def _ratio(n:float|None,d:float|None)->float|None:
    if n is None or d is None or d<=0: return None
    value=n/d
    return value if math.isfinite(value) else None


def derive_asset_anomalies(facts:dict[str,Any])->dict[str,Any]:
    equity=_ready_inr(facts,"total_equity")
    assets=_ready_inr(facts,"total_assets")
    cash=_ready_inr(facts,"cash")
    ci=_ready_inr(facts,"current_investments")
    ni=_ready_inr(facts,"noncurrent_investments")
    bc=_ready_inr(facts,"borrowings_current")
    bn=_ready_inr(facts,"borrowings_noncurrent")
    prop=_ready_inr(facts,"investment_property")
    ppe=_ready_inr(facts,"ppe")
    cwip=_ready_inr(facts,"capital_work_in_progress")
    goodwill=_ready_inr(facts,"goodwill")
    intang=_ready_inr(facts,"other_intangibles")
    inv=_ready_inr(facts,"inventories")
    recv=_ready_inr(facts,"trade_receivables")

    investments=None if ci is None or ni is None else ci+ni
    borrowings=None if bc is None or bn is None else bc+bn
    nfa=None if cash is None or investments is None or borrowings is None else cash+investments-borrowings
    tangible=None if equity is None or goodwill is None or intang is None else equity-goodwill-intang
    wc=None if inv is None or recv is None else inv+recv

    ratios={
        "net_financial_assets_to_equity":_ratio(nfa,equity),
        "investments_to_assets":_ratio(investments,assets),
        "investment_property_to_equity":_ratio(prop,equity),
        "cwip_to_ppe":_ratio(cwip,ppe),
        "intangibles_to_equity":_ratio(None if goodwill is None or intang is None else goodwill+intang,equity),
        "working_capital_assets_to_assets":_ratio(wc,assets),
        "tangible_equity_to_equity":_ratio(tangible,equity),
    }
    opportunity=[]
    if ratios["net_financial_assets_to_equity"] is not None and ratios["net_financial_assets_to_equity"]>=0.50: opportunity.append("LIQUID_ASSET_HEAVY")
    if ratios["investments_to_assets"] is not None and ratios["investments_to_assets"]>=0.20: opportunity.append("INVESTMENT_HOLDING_HEAVY")
    if ratios["investment_property_to_equity"] is not None and ratios["investment_property_to_equity"]>=0.10: opportunity.append("INVESTMENT_PROPERTY_MATERIAL")
    if ratios["cwip_to_ppe"] is not None and ratios["cwip_to_ppe"]>=0.25: opportunity.append("CWIP_CAPACITY_INFLECTION")
    caution=[]
    if ratios["intangibles_to_equity"] is not None and ratios["intangibles_to_equity"]>=0.50: caution.append("INTANGIBLE_HEAVY_CAUTION")
    if ratios["working_capital_assets_to_assets"] is not None and ratios["working_capital_assets_to_assets"]>=0.40: caution.append("WORKING_CAPITAL_HEAVY_CAUTION")

    return {
        "derived_values":{
            "investments":investments,
            "borrowings":borrowings,
            "net_financial_assets":nfa,
            "tangible_equity":tangible,
            "working_capital_assets":wc,
        },
        "ratios":ratios,
        "opportunity_flags":opportunity,
        "caution_flags":caution,
        "business_model_context_required":True,
    }


def build_asset_anomaly_panel(fa_panel:dict[str,Any])->dict[str,Any]:
    if fa_panel.get("panel_id")!="FA001-D002-v1" or fa_panel.get("panel_sha256")!=EXPECTED_FA_SHA:
        raise AlphaContractError("HA001 requires frozen FA001-D002 panel")
    rows=fa_panel.get("rows")
    if not isinstance(rows,list) or len(rows)!=EXPECTED_COUNT:
        raise AlphaContractError("HA001 FA rows unavailable")
    output=[]
    opp=Counter(); caution=Counter()
    nfa_ready=invest_ready=cwip_ready=0
    for base in rows:
        if not isinstance(base,dict): raise TypeError("HA001 FA rows must be objects")
        symbol=str(base.get("symbol") or "").upper()
        annual=base.get("annual")
        facts={}
        if isinstance(annual,dict) and annual.get("status")=="READY":
            parsed=annual.get("parsed")
            if isinstance(parsed,dict) and isinstance(parsed.get("facts"),dict):
                facts=parsed["facts"]
        derived=derive_asset_anomalies(facts)
        if derived["ratios"]["net_financial_assets_to_equity"] is not None: nfa_ready+=1
        if derived["ratios"]["investments_to_assets"] is not None: invest_ready+=1
        if derived["ratios"]["cwip_to_ppe"] is not None: cwip_ready+=1
        for x in derived["opportunity_flags"]: opp[x]+=1
        for x in derived["caution_flags"]: caution[x]+=1
        output.append({
            "symbol":symbol,
            "isin":base.get("isin"),
            "company_name":base.get("company_name"),
            "in_existing_u001":bool(base.get("in_existing_u001")),
            **derived,
            "return_outcomes_opened":False,
            "portfolio_eligibility_allowed":False,
            "live_capital_allowed":False,
        })
    gates={
        "complete_identity_accounting":len(output)==EXPECTED_COUNT,
        "minimum_nfa_equity_coverage_60pct":nfa_ready/EXPECTED_COUNT>=0.60,
        "minimum_investments_assets_coverage_60pct":invest_ready/EXPECTED_COUNT>=0.60,
        "minimum_cwip_ppe_coverage_50pct":cwip_ready/EXPECTED_COUNT>=0.50,
    }
    out={
        "schema_version":1,
        "panel_id":PANEL_ID,
        "classification":"FULL_MARKET_ASSET_ANOMALY_ROUTING_NOT_VALUATION",
        "source_fa001_panel_sha256":EXPECTED_FA_SHA,
        "identity_count":EXPECTED_COUNT,
        "net_financial_assets_to_equity_ready_count":nfa_ready,
        "investments_to_assets_ready_count":invest_ready,
        "cwip_to_ppe_ready_count":cwip_ready,
        "opportunity_flag_counts":dict(sorted(opp.items())),
        "caution_flag_counts":dict(sorted(caution.items())),
        "any_opportunity_flag_count":sum(bool(r["opportunity_flags"]) for r in output),
        "threshold_passes":gates,
        "feasibility_pass":all(gates.values()),
        "promotion_allowed_to_deep_research_routing":all(gates.values()),
        "rows":sorted(output,key=lambda r:r["symbol"]),
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    out["panel_sha256"]=digest(out)
    return out
