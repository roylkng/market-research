from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.execution import ExecutionError, TradingCalendar, TradingSession

IST = ZoneInfo("Asia/Kolkata")
CALENDAR_BUILD_RULE = "nse-cm-weekday-minus-official-holidays-v1"
HOLIDAY_SOURCE_URL = "https://www.nseindia.com/api/holiday-master?type=trading"


class CalendarSnapshotError(ValueError):
    """Raised when an explicit NSE calendar cannot be frozen without guessing."""


@dataclass(frozen=True)
class SpecialSession:
    session_date: str
    open_timestamp_utc: str
    close_timestamp_utc: str
    source_url: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class CalendarSnapshot:
    schema_version: int
    sha256: str
    version: str
    build_rule: str
    captured_at_utc: str
    source_url: str
    source_sha256: str
    start_date: str
    end_date: str
    sessions: tuple[TradingSession, ...]
    holidays: tuple[str, ...]
    unresolved_special_dates: tuple[str, ...]
    special_sessions: tuple[SpecialSession, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sessions"] = [session.to_dict() for session in self.sessions]
        payload["holidays"] = list(self.holidays)
        payload["unresolved_special_dates"] = list(self.unresolved_special_dates)
        payload["special_sessions"] = [session.to_dict() for session in self.special_sessions]
        return payload

    def trading_calendar_for_event(self, exchange_published_at_utc: str) -> TradingCalendar:
        calendar = TradingCalendar(list(self.sessions), version=self.version)
        publication = _timestamp(exchange_published_at_utc, "exchange_published_at_utc")
        local_date = publication.astimezone(IST).date()
        unresolved = [date.fromisoformat(value) for value in self.unresolved_special_dates]
        if any(value <= local_date for value in unresolved):
            raise CalendarSnapshotError(
                "calendar has an unresolved special-session date on/before the event; "
                "refresh the frozen calendar before scoring"
            )
        try:
            _, exit_session = calendar.schedule(exchange_published_at_utc)
        except ExecutionError as exc:
            raise CalendarSnapshotError(str(exc)) from exc
        exit_date = date.fromisoformat(exit_session.session_date)
        if any(local_date < value <= exit_date for value in unresolved):
            raise CalendarSnapshotError(
                "paper-position horizon crosses an unresolved special-session date"
            )
        return calendar


def _canonical_hash(payload: Any) -> str:
    try:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    except (TypeError, ValueError) as exc:
        raise CalendarSnapshotError("calendar payload must contain finite JSON values") from exc
    return hashlib.sha256(encoded).hexdigest()


def _timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise CalendarSnapshotError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise CalendarSnapshotError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _session_for_regular_day(day: date) -> TradingSession:
    opened = datetime.combine(day, time(9, 15), tzinfo=IST).astimezone(UTC)
    closed = datetime.combine(day, time(15, 30), tzinfo=IST).astimezone(UTC)
    return TradingSession(
        session_date=day.isoformat(),
        open_timestamp_utc=opened.isoformat().replace("+00:00", "Z"),
        close_timestamp_utc=closed.isoformat().replace("+00:00", "Z"),
    )


def _parse_holiday_date(value: Any) -> date:
    if not isinstance(value, str):
        raise CalendarSnapshotError("holiday tradingDate must be a string")
    try:
        return datetime.strptime(value.strip(), "%d-%b-%Y").date()
    except ValueError as exc:
        raise CalendarSnapshotError(f"invalid holiday tradingDate: {value}") from exc


def build_calendar_snapshot(
    holiday_payload: Any,
    *,
    raw_holiday_bytes: bytes,
    start_date: date,
    end_date: date,
    captured_at: datetime,
    version: str,
    special_sessions: tuple[SpecialSession, ...] = (),
) -> CalendarSnapshot:
    if start_date > end_date:
        raise CalendarSnapshotError("calendar start_date must not exceed end_date")
    if captured_at.tzinfo is None:
        raise CalendarSnapshotError("calendar captured_at must include timezone")
    if not isinstance(version, str) or not version.strip():
        raise CalendarSnapshotError("calendar version is required")
    if not raw_holiday_bytes:
        raise CalendarSnapshotError("exact holiday source bytes are required")
    if not isinstance(holiday_payload, dict) or not isinstance(holiday_payload.get("CM"), list):
        raise CalendarSnapshotError("holiday master must contain CM list")

    holiday_dates: set[date] = set()
    unresolved_special: set[date] = set()
    for row in holiday_payload["CM"]:
        if not isinstance(row, dict):
            raise CalendarSnapshotError("CM holiday row must be an object")
        holiday = _parse_holiday_date(row.get("tradingDate"))
        if start_date <= holiday <= end_date:
            holiday_dates.add(holiday)
            description = str(row.get("description") or "")
            if "*" in description or "laxmi pujan" in description.casefold():
                unresolved_special.add(holiday)

    special_by_date: dict[date, SpecialSession] = {}
    for special in special_sessions:
        try:
            day = date.fromisoformat(special.session_date)
        except ValueError as exc:
            raise CalendarSnapshotError(
                f"invalid special session date: {special.session_date}"
            ) from exc
        if day in special_by_date:
            raise CalendarSnapshotError(f"duplicate special session date: {day}")
        opened = _timestamp(special.open_timestamp_utc, "special session open")
        closed = _timestamp(special.close_timestamp_utc, "special session close")
        if (
            opened >= closed
            or opened.astimezone(IST).date() != day
            or closed.astimezone(IST).date() != day
        ):
            raise CalendarSnapshotError(f"invalid special session timestamps: {day}")
        if not special.source_url.strip():
            raise CalendarSnapshotError(f"special session source URL is required: {day}")
        special_by_date[day] = special
        unresolved_special.discard(day)

    sessions: list[TradingSession] = []
    cursor = start_date
    while cursor <= end_date:
        if cursor in special_by_date:
            special = special_by_date[cursor]
            sessions.append(
                TradingSession(
                    session_date=special.session_date,
                    open_timestamp_utc=special.open_timestamp_utc,
                    close_timestamp_utc=special.close_timestamp_utc,
                )
            )
        elif cursor.weekday() < 5 and cursor not in holiday_dates:
            sessions.append(_session_for_regular_day(cursor))
        cursor += timedelta(days=1)

    provisional = {
        "schema_version": 1,
        "version": version,
        "build_rule": CALENDAR_BUILD_RULE,
        "captured_at_utc": captured_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "source_url": HOLIDAY_SOURCE_URL,
        "source_sha256": hashlib.sha256(raw_holiday_bytes).hexdigest(),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "sessions": [session.to_dict() for session in sessions],
        "holidays": sorted(value.isoformat() for value in holiday_dates),
        "unresolved_special_dates": sorted(value.isoformat() for value in unresolved_special),
        "special_sessions": [value.to_dict() for _, value in sorted(special_by_date.items())],
    }
    return CalendarSnapshot(
        sha256=_canonical_hash(provisional),
        sessions=tuple(sessions),
        holidays=tuple(provisional["holidays"]),
        unresolved_special_dates=tuple(provisional["unresolved_special_dates"]),
        special_sessions=tuple(value for _, value in sorted(special_by_date.items())),
        **{
            key: value
            for key, value in provisional.items()
            if key not in {"sessions", "holidays", "unresolved_special_dates", "special_sessions"}
        },
    )


def load_calendar_snapshot(path: str | Path) -> CalendarSnapshot:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CalendarSnapshotError(f"could not read calendar snapshot {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CalendarSnapshotError("calendar snapshot root must be an object")
    declared = payload.get("sha256")
    unsigned = dict(payload)
    unsigned.pop("sha256", None)
    if not isinstance(declared, str) or _canonical_hash(unsigned) != declared:
        raise CalendarSnapshotError("calendar snapshot SHA-256 mismatch")
    try:
        sessions = tuple(TradingSession(**row) for row in payload["sessions"])
        specials = tuple(SpecialSession(**row) for row in payload.get("special_sessions", []))
        snapshot = CalendarSnapshot(
            schema_version=payload["schema_version"],
            sha256=declared,
            version=payload["version"],
            build_rule=payload["build_rule"],
            captured_at_utc=payload["captured_at_utc"],
            source_url=payload["source_url"],
            source_sha256=payload["source_sha256"],
            start_date=payload["start_date"],
            end_date=payload["end_date"],
            sessions=sessions,
            holidays=tuple(payload["holidays"]),
            unresolved_special_dates=tuple(payload.get("unresolved_special_dates", [])),
            special_sessions=specials,
        )
    except (KeyError, TypeError) as exc:
        raise CalendarSnapshotError(f"invalid calendar snapshot: {exc}") from exc
    if snapshot.schema_version != 1 or snapshot.build_rule != CALENDAR_BUILD_RULE:
        raise CalendarSnapshotError("unsupported calendar snapshot schema/build rule")
    TradingCalendar(list(snapshot.sessions), version=snapshot.version)
    return snapshot
