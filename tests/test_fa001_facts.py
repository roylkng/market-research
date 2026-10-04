from __future__ import annotations

from marketlab.fa001_facts import (
    EXPECTED_SS001_CENSUS_SHA,
    SHARD_COUNT,
    build_full_fact_panel,
    deterministic_shard,
    parse_filing_facts,
)
from marketlab.fa001_schema_audit import FilingCandidate


def _candidate(period: str) -> FilingCandidate:
    return FilingCandidate(
        symbol="TEST",
        accounting_basis="Consolidated",
        period_end=period,
        exchange_published_at_utc="2026-07-20T12:00:00Z",
        source_url="https://nsearchives.nseindia.com/test.xml",
        discovery_row_sha256="a" * 64,
    )


def _annual_xml(*, conflicting_borrowing: bool = False) -> bytes:
    extra_context = """
    <xbrli:context id="I2">
      <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:instant>2026-03-31</xbrli:instant></xbrli:period>
    </xbrli:context>
    """ if conflicting_borrowing else ""
    conflict_fact = (
        '<in:BorrowingsCurrent contextRef="I2" unitRef="INR">51</in:BorrowingsCurrent>'
        if conflicting_borrowing else ""
    )
    return f"""<?xml version="1.0"?>
<xbrli:xbrl
 xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:in="http://www.sebi.gov.in/xbrl">
 <xbrli:context id="FY">
  <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>2025-04-01</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period>
 </xbrli:context>
 <xbrli:context id="I">
  <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:instant>2026-03-31</xbrli:instant></xbrli:period>
 </xbrli:context>
 {extra_context}
 <in:Symbol contextRef="FY">TEST</in:Symbol>
 <in:TotalAssets contextRef="I" unitRef="INR">1000</in:TotalAssets>
 <in:TotalEquity contextRef="I" unitRef="INR">600</in:TotalEquity>
 <in:CashAndCashEquivalents contextRef="I" unitRef="INR">100</in:CashAndCashEquivalents>
 <in:BorrowingsCurrent contextRef="I" unitRef="INR">50</in:BorrowingsCurrent>
 {conflict_fact}
 <in:BorrowingsNoncurrent contextRef="I" unitRef="INR">75</in:BorrowingsNoncurrent>
 <in:CurrentInvestments contextRef="I" unitRef="INR">80</in:CurrentInvestments>
 <in:NetCashFlowsFromUsedInOperatingActivities contextRef="FY" unitRef="INR">120</in:NetCashFlowsFromUsedInOperatingActivities>
</xbrli:xbrl>
""".encode()


def _quarter_xml() -> bytes:
    return b"""<?xml version="1.0"?>
<xbrli:xbrl
 xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:in="http://www.sebi.gov.in/xbrl">
 <xbrli:context id="Q">
  <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period>
 </xbrli:context>
 <in:Symbol contextRef="Q">TEST</in:Symbol>
 <in:RevenueFromOperations contextRef="Q" unitRef="INR">500</in:RevenueFromOperations>
 <in:ProfitLossForPeriod contextRef="Q" unitRef="INR">50</in:ProfitLossForPeriod>
 <in:FinanceCosts contextRef="Q" unitRef="INR">5</in:FinanceCosts>
</xbrli:xbrl>
"""


def test_annual_fact_parser_resolves_frozen_contexts() -> None:
    parsed = parse_filing_facts(
        _annual_xml(),
        candidate=_candidate("2026-03-31"),
        filing_kind="ANNUAL",
    )
    assert parsed["facts"]["total_assets"]["status"] == "READY"
    assert parsed["facts"]["total_assets"]["value"] == 1000
    assert parsed["facts"]["total_assets"]["unit_ref"] == "INR"
    assert parsed["facts"]["operating_cash_flow"]["status"] == "READY"


