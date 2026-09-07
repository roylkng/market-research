from __future__ import annotations

from marketlab.h002_historical_calendar import (
    MUHURAT_2025_DATE,
    build_hr002_calendar,
    sessions_2025,
)


def _phase_a_manifest() -> dict:
    return {
        "manifest_sha256": "a" * 64,
        "calendar_snapshot": {
            "sha256": "b" * 64,
            "unresolved_special_dates": [],
            "sessions": [
                {
                    "session_date": "2026-01-02",
                    "open_timestamp_utc": "2026-01-02T03:45:00Z",
                    "close_timestamp_utc": "2026-01-02T10:00:00Z",
                },
                {
                    "session_date": "2026-01-05",
                    "open_timestamp_utc": "2026-01-05T03:45:00Z",
                    "close_timestamp_utc": "2026-01-05T10:00:00Z",
                },
            ],
        },
    }


def test_2025_calendar_excludes_holidays_but_keeps_muhurat_as_special_session():
    sessions = {item.session_date: item for item in sessions_2025()}
    assert "2025-03-14" not in sessions
    assert "2025-04-18" not in sessions
    assert "2025-10-22" not in sessions
    assert MUHURAT_2025_DATE.isoformat() in sessions
    muhurat = sessions[MUHURAT_2025_DATE.isoformat()]
    assert muhurat.open_timestamp_utc == "2025-10-21T08:15:00Z"
    assert muhurat.close_timestamp_utc == "2025-10-21T09:15:00Z"


def test_hr002_calendar_binds_exact_2025_sources_and_frozen_2026_calendar():
    calendar, evidence = build_hr002_calendar(
        phase_a_2026_manifest=_phase_a_manifest(),
        phase_a_2026_manifest_sha256="a" * 64,
        holiday_2025_raw_sha256="c" * 64,
        muhurat_2025_raw_sha256="d" * 64,
    )
    assert calendar.session("2025-10-21").close_timestamp_utc == "2025-10-21T09:15:00Z"
    assert calendar.session("2026-01-02").open_timestamp_utc == "2026-01-02T03:45:00Z"
    assert evidence["holiday_2025_raw_sha256"] == "c" * 64
    assert evidence["muhurat_2025_raw_sha256"] == "d" * 64
    assert evidence["bound_hr001_phase_a_manifest_sha256"] == "a" * 64
    assert evidence["trading_calendar_sha256"] == calendar.sha256
