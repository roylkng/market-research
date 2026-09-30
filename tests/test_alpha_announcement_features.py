from datetime import date

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_announcement_features import (
    ANNOUNCEMENT_DEFINITIONS,
    SOURCE_END,
    SOURCE_START,
    augment_feature_panel_with_announcements,
    build_announcement_source_panel,
    classify_topics,
)


def _all_days():
    return [
        date.fromordinal(SOURCE_START.toordinal() + offset).isoformat()
        for offset in range((SOURCE_END - SOURCE_START).days + 1)
    ]


def _raw_row(symbol, seq, timestamp, text):
    return {
        "symbol": symbol,
        "seq_id": seq,
        "exchdisstime": timestamp,
        "desc": text,
        "attchmntText": "",
        "attchmntFile": (
            "https://nsearchives.nseindia.com/"
            f"corporate/{symbol}-{seq}.pdf"
        ),
    }


def test_t007_taxonomy_is_multilabel_and_direction_free():
    topics = classify_topics(
        {
            "desc": "New order and capacity investment",
            "attchmntText": "Company plans capex for customer contract",
        }
    )
    assert "ORDER_CUSTOMER" in topics
    assert "CAPACITY_INVESTMENT" in topics
    assert "GOVERNANCE_RISK" not in topics


def test_t007_source_panel_requires_every_frozen_calendar_day():
    days = _all_days()
    payloads = {day: [] for day in days}
    hashes = {day: f"{index + 1:064x}" for index, day in enumerate(days)}
    payloads["2026-09-17"] = [
        _raw_row(
            "INFY",
            "1",
            "17-Sep-2026 16:00:00",
            "Company wins customer order",
        )
    ]
    panel = build_announcement_source_panel(
        daily_payloads=payloads,
        daily_raw_sha256=hashes,
    )
    assert panel["daily_source_count"] == len(days)
    assert panel["announcement_count"] == 1
    event = next(
        row
        for session in panel["sessions"]
        for row in session["announcements"]
    )
    assert event["material"] is True
    assert event["topics"] == ["ORDER_CUSTOMER"]
    assert len(panel["panel_sha256"]) == 64

    payloads.pop(days[0])
    with pytest.raises(AlphaContractError, match="exactly cover"):
        build_announcement_source_panel(
            daily_payloads=payloads,
            daily_raw_sha256=hashes,
        )


