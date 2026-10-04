from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from marketlab.alpha_fundamental import FilingCandidate, FundamentalPair
from marketlab.fundamental_quality import (
    CORE_METRICS,
    AnnualQualityFacts,
    build_quality_metrics,
    issuer_identity_continuity,
    parse_annual_quality_filing,
    quality_record,
    validate_annual_shape,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "fixtures"
    / "filings"
    / "infy_fy26_annual_quality_source_derived.html"
)


def _candidate(
    *,
    period: str = "2026-03-31",
    url: str = "https://nsearchives.nseindia.com/test.html",
) -> FilingCandidate:
    return FilingCandidate(
        symbol="INFY",
        accounting_basis="Consolidated",
        period_end=period,
        exchange_published_at_utc="2026-04-23T15:31:54Z",
        source_url=url,
        discovery_row_sha256="a" * 64,
        discovery_row={},
    )


def _facts(
    *,
    period: str,
    revenue: float,
    pbt: float,
    finance: float,
    pat: float,
    assets: float,
    equity: float,
    current_liabilities: float,
    cash: float,
    borrowings_current: float,
    borrowings_noncurrent: float,
    cfo: float,
    ppe: float,
) -> AnnualQualityFacts:
    start = "2025-04-01" if period == "2026-03-31" else "2024-04-01"
    return AnnualQualityFacts(
        parser_version="test",
        symbol="INFY",
        isin="INE009A01021",
        company_name="Infosys Limited",
        accounting_basis="Consolidated",
        financial_year_start=start,
        period_end=period,
        currency="INR",
        rounding="Lakhs",
        raw_sha256="b" * 64,
        source_url="https://x/test",
        facts={
            "revenue": revenue,
            "profit_before_tax": pbt,
            "finance_costs": finance,
            "profit_after_tax": pat,
            "total_assets": assets,
            "total_equity": equity,
            "current_liabilities": current_liabilities,
            "cash_and_cash_equivalents": cash,
            "borrowings_current": borrowings_current,
            "borrowings_noncurrent": borrowings_noncurrent,
            "operating_cash_flow": cfo,
            "purchase_ppe": ppe,
        },
    )


def test_source_derived_html_parses_annual_quality_facts() -> None:
    parsed = parse_annual_quality_filing(
        FIXTURE.read_bytes(),
        candidate=_candidate(),
    )
    validate_annual_shape(parsed)

    assert parsed.symbol == "INFY"
    assert parsed.period_end == "2026-03-31"
    assert parsed.facts["revenue"] == pytest.approx(1_786_500_000_000.0)
    assert parsed.facts["profit_after_tax"] == pytest.approx(294_740_000_000.0)
    assert parsed.facts["total_assets"] == pytest.approx(1_559_670_000_000.0)
    assert parsed.facts["operating_cash_flow"] == pytest.approx(339_860_000_000.0)
    assert parsed.facts["purchase_ppe"] == pytest.approx(27_270_000_000.0)


