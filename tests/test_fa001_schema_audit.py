from __future__ import annotations

from datetime import UTC, datetime

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.fa001_schema_audit import (
    ANNUAL_PERIOD_END,
    QUARTER_PERIOD_END,
    FilingCandidate,
    build_schema_audit,
    parse_schema_inventory,
    select_audit_filings,
)


def _discovery_row(period: str, basis: str, published: str, url: str) -> dict:
    return {
        "type": "Integrated Filing- Financials",
        "symbol": "TEST",
        "consolidated": basis,
        "qe_Date": period,
        "broadcast_Date": published,
        "xbrl": url,
    }


def test_selector_prefers_consolidated_and_same_basis_quarter() -> None:
    payload = {
        "data": [
            _discovery_row(
                "31-Mar-2026",
                "Standalone",
                "20-Apr-2026 18:00:00",
                "https://nsearchives.nseindia.com/fy26sa.xml",
            ),
            _discovery_row(
                "31-Mar-2026",
                "Consolidated",
                "21-Apr-2026 18:00:00",
                "https://nsearchives.nseindia.com/fy26c.xml",
            ),
            _discovery_row(
                "30-Jun-2026",
                "Standalone",
                "20-Jul-2026 18:00:00",
                "https://nsearchives.nseindia.com/q1sa.xml",
            ),
            _discovery_row(
                "30-Jun-2026",
                "Consolidated",
                "21-Jul-2026 18:00:00",
                "https://nsearchives.nseindia.com/q1c.xml",
            ),
        ]
    }
    annual, quarter = select_audit_filings(payload, symbol="TEST")
    assert annual is not None
    assert quarter is not None
    assert annual.accounting_basis == "Consolidated"
    assert quarter.accounting_basis == "Consolidated"


def _xbrl(period_end: str, annual: bool) -> bytes:
    start = "2025-04-01" if annual else "2026-04-01"
    duration = "FY" if annual else "Q"
    instant = "I"
    facts = """
      <in:TotalAssets contextRef="I">1000</in:TotalAssets>
      <in:TotalEquity contextRef="I">600</in:TotalEquity>
      <in:CashAndCashEquivalents contextRef="I">100</in:CashAndCashEquivalents>
      <in:BorrowingsCurrent contextRef="I">50</in:BorrowingsCurrent>
      <in:BorrowingsNoncurrent contextRef="I">75</in:BorrowingsNoncurrent>
      <in:CurrentInvestments contextRef="I">80</in:CurrentInvestments>
      <in:PropertyPlantAndEquipment contextRef="I">300</in:PropertyPlantAndEquipment>
      <in:Goodwill contextRef="I">10</in:Goodwill>
      <in:NetCashFlowsFromUsedInOperatingActivities contextRef="FY">120</in:NetCashFlowsFromUsedInOperatingActivities>
      <in:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities contextRef="FY">20</in:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities>
    """ if annual else """
      <in:RevenueFromOperations contextRef="Q">500</in:RevenueFromOperations>
      <in:ProfitLossForPeriod contextRef="Q">50</in:ProfitLossForPeriod>
      <in:FinanceCosts contextRef="Q">5</in:FinanceCosts>
      <in:DepreciationDepletionAndAmortisationExpense contextRef="Q">10</in:DepreciationDepletionAndAmortisationExpense>
    """
    return f"""<?xml version="1.0"?>
<xbrli:xbrl
 xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:in="http://www.sebi.gov.in/xbrl">
 <xbrli:context id="{duration}">
  <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{period_end}</xbrli:endDate></xbrli:period>
 </xbrli:context>
 <xbrli:context id="{instant}">
  <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:instant>{period_end}</xbrli:instant></xbrli:period>
 </xbrli:context>
 <in:Symbol contextRef="{duration}">TEST</in:Symbol>
 {facts}
</xbrli:xbrl>
""".encode()


def _candidate(period: str, annual: bool) -> FilingCandidate:
    return FilingCandidate(
        symbol="TEST",
        accounting_basis="Consolidated",
        period_end=period,
        exchange_published_at_utc="2026-07-20T12:30:00Z",
        source_url=(
            "https://nsearchives.nseindia.com/annual.xml"
            if annual
            else "https://nsearchives.nseindia.com/q1.xml"
        ),
        discovery_row_sha256="a" * 64,
    )


def test_annual_schema_inventory_resolves_core_asset_families() -> None:
    audit = parse_schema_inventory(
        _xbrl(ANNUAL_PERIOD_END, True),
        candidate=_candidate(ANNUAL_PERIOD_END, True),
    )
    families = audit["family_status"]
    assert families["total_assets"]["ready"] is True
    assert families["total_equity"]["ready"] is True
    assert families["cash"]["ready"] is True
    assert families["borrowings_current"]["ready"] is True
    assert families["borrowings_noncurrent"]["ready"] is True
    assert families["current_investments"]["ready"] is True
    assert audit["context_counts"]["annual"] == 1
    assert audit["context_counts"]["instant"] == 1


def test_quarter_schema_inventory_resolves_revenue_and_pat() -> None:
    audit = parse_schema_inventory(
        _xbrl(QUARTER_PERIOD_END, False),
        candidate=_candidate(QUARTER_PERIOD_END, False),
    )
    assert audit["family_status"]["revenue"]["ready"] is True
    assert audit["family_status"]["pat"]["ready"] is True
    assert audit["context_counts"]["quarter"] == 1


def _ready_observation(symbol: str) -> dict:
    annual_families = {
        key: {"ready": True}
        for key in (
            "total_assets",
            "total_equity",
            "cash",
            "borrowings_current",
            "borrowings_noncurrent",
            "current_investments",
        )
    }
    quarter_families = {
        "revenue": {"ready": True},
        "pat": {"ready": True},
    }
    return {
        "symbol": symbol,
        "annual": {
            "status": "READY",
            "audit": {
                "family_status": annual_families,
                "keyword_concepts": [],
            },
        },
        "quarter": {
            "status": "READY",
            "audit": {
                "family_status": quarter_families,
                "keyword_concepts": [],
            },
        },
    }


def test_full_audit_gates_pass_with_complete_sample() -> None:
    sample = {
        "symbols": [{"symbol": f"S{i:02d}"} for i in range(48)]
    }
    observations = [_ready_observation(f"S{i:02d}") for i in range(48)]
    result = build_schema_audit(
        sample=sample,
        observations=observations,
        captured_at_utc=datetime.now(UTC).isoformat(),
    )
    assert result["annual_ready_count"] == 48
    assert result["quarter_ready_count"] == 48
    assert result["feasibility_pass"] is True
    assert result["portfolio_eligibility_allowed"] is False


def test_full_audit_rejects_missing_sample_identity() -> None:
    sample = {"symbols": [{"symbol": f"S{i:02d}"} for i in range(48)]}
    observations = [_ready_observation(f"S{i:02d}") for i in range(47)]
    with pytest.raises(AlphaContractError, match="do not cover frozen sample"):
        build_schema_audit(
            sample=sample,
            observations=observations,
            captured_at_utc=datetime.now(UTC).isoformat(),
        )
