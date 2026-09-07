from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.execution import TradingCalendar, TradingSession

IST = ZoneInfo("Asia/Kolkata")
HOLIDAY_2025_SOURCE_URL = "https://nsearchives.nseindia.com/content/circulars/CMTR65587.pdf"
MUHURAT_2025_SOURCE_URL = "https://nsearchives.nseindia.com/content/circulars/CMTR70319.pdf"

# NSE/CMTR/65587, Capital Market Segment, dated 13-Dec-2024.
CM_HOLIDAYS_2025 = frozenset(
    {
        date(2025, 2, 26),
        date(2025, 3, 14),
        date(2025, 3, 31),
        date(2025, 4, 10),
        date(2025, 4, 14),
        date(2025, 4, 18),
        date(2025, 5, 1),
        date(2025, 8, 15),
        date(2025, 8, 27),
        date(2025, 10, 2),
        date(2025, 10, 21),
        date(2025, 10, 22),
        date(2025, 11, 5),
        date(2025, 12, 25),
    }
)
MUHURAT_2025_DATE = date(2025, 10, 21)


class HistoricalCalendarError(ValueError):
    """Raised when the mixed historical trading calendar cannot be proven exactly."""


def _canonical_hash(payload: Any) -> str:
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HistoricalCalendarError("historical calendar payload must be finite JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _sha256(value: str, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise HistoricalCalendarError(f"{field} must be a 64-character SHA-256")
    if any(character not in "0123456789abcdefABCDEF" for character in value):
        raise HistoricalCalendarError(f"{field} must contain only hexadecimal characters")
    return value.lower()


def _regular_session(day: date) -> TradingSession:
    opened = datetime.combine(day, time(9, 15), tzinfo=IST).astimezone(UTC)
    closed = datetime.combine(day, time(15, 30), tzinfo=IST).astimezone(UTC)
    return TradingSession(
        session_date=day.isoformat(),
        open_timestamp_utc=opened.isoformat().replace("+00:00", "Z"),
        close_timestamp_utc=closed.isoformat().replace("+00:00", "Z"),
    )


def _muhurat_session() -> TradingSession:
    opened = datetime.combine(MUHURAT_2025_DATE, time(13, 45), tzinfo=IST).astimezone(UTC)
    closed = datetime.combine(MUHURAT_2025_DATE, time(14, 45), tzinfo=IST).astimezone(UTC)
    return TradingSession(
        session_date=MUHURAT_2025_DATE.isoformat(),
        open_timestamp_utc=opened.isoformat().replace("+00:00", "Z"),
        close_timestamp_utc=closed.isoformat().replace("+00:00", "Z"),
    )


def sessions_2025(*, start_date: date = date(2025, 3, 1)) -> tuple[TradingSession, ...]:
    if start_date.year != 2025:
        raise HistoricalCalendarError("2025 calendar start_date must be in calendar year 2025")
    sessions: list[TradingSession] = []
    cursor = start_date
    end = date(2025, 12, 31)
    while cursor <= end:
        if cursor == MUHURAT_2025_DATE:
            sessions.append(_muhurat_session())
        elif cursor.weekday() < 5 and cursor not in CM_HOLIDAYS_2025:
            sessions.append(_regular_session(cursor))
        cursor += timedelta(days=1)
    return tuple(sessions)


def build_hr002_calendar(
    *,
    phase_a_2026_manifest: dict[str, Any],
    phase_a_2026_manifest_sha256: str,
    holiday_2025_raw_sha256: str,
    muhurat_2025_raw_sha256: str,
) -> tuple[TradingCalendar, dict[str, Any]]:
    phase_a_sha = _sha256(phase_a_2026_manifest_sha256, field="phase_a_2026_manifest_sha256")
    holiday_sha = _sha256(holiday_2025_raw_sha256, field="holiday_2025_raw_sha256")
    muhurat_sha = _sha256(muhurat_2025_raw_sha256, field="muhurat_2025_raw_sha256")
    if phase_a_2026_manifest.get("manifest_sha256") != phase_a_sha:
        raise HistoricalCalendarError("bound H002-HR001 Phase-A manifest SHA does not match document")
    calendar_payload = phase_a_2026_manifest.get("calendar_snapshot")
    if not isinstance(calendar_payload, dict):
        raise HistoricalCalendarError("H002-HR001 Phase-A manifest lacks frozen calendar snapshot")
    if calendar_payload.get("unresolved_special_dates"):
        raise HistoricalCalendarError("bound 2026 calendar has unresolved special sessions")
    try:
        sessions_2026 = tuple(
            TradingSession(**item) for item in calendar_payload.get("sessions", [])
        )
    except TypeError as exc:
        raise HistoricalCalendarError(f"invalid bound 2026 session: {exc}") from exc
    if not sessions_2026:
        raise HistoricalCalendarError("bound 2026 calendar contains no sessions")
    if any(not session.session_date.startswith("2026-") for session in sessions_2026):
        raise HistoricalCalendarError("bound 2026 calendar contains a session outside 2026")

    all_sessions = (*sessions_2025(), *sessions_2026)
    evidence = {
        "schema_version": 1,
        "build_rule": "H002-HR002-NSE-CM-2025-circular-plus-HR001-2026-v1",
        "holiday_2025_source_url": HOLIDAY_2025_SOURCE_URL,
        "holiday_2025_raw_sha256": holiday_sha,
        "muhurat_2025_source_url": MUHURAT_2025_SOURCE_URL,
        "muhurat_2025_raw_sha256": muhurat_sha,
        "bound_hr001_phase_a_manifest_sha256": phase_a_sha,
        "bound_2026_calendar_sha256": calendar_payload.get("sha256"),
        "session_count_2025": len(sessions_2025()),
        "session_count_2026": len(sessions_2026),
        "muhurat_2025": _muhurat_session().to_dict(),
    }
    version = "H002-HR002-CAL-" + _canonical_hash(evidence)[:24]
    calendar = TradingCalendar(list(all_sessions), version=version)
    evidence["trading_calendar_version"] = calendar.version
    evidence["trading_calendar_sha256"] = calendar.sha256
    return calendar, evidence
