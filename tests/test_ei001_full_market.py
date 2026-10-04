from __future__ import annotations

from marketlab.ei001_full_market import build_comparable_from_fa_current


def _fact(value,unit="INR",status="READY"):
    return {"status":status,"value":value,"unit_ref":unit,"selected_concept":"X"}


def test_comparable_requires_ready_and_exact_unit_match():
    current={f:_fact(10.0) for f in ("revenue","pat","pbt","finance_costs","depreciation")}
    current["basic_eps"]=_fact(2.0,"INRPerShare")
    prior={"families":{f:_fact(5.0) for f in ("revenue","pat","pbt","finance_costs","depreciation")}}
    prior["families"]["basic_eps"]=_fact(1.0,"INRPerShare")
    result=build_comparable_from_fa_current(current_facts=current,prior=prior)
    assert result["revenue"]["status"]=="COMPARABLE_READY"
    assert result["revenue"]["current_value"]==10.0
    assert result["revenue"]["prior_value"]==5.0
    assert result["basic_eps"]["unit_ref"]=="INRPerShare"


def test_unit_mismatch_fails_closed():
    current={"revenue":_fact(10.0,"INR")}
    prior={"families":{"revenue":_fact(1.0,"USD")}}
    result=build_comparable_from_fa_current(current_facts=current,prior=prior)
    assert result["revenue"]["status"]=="NOT_COMPARABLE"
    assert result["revenue"]["current_value"] is None
