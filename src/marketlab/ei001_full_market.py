from __future__ import annotations

from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.fa001_facts import EXPECTED_IDENTITY_COUNT, SHARD_COUNT, deterministic_shard

PANEL_ID="EI001-D002-v1"
EXPECTED_FA001_PANEL_SHA=(
    "cb8a408b6904799750a5aa08210f909ae8b285005273b5588fb1f8b7a6019124"
)
FAMILIES=("revenue","pat","pbt","finance_costs","depreciation","basic_eps")


def _ready_fact(value: object)->bool:
    return isinstance(value,dict) and value.get("status")=="READY"


def current_quarter_projection(row:dict[str,Any])->dict[str,Any] | None:
    quarter=row.get("quarter")
    if not isinstance(quarter,dict) or quarter.get("status")!="READY":
        return None
    parsed=quarter.get("parsed")
    candidate=quarter.get("candidate")
    if not isinstance(parsed,dict) or not isinstance(candidate,dict):
        return None
    facts=parsed.get("facts")
    if not isinstance(facts,dict):
        return None
    return {
        "symbol":row.get("symbol"),
        "accounting_basis":candidate.get("accounting_basis"),
        "period_end":candidate.get("period_end"),
        "source_url":candidate.get("source_url"),
        "exchange_published_at_utc":candidate.get("exchange_published_at_utc"),
        "raw_sha256":parsed.get("raw_sha256"),
        "families":{
            family:facts.get(family)
            for family in FAMILIES
        },
    }


def compare_current_prior(
    *,
    current:dict[str,Any],
    prior:dict[str,Any],
)->dict[str,Any]:
    if current.get("symbol")!=prior.get("symbol"):
        raise AlphaContractError("EI001 D002 current/prior symbol mismatch")
    if current.get("accounting_basis")!=prior.get("accounting_basis"):
        raise AlphaContractError("EI001 D002 current/prior basis mismatch")
    output={}
    for family in FAMILIES:
        cur=current["families"].get(family)
        prv=prior["families"].get(family)
        ready=(
            _ready_fact(cur)
            and _ready_fact(prv)
            and cur.get("unit_ref") not in (None,"")
            and cur.get("unit_ref")==prv.get("unit_ref")
        )
        output[family]={
            "status":"COMPARABLE_READY" if ready else "NOT_COMPARABLE",
            "unit_match":bool(ready),
            "current_value":cur.get("value") if ready else None,
            "prior_value":prv.get("value") if ready else None,
            "unit_ref":cur.get("unit_ref") if ready else None,
            "current_concept":cur.get("selected_concept") if isinstance(cur,dict) else None,
            "prior_concept":prv.get("selected_concept") if isinstance(prv,dict) else None,
        }
    return output


def validate_fa001_panel(panel:dict[str,Any])->list[dict[str,Any]]:
    if panel.get("panel_id")!="FA001-D002-v1":
        raise AlphaContractError("EI001 D002 requires FA001-D002-v1")
    if panel.get("panel_sha256")!=EXPECTED_FA001_PANEL_SHA:
        raise AlphaContractError("EI001 D002 FA001 panel SHA mismatch")
    if panel.get("identity_count")!=EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("EI001 D002 identity count mismatch")
    for field in (
        "return_outcomes_opened","model_fitted",
        "portfolio_eligibility_allowed","live_capital_allowed",
    ):
        if panel.get(field) is not False:
            raise AlphaContractError(f"EI001 D002 requires FA001 {field}=false")
    rows=panel.get("rows")
    if not isinstance(rows,list) or len(rows)!=EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("EI001 D002 FA001 rows unavailable")
    return rows


