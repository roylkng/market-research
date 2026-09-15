from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from marketlab.h024_acquisition import canonical_hash
from marketlab.h024_historical import HORIZONS
from marketlab.h024_prospective import PROTOCOL_ID, H024ProspectiveError

SESSION_LEDGER_VERSION = 1


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise H024ProspectiveError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise H024ProspectiveError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H024ProspectiveError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise H024ProspectiveError("timestamp must include timezone")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _record_hash(record: dict[str, Any], field: str) -> str:
    return canonical_hash({key: value for key, value in record.items() if key != field})


def _ledger_hash(ledger: dict[str, Any]) -> str:
    return canonical_hash({key: value for key, value in ledger.items() if key != "ledger_sha256"})


def new_session_ledger() -> dict[str, Any]:
    ledger = {
        "schema_version": SESSION_LEDGER_VERSION,
        "protocol_id": PROTOCOL_ID,
        "record_count": 0,
        "records": [],
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def session_id(session_date: str) -> str:
    if not isinstance(session_date, str) or not session_date:
        raise H024ProspectiveError("H024 observed session date is invalid")
    return canonical_hash(
        {
            "protocol_id": PROTOCOL_ID,
            "record_type": "OBSERVED_COMPLETED_NSE_SESSION",
            "session_date": session_date,
        }
    )


def build_session_record(
    *, benchmark_bar: dict[str, Any], observed_at_utc: str
) -> dict[str, Any]:
    required = {
        "benchmark_id",
        "index_name",
        "session_date",
        "open_price",
        "close_price",
        "source_url",
        "raw_sha256",
    }
    if not isinstance(benchmark_bar, dict) or not required.issubset(benchmark_bar):
        raise H024ProspectiveError("H024 observed-session benchmark evidence is incomplete")
    if benchmark_bar["benchmark_id"] != "nifty_500" or benchmark_bar["index_name"] != "Nifty 500":
        raise H024ProspectiveError("H024 observed session is not evidenced by Nifty 500")
    if not _is_sha256(benchmark_bar["raw_sha256"]):
        raise H024ProspectiveError("H024 observed-session raw hash is invalid")
    if not isinstance(benchmark_bar["source_url"], str) or not benchmark_bar[
        "source_url"
    ].startswith("https://"):
        raise H024ProspectiveError("H024 observed-session source URL is invalid")
    observed = _timestamp(observed_at_utc, field="session.observed_at_utc")
    session_date = str(benchmark_bar["session_date"])
    record: dict[str, Any] = {
        "session_id": session_id(session_date),
        "session_date": session_date,
        "benchmark_bar": dict(benchmark_bar),
        "observed_at_utc": _utc_text(observed),
    }
    record["session_record_sha256"] = _record_hash(record, "session_record_sha256")
    validate_session_record(record)
    return record


def validate_session_record(record: dict[str, Any]) -> None:
    required = {
        "session_id",
        "session_date",
        "benchmark_bar",
        "observed_at_utc",
        "session_record_sha256",
    }
    if not isinstance(record, dict) or not required.issubset(record):
        raise H024ProspectiveError("H024 observed-session record is incomplete")
    day = str(record["session_date"])
    if record["session_id"] != session_id(day):
        raise H024ProspectiveError("H024 observed-session identity mismatch")
    bar = record["benchmark_bar"]
    if not isinstance(bar, dict) or str(bar.get("session_date") or "") != day:
        raise H024ProspectiveError("H024 observed-session benchmark date mismatch")
    if bar.get("benchmark_id") != "nifty_500" or bar.get("index_name") != "Nifty 500":
        raise H024ProspectiveError("H024 observed-session benchmark identity mismatch")
    if not _is_sha256(bar.get("raw_sha256")):
        raise H024ProspectiveError("H024 observed-session benchmark hash is invalid")
    _timestamp(record["observed_at_utc"], field="session.observed_at_utc")
    if record["session_record_sha256"] != _record_hash(record, "session_record_sha256"):
        raise H024ProspectiveError("H024 observed-session record digest mismatch")


def validate_session_ledger(ledger: dict[str, Any]) -> None:
    if not isinstance(ledger, dict):
        raise TypeError("H024 observed-session ledger must be an object")
    if (
        ledger.get("schema_version") != SESSION_LEDGER_VERSION
        or ledger.get("protocol_id") != PROTOCOL_ID
    ):
        raise H024ProspectiveError("H024 observed-session ledger header is invalid")
    if not isinstance(ledger.get("records"), list):
        raise H024ProspectiveError("H024 observed-session ledger records must be a list")
    if ledger.get("record_count") != len(ledger["records"]):
        raise H024ProspectiveError("H024 observed-session ledger record count mismatch")
    if ledger.get("ledger_sha256") != _ledger_hash(ledger):
        raise H024ProspectiveError("H024 observed-session ledger digest mismatch")
    seen: set[str] = set()
    prior_day: str | None = None
    for record in ledger["records"]:
        validate_session_record(record)
        day = str(record["session_date"])
        if day in seen:
            raise H024ProspectiveError("duplicate H024 observed completed session")
        seen.add(day)
        if prior_day is not None and day <= prior_day:
            raise H024ProspectiveError("H024 observed-session ledger is not increasing")
        prior_day = day


def append_session(ledger: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    validate_session_ledger(ledger)
    validate_session_record(record)
    day = str(record["session_date"])
    existing = [row for row in ledger["records"] if row["session_date"] == day]
    if existing:
        if existing[0] != record:
            # A repeated official archive observation may occur later. The first exact
            # prospective observation remains canonical rather than silently rewriting it.
            first_bar = existing[0]["benchmark_bar"]
            new_bar = record["benchmark_bar"]
            if first_bar != new_bar:
                raise H024ProspectiveError(
                    f"{day}: H024 observed-session official evidence changed"
                )
        return ledger
    records = [dict(row) for row in ledger["records"]] + [record]
    records.sort(key=lambda row: str(row["session_date"]))
    result = dict(ledger)
    result["records"] = records
    result["record_count"] = len(records)
    result["ledger_sha256"] = _ledger_hash(result)
    validate_session_ledger(result)
    return result


def observed_horizon_exit_session(
    ledger: dict[str, Any], *, entry_session: str, horizon: int
) -> dict[str, Any] | None:
    validate_session_ledger(ledger)
    if horizon not in HORIZONS:
        raise H024ProspectiveError(f"unsupported H024 horizon: {horizon}")
    dates = [str(row["session_date"]) for row in ledger["records"]]
    try:
        entry_index = dates.index(entry_session)
    except ValueError:
        return None
    target = entry_index + horizon - 1
    if target >= len(ledger["records"]):
        return None
    return dict(ledger["records"][target])


def observed_session_count_from_entry(
    ledger: dict[str, Any], *, entry_session: str
) -> int:
    validate_session_ledger(ledger)
    dates = [str(row["session_date"]) for row in ledger["records"]]
    try:
        entry_index = dates.index(entry_session)
    except ValueError:
        return 0
    return len(dates) - entry_index
