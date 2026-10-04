from __future__ import annotations

from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ei001_context_audit import AUDIT_FAMILIES

PANEL_ID="EI001-D002-v1"
EXPECTED_FA_PANEL_SHA="cb8a408b6904799750a5aa08210f909ae8b285005273b5588fb1f8b7a6019124"
EXPECTED_COUNT=2319


def build_comparable_from_fa_current(
    *,
    current_facts: dict[str,Any],
    prior: dict[str,Any],
)->dict[str,Any]:
    families={}
    prior_families=prior.get("families")
    if not isinstance(prior_families,dict):
        raise AlphaContractError("EI001 D002 prior families unavailable")
    for family in AUDIT_FAMILIES:
        current=current_facts.get(family)
        previous=prior_families.get(family)
        if not isinstance(current,dict) or not isinstance(previous,dict):
            families[family]={"status":"NOT_COMPARABLE","current_value":None,"prior_value":None,"unit_ref":None}
            continue
        ready=(
            current.get("status")=="READY"
            and previous.get("status")=="READY"
            and current.get("unit_ref")
            and current.get("unit_ref")==previous.get("unit_ref")
        )
        families[family]={
            "status":"COMPARABLE_READY" if ready else "NOT_COMPARABLE",
            "current_value":current.get("value") if ready else None,
            "prior_value":previous.get("value") if ready else None,
            "unit_ref":current.get("unit_ref") if ready else None,
            "current_concept":current.get("selected_concept"),
            "prior_concept":previous.get("selected_concept"),
        }
    return families


def build_full_comparative_panel(
    *,
    fa_panel:dict[str,Any],
    acquired_rows:list[dict[str,Any]],
    captured_at_utc:str,
)->dict[str,Any]:
    if fa_panel.get("panel_id")!="FA001-D002-v1":
        raise AlphaContractError("EI001 D002 requires FA001-D002")
    if fa_panel.get("panel_sha256")!=EXPECTED_FA_PANEL_SHA:
        raise AlphaContractError("EI001 D002 FA001 panel SHA mismatch")
    source_rows=fa_panel.get("rows")
    if not isinstance(source_rows,list) or len(source_rows)!=EXPECTED_COUNT:
        raise AlphaContractError("EI001 D002 FA001 rows unavailable")
    source={str(r.get("symbol") or "").upper():r for r in source_rows if isinstance(r,dict)}
    if len(source)!=EXPECTED_COUNT:
        raise AlphaContractError("EI001 D002 FA001 symbols not unique")
    acquired={str(r.get("symbol") or "").upper():r for r in acquired_rows if isinstance(r,dict)}
    if set(acquired)!=set(source):
        raise AlphaContractError("EI001 D002 identity accounting mismatch")

    rows=[]
    state_counts=Counter()
    family_ready=Counter()
    current_ready=0
    prior_candidate=0
    revenue_pat=0
    revenue_pat_pbt=0

    for symbol in sorted(source):
        base=source[symbol]
        row=acquired[symbol]
        quarter=base.get("quarter")
        if isinstance(quarter,dict) and quarter.get("status")=="READY":
            current_ready+=1
        if row.get("prior_candidate_available") is True:
            prior_candidate+=1
        state=str(row.get("status") or "UNKNOWN")
        state_counts[state]+=1
        comparable=row.get("comparable")
        ready_set=set()
        if state=="PAIR_READY":
            if not isinstance(comparable,dict):
                raise AlphaContractError(f"{symbol}: PAIR_READY lacks comparable map")
            ready_set={f for f in AUDIT_FAMILIES if isinstance(comparable.get(f),dict) and comparable[f].get("status")=="COMPARABLE_READY"}
            for f in ready_set: family_ready[f]+=1
            if {"revenue","pat"}.issubset(ready_set): revenue_pat+=1
            if {"revenue","pat","pbt"}.issubset(ready_set): revenue_pat_pbt+=1
        rows.append({
            "symbol":symbol,
            "isin":base.get("isin"),
            "company_name":base.get("company_name"),
            "in_existing_u001":bool(base.get("in_existing_u001")),
            "status":state,
            "reason":row.get("reason"),
            "current":row.get("current"),
            "prior":row.get("prior"),
            "comparable":comparable,
            "return_outcomes_opened":False,
            "portfolio_eligibility_allowed":False,
            "live_capital_allowed":False,
        })

    gates={
        "complete_identity_accounting":len(rows)==EXPECTED_COUNT,
        "minimum_current_q1_ready_80pct":current_ready/EXPECTED_COUNT>=0.80,
        "minimum_prior_q1_candidate_65pct":prior_candidate/EXPECTED_COUNT>=0.65,
        "minimum_comparable_revenue_pat_60pct":revenue_pat/EXPECTED_COUNT>=0.60,
        "minimum_comparable_revenue_pat_pbt_55pct":revenue_pat_pbt/EXPECTED_COUNT>=0.55,
    }
    out={
        "schema_version":1,
        "panel_id":PANEL_ID,
        "classification":"FULL_MARKET_SAME_QUARTER_COMPARATIVE_FACTS_NOT_ALPHA",
        "captured_at_utc":captured_at_utc,
        "source_fa001_panel_sha256":EXPECTED_FA_PANEL_SHA,
        "identity_count":EXPECTED_COUNT,
        "current_q1_ready_count":current_ready,
        "prior_q1_candidate_count":prior_candidate,
        "comparable_family_counts":dict(sorted(family_ready.items())),
        "comparable_revenue_pat_count":revenue_pat,
        "comparable_revenue_pat_pbt_count":revenue_pat_pbt,
        "source_state_counts":dict(sorted(state_counts.items())),
        "threshold_passes":gates,
        "feasibility_pass":all(gates.values()),
        "promotion_allowed_to_inflection_screen":all(gates.values()),
        "rows":rows,
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    out["panel_sha256"]=digest(out)
    return out
