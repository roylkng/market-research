from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from marketlab.calendar_snapshot import CalendarSnapshot
from marketlab.paperfund_state import validate_fund_state


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("PF001 calendar close timestamp is required")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("PF001 calendar close timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def next_pending_pf001_session(
    calendar: CalendarSnapshot,
    *,
    states: list[dict[str, Any]],
    now: datetime,
) -> str | None:
    """Return the oldest completed frozen NSE session not yet processed by PF001."""

    if now.tzinfo is None:
        raise ValueError("PF001 scheduler now must be timezone-aware")
    if not states:
        raise ValueError("PF001 scheduler requires at least one fund state")

    last_sessions: set[str | None] = set()
    for state in states:
        errors = validate_fund_state(state)
        if errors:
            raise ValueError({"pf001_state_errors": errors})
        last = state.get("last_session_date")
        if last is not None and not isinstance(last, str):
            raise ValueError("PF001 last_session_date must be string or null")
        last_sessions.add(last)

    if len(last_sessions) != 1:
        raise ValueError(
            "PF001 books are out of sync and cannot advance automatically: "
            f"{sorted(str(value) for value in last_sessions)}"
        )
    last_session = next(iter(last_sessions))
    now_utc = now.astimezone(UTC)

    pending: list[str] = []
    for session in calendar.sessions:
        session_date = str(session.session_date)
        if last_session is not None and session_date <= last_session:
            continue
        if _timestamp(session.close_timestamp_utc) <= now_utc:
            pending.append(session_date)

    return min(pending) if pending else None
