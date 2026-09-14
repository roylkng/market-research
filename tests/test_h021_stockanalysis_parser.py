from __future__ import annotations

import pytest

from marketlab.h021_stockanalysis_parser import (
    normalize_fiscal_period,
    parse_annual_forecast,
    parse_period_ending,
)


def _html(*, currency: str = "INR", identity: str = "NSE:AAA") -> bytes:
    return f"""
    <html><body>
      <h1>Alpha Limited ({identity})</h1>
      <p>Financial currency is {currency}.</p>
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


def test_normalizers_use_canonical_period_identity() -> None:
    assert normalize_fiscal_period("FY 2027") == "FY2027"
    assert normalize_fiscal_period("FY2027") == "FY2027"
    assert normalize_fiscal_period("2027") is None
    assert parse_period_ending("Mar 31, 2027") == "2027-03-31"
    assert parse_period_ending("2027-03-31") == "2027-03-31"


def test_parser_extracts_exact_requested_annual_column() -> None:
    result = parse_annual_forecast(
        symbol="AAA",
        source_url="https://stockanalysis.com/quote/nse/AAA/forecast/",
        html=_html(),
        expected_fiscal_period="FY2027",
        expected_period_ending="2027-03-31",
    )

    assert result.symbol == "AAA"
    assert result.fiscal_period == "FY2027"
    assert result.period_ending == "2027-03-31"
    assert result.consensus_eps == pytest.approx(10.75)
    assert result.eps_currency == "INR"
    assert result.revenue_growth_forecast_pct == pytest.approx(12.5)
    assert result.analyst_count == 7
    assert result.provider == "S&P Global Market Intelligence"


def test_parser_preserves_provider_financial_currency_not_listing_assumption() -> None:
    result = parse_annual_forecast(
        symbol="AAA",
        source_url="https://stockanalysis.com/quote/nse/AAA/forecast/",
        html=_html(currency="USD"),
        expected_fiscal_period="FY2027",
        expected_period_ending="2027-03-31",
    )

    assert result.eps_currency == "USD"


def test_parser_refuses_silent_period_rollover() -> None:
    with pytest.raises(ValueError, match="matching annual forecast column"):
        parse_annual_forecast(
            symbol="AAA",
            source_url="https://stockanalysis.com/quote/nse/AAA/forecast/",
            html=_html(),
            expected_fiscal_period="FY2029",
            expected_period_ending="2029-03-31",
        )


def test_parser_refuses_wrong_identity() -> None:
    with pytest.raises(ValueError, match="identity marker"):
        parse_annual_forecast(
            symbol="AAA",
            source_url="https://stockanalysis.com/quote/nse/AAA/forecast/",
            html=_html(identity="NSE:BBB"),
            expected_fiscal_period="FY2027",
            expected_period_ending="2027-03-31",
        )


def test_parser_refuses_missing_provider_currency() -> None:
    html = _html().replace(b"Financial currency is INR.", b"Financial statements")
    with pytest.raises(ValueError, match="currency marker"):
        parse_annual_forecast(
            symbol="AAA",
            source_url="https://stockanalysis.com/quote/nse/AAA/forecast/",
            html=html,
            expected_fiscal_period="FY2027",
            expected_period_ending="2027-03-31",
        )


def test_parser_refuses_unparsable_eps() -> None:
    html = _html().replace(b">10.75<", b">N/A<")
    with pytest.raises(ValueError, match="consensus EPS"):
        parse_annual_forecast(
            symbol="AAA",
            source_url="https://stockanalysis.com/quote/nse/AAA/forecast/",
            html=html,
            expected_fiscal_period="FY2027",
            expected_period_ending="2027-03-31",
        )
