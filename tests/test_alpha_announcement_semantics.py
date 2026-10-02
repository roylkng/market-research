import math
from datetime import date

import pytest

from marketlab.alpha import digest
from marketlab.alpha_announcement_semantics import (
    EXPECTED_ANNOUNCEMENT_PANEL_SHA256,
    HASH_DIMENSIONS,
    SEMANTIC_DEFINITIONS,
    announcement_ngrams,
    augment_feature_panel_with_hashed_semantics,
    hashed_semantic_vector,
    normalize_text,
)


def test_semantic_normalization_and_distinct_ngrams_are_deterministic():
    assert normalize_text("  Café—PROFIT  123  ") == [
        "caf",
        "profit",
        "123",
    ]
    terms = announcement_ngrams(
        desc="Profit profit rises",
        attachment_text="profit rises",
    )
    assert terms == tuple(sorted(set(terms)))
    assert terms.count("u:profit") == 1
    assert "b:profit_profit" in terms
    assert "b:profit_rises" in terms


def test_hashed_semantic_vector_is_64d_signed_and_l2_normalized():
    first = hashed_semantic_vector(
        desc="Order received from customer",
        attachment_text="Large contract award",
    )
    second = hashed_semantic_vector(
        desc="Order received from customer",
        attachment_text="Large contract award",
    )
    assert first == second
    assert len(first) == HASH_DIMENSIONS == 64
    assert math.sqrt(sum(value * value for value in first)) == pytest.approx(
        1.0
    )
    assert any(value > 0 for value in first)
    assert any(value < 0 for value in first)


def _source_dates():
    start = date(2025, 9, 1)
    end = date(2026, 9, 25)
    return [
        date.fromordinal(start.toordinal() + offset).isoformat()
        for offset in range((end - start).days + 1)
    ]


def _market_panel():
    panel = {
        "schema_version": 1,
        "panel_id": "TEST-MARKET",
        "sessions": [
            {
                "session_date": "2026-04-01",
                "equities": [
                    {
                        "session_date": "2026-04-01",
                        "symbol": "TEST",
                        "isin": "INE000000001",
                        "open_price": 100.0,
                        "high_price": 103.0,
                        "low_price": 99.0,
                        "close_price": 102.0,
                        "previous_close": 100.0,
                        "volume": 100000.0,
                        "turnover_inr": 30_000_000.0,
                        "trade_count": 1000.0,
                    },
                    {
                        "session_date": "2026-04-01",
                        "symbol": "ZERO",
                        "isin": "INE000000002",
                        "open_price": 100.0,
                        "high_price": 103.0,
                        "low_price": 99.0,
                        "close_price": 102.0,
                        "previous_close": 100.0,
                        "volume": 100000.0,
                        "turnover_inr": 30_000_000.0,
                        "trade_count": 1000.0,
                    },
                ],
            }
        ],
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _base_panel():
    definitions = [
        {
            "name": "momentum_20",
            "family": "price_trend",
            "version": "v1",
            "description": "test",
            "lookback_sessions": 20,
            "availability_lag_sessions": 0,
        }
    ]
    rows = [
        {
            "feature_session": "2026-04-01",
            "symbol": symbol,
            "isin": isin,
            "feature_set_sha256": "base",
            "values": {"momentum_20": 0.5},
        }
        for symbol, isin in (
            ("TEST", "INE000000001"),
            ("ZERO", "INE000000002"),
        )
    ]
    panel = {
        "schema_version": 1,
        "panel_id": "CORE27-TEST",
        "feature_definitions": definitions,
        "feature_set_sha256": "base",
        "rows": rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _announcement_panel():
    sessions = [
        {
            "calendar_date": day,
            "raw_sha256": "a" * 64,
            "announcement_count": 0,
            "announcements": [],
        }
        for day in _source_dates()
    ]
    by_day = {row["calendar_date"]: row for row in sessions}
    by_day["2026-04-01"]["announcements"] = [
        {
            "symbol": "TEST",
            "seq_id": "1",
            "announcement_id": "event1",
            "exchange_published_at_utc": "2026-04-01T10:30:00+00:00",
            "desc": "Large customer order",
            "attchmntText": "Contract awarded",
            "attchmntFile": "x.pdf",
        },
        {
            "symbol": "TEST",
            "seq_id": "2",
            "announcement_id": "event2",
            "exchange_published_at_utc": "2026-04-01T09:00:00+00:00",
            "desc": "Pre close result",
            "attchmntText": "Must not enter T012",
            "attchmntFile": "y.pdf",
        },
        {
            "symbol": "MISSING",
            "seq_id": "3",
            "announcement_id": "event3",
            "exchange_published_at_utc": "2026-04-01T10:40:00+00:00",
            "desc": "No same session identity",
            "attchmntText": "",
            "attchmntFile": "",
        },
    ]
    by_day["2026-04-01"]["announcement_count"] = 3
    panel = {
        "schema_version": 1,
        "panel_id": "AE001-T007-HISTORICAL-ANNOUNCEMENTS-v1",
        "source_start": "2025-09-01",
        "source_end": "2026-09-25",
        "daily_source_count": len(sessions),
        "announcement_count": 3,
        "sessions": sessions,
        "market_return_outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def test_semantic_augmentation_uses_only_same_day_postclose_text(monkeypatch):
    announcements = _announcement_panel()
    monkeypatch.setattr(
        "marketlab.alpha_announcement_semantics.EXPECTED_ANNOUNCEMENT_PANEL_SHA256",
        announcements["panel_sha256"],
    )
    augmented = augment_feature_panel_with_hashed_semantics(
        feature_panel=_base_panel(),
        market_panel=_market_panel(),
        announcement_panel=announcements,
    )
    assert augmented["panel_id"] == "AE001-T012-CORE91-v1"
    assert augmented["feature_row_count"] == 2
    assert len(SEMANTIC_DEFINITIONS) == 64
    assert augmented["semantic_eligible_event_count"] == 1
    assert augmented["semantic_excluded_preclose_count"] == 1
    assert augmented["semantic_excluded_no_identity_count"] == 1

    rows = {row["symbol"]: row for row in augmented["rows"]}
    test_values = [
        rows["TEST"]["values"][f"annsem_hash_{index:02d}"]
        for index in range(64)
    ]
    zero_values = [
        rows["ZERO"]["values"][f"annsem_hash_{index:02d}"]
        for index in range(64)
    ]
    expected = hashed_semantic_vector(
        desc="Large customer order",
        attachment_text="Contract awarded",
    )
    assert test_values == pytest.approx(expected)
    assert zero_values == pytest.approx([0.0] * 64)
    assert set(rows) == {"TEST", "ZERO"}


def test_semantic_source_hash_is_frozen():
    assert len(EXPECTED_ANNOUNCEMENT_PANEL_SHA256) == 64
