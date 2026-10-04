from __future__ import annotations

import csv
import io
import zipfile
from datetime import date

import pytest

from marketlab.normalized_valuation import (
    AnnualFilingCandidate,
    NV001SourceError,
    candidate_price_dates,
    legacy_bhavcopy_url,
    parse_annual_basic_eps,
    parse_price_close,
    price_source,
    select_four_year_annual_filings,
    trailing_pe,
)


def _integrated_row(period: str, basis: str, published: str, url: str) -> dict:
    return {
        "type": "Integrated Filing- Financials",
        "symbol": "TEST",
        "consolidated": basis,
        "qe_Date": period,
        "broadcast_Date": published,
        "xbrl": url,
    }


def _legacy_row(period: str, basis: str, published: str, url: str) -> dict:
    legacy_basis = "Non-Consolidated" if basis == "Standalone" else basis
    return {
        "symbol": "TEST",
        "consolidated": legacy_basis,
        "toDate": period,
        "broadCastDate": published,
        "xbrl": url,
    }


def test_select_four_year_filings_prefers_complete_consolidated_basis() -> None:
    integrated = {
        "data": [
            _integrated_row(
                "31-Mar-2025",
                "Consolidated",
                "20-Apr-2025 18:00:00",
                "https://nsearchives.nseindia.com/corporate/xbrl/fy25.xml",
            ),
            _integrated_row(
                "31-Mar-2026",
                "Consolidated",
                "20-Apr-2026 18:00:00",
                "https://nsearchives.nseindia.com/corporate/xbrl/fy26.xml",
            ),
            _integrated_row(
                "31-Mar-2025",
                "Standalone",
                "20-Apr-2025 17:00:00",
                "https://nsearchives.nseindia.com/corporate/xbrl/fy25sa.xml",
            ),
            _integrated_row(
                "31-Mar-2026",
                "Standalone",
                "20-Apr-2026 17:00:00",
                "https://nsearchives.nseindia.com/corporate/xbrl/fy26sa.xml",
            ),
        ]
    }
    legacy = [
        _legacy_row(
            "31-Mar-2023",
            "Consolidated",
            "20-Apr-2023 18:00:00",
            "https://nsearchives.nseindia.com/corporate/xbrl/fy23.xml",
        ),
        _legacy_row(
            "31-Mar-2024",
            "Consolidated",
            "20-Apr-2024 18:00:00",
            "https://nsearchives.nseindia.com/corporate/xbrl/fy24.xml",
        ),
        _legacy_row(
            "31-Mar-2023",
            "Standalone",
            "20-Apr-2023 17:00:00",
            "https://nsearchives.nseindia.com/corporate/xbrl/fy23sa.xml",
        ),
        _legacy_row(
            "31-Mar-2024",
            "Standalone",
            "20-Apr-2024 17:00:00",
            "https://nsearchives.nseindia.com/corporate/xbrl/fy24sa.xml",
        ),
    ]

    basis, candidates = select_four_year_annual_filings(
        integrated,
        legacy,
        symbol="TEST",
    )

    assert basis == "Consolidated"
    assert [row.period_end for row in candidates] == [
        "2023-03-31",
        "2024-03-31",
        "2025-03-31",
        "2026-03-31",
    ]


def test_select_four_year_filings_fails_without_one_complete_basis() -> None:
    integrated = {
        "data": [
            _integrated_row(
                "31-Mar-2025",
                "Consolidated",
                "20-Apr-2025 18:00:00",
                "https://nsearchives.nseindia.com/corporate/xbrl/fy25.xml",
            ),
            _integrated_row(
                "31-Mar-2026",
                "Consolidated",
                "20-Apr-2026 18:00:00",
                "https://nsearchives.nseindia.com/corporate/xbrl/fy26.xml",
            ),
        ]
    }
    legacy = [
        _legacy_row(
            "31-Mar-2023",
            "Standalone",
            "20-Apr-2023 17:00:00",
            "https://nsearchives.nseindia.com/corporate/xbrl/fy23sa.xml",
        ),
        _legacy_row(
            "31-Mar-2024",
            "Standalone",
            "20-Apr-2024 17:00:00",
            "https://nsearchives.nseindia.com/corporate/xbrl/fy24sa.xml",
        ),
    ]
    with pytest.raises(NV001SourceError, match="single accounting basis"):
        select_four_year_annual_filings(integrated, legacy, symbol="TEST")


