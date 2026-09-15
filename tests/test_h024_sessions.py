from __future__ import annotations

from datetime import date, timedelta

import pytest

from marketlab.h024_prospective import H024ProspectiveError
from marketlab.h024_sessions import (
    append_session,
    build_session_record,
    new_session_ledger,
    observed_horizon_exit_session,
    observed_session_count_from_entry,
    validate_session_ledger,
)


def _bar(day: str, *, digest: str = "a" * 64, close: float = 1000.0) -> dict:
    return {
        "benchmark_id": "nifty_500",
        "index_name": "Nifty 500",
        "session_date": day,
        "open_price": close - 5.0,
        "close_price": close,
        "source_url": (
            "https://archives.nseindia.com/content/indices/"
            f"ind_close_all_{date.fromisoformat(day).strftime('%d%m%Y')}.csv"
        ),
        "raw_sha256": digest,
    }


def _append(ledger: dict, day: str, *, digest: str = "a" * 64) -> dict:
    return append_session(
        ledger,
        build_session_record(
            benchmark_bar=_bar(day, digest=digest),
            observed_at_utc=f"{day}T12:30:00Z",
        ),
    )


def test_observed_sessions_are_append_only_and_increasing() -> None:
    ledger = new_session_ledger()
    ledger = _append(ledger, "2026-09-16")
    ledger = _append(ledger, "2026-09-17")
    validate_session_ledger(ledger)

    assert ledger["record_count"] == 2
    assert [row["session_date"] for row in ledger["records"]] == [
        "2026-09-16",
        "2026-09-17",
    ]


def test_repeat_observation_keeps_first_prospective_freeze() -> None:
    ledger = _append(new_session_ledger(), "2026-09-16")
    repeated = append_session(
        ledger,
        build_session_record(
            benchmark_bar=_bar("2026-09-16"),
            observed_at_utc="2026-09-17T12:30:00Z",
        ),
    )

    assert repeated == ledger
    assert repeated["records"][0]["observed_at_utc"] == "2026-09-16T12:30:00Z"


def test_official_snapshot_drift_fails_closed() -> None:
    ledger = _append(new_session_ledger(), "2026-09-16")
    changed = build_session_record(
        benchmark_bar=_bar("2026-09-16", digest="b" * 64),
        observed_at_utc="2026-09-17T12:30:00Z",
    )

    with pytest.raises(H024ProspectiveError, match="official evidence changed"):
        append_session(ledger, changed)


def test_horizon_uses_observed_sessions_not_calendar_days() -> None:
    ledger = new_session_ledger()
    cursor = date(2026, 9, 17)
    observed_days: list[str] = []
    while len(observed_days) < 25:
        if cursor.weekday() < 5:
            observed_days.append(cursor.isoformat())
            ledger = _append(ledger, cursor.isoformat())
        cursor += timedelta(days=1)

    exit_record = observed_horizon_exit_session(
        ledger,
        entry_session="2026-09-17",
        horizon=20,
    )
    assert exit_record is not None
    assert exit_record["session_date"] == observed_days[19]
    assert observed_session_count_from_entry(ledger, entry_session="2026-09-17") == 25


def test_observed_horizon_crosses_forward_calendar_boundary_without_prediction() -> None:
    ledger = new_session_ledger()
    cursor = date(2026, 9, 17)
    observed_days: list[str] = []
    while len(observed_days) < 130:
        if cursor.weekday() < 5:
            observed_days.append(cursor.isoformat())
            ledger = _append(ledger, cursor.isoformat())
        cursor += timedelta(days=1)

    exit_record = observed_horizon_exit_session(
        ledger,
        entry_session="2026-09-17",
        horizon=120,
    )
    assert exit_record is not None
    assert exit_record["session_date"] == observed_days[119]
    assert date.fromisoformat(exit_record["session_date"]) > date(2026, 12, 31)


def test_special_weekend_session_is_counted_when_officially_observed() -> None:
    ledger = new_session_ledger()
    for day in ("2026-10-16", "2026-10-17", "2026-10-19"):
        ledger = _append(ledger, day)

    assert [row["session_date"] for row in ledger["records"]] == [
        "2026-10-16",
        "2026-10-17",
        "2026-10-19",
    ]