def _market_panel():
    sessions = []
    for index, day in enumerate(("2026-09-16", "2026-09-17", "2026-09-18")):
        sessions.append(
            {
                "session_date": day,
                "equities": [
                    {
                        "session_date": day,
                        "symbol": "TEST",
                        "isin": "INE000000001",
                        "open_price": 100.0 + index,
                        "high_price": 102.0 + index,
                        "low_price": 99.0 + index,
                        "close_price": 101.0 + index,
                        "previous_close": 100.0 + index,
                        "volume": 100000.0,
                        "turnover_inr": 30000000.0,
                        "trade_count": 1000.0,
                    },
                    {
                        "session_date": day,
                        "symbol": "QUIET",
                        "isin": "INE000000002",
                        "open_price": 50.0,
                        "high_price": 51.0,
                        "low_price": 49.0,
                        "close_price": 50.5,
                        "previous_close": 50.0,
                        "volume": 100000.0,
                        "turnover_inr": 30000000.0,
                        "trade_count": 1000.0,
                    },
                ],
            }
        )
    panel = {
        "schema_version": 1,
        "panel_id": "TEST-MARKET",
        "sessions": sessions,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _feature_panel():
    rows = []
    for day in ("2026-09-16", "2026-09-17", "2026-09-18"):
        for symbol, isin in (
            ("TEST", "INE000000001"),
            ("QUIET", "INE000000002"),
        ):
            rows.append(
                {
                    "feature_session": day,
                    "symbol": symbol,
                    "isin": isin,
                    "values": {"base": 1.0},
                    "feature_set_sha256": "base",
                }
            )
    panel = {
        "schema_version": 1,
        "panel_id": "BASE",
        "feature_definitions": [
            {
                "name": "base",
                "family": "price_trend",
                "version": "v1",
                "description": "base",
                "lookback_sessions": 1,
                "availability_lag_sessions": 0,
            }
        ],
        "feature_set_sha256": "base",
        "rows": rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _announcement_panel():
    days = _all_days()
    sessions = [
        {
            "calendar_date": day,
            "raw_sha256": f"{index + 1:064x}",
            "announcement_count": 0,
            "announcements": [],
        }
        for index, day in enumerate(days)
    ]
    by_day = {row["calendar_date"]: row for row in sessions}
    by_day["2026-09-17"]["announcements"] = [
        {
            "announcement_id": "a" * 64,
            "symbol": "TEST",
            "seq_id": "1",
            "exchange_published_at_utc": "2026-09-17T10:30:00+00:00",
            "desc": "order",
            "attchmntText": "",
            "attchmntFile": "https://nsearchives.nseindia.com/a.pdf",
            "topics": ["ORDER_CUSTOMER"],
            "material": True,
        },
        {
            "announcement_id": "b" * 64,
            "symbol": "MISSING",
            "seq_id": "2",
            "exchange_published_at_utc": "2026-09-17T11:00:00+00:00",
            "desc": "capacity",
            "attchmntText": "",
            "attchmntFile": "https://nsearchives.nseindia.com/b.pdf",
            "topics": ["CAPACITY_INVESTMENT"],
            "material": True,
        },
    ]
    by_day["2026-09-17"]["announcement_count"] = 2
    # 19:00 IST, therefore maps to the next completed session, Sep 18.
    by_day["2026-09-17"]["announcements"].append(
        {
            "announcement_id": "c" * 64,
            "symbol": "TEST",
            "seq_id": "3",
            "exchange_published_at_utc": "2026-09-17T13:30:00+00:00",
            "desc": "guidance",
            "attchmntText": "",
            "attchmntFile": "https://nsearchives.nseindia.com/c.pdf",
            "topics": ["RESULTS_GUIDANCE"],
            "material": True,
        }
    )
    by_day["2026-09-17"]["announcement_count"] = 3
    panel = {
        "schema_version": 1,
        "panel_id": "AE001-T007-HISTORICAL-ANNOUNCEMENTS-v1",
        "trial_id": "AE001-T007-v1",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "source_start": SOURCE_START.isoformat(),
        "source_end": SOURCE_END.isoformat(),
        "daily_source_count": len(days),
        "announcement_count": 3,
        "sessions": sessions,
        "market_return_outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def test_t007_augmentation_preserves_quiet_rows_and_maps_cutoffs():
    augmented = augment_feature_panel_with_announcements(
        feature_panel=_feature_panel(),
        market_panel=_market_panel(),
        announcement_panel=_announcement_panel(),
    )
    assert augmented["feature_row_count"] == 6
    assert augmented["announcement_feature_count"] == len(
        ANNOUNCEMENT_DEFINITIONS
    )
    assert augmented["announcement_mapped_event_count"] == 2
    assert augmented[
        "announcement_excluded_no_same_session_eq_identity"
    ] == 1

    by_key = {
        (row["feature_session"], row["symbol"]): row["values"]
        for row in augmented["rows"]
    }
    sep17 = by_key[("2026-09-17", "TEST")]
    assert sep17["ann_total_current"] == 1.0
    assert sep17["ann_material_current"] == 1.0
    assert sep17["ann_order_customer_current"] == 1.0
    assert sep17["ann_results_guidance_current"] == 0.0
    assert sep17["ann_material_5"] == 1.0
    assert sep17["ann_sessions_since_material_cap20"] == 0.0
    assert sep17["ann_after_close_material_current"] == 1.0

    sep18 = by_key[("2026-09-18", "TEST")]
    assert sep18["ann_total_current"] == 1.0
    assert sep18["ann_results_guidance_current"] == 1.0
    assert sep18["ann_material_5"] == 2.0

    quiet = by_key[("2026-09-18", "QUIET")]
    assert quiet["ann_total_current"] == 0.0
    assert quiet["ann_material_20"] == 0.0
    assert quiet["ann_sessions_since_material_cap20"] == 20.0
