from datetime import UTC, datetime

import pytest

from marketlab.universe import UniverseError, build_universe_snapshot


def _quote(symbol: str, macro: str) -> dict:
    return {
        "info": {"isin": f"ISIN-{symbol}", "listingDate": "01-Jan-2000"},
        "industryInfo": {
            "macro": macro,
            "sector": f"sector-{symbol}",
            "industry": f"industry-{symbol}",
            "basicIndustry": f"basic-{symbol}",
        },
    }


def test_selects_top_non_financial_companies_by_ffmc():
    index = {
        "timestamp": "06-Sep-2026 15:30:00",
        "data": [
            {"symbol": "NIFTY 200", "ffmc": 99999},
            {"symbol": "AAA", "ffmc": 600},
            {"symbol": "BANK", "ffmc": 550},
            {"symbol": "CCC", "ffmc": 500},
            {"symbol": "BBB", "ffmc": 500},
            {"symbol": "DDD", "ffmc": 400},
        ],
    }
    quotes = {
        "AAA": _quote("AAA", "Information Technology"),
        "BANK": _quote("BANK", "Financial Services"),
        "BBB": _quote("BBB", "Industrials"),
        "CCC": _quote("CCC", "Healthcare"),
        "DDD": _quote("DDD", "Consumer Discretionary"),
    }

    snapshot = build_universe_snapshot(
        index,
        quotes.__getitem__,
        cohort_id="FY27-Q2",
        selection_size=3,
        captured_at=datetime(2026, 9, 6, 10, 0, tzinfo=UTC),
    )

    assert [member.symbol for member in snapshot.members] == ["AAA", "BBB", "CCC"]
    assert [member.source_rank for member in snapshot.members] == [1, 3, 4]
    assert snapshot.members[1].ffmc == 500
    assert len(snapshot.sha256) == 64


def test_snapshot_hash_is_deterministic():
    index = {"timestamp": "x", "data": [{"symbol": "AAA", "ffmc": 100}]}
    quotes = {"AAA": _quote("AAA", "Information Technology")}
    captured = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)

    one = build_universe_snapshot(
        index, quotes.__getitem__, cohort_id="C", selection_size=1, captured_at=captured
    )
    two = build_universe_snapshot(
        index, quotes.__getitem__, cohort_id="C", selection_size=1, captured_at=captured
    )
    assert one.sha256 == two.sha256
    assert one.to_dict() == two.to_dict()


def test_missing_macro_is_fatal_not_silently_skipped():
    index = {
        "data": [
            {"symbol": "AAA", "ffmc": 100},
            {"symbol": "BBB", "ffmc": 90},
        ]
    }
    quotes = {
        "AAA": {"info": {"isin": "A"}, "industryInfo": {}},
        "BBB": _quote("BBB", "Industrials"),
    }

    with pytest.raises(UniverseError, match="missing NSE macro-sector metadata for AAA"):
        build_universe_snapshot(index, quotes.__getitem__, cohort_id="C", selection_size=1)


def test_too_few_non_financial_names_fails():
    index = {"data": [{"symbol": "BANK", "ffmc": 100}]}
    quotes = {"BANK": _quote("BANK", "Financial Services")}

    with pytest.raises(UniverseError, match="could select only 0"):
        build_universe_snapshot(index, quotes.__getitem__, cohort_id="C", selection_size=1)