def test_conflicting_same_period_fact_fails_closed_as_ambiguous() -> None:
    parsed = parse_filing_facts(
        _annual_xml(conflicting_borrowing=True),
        candidate=_candidate("2026-03-31"),
        filing_kind="ANNUAL",
    )
    borrowing = parsed["facts"]["borrowings_current"]
    assert borrowing["status"] == "AMBIGUOUS"
    assert borrowing["value"] is None
    assert borrowing["selected_concept"] == "BorrowingsCurrent"


def test_quarter_parser_resolves_revenue_and_pat() -> None:
    parsed = parse_filing_facts(
        _quarter_xml(),
        candidate=_candidate("2026-06-30"),
        filing_kind="QUARTER",
    )
    assert parsed["facts"]["revenue"]["status"] == "READY"
    assert parsed["facts"]["pat"]["status"] == "READY"
    assert parsed["context_summary"]["quarter_duration_context_count"] == 1


def test_shard_assignment_is_bounded_and_deterministic() -> None:
    first = deterministic_shard("COFORGE")
    assert 0 <= first < SHARD_COUNT
    assert deterministic_shard("COFORGE") == first


def _ready_fact(value: float = 1.0) -> dict:
    return {
        "status": "READY",
        "value": value,
        "selected_concept": "X",
        "unit_ref": "INR",
        "matching_fact_count": 1,
        "context_refs": ["I"],
    }


def _ready_row(symbol: str, isin: str) -> dict:
    annual_facts = {
        "total_assets": _ready_fact(100),
        "total_equity": _ready_fact(60),
        "cash": _ready_fact(20),
        "borrowings_current": _ready_fact(5),
        "borrowings_noncurrent": _ready_fact(10),
        "current_investments": _ready_fact(8),
        "noncurrent_investments": {
            "status": "MISSING",
            "value": None,
            "selected_concept": None,
            "unit_ref": None,
            "matching_fact_count": 0,
            "context_refs": [],
        },
    }
    quarter_facts = {
        "revenue": _ready_fact(50),
        "pat": _ready_fact(5),
    }
    return {
        "symbol": symbol,
        "isin": isin,
        "annual": {
            "status": "READY",
            "candidate": {"source_url": "https://nsearchives.nseindia.com/a.xml"},
            "parsed": {"raw_sha256": "a" * 64, "facts": annual_facts},
        },
        "quarter": {
            "status": "READY",
            "candidate": {"source_url": "https://nsearchives.nseindia.com/q.xml"},
            "parsed": {"raw_sha256": "b" * 64, "facts": quarter_facts},
        },
    }


def test_full_panel_requires_and_accepts_exact_six_shard_accounting() -> None:
    census_rows = [
        {"symbol": f"S{i:04d}", "isin": f"INE{i:09d}", "company_name": f"C{i}"}
        for i in range(2319)
    ]
    census = {
        "census_id": "SS001-D001-v1",
        "census_sha256": EXPECTED_SS001_CENSUS_SHA,
        "eq_identity_count": 2319,
        "rows": census_rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    grouped = {index: [] for index in range(SHARD_COUNT)}
    for row in census_rows:
        grouped[deterministic_shard(row["symbol"])].append(
            _ready_row(row["symbol"], row["isin"])
        )
    shards = [
        {
            "shard_index": index,
            "shard_count": SHARD_COUNT,
            "source_census_sha256": EXPECTED_SS001_CENSUS_SHA,
            "rows": grouped[index],
        }
        for index in range(SHARD_COUNT)
    ]
    panel = build_full_fact_panel(
        d001_census=census,
        shard_payloads=shards,
        captured_at_utc="2026-10-04T00:00:00Z",
    )
    assert panel["identity_count"] == 2319
    assert panel["annual_core_assets_ready_count"] == 2319
    assert panel["borrowings_ready_count"] == 2319
    assert panel["investments_ready_count"] == 2319
    assert panel["quarter_revenue_pat_ready_count"] == 2319
    assert panel["feasibility_pass"] is True
    assert panel["portfolio_eligibility_allowed"] is False
