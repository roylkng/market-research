from __future__ import annotations

import pytest

from marketlab.h021_stockanalysis_parser import (
    financials_url,
    forecast_url,
    normalize_fiscal_period,
    parse_annual_forecast,
    parse_period_ending,
)


def _forecast_html(*, currency: str | None = "INR", identity: str = "NSE:AAA") -> bytes:
    currency_line = "" if currency is None else f"<p>Financial currency is {currency}.</p>"
    return f"""
    <html><body>
      <h1>Alpha Limited ({identity})</h1>
      {currency_line}
      <p>Data Source: S&P Global Market Intelligence</p>
      <table>
        <tr><th>Fiscal Year</th><th>FY 2026</th><th>FY 2027</th><th>FY 2028</th></tr>
        <tr><td>Period Ending</td><td>Mar 31, 2026</td><td>Mar 31, 2027</td><td>Mar 31, 2028</td></tr>
        <tr><td>Revenue</td><td>100.0B</td><td>112.0B</td><td>125.0B</td></tr>
        <tr><td>Revenue Growth</td><td>9.0%</td><td>12.5%</td><td>11.6%</td></tr>
        <tr><td>EPS</td><td>9.50</td><td>10.75</td><td>12.00</td></tr>
        <tr><td>EPS Growth</td><td>4.0%</td><td>13.2%</td><td>11.6%</td></tr>
        <tr><td>No. Analysts</td><td>8</td><td>7</td><td>5</td></tr>
      </table>
    </body></html>
    """.encode()


def _financials_html(*, currency: str = "USD", identity: str = "NSE:AAA") -> bytes:
    return f"""
    <html><body>
      <h1>Alpha Limited ({identity})</h1>
      <p>Income Statement</p>
      <p>Millions {currency}. Fiscal year is Apr - Mar.</p>
    </body></html>
    """.encode()


def test_url_builders_encode_special_nse_symbols() -> None:
    assert forecast_url("M&M") == "https://stockanalysis.com/quote/nse/M%26M/forecast/"
    assert financials_url("M&M") == "https://stockanalysis.com/quote/nse/M%26M/financials/"


def test_normalizers_use_canonical_period_identity() -> None:
    assert normalize_fiscal_period("FY 2027") == "FY2027"
    assert normalize_fiscal_period("FY2027") == "FY2027"
    assert normalize_fiscal_period("2027") is None
    assert parse_period_ending("Mar 31, 2027") == "2027-03-31"
    assert parse_period_ending("2027-03-31") == "2027-03-31"


def test_parser_extracts_exact_requested_annual_column() -> None:
    source_url = forecast_url("AAA")
    result = parse_annual_forecast(
        symbol="AAA",
        source_url=source_url,
        html=_forecast_html(),
        expected_fiscal_period="FY2027",
        expected_period_ending="2027-03-31",
    )

    assert result.symbol == "AAA"
    assert result.fiscal_period == "FY2027"
    assert result.period_ending == "2027-03-31"
    assert result.consensus_eps == pytest.approx(10.75)
    assert result.eps_currency == "INR"
    assert result.eps_currency_source_url == source_url
    assert result.revenue_growth_forecast_pct == pytest.approx(12.5)
    assert result.analyst_count == 7
    assert result.provider == "S&P Global Market Intelligence"


def test_parser_preserves_forecast_page_financial_currency() -> None:
    result = parse_annual_forecast(
        symbol="AAA",
        source_url=forecast_url("AAA"),
        html=_forecast_html(currency="USD"),
        expected_fiscal_period="FY2027",
        expected_period_ending="2027-03-31",
    )

    assert result.eps_currency == "USD"
    assert result.eps_currency_source_url == forecast_url("AAA")


def test_parser_uses_explicit_financials_page_currency_when_forecast_omits_it() -> None:
    financials_source = financials_url("AAA")
    result = parse_annual_forecast(
        symbol="AAA",
        source_url=forecast_url("AAA"),
        html=_forecast_html(currency=None),
        expected_fiscal_period="FY2027",
        expected_period_ending="2027-03-31",
        financials_html=_financials_html(currency="USD"),
        financials_source_url=financials_source,
    )

    assert result.eps_currency == "USD"
    assert result.eps_currency_source_url == financials_source


def test_parser_refuses_currency_conflict_between_forecast_and_financials() -> None:
    with pytest.raises(ValueError, match="disagree"):
        parse_annual_forecast(
            symbol="AAA",
            source_url=forecast_url("AAA"),
            html=_forecast_html(currency="INR"),
            expected_fiscal_period="FY2027",
            expected_period_ending="2027-03-31",
            financials_html=_financials_html(currency="USD"),
            financials_source_url=financials_url("AAA"),
        )


def test_parser_refuses_silent_period_rollover() -> None:
    with pytest.raises(ValueError, match="matching annual forecast column"):
        parse_annual_forecast(
            symbol="AAA",
            source_url=forecast_url("AAA"),
            html=_forecast_html(),
            expected_fiscal_period="FY2029",
            expected_period_ending="2029-03-31",
        )


def test_parser_refuses_wrong_forecast_identity() -> None:
    with pytest.raises(ValueError, match="identity marker"):
        parse_annual_forecast(
            symbol="AAA",
            source_url=forecast_url("AAA"),
            html=_forecast_html(identity="NSE:BBB"),
            expected_fiscal_period="FY2027",
            expected_period_ending="2027-03-31",
        )


def test_parser_refuses_wrong_financials_identity() -> None:
    with pytest.raises(ValueError, match="financials page identity marker"):
        parse_annual_forecast(
            symbol="AAA",
            source_url=forecast_url("AAA"),
            html=_forecast_html(currency=None),
            expected_fiscal_period="FY2027",
            expected_period_ending="2027-03-31",
            financials_html=_financials_html(identity="NSE:BBB"),
            financials_source_url=financials_url("AAA"),
        )


def test_parser_refuses_missing_currency_from_both_pages() -> None:
    financials = _financials_html().replace(b"Millions USD.", b"Financial statements.")
    with pytest.raises(ValueError, match="forecast/reporting currency marker"):
        parse_annual_forecast(
            symbol="AAA",
            source_url=forecast_url("AAA"),
            html=_forecast_html(currency=None),
            expected_fiscal_period="FY2027",
            expected_period_ending="2027-03-31",
            financials_html=financials,
            financials_source_url=financials_url("AAA"),
        )


def test_parser_refuses_unparsable_eps() -> None:
    html = _forecast_html().replace(b">10.75<", b">N/A<")
    with pytest.raises(ValueError, match="consensus EPS"):
        parse_annual_forecast(
            symbol="AAA",
            source_url=forecast_url("AAA"),
            html=html,
            expected_fiscal_period="FY2027",
            expected_period_ending="2027-03-31",
        )
