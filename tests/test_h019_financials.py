from datetime import date
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import h019_financials as h019


def xbrl(*facts: str) -> bytes:
    body = "".join(facts)
    return f'<xbrl xmlns="http://www.xbrl.org/2003/instance">{body}</xbrl>'.encode()


def fact(name: str, value: str, *, context: str = "OneD", unit: str = "INR") -> str:
    return f'<i:{name} xmlns:i="urn:test" contextRef="{context}" unitRef="{unit}">{value}</i:{name}>'


def valid_document() -> bytes:
    return xbrl(
        fact("RevenueFromOperations", "100000000"),
        fact("ProfitLossForPeriod", "8000000"),
        fact("ProfitBeforeExceptionalItemsAndTax", "12000000"),
        fact(
            "BasicEarningsLossPerShareFromContinuingOperations",
            "4.0",
            unit="INRPerShare",
        ),
        fact("PaidUpValueOfEquityShareCapital", "20000000"),
        fact("FaceValueOfEquityShareCapital", "10", unit="INRPerShare"),
        # Comparative/cumulative source facts must not be selected.
        fact("RevenueFromOperations", "300000000", context="FourD"),
        fact("ProfitLossForPeriod", "25000000", context="FourD"),
    )


def test_parse_exact_one_d_financials() -> None:
    parsed = h019.parse_quarterly_financials(valid_document(), date(2023, 9, 30))
    assert parsed.revenue == 100000000
    assert parsed.profit_after_tax == 8000000
    assert parsed.pre_exception_pretax_profit == 12000000
    assert parsed.basic_eps == 4.0
    assert parsed.share_count == 2_000_000
    assert parsed.net_margin == pytest.approx(0.08)
    assert parsed.pre_exception_pretax_margin == pytest.approx(0.12)


def test_missing_required_one_d_fact_fails_closed() -> None:
    raw = valid_document().replace(
        fact("ProfitLossForPeriod", "8000000").encode(),
        b"",
    )
    with pytest.raises(h019.H019FinancialError, match="ProfitLossForPeriod"):
        h019.parse_quarterly_financials(raw, date(2023, 9, 30))


def test_duplicate_one_d_fact_fails_closed() -> None:
    raw = valid_document().replace(
        b"</xbrl>",
        fact("RevenueFromOperations", "999").encode() + b"</xbrl>",
    )
    with pytest.raises(h019.H019FinancialError, match="found 2"):
        h019.parse_quarterly_financials(raw, date(2023, 9, 30))


def test_wrong_unit_is_not_accepted_as_substitute() -> None:
    raw = valid_document().replace(
        fact("FaceValueOfEquityShareCapital", "10", unit="INRPerShare").encode(),
        fact("FaceValueOfEquityShareCapital", "10", unit="INR").encode(),
    )
    with pytest.raises(h019.H019FinancialError, match="FaceValueOfEquityShareCapital"):
        h019.parse_quarterly_financials(raw, date(2023, 9, 30))


def test_four_d_only_is_not_accepted_as_current_quarter() -> None:
    raw = valid_document().replace(
        fact("RevenueFromOperations", "100000000").encode(),
        b"",
    )
    with pytest.raises(h019.H019FinancialError, match="RevenueFromOperations"):
        h019.parse_quarterly_financials(raw, date(2023, 9, 30))


def test_nonpositive_share_primitives_fail_closed() -> None:
    raw = valid_document().replace(
        fact("FaceValueOfEquityShareCapital", "10", unit="INRPerShare").encode(),
        fact("FaceValueOfEquityShareCapital", "0", unit="INRPerShare").encode(),
    )
    with pytest.raises(h019.H019FinancialError, match="face value"):
        h019.parse_quarterly_financials(raw, date(2023, 9, 30))


def test_non_xbrl_root_is_rejected() -> None:
    with pytest.raises(h019.H019FinancialError, match="not XBRL"):
        h019.parse_quarterly_financials(b"<html></html>", date(2023, 9, 30))