def test_xbrl_parser_uses_annual_duration_and_year_end_instant_contexts() -> None:
    xml = """<?xml version="1.0"?>
    <xbrli:xbrl
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:in-capmkt="http://www.sebi.gov.in/xbrl/2025-01-31/in-capmkt">
      <xbrli:context id="Q">
        <xbrli:entity><xbrli:identifier scheme="test">500209</xbrli:identifier></xbrli:entity>
        <xbrli:period>
          <xbrli:startDate>2026-01-01</xbrli:startDate>
          <xbrli:endDate>2026-03-31</xbrli:endDate>
        </xbrli:period>
      </xbrli:context>
      <xbrli:context id="FY">
        <xbrli:entity><xbrli:identifier scheme="test">500209</xbrli:identifier></xbrli:entity>
        <xbrli:period>
          <xbrli:startDate>2025-04-01</xbrli:startDate>
          <xbrli:endDate>2026-03-31</xbrli:endDate>
        </xbrli:period>
      </xbrli:context>
      <xbrli:context id="I">
        <xbrli:entity><xbrli:identifier scheme="test">500209</xbrli:identifier></xbrli:entity>
        <xbrli:period><xbrli:instant>2026-03-31</xbrli:instant></xbrli:period>
      </xbrli:context>
      <in-capmkt:Symbol contextRef="Q">INFY</in-capmkt:Symbol>
      <in-capmkt:ISIN contextRef="Q">INE009A01021</in-capmkt:ISIN>
      <in-capmkt:NameOfTheCompany contextRef="Q">INFOSYS LIMITED</in-capmkt:NameOfTheCompany>
      <in-capmkt:DateOfStartOfFinancialYear contextRef="Q">2025-04-01</in-capmkt:DateOfStartOfFinancialYear>
      <in-capmkt:DateOfEndOfFinancialYear contextRef="Q">2026-03-31</in-capmkt:DateOfEndOfFinancialYear>
      <in-capmkt:NatureOfReportStandaloneConsolidated contextRef="Q">Consolidated</in-capmkt:NatureOfReportStandaloneConsolidated>
      <in-capmkt:DescriptionOfPresentationCurrency contextRef="Q">INR</in-capmkt:DescriptionOfPresentationCurrency>
      <in-capmkt:RevenueFromOperations contextRef="Q">40</in-capmkt:RevenueFromOperations>
      <in-capmkt:RevenueFromOperations contextRef="FY">180</in-capmkt:RevenueFromOperations>
      <in-capmkt:ProfitBeforeTax contextRef="FY">40</in-capmkt:ProfitBeforeTax>
      <in-capmkt:FinanceCosts contextRef="FY">2</in-capmkt:FinanceCosts>
      <in-capmkt:ProfitLossForPeriod contextRef="FY">30</in-capmkt:ProfitLossForPeriod>
      <in-capmkt:TotalAssets contextRef="I">160</in-capmkt:TotalAssets>
      <in-capmkt:TotalEquity contextRef="I">95</in-capmkt:TotalEquity>
      <in-capmkt:TotalCurrentLiabilities contextRef="I">50</in-capmkt:TotalCurrentLiabilities>
      <in-capmkt:CashAndCashEquivalents contextRef="I">20</in-capmkt:CashAndCashEquivalents>
      <in-capmkt:CashAndCashEquivalentsCashFlowStatement contextRef="I">999</in-capmkt:CashAndCashEquivalentsCashFlowStatement>
      <in-capmkt:BorrowingsCurrent contextRef="I">4</in-capmkt:BorrowingsCurrent>
      <in-capmkt:BorrowingsNoncurrent contextRef="I">6</in-capmkt:BorrowingsNoncurrent>
      <in-capmkt:NetCashFlowsFromUsedInOperatingActivities contextRef="FY">35</in-capmkt:NetCashFlowsFromUsedInOperatingActivities>
      <in-capmkt:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities contextRef="FY">3</in-capmkt:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities>
    </xbrli:xbrl>
    """
    parsed = parse_annual_quality_filing(
        xml.encode(),
        candidate=_candidate(url="https://x/test.xml"),
    )

    assert parsed.facts["revenue"] == 180
    assert parsed.facts["total_assets"] == 160
    assert parsed.facts["cash_and_cash_equivalents"] == 20
    assert parsed.facts["operating_cash_flow"] == 35
    assert parsed.facts["purchase_ppe"] == 3




def test_identity_continuity_accepts_same_isin_symbol_rename() -> None:
    target = _facts(
        period="2026-03-31",
        revenue=200.0,
        pbt=30.0,
        finance=5.0,
        pat=24.0,
        assets=180.0,
        equity=100.0,
        current_liabilities=60.0,
        cash=15.0,
        borrowings_current=10.0,
        borrowings_noncurrent=20.0,
        cfo=30.0,
        ppe=6.0,
    )
    baseline = replace(
        target,
        symbol="LTIM",
        period_end="2025-03-31",
        financial_year_start="2024-04-01",
    )
    assert issuer_identity_continuity(target, baseline) == "SAME_ISIN"


def test_identity_continuity_accepts_same_symbol_isin_replacement() -> None:
    target = _facts(
        period="2026-03-31",
        revenue=200.0,
        pbt=30.0,
        finance=5.0,
        pat=24.0,
        assets=180.0,
        equity=100.0,
        current_liabilities=60.0,
        cash=15.0,
        borrowings_current=10.0,
        borrowings_noncurrent=20.0,
        cfo=30.0,
        ppe=6.0,
    )
    target = replace(target, symbol="COFORGE", isin="INE591G01025")
    baseline = replace(
        target,
        isin="INE591G01017",
        period_end="2025-03-31",
        financial_year_start="2024-04-01",
    )
    assert issuer_identity_continuity(target, baseline) == "SAME_NORMALIZED_SYMBOL"


def test_parser_accepts_symbol_format_change_when_expected_isin_matches() -> None:
    document = FIXTURE.read_text(encoding="utf-8").replace(
        "<td>INFY</td>",
        "<td>INF-Y</td>",
        1,
    )
    parsed = parse_annual_quality_filing(
        document.encode(),
        candidate=_candidate(),
        expected_isin="INE009A01021",
    )
    assert parsed.symbol == "INF-Y"
    assert parsed.isin == "INE009A01021"


