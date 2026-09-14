from __future__ import annotations

import pytest

from marketlab.h023_ownership import (
    MF_CONTEXT_REF,
    MF_DETAIL_AXIS,
    MF_SHAREHOLDING_CONCEPT,
    H023OwnershipError,
    is_standard_quarter_end,
    ownership_delta_pp,
    parse_mutual_fund_ownership_xbrl,
    parser_contract,
    previous_quarter_end,
    select_latest_adjacent_quarter_filings,
    select_latest_revision_for_report_date,
)


def _xml(
    *,
    value: str = "0.1011",
    unit: str = "pure",
    duplicates: int = 1,
    report_date: str = "2026-06-30",
    detail_axis: str | None = None,
) -> bytes:
    facts = "".join(
        f'<shp:{MF_SHAREHOLDING_CONCEPT} contextRef="{MF_CONTEXT_REF}" '
        f'unitRef="{unit}" decimals="INF">{value}</shp:{MF_SHAREHOLDING_CONCEPT}>'
        for _ in range(duplicates)
    )
    detail_context = ""
    if detail_axis is not None:
        detail_context = (
            '<xbrli:context id="D_MutualFundsOrUTI_Context15">'
            '<xbrli:entity><xbrli:identifier scheme="test">ENTITY</xbrli:identifier>'
            '<xbrli:segment>'
            f'<xbrldi:typedMember dimension="shp:{detail_axis}">'
            '<shp:MutualFundsOrUTIDomain>D_MutualFundsOrUTI_Context15</shp:MutualFundsOrUTIDomain>'
            '</xbrldi:typedMember>'
            '</xbrli:segment></xbrli:entity>'
            f'<xbrli:period><xbrli:instant>{report_date}</xbrli:instant></xbrli:period>'
            '</xbrli:context>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" '
        'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" '
        'xmlns:shp="http://example.test/shp">'
        f'<xbrli:context id="{MF_CONTEXT_REF}">'
        '<xbrli:entity><xbrli:identifier scheme="test">ENTITY</xbrli:identifier></xbrli:entity>'
        f'<xbrli:period><xbrli:instant>{report_date}</xbrli:instant></xbrli:period>'
        '</xbrli:context>'
        f'{detail_context}'
        f'{facts}'
        '</xbrli:xbrl>'
    ).encode()


def _parse(raw: bytes, *, report_date: str = "2026-06-30"):
    return parse_mutual_fund_ownership_xbrl(raw, expected_report_date=report_date)


def _row(
    *,
    record_id: str,
    report_date: str,
    broadcast: str,
    symbol: str = "ABC",
) -> dict[str, str]:
    return {
        "symbol": symbol,
        "recordId": record_id,
        "date": report_date,
        "broadcastDate": broadcast,
        "xbrl": f"https://nsearchives.nseindia.com/corporate/xbrl/{record_id}.xml",
    }


def test_exact_mutual_fund_fact_is_fraction_and_percentage() -> None:
    parsed = _parse(_xml(value="0.1011", detail_axis=MF_DETAIL_AXIS))
    assert parsed.context_ref == MF_CONTEXT_REF
    assert parsed.concept == MF_SHAREHOLDING_CONCEPT
    assert parsed.unit_ref == "pure"
    assert parsed.report_date == "2026-06-30"
    assert parsed.fraction == pytest.approx(0.1011)
    assert parsed.percentage == pytest.approx(10.11)


def test_parser_allows_aggregate_context_without_named_fund_details() -> None:
    parsed = _parse(_xml(value="0"))
    assert parsed.percentage == 0.0


def test_parser_rejects_missing_exact_context() -> None:
    raw = _xml().replace(MF_CONTEXT_REF.encode(), b"SomeOtherContext")
    with pytest.raises(H023OwnershipError, match="expected one exact Mutual Fund context"):
        _parse(raw)


def test_parser_rejects_context_period_mismatch() -> None:
    with pytest.raises(H023OwnershipError, match="context period does not match"):
        _parse(_xml(report_date="2026-03-31"), report_date="2026-06-30")


def test_parser_rejects_unexpected_mutual_fund_detail_axis() -> None:
    with pytest.raises(H023OwnershipError, match="unexpected Mutual Fund XBRL detail axis"):
        _parse(_xml(detail_axis="UnexpectedMutualFundsOrUTIAxis"))


def test_parser_rejects_duplicate_fact() -> None:
    with pytest.raises(H023OwnershipError, match="expected one Mutual Fund shareholding fact"):
        _parse(_xml(duplicates=2))


def test_parser_rejects_wrong_unit_and_out_of_range_value() -> None:
    with pytest.raises(H023OwnershipError, match="unexpected Mutual Fund shareholding unit"):
        _parse(_xml(unit="shares"))
    with pytest.raises(H023OwnershipError, match="out of range"):
        _parse(_xml(value="1.01"))


