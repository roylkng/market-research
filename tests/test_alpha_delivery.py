import csv
import io
from datetime import UTC, date, datetime, timedelta

import pytest

from marketlab.alpha import digest
from marketlab.alpha_delivery import (
    acquire_historical_delivery_panel,
    augment_feature_panel_with_delivery,
    delivery_session_quality,
    parse_sec_bhavdata_full,
)
from marketlab.alpha_market import DailyEquityObservation


def _csv(day: str, *, symbol: str = "TEST", series: str = "EQ") -> bytes:
    fields = [
        " SYMBOL",
        " SERIES",
        " DATE1",
        " PREV_CLOSE",
        " OPEN_PRICE",
        " HIGH_PRICE",
        " LOW_PRICE",
        " LAST_PRICE",
        " CLOSE_PRICE",
        " AVG_PRICE",
        " TTL_TRD_QNTY",
        " TURNOVER_LACS",
        " NO_OF_TRADES",
        " DELIV_QTY",
        " DELIV_PER",
    ]
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    writer.writerow(
        {
            " SYMBOL": f" {symbol}",
            " SERIES": f" {series}",
            " DATE1": f" {day}",
            " PREV_CLOSE": " 100",
            " OPEN_PRICE": " 101",
            " HIGH_PRICE": " 103",
            " LOW_PRICE": " 100",
            " LAST_PRICE": " 102",
            " CLOSE_PRICE": " 102",
            " AVG_PRICE": " 101.5",
            " TTL_TRD_QNTY": " 1000",
            " TURNOVER_LACS": " 1.015",
            " NO_OF_TRADES": " 100",
            " DELIV_QTY": " 400",
            " DELIV_PER": " 40.00",
        }
    )
    return text.getvalue().encode()


def test_delivery_parser_strips_nse_whitespace_and_reads_eq_fields():
    parsed = parse_sec_bhavdata_full(
        _csv("25-Sep-2026"),
        session_date=date(2026, 9, 25),
    )
    assert len(parsed) == 1
    row = parsed[0]
    assert row.symbol == "TEST"
    assert row.delivery_qty == 400.0
    assert row.delivery_pct == pytest.approx(0.40)
    assert row.avg_price == 101.5


def test_delivery_source_quality_excludes_internally_inconsistent_session():
    raw = _csv("25-Sep-2026").replace(b" 40.00", b" 60.00")
    rows = parse_sec_bhavdata_full(
        raw,
        session_date=date(2026, 9, 25),
    )
    quality = delivery_session_quality(rows)
    assert quality["status"] == "EXCLUDE_SESSION_INTERNAL_FIELD_INCONSISTENCY"
    assert quality["violating_row_count"] == 1
    assert quality["max_abs_diff_pp"] > 0.05


def test_delivery_acquisition_requires_every_market_session():
    sessions = ["2026-09-24", "2026-09-25"]

    def fetcher(url):
        day = "24-Sep-2026" if "24092026" in url else "25-Sep-2026"
        return _csv(day)

    panel = acquire_historical_delivery_panel(
        session_dates=sessions,
        fetcher=fetcher,
        captured_at_utc=datetime(2026, 9, 27, tzinfo=UTC),
    )
    assert panel["session_count"] == 2
    assert panel["excluded_source_quality_session_count"] == 0
    assert len(panel["panel_sha256"]) == 64
    assert panel["historical_archives_captured_prospectively"] is False


