from __future__ import annotations

import pytest

from marketlab.h023_ownership import (
    MF_CONTEXT_REF,
    MF_SHAREHOLDING_CONCEPT,
    H023OwnershipError,
    ownership_delta_pp,
    parse_mutual_fund_ownership_xbrl,
    parser_contract,
    select_latest_distinct_filings,
)


def _xml(*, value: str = "0.1011", unit: str = "pure", duplicates: int = 1) -> bytes:
    facts = "".join(
        f'<shp:{MF_SHAREHOLDING_CONCEPT} contextRef="{MF_CONTEXT_REF}" '
        f'unitRef="{unit}" decimals="INF">{value}</shp:{MF_SHAREHOLDING_CONCEPT}>'
        for _ in range(duplicates)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" '
        'xmlns:shp="http://example.test/shp">'
        f'<xbrli:context id="{MF_CONTEXT_REF}">'
        '<xbrli:entity><xbrli:identifier scheme="test">ENTITY</xbrli:identifier></xbrli:entity>'
        '<xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>'
        '</xbrli:context>'
        f'{facts}'
        '</xbrli:xbrl>'
    ).encode()


def test_exact_mutual_fund_fact_is_fraction_and_percentage() -> None:
    parsed = parse_mutual_fund_ownership_xbrl(_xml(value="0.1011"))
    assert parsed.context_ref == MF_CONTEXT_REF
    assert parsed.concept == MF_SHAREHOLDING_CONCEPT
    assert parsed.unit_ref == "pure"
    assert parsed.fraction == pytest.approx(0.1011)
    assert parsed.percentage == pytest.approx(10.11)


def test_parser_rejects_missing_exact_context() -> None:
    raw = _xml().replace(MF_CONTEXT_REF.encode(), b"SomeOtherContext")
    with pytest.raises(H023OwnershipError, match="missing exact Mutual Fund context"):
        parse_mutual_fund_ownership_xbrl(raw)


def test_parser_rejects_duplicate_fact() -> None:
    with pytest.raises(H023OwnershipError, match="expected one Mutual Fund shareholding fact"):
        parse_mutual_fund_ownership_xbrl(_xml(duplicates=2))


def test_parser_rejects_wrong_unit_and_out_of_range_value() -> None:
    with pytest.raises(H023OwnershipError, match="unexpected Mutual Fund shareholding unit"):
        parse_mutual_fund_ownership_xbrl(_xml(unit="shares"))
    with pytest.raises(H023OwnershipError, match="out of range"):
        parse_mutual_fund_ownership_xbrl(_xml(value="1.01"))


def test_latest_distinct_filings_use_broadcast_time_and_latest_revision() -> None:
    payload = [
        {
            "symbol": "ABC",
            "recordId": "old-q1",
            "date": "31-MAR-2026",
            "broadcastDate": "20-APR-2026 10:00:00",
            "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/old-q1.xml",
        },
        {
            "symbol": "ABC",
            "recordId": "q2-original",
            "date": "30-JUN-2026",
            "broadcastDate": "15-JUL-2026 18:00:00",
            "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/q2-original.xml",
        },
        {
            "symbol": "ABC",
            "recordId": "q2-revision",
            "date": "30-JUN-2026",
            "broadcastDate": "16-JUL-2026 18:00:00",
            "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/q2-revision.xml",
        },
        {
            "symbol": "ABC",
            "recordId": "q4-prior-year",
            "date": "31-DEC-2025",
            "broadcastDate": "20-JAN-2026 12:00:00",
            "xbrl": "https://nsearchives.nseindia.com/corporate/xbrl/q4.xml",
        },
    ]
    selected = select_latest_distinct_filings(payload, symbol="ABC", count=2)
    assert [row.record_id for row in selected] == ["q2-revision", "old-q1"]
    assert [row.report_date for row in selected] == ["2026-06-30", "2026-03-31"]
    assert selected[0].broadcast_at_utc == "2026-07-16T12:30:00Z"


def test_ownership_delta_is_percentage_points() -> None:
    current = parse_mutual_fund_ownership_xbrl(_xml(value="0.1011"))
    prior = parse_mutual_fund_ownership_xbrl(_xml(value="0.0875"))
    assert ownership_delta_pp(current, prior) == pytest.approx(1.36)


def test_contract_freezes_exact_source_semantics() -> None:
    contract = parser_contract()
    assert contract == {
        "context_ref": MF_CONTEXT_REF,
        "concept": MF_SHAREHOLDING_CONCEPT,
        "unit_ref": "pure",
        "value_semantics": "fraction_of_total_shares",
        "percentage_conversion": "fraction * 100",
        "signal_primitive": "current_percentage - prior_distinct_report_percentage",
        "filing_order": "NSE broadcastDate descending, latest revision per distinct report date",
        "availability_timestamp": "NSE broadcastDate interpreted as Asia/Kolkata",
    }
