from __future__ import annotations

import csv
import io
import zipfile
from datetime import UTC, date, datetime

import pytest

from marketlab.intelligence_market_audit import MarketAuditError, build_market_audit
from marketlab.intelligence_store import ResearchStore

SESSION = date(2026, 9, 17)
CAPTURED = "2026-09-17T13:30:00+00:00"


def archive(rows):
    fields = [
        "TradDt", "Sgmt", "Src", "FinInstrmTp", "ISIN", "TckrSymb", "SctySrs",
        "OpnPric", "ClsPric", "PrvsClsgPric", "TtlTradgVol", "TtlTrfVal",
    ]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as zipped:
        zipped.writestr("bhav.csv", out.getvalue())
    return payload.getvalue()


def row(symbol, previous, close, *, open_price=None, turnover=50_000_000, series="EQ"):
    return {
        "TradDt": SESSION.isoformat(), "Sgmt": "CM", "Src": "NSE", "FinInstrmTp": "STK",
        "ISIN": "INE" + symbol.ljust(9, "X")[:9] + "1", "TckrSymb": symbol,
        "SctySrs": series, "OpnPric": open_price or previous, "ClsPric": close,
        "PrvsClsgPric": previous, "TtlTradgVol": "100000", "TtlTrfVal": str(turnover),
    }


def panel():
    return {"panel_id": "P", "members": [{"symbol": "AAA"}]}


def news(item_id, symbol, publication, first_seen, *, external=False):
    return {
        "item_id": item_id,
        "processed_at": first_seen,
        "first_seen_at": first_seen,
        "publication": {"value": publication, "precision": "SECOND"},
        "mentions": {
            "panel_symbols": [] if external else [symbol],
            "unverified_nse_symbols": [symbol] if external else [],
        },
        "topics": [{"topic": "orders"}],
    }


def test_official_market_is_denominator_and_liquidity_filter_is_explicit(tmp_path):
    raw = archive([
        row("AAA", 100, 110),
        row("BBB", 100, 94),
        row("ILLIQ", 100, 140, turnover=1_000_000),
        row("SME", 100, 150, series="SM"),
    ])
    with ResearchStore(tmp_path) as store:
        store.append("panel", "P", panel())
        report = build_market_audit(raw, session_date=SESSION, store=store, captured_at=CAPTURED)
    assert report["universe"]["eq_count"] == 3
    assert report["universe"]["liquid_eq_count"] == 2
    assert {r["symbol"] for r in report["movers"]} == {"AAA", "BBB"}
    assert next(r for r in report["movers"] if r["symbol"] == "AAA")["close_return_pct"] == pytest.approx(10)


def test_public_preopen_but_postclose_system_observation_is_not_a_prospective_hit(tmp_path):
    raw = archive([row("AAA", 100, 110)])
    with ResearchStore(tmp_path) as store:
        store.append("panel", "P", panel())
        store.append("news_item", "n1", news(
            "n1", "AAA", "2026-09-17T03:00:00+00:00", "2026-09-17T11:00:00+00:00"))
        report = build_market_audit(raw, session_date=SESSION, store=store, captured_at=CAPTURED)
    audit = report["movers"][0]["news_audit"]
    assert audit["public_timing"] == "PRE_OPEN"
    assert audit["system_timing"] == "POST_CLOSE"
    assert audit["coverage_class"] == "PUBLIC_PREOPEN_NOT_OBSERVED_IN_TIME"


def test_actual_preopen_observation_counts_as_system_hit(tmp_path):
    raw = archive([row("AAA", 100, 110)])
    with ResearchStore(tmp_path) as store:
        store.append("panel", "P", panel())
        store.append("news_item", "n1", news(
            "n1", "AAA", "2026-09-17T02:45:00+00:00", "2026-09-17T03:15:00+00:00"))
        report = build_market_audit(raw, session_date=SESSION, store=store, captured_at=CAPTURED)
    assert report["movers"][0]["news_audit"]["coverage_class"] == "SYSTEM_PREOPEN_HIT"


def test_intraday_observation_is_distinct_from_preopen(tmp_path):
    raw = archive([row("AAA", 100, 110)])
    with ResearchStore(tmp_path) as store:
        store.append("panel", "P", panel())
        store.append("news_item", "n1", news(
            "n1", "AAA", "2026-09-17T05:00:00+00:00", "2026-09-17T05:10:00+00:00"))
        report = build_market_audit(raw, session_date=SESSION, store=store, captured_at=CAPTURED)
    assert report["movers"][0]["news_audit"]["coverage_class"] == "SYSTEM_INTRADAY_HIT"


def test_external_symbol_can_be_audited_without_being_in_deep_panel(tmp_path):
    raw = archive([row("BBB", 100, 110)])
    with ResearchStore(tmp_path) as store:
        store.append("panel", "P", panel())
        store.append("news_item", "n1", news(
            "n1", "BBB", "2026-09-17T03:00:00+00:00", "2026-09-17T11:00:00+00:00",
            external=True))
        report = build_market_audit(raw, session_date=SESSION, store=store, captured_at=CAPTURED)
    mover = report["movers"][0]
    assert mover["in_deep_panel"] is False
    assert mover["news_audit"]["matched_item_ids"] == ["n1"]


def test_no_link_is_an_explicit_miss_not_neutral_sentiment(tmp_path):
    raw = archive([row("AAA", 100, 110)])
    with ResearchStore(tmp_path) as store:
        store.append("panel", "P", panel())
        report = build_market_audit(raw, session_date=SESSION, store=store, captured_at=CAPTURED)
    assert report["coverage_class_counts"] == {"NOT_DISCOVERED": 1}
    assert report["forecast"] is None
    assert report["live_capital_allowed"] is False


def test_top_abs_movers_are_retained_even_below_threshold(tmp_path):
    raw = archive([row("AAA", 100, 101), row("BBB", 100, 99.5), row("CCC", 100, 100.1)])
    with ResearchStore(tmp_path) as store:
        store.append("panel", "P", panel())
        report = build_market_audit(
            raw, session_date=SESSION, store=store, captured_at=CAPTURED,
            move_threshold_pct=5, top_abs_movers=2,
        )
    assert [r["symbol"] for r in report["movers"]] == ["AAA", "BBB"]
    assert report["universe"]["threshold_mover_count"] == 0


def test_wrong_session_or_duplicate_symbol_is_rejected(tmp_path):
    wrong = row("AAA", 100, 110)
    wrong["TradDt"] = "2026-09-16"
    with ResearchStore(tmp_path / "a") as store, pytest.raises(MarketAuditError, match="no NSE EQ"):
        build_market_audit(archive([wrong]), session_date=SESSION, store=store, captured_at=CAPTURED)
    with ResearchStore(tmp_path / "b") as store, pytest.raises(MarketAuditError, match="duplicate"):
        build_market_audit(
            archive([row("AAA", 100, 110), row("AAA", 100, 111)]),
            session_date=SESSION, store=store, captured_at=CAPTURED,
        )