def _annual_xbrl(eps: float = 20.0) -> bytes:
    return f"""<?xml version="1.0"?>
<xbrli:xbrl
 xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:in-capmkt="http://www.sebi.gov.in/xbrl">
 <xbrli:context id="Q">
  <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period>
 </xbrli:context>
 <xbrli:context id="FY">
  <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period>
 </xbrli:context>
 <in-capmkt:Symbol contextRef="Q">TEST</in-capmkt:Symbol>
 <in-capmkt:ISIN contextRef="Q">INE000000001</in-capmkt:ISIN>
 <in-capmkt:NatureOfReportStandaloneConsolidated contextRef="Q">Consolidated</in-capmkt:NatureOfReportStandaloneConsolidated>
 <in-capmkt:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations contextRef="Q">5</in-capmkt:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations>
 <in-capmkt:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations contextRef="FY">{eps}</in-capmkt:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations>
</xbrli:xbrl>
""".encode()


def test_parse_annual_eps_uses_annual_duration_not_q4() -> None:
    candidate = AnnualFilingCandidate(
        symbol="TEST",
        accounting_basis="Consolidated",
        period_end="2025-03-31",
        exchange_published_at_utc="2025-04-20T12:30:00Z",
        source_url="https://nsearchives.nseindia.com/corporate/xbrl/test.xml",
        source_family="NSE_INTEGRATED_FILING",
        discovery_row_sha256="a" * 64,
    )
    parsed = parse_annual_basic_eps(_annual_xbrl(24.0), candidate=candidate)
    assert parsed.basic_eps == 24.0
    assert parsed.annual_start == "2024-04-01"


def _legacy_annual_xbrl(
    *,
    period_end: str = "2024-03-31",
    q4_eps: float = 19.25,
    annual_eps: float = 63.39,
    financial_year_start: str = "2023-04-01",
) -> bytes:
    return f"""<?xml version="1.0"?>
<xbrli:xbrl
 xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:in-capmkt="http://www.sebi.gov.in/xbrl">
 <xbrli:context id="OneD">
  <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>{period_end}</xbrli:endDate></xbrli:period>
 </xbrli:context>
 <xbrli:context id="FourD">
  <xbrli:entity><xbrli:identifier scheme="test">1</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>{period_end}</xbrli:endDate></xbrli:period>
 </xbrli:context>
 <in-capmkt:Symbol contextRef="OneD">TEST</in-capmkt:Symbol>
 <in-capmkt:ISIN contextRef="OneD">INE000000001</in-capmkt:ISIN>
 <in-capmkt:NatureOfReportStandaloneConsolidated contextRef="OneD">Consolidated</in-capmkt:NatureOfReportStandaloneConsolidated>
 <in-capmkt:DateOfStartOfFinancialYear contextRef="OneD">{financial_year_start}</in-capmkt:DateOfStartOfFinancialYear>
 <in-capmkt:DateOfEndOfFinancialYear contextRef="OneD">{period_end}</in-capmkt:DateOfEndOfFinancialYear>
 <in-capmkt:DateOfEndOfReportingPeriod contextRef="OneD">{period_end}</in-capmkt:DateOfEndOfReportingPeriod>
 <in-capmkt:DateOfEndOfReportingPeriod contextRef="FourD">{period_end}</in-capmkt:DateOfEndOfReportingPeriod>
 <in-capmkt:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations contextRef="OneD">{q4_eps}</in-capmkt:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations>
 <in-capmkt:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations contextRef="FourD">{annual_eps}</in-capmkt:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations>
</xbrli:xbrl>
""".encode()


