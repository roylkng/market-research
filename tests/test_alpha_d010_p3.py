from datetime import date

from marketlab.alpha_d010_p3 import (
    SHORT_SCHEMA,
    SLB_SCHEMA,
    build_p3_source_panel,
    map_source_rows,
    parse_short_selling,
    parse_slb_open_positions,
    summarize_p3,
)
from marketlab.alpha_market import DailyEquityObservation


def _eq(symbol="SBIN", isin="INE062A01020"):
    return DailyEquityObservation(
        session_date="2026-09-25",
        symbol=symbol,
        isin=isin,
        open_price=100.0,
        high_price=101.0,
        low_price=99.0,
        close_price=100.5,
        previous_close=100.0,
        volume=1000.0,
        turnover_inr=30_000_000.0,
        trade_count=100.0,
    )


def test_parse_short_selling_exact_schema_and_date():
    raw = (
        "Security Name,Symbol Name,Trade Date,Quantity\n"
        "STATE BANK OF INDIA,SBIN,25-Sep-2026,1,000\n"
    ).replace(",1,000", ',"1,000"').encode()
    rows, header = parse_short_selling(
        raw,
        session_date=date(2026, 9, 25),
    )
    assert header == SHORT_SCHEMA
    assert rows[0].symbol == "SBIN"
    assert rows[0].quantity == 1000.0


def test_parse_slb_exact_schema():
    raw = (
        b"Sr no,Security,Series,Outstanding Quantity at the end of the day\n"
        b"1,SBIN,EQ,2500\n"
    )
    rows, header = parse_slb_open_positions(raw)
    assert header == SLB_SCHEMA
    assert rows[0].symbol == "SBIN"
    assert rows[0].outstanding_quantity == 2500.0


def test_identity_mapping_retains_duplicates_without_aggregation():
    short_raw = (
        b"Security Name,Symbol Name,Trade Date,Quantity\n"
        b"STATE BANK OF INDIA,SBIN,25-Sep-2026,100\n"
        b"STATE BANK OF INDIA,SBIN,25-Sep-2026,200\n"
    )
    slb_raw = (
        b"Sr no,Security,Series,Outstanding Quantity at the end of the day\n"
        b"1,SBIN,EQ,300\n"
        b"2,SBIN,EQ,400\n"
    )
    short_rows, _ = parse_short_selling(
        short_raw,
        session_date=date(2026, 9, 25),
    )
    slb_rows, _ = parse_slb_open_positions(slb_raw)
    session = map_source_rows(
        short_rows=short_rows,
        slb_rows=slb_rows,
        equities=[_eq()],
        session_date="2026-09-25",
        short_raw_sha256="a" * 64,
        slb_raw_sha256="b" * 64,
    )
    assert session["short_selling"]["mapped_row_count"] == 2
    assert session["short_selling"]["duplicate_symbol_row_count"] == 1
    assert session["slb_open_positions"]["duplicate_symbol_series_row_count"] == 1
    assert len(session["short_selling"]["rows"]) == 2


def test_p3_promotes_when_frozen_coverage_and_identity_gates_pass():
    sessions = []
    for index in range(20):
        sessions.append(
            {
                "session_date": f"2026-09-{index + 1:02d}",
                "udiff_eq_count": 1000,
                "short_selling": {
                    "source_status": "READY",
                    "raw_sha256": "a" * 64,
                    "row_count": 10,
                    "mapped_row_count": 10,
                    "unmatched_row_count": 0,
                    "duplicate_symbol_row_count": 0,
                    "duplicate_symbols": [],
                    "rows": [],
                },
                "slb_open_positions": {
                    "source_status": "READY",
                    "raw_sha256": "b" * 64,
                    "row_count": 100,
                    "mapped_row_count": 99,
                    "unmatched_row_count": 1,
                    "duplicate_symbol_row_count": 0,
                    "duplicate_symbol_series_row_count": 0,
                    "duplicate_symbols": [],
                    "series_counts": {"EQ": 100},
                    "rows": [],
                },
            }
        )
    report = summarize_p3(
        sessions=sessions,
        short_schemas=[SHORT_SCHEMA] * 20,
        slb_schemas=[SLB_SCHEMA] * 20,
    )
    assert report["status"] == "PROMOTE_P4_FEATURE_SEMANTICS"
    assert report["return_labels_opened"] is False
    panel = build_p3_source_panel(
        sessions=sessions,
        report_sha256=report["report_sha256"],
    )
    assert panel["outcomes_attached"] is False
    assert len(panel["panel_sha256"]) == 64
