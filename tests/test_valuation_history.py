from __future__ import annotations

import pytest

from marketlab.alpha_fundamental import FilingCandidate
from marketlab.valuation_history import (
    compute_ttm_pe_proxy,
    parse_quarterly_valuation_filing,
    publication_market_date,
    select_period_filing,
    select_snapshot_filings,
)


def _integrated_row(
    *,
    period: str,
    basis: str = "Consolidated",
    url: str = "https://x/current.xml",
    published: str = "20-Oct-2025 18:00:00",
) -> dict:
    return {
        "type": "Integrated Filing- Financials",
        "symbol": "TEST",
        "consolidated": basis,
        "qe_Date": period,
        "broadcast_Date": published,
        "xbrl": url,
    }


def _legacy_row(
    *,
    period: str,
    basis: str = "Consolidated",
    url: str = "https://x/legacy.xml",
    published: str = "20-Jan-2025 18:00:00",
) -> dict:
    return {
        "symbol": "TEST",
        "consolidated": basis,
        "toDate": period,
        "broadCastDate": published,
        "xbrl": url,
    }


def test_period_selector_prefers_integrated_then_legacy() -> None:
    integrated = {
        "data": [
            _integrated_row(period="30-Sep-2025", url="https://x/integrated.xml")
        ]
    }
    legacy = [
        _legacy_row(period="30-Sep-2025", url="https://x/legacy.xml"),
        _legacy_row(period="31-Dec-2024", url="https://x/dec-legacy.xml"),
    ]

    current = select_period_filing(
        integrated,
        legacy,
        symbol="TEST",
        period_end="2025-09-30",
        accounting_basis="Consolidated",
    )
    old = select_period_filing(
        integrated,
        legacy,
        symbol="TEST",
        period_end="2024-12-31",
        accounting_basis="Consolidated",
    )

    assert current.source_family == "INTEGRATED"
    assert current.candidate.source_url.endswith("integrated.xml")
    assert old.source_family == "LEGACY"
    assert old.candidate.source_url.endswith("dec-legacy.xml")


def test_snapshot_selector_requires_one_basis_for_all_four_quarters() -> None:
    periods = ("2024-12-31", "2025-03-31", "2025-06-30", "2025-09-30")
    integrated = {
        "data": [
            _integrated_row(
                period=period,
                basis="Consolidated",
                url=f"https://x/{period}.xml",
            )
            for period in periods
        ]
    }
    basis, selected = select_snapshot_filings(
        integrated,
        [],
        symbol="TEST",
        required_periods=periods,
    )
    assert basis == "Consolidated"
    assert tuple(selected) == periods


def _candidate() -> FilingCandidate:
    return FilingCandidate(
        symbol="TEST",
        accounting_basis="Consolidated",
        period_end="2025-09-30",
        exchange_published_at_utc="2025-10-20T12:30:00Z",
        source_url="https://x/test.xml",
        discovery_row_sha256="a" * 64,
        discovery_row={},
    )


def test_quarter_parser_derives_split_aware_share_count_from_xbrl() -> None:
    xml = """<?xml version="1.0"?>
    <xbrli:xbrl
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:in-capmkt="http://www.sebi.gov.in/xbrl/2025-01-31/in-capmkt">
      <xbrli:context id="OneD">
        <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
        <xbrli:period>
          <xbrli:startDate>2025-07-01</xbrli:startDate>
          <xbrli:endDate>2025-09-30</xbrli:endDate>
        </xbrli:period>
      </xbrli:context>
      <xbrli:context id="OneI">
        <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
        <xbrli:period><xbrli:instant>2025-09-30</xbrli:instant></xbrli:period>
      </xbrli:context>
      <in-capmkt:Symbol contextRef="OneD">TEST</in-capmkt:Symbol>
      <in-capmkt:ISIN contextRef="OneD">INE000000001</in-capmkt:ISIN>
      <in-capmkt:NameOfTheCompany contextRef="OneD">TEST LIMITED</in-capmkt:NameOfTheCompany>
      <in-capmkt:DateOfStartOfFinancialYear contextRef="OneD">2025-04-01</in-capmkt:DateOfStartOfFinancialYear>
      <in-capmkt:DateOfEndOfFinancialYear contextRef="OneD">2026-03-31</in-capmkt:DateOfEndOfFinancialYear>
      <in-capmkt:DateOfStartOfReportingPeriod contextRef="OneD">2025-07-01</in-capmkt:DateOfStartOfReportingPeriod>
      <in-capmkt:DateOfEndOfReportingPeriod contextRef="OneD">2025-09-30</in-capmkt:DateOfEndOfReportingPeriod>
      <in-capmkt:TypeOfReportingPeriod contextRef="OneD">Quarterly</in-capmkt:TypeOfReportingPeriod>
      <in-capmkt:ReportingQuarter contextRef="OneD">Second quarter</in-capmkt:ReportingQuarter>
      <in-capmkt:NatureOfReportStandaloneConsolidated contextRef="OneD">Consolidated</in-capmkt:NatureOfReportStandaloneConsolidated>
      <in-capmkt:DescriptionOfPresentationCurrency contextRef="OneD">INR</in-capmkt:DescriptionOfPresentationCurrency>
      <in-capmkt:LevelOfRounding contextRef="OneD">Crores</in-capmkt:LevelOfRounding>
      <in-capmkt:ProfitLossForPeriod contextRef="OneD">1500000000</in-capmkt:ProfitLossForPeriod>
      <in-capmkt:PaidUpValueOfEquityShareCapital contextRef="OneD">1000000000</in-capmkt:PaidUpValueOfEquityShareCapital>
      <in-capmkt:FaceValueOfEquityShareCapital contextRef="OneD">2</in-capmkt:FaceValueOfEquityShareCapital>
      <in-capmkt:EquityShareCapital contextRef="OneI">1000000000</in-capmkt:EquityShareCapital>
    </xbrli:xbrl>
    """

    facts = parse_quarterly_valuation_filing(
        xml.encode(),
        candidate=_candidate(),
    )

    assert facts.total_profit_inr == 1_500_000_000
    assert facts.paid_up_equity_share_capital_inr == 1_000_000_000
    assert facts.face_value_per_share_inr == 2
    assert facts.share_count == 500_000_000


def test_ttm_pe_proxy_matches_frozen_formula() -> None:
    result = compute_ttm_pe_proxy(
        quarterly_profits_inr=[1.0e9, 1.2e9, 1.4e9, 1.4e9],
        share_count=500_000_000,
        price_inr=100.0,
    )
    assert result["ttm_profit_inr"] == pytest.approx(5.0e9)
    assert result["market_cap_inr"] == pytest.approx(50.0e9)
    assert result["ttm_pe_proxy"] == pytest.approx(10.0)
    assert result["earnings_yield_proxy"] == pytest.approx(0.1)


def test_ttm_pe_refuses_nonpositive_ttm_profit() -> None:
    with pytest.raises(Exception, match="TTM PAT"):
        compute_ttm_pe_proxy(
            quarterly_profits_inr=[1.0, -2.0, 0.0, 0.0],
            share_count=10.0,
            price_inr=100.0,
        )


def test_publication_market_date_uses_india_calendar_date() -> None:
    assert publication_market_date("2025-10-20T20:30:00+00:00") == "2025-10-21"