def test_legacy_annual_eps_uses_exact_fourd_full_year_context() -> None:
    candidate = AnnualFilingCandidate(
        symbol="TEST",
        accounting_basis="Consolidated",
        period_end="2024-03-31",
        exchange_published_at_utc="2024-04-20T12:30:00Z",
        source_url="https://nsearchives.nseindia.com/corporate/xbrl/legacy.xml",
        source_family="NSE_LEGACY_FINANCIAL_RESULTS",
        discovery_row_sha256="a" * 64,
    )
    parsed = parse_annual_basic_eps(
        _legacy_annual_xbrl(q4_eps=19.25, annual_eps=63.39),
        candidate=candidate,
    )

    assert parsed.basic_eps == pytest.approx(63.39)
    assert parsed.annual_start == "2023-04-01"


def test_legacy_fourd_refuses_incompatible_financial_year_metadata() -> None:
    candidate = AnnualFilingCandidate(
        symbol="TEST",
        accounting_basis="Consolidated",
        period_end="2024-03-31",
        exchange_published_at_utc="2024-04-20T12:30:00Z",
        source_url="https://nsearchives.nseindia.com/corporate/xbrl/legacy.xml",
        source_family="NSE_LEGACY_FINANCIAL_RESULTS",
        discovery_row_sha256="a" * 64,
    )
    with pytest.raises(NV001SourceError, match="financial-year start"):
        parse_annual_basic_eps(
            _legacy_annual_xbrl(financial_year_start="2023-01-01"),
            candidate=candidate,
        )


def _zip_csv(name: str, header: list[str], rows: list[list[object]]) -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(header)
    writer.writerows(rows)
    raw = stream.getvalue().encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(name, raw)
    return out.getvalue()


def test_parse_legacy_bhavcopy_close_with_exact_identity() -> None:
    raw = _zip_csv(
        "cm21APR2023bhav.csv",
        ["SYMBOL", "SERIES", "OPEN", "HIGH", "LOW", "CLOSE", "ISIN"],
        [["TEST", "EQ", "100", "110", "99", "108", "INE000000001"]],
    )
    anchor = parse_price_close(
        raw,
        source_family="NSE_LEGACY_CM_BHAVCOPY",
        session_date=date(2023, 4, 21),
        symbol="TEST",
        expected_isin="INE000000001",
        source_url=legacy_bhavcopy_url(date(2023, 4, 21)),
    )
    assert anchor.close_price == 108.0
    assert anchor.symbol == "TEST"


def test_parse_udiff_can_fallback_to_exact_isin_after_symbol_change() -> None:
    raw = _zip_csv(
        "BhavCopy.csv",
        ["TradDt", "Sgmt", "Src", "FinInstrmTp", "ISIN", "TckrSymb", "SctySrs", "ClsPric"],
        [["2025-04-21", "CM", "NSE", "STK", "INE000000001", "NEWTEST", "EQ", "220"]],
    )
    anchor = parse_price_close(
        raw,
        source_family="NSE_UDIFF_BHAVCOPY",
        session_date=date(2025, 4, 21),
        symbol="OLDTEST",
        expected_isin="INE000000001",
        source_url="https://nsearchives.nseindia.com/test.zip",
    )
    assert anchor.symbol == "NEWTEST"
    assert anchor.close_price == 220.0


def test_price_source_switches_on_frozen_udiff_start_date() -> None:
    family_old, url_old = price_source(date(2024, 7, 5))
    family_new, url_new = price_source(date(2024, 7, 8))
    assert family_old == "NSE_LEGACY_CM_BHAVCOPY"
    assert "historical/EQUITIES/2024/JUL" in url_old
    assert family_new == "NSE_UDIFF_BHAVCOPY"
    assert "BhavCopy_NSE_CM" in url_new


def test_candidate_price_dates_start_strictly_after_publication_day() -> None:
    candidate = AnnualFilingCandidate(
        symbol="TEST",
        accounting_basis="Consolidated",
        period_end="2025-03-31",
        exchange_published_at_utc="2025-04-20T12:30:00Z",
        source_url="https://nsearchives.nseindia.com/test.xml",
        source_family="NSE_INTEGRATED_FILING",
        discovery_row_sha256="a" * 64,
    )
    days = candidate_price_dates(candidate)
    assert days[0] == date(2025, 4, 21)
    assert len(days) == 10


def test_trailing_pe_requires_positive_eps_and_price() -> None:
    assert trailing_pe(200.0, 10.0) == 20.0
    with pytest.raises(NV001SourceError):
        trailing_pe(200.0, -1.0)
