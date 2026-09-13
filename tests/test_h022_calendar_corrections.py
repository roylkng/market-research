from __future__ import annotations

from datetime import date

from marketlab.h022_outcomes import build_frozen_sessions


def test_union_budget_sunday_session_is_registered() -> None:
    sessions = build_frozen_sessions(
        start_date=date(2026, 1, 30),
        end_date=date(2026, 2, 2),
    )
    by_date = {row.session_date: row for row in sessions}

    assert by_date["2026-02-01"].special is True
    assert by_date["2026-02-01"].open_timestamp_utc == "2026-02-01T03:45:00Z"
    assert by_date["2026-02-01"].close_timestamp_utc == "2026-02-01T10:00:00Z"