def build_full_comparative_panel(
    *,
    fa001_panel:dict[str,Any],
    shard_payloads:list[dict[str,Any]],
    captured_at_utc:str,
)->dict[str,Any]:
    source_rows=validate_fa001_panel(fa001_panel)
    expected={str(row["symbol"]).upper():row for row in source_rows if isinstance(row,dict)}
    if len(expected)!=EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("EI001 D002 source symbols are not unique")

    shard_indexes={
        int(payload.get("shard_index"))
        for payload in shard_payloads if isinstance(payload,dict)
    }
    if shard_indexes!=set(range(SHARD_COUNT)):
        raise AlphaContractError("EI001 D002 shard set is incomplete")

    merged={}
    for payload in shard_payloads:
        if payload.get("shard_count")!=SHARD_COUNT:
            raise AlphaContractError("EI001 D002 shard_count mismatch")
        if payload.get("source_fa001_panel_sha256")!=EXPECTED_FA001_PANEL_SHA:
            raise AlphaContractError("EI001 D002 shard source SHA mismatch")
        rows=payload.get("rows")
        if not isinstance(rows,list):
            raise TypeError("EI001 D002 shard rows must be a list")
        for row in rows:
            if not isinstance(row,dict):
                raise TypeError("EI001 D002 row must be an object")
            symbol=str(row.get("symbol") or "").upper()
            if symbol not in expected or symbol in merged:
                raise AlphaContractError("EI001 D002 merged identity mismatch")
            if deterministic_shard(symbol)!=int(payload["shard_index"]):
                raise AlphaContractError(f"{symbol}: wrong deterministic shard")
            merged[symbol]=row
    if set(merged)!=set(expected):
        raise AlphaContractError("EI001 D002 merged rows do not cover full market")

    states=Counter()
    family_ready=Counter()
    current_source=0
    prior_candidate=0
    pair_ready=0
    revenue_pat=0
    revenue_pat_pbt=0

    for symbol,row in merged.items():
        states[str(row.get("status") or "UNKNOWN")]+=1
        if row.get("current_source_available") is True:
            current_source+=1
        if row.get("prior_candidate_available") is True:
            prior_candidate+=1
        if row.get("status")!="PAIR_READY":
            continue
        pair_ready+=1
        comp=row.get("comparable")
        if not isinstance(comp,dict):
            raise AlphaContractError(f"{symbol}: PAIR_READY comparable map missing")
        ready={
            family for family in FAMILIES
            if isinstance(comp.get(family),dict)
            and comp[family].get("status")=="COMPARABLE_READY"
        }
        for family in ready:
            family_ready[family]+=1
        if {"revenue","pat"}.issubset(ready):
            revenue_pat+=1
        if {"revenue","pat","pbt"}.issubset(ready):
            revenue_pat_pbt+=1

    n=EXPECTED_IDENTITY_COUNT
    gates={
        "complete_identity_accounting":len(merged)==n,
        "minimum_current_q1_source_75pct":current_source/n>=0.75,
        "minimum_prior_q1_candidate_70pct":prior_candidate/n>=0.70,
        "minimum_comparable_revenue_pat_65pct":revenue_pat/n>=0.65,
        "minimum_comparable_revenue_pat_pbt_60pct":revenue_pat_pbt/n>=0.60,
    }
    output={
        "schema_version":1,
        "panel_id":PANEL_ID,
        "classification":"FULL_MARKET_SAME_QUARTER_COMPARATIVE_FACT_PLANE_NOT_ALPHA",
        "captured_at_utc":captured_at_utc,
        "source_fa001_panel_sha256":EXPECTED_FA001_PANEL_SHA,
        "identity_count":n,
        "current_q1_source_count":current_source,
        "current_q1_source_ratio":current_source/n,
        "prior_q1_candidate_count":prior_candidate,
        "prior_q1_candidate_ratio":prior_candidate/n,
        "pair_ready_count":pair_ready,
        "comparable_family_counts":dict(sorted(family_ready.items())),
        "comparable_revenue_pat_count":revenue_pat,
        "comparable_revenue_pat_ratio":revenue_pat/n,
        "comparable_revenue_pat_pbt_count":revenue_pat_pbt,
        "comparable_revenue_pat_pbt_ratio":revenue_pat_pbt/n,
        "source_state_counts":dict(sorted(states.items())),
        "threshold_passes":gates,
        "feasibility_pass":all(gates.values()),
        "promotion_allowed_to_inflection_screen":all(gates.values()),
        "rows":[merged[s] for s in sorted(merged)],
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    output["panel_sha256"]=digest(output)
    return output