def test_quality_metrics_match_frozen_formulas() -> None:
    target = _facts(
        period="2026-03-31",
        revenue=200.0,
        pbt=30.0,
        finance=5.0,
        pat=24.0,
        assets=180.0,
        equity=100.0,
        current_liabilities=60.0,
        cash=15.0,
        borrowings_current=10.0,
        borrowings_noncurrent=20.0,
        cfo=30.0,
        ppe=6.0,
    )
    baseline = _facts(
        period="2025-03-31",
        revenue=160.0,
        pbt=24.0,
        finance=4.0,
        pat=18.0,
        assets=150.0,
        equity=85.0,
        current_liabilities=50.0,
        cash=12.0,
        borrowings_current=8.0,
        borrowings_noncurrent=18.0,
        cfo=22.0,
        ppe=5.0,
    )

    metrics = build_quality_metrics(target=target, baseline=baseline)

    assert metrics["roce_proxy"] == pytest.approx(35.0 / 110.0)
    assert metrics["cfo_to_pat"] == pytest.approx(1.25)
    assert metrics["cfo_minus_ppe_to_pat"] == pytest.approx(1.0)
    assert metrics["accruals_to_avg_assets"] == pytest.approx(-6.0 / 165.0)
    assert metrics["net_borrowings_to_equity"] == pytest.approx(0.15)
    assert metrics["ppe_capex_to_revenue"] == pytest.approx(0.03)


def test_missing_quality_fact_is_not_imputed() -> None:
    target = _facts(
        period="2026-03-31",
        revenue=200.0,
        pbt=30.0,
        finance=5.0,
        pat=24.0,
        assets=180.0,
        equity=100.0,
        current_liabilities=60.0,
        cash=15.0,
        borrowings_current=10.0,
        borrowings_noncurrent=20.0,
        cfo=30.0,
        ppe=6.0,
    )
    target = replace(
        target,
        facts={**target.facts, "operating_cash_flow": None},
    )
    baseline = _facts(
        period="2025-03-31",
        revenue=160.0,
        pbt=24.0,
        finance=4.0,
        pat=18.0,
        assets=150.0,
        equity=85.0,
        current_liabilities=50.0,
        cash=12.0,
        borrowings_current=8.0,
        borrowings_noncurrent=18.0,
        cfo=22.0,
        ppe=5.0,
    )

    metrics = build_quality_metrics(target=target, baseline=baseline)

    assert metrics["cfo_to_pat"] is None
    assert metrics["cfo_minus_ppe_to_pat"] is None
    assert metrics["accruals_to_avg_assets"] is None


def test_quality_record_keeps_portfolio_and_live_capital_disabled() -> None:
    target_candidate = _candidate()
    baseline_candidate = _candidate(
        period="2025-03-31",
        url="https://x/base.html",
    )
    pair = FundamentalPair(
        symbol="INFY",
        accounting_basis="Consolidated",
        target=target_candidate,
        baseline=baseline_candidate,
    )
    target = _facts(
        period="2026-03-31",
        revenue=200.0,
        pbt=30.0,
        finance=5.0,
        pat=24.0,
        assets=180.0,
        equity=100.0,
        current_liabilities=60.0,
        cash=15.0,
        borrowings_current=10.0,
        borrowings_noncurrent=20.0,
        cfo=30.0,
        ppe=6.0,
    )
    baseline = _facts(
        period="2025-03-31",
        revenue=160.0,
        pbt=24.0,
        finance=4.0,
        pat=18.0,
        assets=150.0,
        equity=85.0,
        current_liabilities=50.0,
        cash=12.0,
        borrowings_current=8.0,
        borrowings_noncurrent=18.0,
        cfo=22.0,
        ppe=5.0,
    )

    record = quality_record(
        pair=pair,
        target=target,
        baseline=baseline,
        discovery_raw_sha256="d" * 64,
    )

    assert set(record["metrics"]) == set(CORE_METRICS)
    assert record["all_core_metrics_complete"] is True
    assert record["issuer_identity_continuity"] == "SAME_ISIN"
    assert record["target_isin"] == "INE009A01021"
    assert record["baseline_isin"] == "INE009A01021"
    assert record["return_outcomes_opened"] is False
    assert record["model_fitted"] is False
    assert record["portfolio_eligibility_allowed"] is False
    assert record["live_capital_allowed"] is False
