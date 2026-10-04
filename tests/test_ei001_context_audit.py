from __future__ import annotations

from marketlab.ei001_context_audit import (
    build_context_audit,
    parse_comparative_quarter,
)
from marketlab.fa001_schema_audit import FilingCandidate


def _candidate() -> FilingCandidate:
    return FilingCandidate(
        symbol="TEST",
        accounting_basis="Consolidated",
        period_end="2026-06-30",
        exchange_published_at_utc="2026-07-30T12:00:00+00:00",
        source_url="https://nsearchives.nseindia.com/corporate/xbrl/test.xml",
        discovery_row_sha256="a"*64,
    )


def _xml(*, prior_unit: str = "INR", dimensional_prior: bool = False) -> bytes:
    segment = (
        '<xbrli:scenario><xbrldi:explicitMember '
        'dimension="in-capmkt:SomeAxis">in-capmkt:SomeMember'
        '</xbrldi:explicitMember></xbrli:scenario>'
        if dimensional_prior
        else ""
    )
    return f'''<?xml version="1.0"?>
<xbrli:xbrl
 xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
 xmlns:in-capmkt="http://www.sebi.gov.in/xbrl">
 <xbrli:context id="CUR">
  <xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period>
 </xbrli:context>
 <xbrli:context id="PY">
  <xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity>
  {segment}
  <xbrli:period><xbrli:startDate>2025-04-01</xbrli:startDate><xbrli:endDate>2025-06-30</xbrli:endDate></xbrli:period>
 </xbrli:context>
 <in-capmkt:RevenueFromOperations contextRef="CUR" unitRef="INR">120</in-capmkt:RevenueFromOperations>
 <in-capmkt:RevenueFromOperations contextRef="PY" unitRef="{prior_unit}">100</in-capmkt:RevenueFromOperations>
 <in-capmkt:ProfitLossForPeriod contextRef="CUR" unitRef="INR">18</in-capmkt:ProfitLossForPeriod>
 <in-capmkt:ProfitLossForPeriod contextRef="PY" unitRef="{prior_unit}">10</in-capmkt:ProfitLossForPeriod>
 <in-capmkt:ProfitBeforeTax contextRef="CUR" unitRef="INR">24</in-capmkt:ProfitBeforeTax>
 <in-capmkt:ProfitBeforeTax contextRef="PY" unitRef="{prior_unit}">14</in-capmkt:ProfitBeforeTax>
</xbrli:xbrl>'''.encode()


def test_comparative_parser_resolves_explicit_same_quarter_facts() -> None:
    parsed=parse_comparative_quarter(_xml(),candidate=_candidate())
    assert parsed["current_context_count"]==1
    assert parsed["prior_year_context_count"]==1
    assert parsed["periods"]["current"]["revenue"]["value"]==120
    assert parsed["periods"]["prior_year"]["revenue"]["value"]==100
    assert parsed["comparable"]["revenue"]["status"]=="COMPARABLE_READY"
    assert parsed["comparable"]["pat"]["status"]=="COMPARABLE_READY"


def test_unit_mismatch_fails_comparable_state() -> None:
    parsed=parse_comparative_quarter(_xml(prior_unit="USD"),candidate=_candidate())
    assert parsed["comparable"]["revenue"]["status"]=="NOT_COMPARABLE"
    assert parsed["comparable"]["revenue"]["unit_match"] is False


def test_dimensional_prior_context_is_not_used() -> None:
    parsed=parse_comparative_quarter(
        _xml(dimensional_prior=True),
        candidate=_candidate(),
    )
    assert parsed["prior_year_context_count"]==0
    assert parsed["comparable"]["revenue"]["status"]=="NOT_COMPARABLE"


def _sample() -> dict:
    return {
        "symbols":[{"symbol":f"S{idx:02d}"} for idx in range(48)]
    }


def test_audit_gates_are_based_only_on_ready_comparables() -> None:
    observations=[]
    for idx in range(48):
        parsed={
            "comparable":{
                family:{"status":"COMPARABLE_READY","unit_match":True}
                for family in (
                    "revenue","pat","pbt","finance_costs","depreciation","basic_eps"
                )
            }
        }
        observations.append({"symbol":f"S{idx:02d}","status":"READY","parsed":parsed})
    audit=build_context_audit(
        sample=_sample(),
        observations=observations,
        captured_at_utc="2026-10-04T16:00:00Z",
    )
    assert audit["feasibility_pass"] is True
    assert audit["comparable_revenue_pat_count"]==48
    assert audit["portfolio_eligibility_allowed"] is False
