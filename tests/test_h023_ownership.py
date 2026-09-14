from __future__ import annotations

import pytest

from marketlab.h023_ownership import (
    MF_CONTEXT_REF,
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
        "availability_timestamp": "NSE broadcastDate interpreted as Asia/Kolkata",
        "eligible_report_dates": "standard calendar quarter ends only",
        "prior_period": "immediately previous calendar quarter end",
        "revision_selection": "latest public broadcast for each selected report date as of evaluation",
    }