def test_quarter_end_helpers_are_exact() -> None:
    assert is_standard_quarter_end("2026-03-31")
    assert is_standard_quarter_end("2026-06-30")
    assert is_standard_quarter_end("2026-09-30")
    assert is_standard_quarter_end("2026-12-31")
    assert not is_standard_quarter_end("2026-06-23")
    assert previous_quarter_end("2026-03-31") == "2025-12-31"
    assert previous_quarter_end("2026-06-30") == "2026-03-31"
    assert previous_quarter_end("2026-09-30") == "2026-06-30"
    assert previous_quarter_end("2026-12-31") == "2026-09-30"


def test_adjacent_quarter_selection_ignores_intervening_and_stale_backfills() -> None:
    payload = [
        _row(
            record_id="q2-original",
            report_date="30-JUN-2026",
            broadcast="15-JUL-2026 18:00:00",
        ),
        _row(
            record_id="q2-revision",
            report_date="30-JUN-2026",
            broadcast="16-JUL-2026 18:00:00",
        ),
        _row(
            record_id="odd-date",
            report_date="23-JUN-2026",
            broadcast="24-JUN-2026 18:00:00",
        ),
        _row(
            record_id="late-old-backfill",
            report_date="31-DEC-2024",
            broadcast="04-JUN-2026 18:00:00",
        ),
        _row(
            record_id="q1",
            report_date="31-MAR-2026",
            broadcast="20-APR-2026 10:00:00",
        ),
    ]
    selected = select_latest_adjacent_quarter_filings(payload, symbol="ABC")
    assert [row.record_id for row in selected] == ["q2-revision", "q1"]
    assert [row.report_date for row in selected] == ["2026-06-30", "2026-03-31"]


def test_as_of_timestamp_prevents_future_revision_leakage() -> None:
    payload = [
        _row(
            record_id="q2-original",
            report_date="30-JUN-2026",
            broadcast="15-JUL-2026 18:00:00",
        ),
        _row(
            record_id="q2-future-revision",
            report_date="30-JUN-2026",
            broadcast="16-JUL-2026 18:00:00",
        ),
    ]
    selected = select_latest_revision_for_report_date(
        payload,
        symbol="ABC",
        report_date="2026-06-30",
        as_of_utc="2026-07-15T13:00:00Z",
    )
    assert selected is not None
    assert selected.record_id == "q2-original"
    assert selected.broadcast_at_utc == "2026-07-15T12:30:00Z"


def test_adjacent_quarter_selection_fails_closed_when_prior_quarter_missing() -> None:
    payload = [
        _row(
            record_id="q2",
            report_date="30-JUN-2026",
            broadcast="15-JUL-2026 18:00:00",
        ),
        _row(
            record_id="q4-old",
            report_date="31-DEC-2025",
            broadcast="20-JAN-2026 12:00:00",
        ),
    ]
    selected = select_latest_adjacent_quarter_filings(payload, symbol="ABC")
    assert len(selected) == 1
    assert selected[0].report_date == "2026-06-30"


def test_ownership_delta_is_percentage_points_and_requires_adjacent_periods() -> None:
    current = _parse(_xml(value="0.1011", report_date="2026-06-30"))
    prior = _parse(
        _xml(value="0.0875", report_date="2026-03-31"),
        report_date="2026-03-31",
    )
    assert ownership_delta_pp(current, prior) == pytest.approx(1.36)

    stale = _parse(
        _xml(value="0.08", report_date="2025-12-31"),
        report_date="2025-12-31",
    )
    with pytest.raises(H023OwnershipError, match="requires adjacent calendar quarters"):
        ownership_delta_pp(current, stale)


def test_contract_freezes_exact_source_semantics() -> None:
    contract = parser_contract()
    assert contract == {
        "context_ref": MF_CONTEXT_REF,
        "concept": MF_SHAREHOLDING_CONCEPT,
        "unit_ref": "pure",
        "value_semantics": "fraction_of_total_shares",
        "percentage_conversion": "fraction * 100",
        "context_period": "exact xbrli:instant equals selected NSE master report date",
        "detail_axis_guard": (
            "when Mutual Fund typed-member detail contexts exist, their dimension local-name "
            f"must equal {MF_DETAIL_AXIS}"
        ),
        "availability_timestamp": "NSE broadcastDate interpreted as Asia/Kolkata",
        "eligible_report_dates": "standard calendar quarter ends only",
        "prior_period": "immediately previous calendar quarter end",
        "revision_selection": "latest public broadcast for each selected report date as of evaluation",
    }
