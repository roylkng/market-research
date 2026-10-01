from marketlab.alpha_d010_p3 import ShortSellingRow
from marketlab.alpha_d010_p3b import (
    map_lagged_short_rows,
    summarize_p3b,
)
from marketlab.alpha_market import DailyEquityObservation


def _eq(day, symbol, isin):
    return DailyEquityObservation(
        session_date=day,
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


def test_p3b_maps_trade_date_identity_then_isin_continuity():
    result = map_lagged_short_rows(
        publication_session="2026-09-25",
        trade_session="2026-09-24",
        rows=[
            ShortSellingRow(
                security_name="Example",
                symbol="OLD",
                trade_date="2026-09-24",
                quantity=100.0,
            )
        ],
        trade_date_equities=[
            _eq("2026-09-24", "OLD", "INE000000001")
        ],
        publication_equities=[
            _eq("2026-09-25", "NEW", "INE000000001")
        ],
        raw_sha256="a" * 64,
        source_status="READY",
    )
    row = result["rows"][0]
    assert row["trade_date_mapped_isin"] == "INE000000001"
    assert row["publication_symbol"] == "NEW"
    assert row["publication_continuity_status"] == "SAME_ISIN_PRESENT"


def test_p3b_promotes_stable_high_coverage_source():
    sessions = []
    for index in range(20):
        sessions.append(
            {
                "publication_session": f"2026-09-{index + 1:02d}",
                "trade_session": f"2026-08-{index + 1:02d}",
                "source_status": "READY",
                "raw_sha256": "a" * 64,
                "source_row_count": 100,
                "trade_date_mapped_row_count": 99,
                "trade_date_unmatched_row_count": 1,
                "publication_continuity_row_count": 98,
                "publication_discontinuity_row_count": 1,
                "duplicate_symbol_row_count": 0,
                "duplicate_symbols": [],
                "rows": [],
            }
        )
    report = summarize_p3b(
        sessions,
        schemas=[
            (
                "Security Name",
                "Symbol Name",
                "Trade Date",
                "Quantity",
            )
        ] * 20,
    )
    assert report["historical_viability_pass"] is True
    assert report["status"] == "PROMOTE_P4_FEATURE_SEMANTICS"
