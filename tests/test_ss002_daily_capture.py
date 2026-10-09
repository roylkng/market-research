from __future__ import annotations

import csv
import io
import json
from datetime import date

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss002_daily_capture import (
    build_daily_capture,
    classify_capture_lag,
    deterministic_gzip,
    raw_sha256,
)
from scripts.run_ss002_p001_daily import pending_source_dates


def _master() -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        [
            "SYMBOL",
            "NAME OF COMPANY",
            "SERIES",
            "DATE OF LISTING",
            "PAID UP VALUE",
            "MARKET LOT",
            "ISIN NUMBER",
            "FACE VALUE",
        ]
    )
    writer.writerow(
        ["ABC", "ABC LIMITED", "EQ", "01-Jan-2020", "10", "1", "INE000A01001", "10"]
    )
    writer.writerow(
        ["BEONLY", "BE LIMITED", "BE", "01-Jan-2020", "10", "1", "INE000B01001", "10"]
    )
    return stream.getvalue().encode()


def _announcement_rows() -> list[dict]:
    return [
        {
            "symbol": "ABC",
            "seq_id": "1000001",
            "exchdisstime": "09-Oct-2026 20:12:00",
            "desc": "Buyback",
            "attchmntText": "Proposed buyback of USD-denominated bonds.",
            "attchmntFile": "https://nsearchives.nseindia.com/corporate/abc.pdf",
        },
        {
            "symbol": "BEONLY",
            "seq_id": "1000002",
            "exchdisstime": "09-Oct-2026 21:12:00",
            "desc": "Open Offer",
            "attchmntText": "Proposed open offer to public shareholders.",
            "attchmntFile": "",
        },
        {
            "symbol": "ABC",
            "seq_id": "1000003",
            "exchdisstime": "09-Oct-2026 21:30:00",
            "desc": "General Update",
            "attchmntText": "Office address change.",
            "attchmntFile": "",
        },
    ]


def _capture() -> dict:
    rows = _announcement_rows()
    raw = json.dumps(rows).encode()
    return build_daily_capture(
        source_day=date(2026, 10, 9),
        announcement_payload=rows,
        announcement_raw=raw,
        equity_master_raw=_master(),
        acquired_at_utc="2026-10-10T06:35:00Z",
    )


def test_capture_keeps_full_source_and_routes_only_category_hints() -> None:
    c = _capture()
    assert c["announcement_count"] == 3
    assert c["candidate_event_count"] == 2
    assert c["candidate_current_eq_event_count"] == 1
    assert c["candidate_mapping_state_counts"] == {
        "ARCHIVAL_OR_UNMATCHED_AT_CAPTURE": 1,
        "SYMBOL_IN_EQ_MASTER_AT_CAPTURE": 1,
    }
    by_symbol = {row["symbol"]: row for row in c["candidate_events"]}
    assert by_symbol["ABC"]["category_hints_only"] == ["BUYBACK"]
    assert by_symbol["ABC"]["economic_relevance_verified"] is False
    assert by_symbol["ABC"]["current_eq_isin_at_capture"] == "INE000A01001"
    assert by_symbol["BEONLY"]["mapping_state"] == "ARCHIVAL_OR_UNMATCHED_AT_CAPTURE"
    assert len({row["announcement_id"] for row in c["announcements"]}) == 3
    assert c["return_outcomes_opened"] is False
    assert c["portfolio_eligibility_allowed"] is False


def test_raw_and_gzip_hashes_preserve_exact_evidence() -> None:
    c = _capture()
    rows = _announcement_rows()
    raw = json.dumps(rows).encode()
    source = c["sources"]["announcement"]
    assert source["raw_sha256"] == raw_sha256(raw)
    assert source["gzip_sha256"] == raw_sha256(deterministic_gzip(raw))
    assert c["sources"]["eq_master"]["as_of"] == "ACQUISITION_TIME_NOT_SOURCE_DAY"


def test_capture_rejects_payload_mismatch_and_wrong_day() -> None:
    rows = _announcement_rows()
    raw = json.dumps(rows).encode()
    with pytest.raises(AlphaContractError, match="differs from raw source"):
        build_daily_capture(
            source_day=date(2026, 10, 9),
            announcement_payload=rows[:-1],
            announcement_raw=raw,
            equity_master_raw=_master(),
            acquired_at_utc="2026-10-10T06:35:00Z",
        )
    with pytest.raises(Exception, match="outside requested window"):
        build_daily_capture(
            source_day=date(2026, 10, 8),
            announcement_payload=rows,
            announcement_raw=raw,
            equity_master_raw=_master(),
            acquired_at_utc="2026-10-10T06:35:00Z",
        )


def test_lag_state_fails_closed_before_completed_date() -> None:
    assert classify_capture_lag(
        date(2026, 10, 9), observed_at_utc="2026-10-10T05:30:00Z"
    ) == "NEXT_DAY_SOURCE_CAPTURE"
    assert classify_capture_lag(
        date(2026, 10, 5), observed_at_utc="2026-10-10T05:30:00Z"
    ) == "HISTORICAL_BACKFILL_CAPTURED_LATER"
    with pytest.raises(AlphaContractError, match="full India-local source day"):
        classify_capture_lag(
            date(2026, 10, 9), observed_at_utc="2026-10-09T10:30:00Z"
        )


def test_pending_date_resolver_is_bounded_and_idempotent(tmp_path) -> None:
    dates = pending_source_dates(
        tmp_path,
        today_ist=date(2026, 10, 15),
        start_date=None,
        end_date=None,
    )
    assert len(dates) == 7
    assert dates[0] == date(2026, 10, 5)
    assert dates[-1] == date(2026, 10, 11)
    (tmp_path / "2026-10-05-v1.json").write_text("immutable")
    dates2 = pending_source_dates(
        tmp_path,
        today_ist=date(2026, 10, 15),
        start_date=None,
        end_date=None,
    )
    assert dates2[0] == date(2026, 10, 6)
    with pytest.raises(AlphaContractError, match="before today"):
        pending_source_dates(
            tmp_path,
            today_ist=date(2026, 10, 10),
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 10),
        )
