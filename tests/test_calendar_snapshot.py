from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from marketlab.calendar_snapshot import (
    CalendarSnapshotError,
    build_calendar_snapshot,
    load_calendar_snapshot,
)


def _holiday_payload():
    return {
        "CM": [
            {"tradingDate": "14-Sep-2026", "description": "Ganesh Chaturthi"},
            {"tradingDate": "02-Oct-2026", "description": "Mahatma Gandhi Jayanti"},
            {"tradingDate": "08-Nov-2026", "description": "Diwali Laxmi Pujan*"},
        ]
    }


def test_calendar_builds_explicit_regular_sessions_and_hashes(tmp_path):
    snapshot = build_calendar_snapshot(
        _holiday_payload(),
        raw_holiday_bytes=b'{"CM":[]}',
        start_date=date(2026, 9, 1),
        end_date=date(2026, 11, 30),
        captured_at=datetime(2026, 9, 6, tzinfo=UTC),
        version="NSE-CM-2026Q4-v1",
    )
    assert "2026-09-14" not in {item.session_date for item in snapshot.sessions}
    assert "2026-11-08" in snapshot.unresolved_special_dates
    assert len(snapshot.sha256) == 64

    path = tmp_path / "calendar.json"
    import json

    path.write_text(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True) + "\n")
    loaded = load_calendar_snapshot(path)
    assert loaded.sha256 == snapshot.sha256


def test_calendar_allows_event_whose_20_session_window_finishes_before_unresolved_special():
    snapshot = build_calendar_snapshot(
        _holiday_payload(),
        raw_holiday_bytes=b"x",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 11, 30),
        captured_at=datetime(2026, 9, 6, tzinfo=UTC),
        version="test",
    )
    calendar = snapshot.trading_calendar_for_event("2026-09-01T12:00:00Z")
    entry, _ = calendar.schedule("2026-09-01T12:00:00Z")
    assert entry.session_date == "2026-09-03"


def test_calendar_refuses_horizon_crossing_unresolved_muhurat_session():
    snapshot = build_calendar_snapshot(
        _holiday_payload(),
        raw_holiday_bytes=b"x",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 12, 31),
        captured_at=datetime(2026, 9, 6, tzinfo=UTC),
        version="test",
    )
    with pytest.raises(CalendarSnapshotError, match="unresolved special-session"):
        snapshot.trading_calendar_for_event("2026-10-15T12:00:00Z")