def _panels(count=21):
    start = date(2026, 1, 1)
    market_sessions = []
    delivery_sessions = []
    close = 100.0
    for index in range(count):
        day = start + timedelta(days=index)
        prior = close
        open_price = prior * 1.001
        close = open_price * (1.0 + index * 0.0001)
        market = DailyEquityObservation(
            session_date=day.isoformat(),
            symbol="TEST",
            isin="INE000000001",
            open_price=open_price,
            high_price=max(open_price, close) * 1.01,
            low_price=min(open_price, close) * 0.99,
            close_price=close,
            previous_close=prior,
            volume=1000 + index,
            turnover_inr=10_000_000 + index,
            trade_count=100 + index,
        )
        market_sessions.append(
            {
                "session_date": day.isoformat(),
                "equities": [market.__dict__],
            }
        )
        delivery_sessions.append(
            {
                "session_date": day.isoformat(),
                "source_url": "https://nsearchives.nseindia.com/x",
                "raw_sha256": f"{index + 1:064x}",
                "source_quality": {
                    "status": "READY",
                    "complete_row_count": 1,
                    "violating_row_count": 0,
                    "max_abs_diff_pp": 0.0,
                    "tolerance_pp": 0.05,
                },
                "rows": [
                    {
                        "session_date": day.isoformat(),
                        "symbol": "TEST",
                        "avg_price": (open_price + close) / 2.0,
                        "traded_qty": 1000 + index,
                        "turnover_lacs": 10.0,
                        "trade_count": 100 + index,
                        "delivery_qty": 400 + index,
                        "delivery_pct": (400 + index) / (1000 + index),
                    }
                ],
            }
        )

    market_panel = {
        "schema_version": 1,
        "panel_id": "TEST-MARKET",
        "sessions": market_sessions,
        "live_capital_allowed": False,
    }
    market_panel["panel_sha256"] = digest(market_panel)
    delivery_panel = {
        "schema_version": 1,
        "panel_id": "AE001-HISTORICAL-DELIVERY-v1",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "historical_archives_captured_prospectively": False,
        "session_count": len(delivery_sessions),
        "source_quality_policy": (
            "EXCLUDE_WHOLE_SESSION_IF_ANY_COMPLETE_EQ_ROW_HAS_"
            "ABS_DELIV_PER_VS_QTY_RATIO_DIFF_GT_0_05_PERCENTAGE_POINTS"
        ),
        "excluded_source_quality_session_count": 0,
        "excluded_source_quality_sessions": [],
        "sessions": delivery_sessions,
        "live_capital_allowed": False,
    }
    delivery_panel["panel_sha256"] = digest(delivery_panel)

    final_day = market_sessions[-1]["session_date"]
    feature_panel = {
        "schema_version": 1,
        "panel_id": "BASE-ACTION-SAFE",
        "feature_definitions": [
            {
                "name": "base_feature",
                "family": "price_trend",
                "version": "v1",
                "description": "base",
                "lookback_sessions": 1,
                "availability_lag_sessions": 0,
            }
        ],
        "feature_set_sha256": "base",
        "sessions": [
            {
                "session_date": final_day,
                "eligible_count": 1,
                "universe_sha256": "old",
            }
        ],
        "rows": [
            {
                "feature_session": final_day,
                "decision_timestamp": f"{final_day}T18:30:00+05:30",
                "symbol": "TEST",
                "isin": "INE000000001",
                "universe_sha256": "old",
                "feature_set_sha256": "base",
                "values": {"base_feature": 0.5},
                "known_at": f"{final_day}T18:00:00+05:30",
                "outcomes_attached": False,
            }
        ],
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    feature_panel["panel_sha256"] = digest(feature_panel)
    return market_panel, delivery_panel, feature_panel


def test_delivery_augmentation_binds_symbol_to_same_session_isin():
    market, delivery, features = _panels()
    augmented = augment_feature_panel_with_delivery(
        feature_panel=features,
        market_panel=market,
        delivery_panel=delivery,
    )
    assert augmented["feature_row_count"] == 1
    row = augmented["rows"][0]
    assert row["isin"] == "INE000000001"
    assert row["values"]["delivery_pct"] is not None
    assert row["values"]["delivery_qty_surprise_20"] is not None
    assert len(row["values"]) == 10
    assert augmented["delivery_join_contract"].endswith("SYMBOL_PLUS_ISIN")


def test_delivery_augmentation_excludes_missing_delivery_history():
    market, delivery, features = _panels()
    delivery["sessions"][10]["rows"] = []
    unsigned = dict(delivery)
    unsigned.pop("panel_sha256", None)
    delivery["panel_sha256"] = digest(unsigned)
    augmented = augment_feature_panel_with_delivery(
        feature_panel=features,
        market_panel=market,
        delivery_panel=delivery,
    )
    assert augmented["feature_row_count"] == 0
    assert augmented["delivery_missing_excluded_row_count"] == 1
    assert augmented["delivery_noncontiguous_excluded_row_count"] == 0


def test_delivery_augmentation_excludes_noncontiguous_21_observation_window():
    market, delivery, features = _panels(count=22)
    delivery["sessions"][10]["rows"] = []
    unsigned = dict(delivery)
    unsigned.pop("panel_sha256", None)
    delivery["panel_sha256"] = digest(unsigned)
    augmented = augment_feature_panel_with_delivery(
        feature_panel=features,
        market_panel=market,
        delivery_panel=delivery,
    )
    assert augmented["feature_row_count"] == 0
    assert augmented["delivery_noncontiguous_excluded_row_count"] == 1
