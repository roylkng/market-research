from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests

from marketlab.h024_acquisition import sha256_bytes, utc_now_text
from marketlab.h024_events import PRIMARY_EVENT_STATUS, validate_event_ledger
from marketlab.h024_historical import HORIZONS, parse_share_action_audit
from marketlab.h024_outcomes import (
    append_entry,
    append_outcome,
    build_entry_record,
    build_outcome_record,
    entry_by_event,
    horizon_exit_session,
    new_entry_ledger,
    new_outcome_ledger,
    outcome_exists,
    validate_entry_ledger,
    validate_outcome_ledger,
)
from marketlab.h024_prospective import validate_calendar
from marketlab.marketdata import index_snapshot_url, udiff_url
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.pf001_marketdata import (
    PF001MarketDataError,
    PF001MarketDataMissingRow,
    parse_pf001_nifty500_index,
    parse_pf001_udiff_equity,
)

IST = ZoneInfo("Asia/Kolkata")
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/152.0 Safari/537.36"
)
PROSPECTIVE_START_DATE = date(2026, 9, 16)


class H024OutcomeAdvanceError(RuntimeError):
    """Raised when prospective H024 outcome state cannot advance without guessing."""


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise H024OutcomeAdvanceError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _load_or_initialize(path: Path, factory) -> dict[str, Any]:
    return _load_json(path) if path.exists() else factory()


def _fetch_archive(
    http: requests.Session,
    url: str,
    *,
    attempts: int,
    timeout: float,
) -> bytes | None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = http.get(url, timeout=timeout)
            if response.status_code == 404:
                return None
            if (
                response.status_code in {403, 429} or response.status_code >= 500
            ) and attempt < attempts:
                time.sleep(0.75 * (2 ** (attempt - 1)))
                continue
            response.raise_for_status()
            if not response.content:
                raise H024OutcomeAdvanceError(f"NSE archive returned empty bytes: {url}")
            return response.content
        except (requests.RequestException, H024OutcomeAdvanceError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(0.75 * (2 ** (attempt - 1)))
                continue
            break
    raise H024OutcomeAdvanceError(f"NSE archive fetch failed for {url}: {last_error}") from last_error


def _retain_raw(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise H024OutcomeAdvanceError(f"raw evidence path collision: {path}")
    path.write_bytes(raw)


def _calendar_session_by_date(calendar: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["session_date"]: row for row in validate_calendar(calendar)}


def _session_completed(
    session: dict[str, Any], *, as_of: date, now_utc: datetime
) -> bool:
    session_day = date.fromisoformat(str(session["session_date"]))
    if session_day < as_of:
        return True
    if session_day > as_of:
        return False
    close = datetime.fromisoformat(str(session["close_timestamp_utc"]))
    if close.tzinfo is None:
        raise H024OutcomeAdvanceError("H024 calendar close lacks timezone")
    return now_utc >= close.astimezone(UTC)


def _index_bar(
    http: requests.Session,
    *,
    session_date: date,
    raw_dir: Path,
    attempts: int,
    timeout: float,
) -> dict[str, Any] | None:
    url = index_snapshot_url(session_date)
    raw = _fetch_archive(http, url, attempts=attempts, timeout=timeout)
    if raw is None:
        return None
    digest = sha256_bytes(raw)
    _retain_raw(raw_dir / "index" / f"{session_date.isoformat()}-{digest[:12]}.csv", raw)
    parsed = parse_pf001_nifty500_index(raw, session_date=session_date)
    return {**parsed.to_dict(), "source_url": url, "raw_sha256": digest}


def _stock_bar(
    http: requests.Session,
    *,
    symbol: str,
    session_date: date,
    raw_dir: Path,
    attempts: int,
    timeout: float,
) -> tuple[bool, dict[str, Any] | None]:
    url = udiff_url(session_date)
    raw = _fetch_archive(http, url, attempts=attempts, timeout=timeout)
    if raw is None:
        return False, None
    digest = sha256_bytes(raw)
    _retain_raw(raw_dir / "udiff" / f"{session_date.isoformat()}-{digest[:12]}.csv.zip", raw)
    try:
        parsed = parse_pf001_udiff_equity(
            raw,
            symbol=symbol,
            session_date=session_date,
        )
    except PF001MarketDataMissingRow:
        return True, None
    return True, {**parsed.to_dict(), "source_url": url, "raw_sha256": digest}


def _audit_recent_unregistered_sessions(
    http: requests.Session,
    *,
    calendar: dict[str, Any],
    as_of: date,
    raw_dir: Path,
    attempts: int,
    timeout: float,
    lookback_days: int,
) -> list[str]:
    expected = set(_calendar_session_by_date(calendar))
    start = max(PROSPECTIVE_START_DATE, as_of - timedelta(days=lookback_days - 1))
    cursor = start
    audited: list[str] = []
    while cursor <= as_of:
        day = cursor.isoformat()
        if day in expected:
            cursor += timedelta(days=1)
            continue
        url = index_snapshot_url(cursor)
        raw = _fetch_archive(http, url, attempts=attempts, timeout=timeout)
        if raw is None:
            audited.append(day)
            cursor += timedelta(days=1)
            continue
        digest = sha256_bytes(raw)
        _retain_raw(raw_dir / "calendar-probes" / f"{day}-{digest[:12]}.csv", raw)
        try:
            parse_pf001_nifty500_index(raw, session_date=cursor)
        except PF001MarketDataMissingRow:
            audited.append(day)
            cursor += timedelta(days=1)
            continue
        except PF001MarketDataError as exc:
            raise H024OutcomeAdvanceError(
                f"unregistered-session probe parser failed for {day}: {exc}"
            ) from exc
        raise H024OutcomeAdvanceError(
            f"official Nifty 500 snapshot exposes unregistered H024 special session: {day}"
        )
    return audited


def _corporate_action_audit(
    client: NSEClient,
    *,
    symbol: str,
    entry_date: str,
    exit_date: str,
    raw_dir: Path,
    event_id: str,
    horizon: int,
) -> tuple[dict[str, Any], str, str] | None:
    try:
        payload, raw = client.corporate_actions_with_raw(
            symbol,
            from_date=date.fromisoformat(entry_date).strftime("%d-%m-%Y"),
            to_date=date.fromisoformat(exit_date).strftime("%d-%m-%Y"),
        )
    except NSEAcquisitionError:
        return None
    query = urlencode(
        {
            "index": "equities",
            "symbol": symbol,
            "from_date": date.fromisoformat(entry_date).strftime("%d-%m-%Y"),
            "to_date": date.fromisoformat(exit_date).strftime("%d-%m-%Y"),
        }
    )
    source_url = f"{client.CORPORATE_ACTION_ENDPOINT.url}?{query}"
    digest = sha256_bytes(raw)
    _retain_raw(
        raw_dir
        / "corporate-actions"
        / f"{event_id[:12]}-{horizon}-{digest[:12]}.json",
        raw,
    )
    return parse_share_action_audit(payload, symbol=symbol), source_url, digest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Advance frozen H024 prospective entry and outcome evidence"
    )
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--special-session-lookback-days", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if (
        args.attempts < 1
        or args.timeout_seconds <= 0
        or args.special_session_lookback_days < 1
    ):
        raise H024OutcomeAdvanceError("invalid H024 outcome-advance configuration")

    now_utc = datetime.now(UTC)
    as_of = (
        date.fromisoformat(args.as_of_date)
        if args.as_of_date is not None
        else now_utc.astimezone(IST).date()
    )
    if as_of < PROSPECTIVE_START_DATE:
        raise H024OutcomeAdvanceError("H024 outcomes cannot advance before prospective start")

    calendar = _load_json(args.calendar)
    sessions_by_date = _calendar_session_by_date(calendar)
    event_ledger = _load_json(args.state_dir / "event-ledger.json")
    validate_event_ledger(event_ledger)
    entry_path = args.state_dir / "entry-ledger.json"
    outcome_path = args.state_dir / "outcome-ledger.json"
    entry_ledger = _load_or_initialize(entry_path, new_entry_ledger)
    outcome_ledger = _load_or_initialize(outcome_path, new_outcome_ledger)
    validate_entry_ledger(entry_ledger)
    validate_outcome_ledger(outcome_ledger)

    http = requests.Session()
    http.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    audited_non_sessions = _audit_recent_unregistered_sessions(
        http,
        calendar=calendar,
        as_of=as_of,
        raw_dir=args.raw_dir,
        attempts=args.attempts,
        timeout=args.timeout_seconds,
        lookback_days=args.special_session_lookback_days,
    )

    started_at = utc_now_text()
    start_entry_count = int(entry_ledger["record_count"])
    start_outcome_count = int(outcome_ledger["record_count"])
    pending: Counter[str] = Counter()
    new_entry_statuses: Counter[str] = Counter()
    new_outcome_statuses: Counter[str] = Counter()
    index_cache: dict[str, dict[str, Any] | None] = {}
    stock_cache: dict[tuple[str, str], tuple[bool, dict[str, Any] | None]] = {}

    def index_bar(day: str) -> dict[str, Any] | None:
        if day not in index_cache:
            index_cache[day] = _index_bar(
                http,
                session_date=date.fromisoformat(day),
                raw_dir=args.raw_dir,
                attempts=args.attempts,
                timeout=args.timeout_seconds,
            )
        return index_cache[day]

    def stock_bar(symbol: str, day: str) -> tuple[bool, dict[str, Any] | None]:
        key = (symbol, day)
        if key not in stock_cache:
            stock_cache[key] = _stock_bar(
                http,
                symbol=symbol,
                session_date=date.fromisoformat(day),
                raw_dir=args.raw_dir,
                attempts=args.attempts,
                timeout=args.timeout_seconds,
            )
        return stock_cache[key]

    primary_events = [
        row for row in event_ledger["records"] if row["status"] == PRIMARY_EVENT_STATUS
    ]
    primary_events.sort(
        key=lambda row: (str(row["planned_entry_session"]), str(row["symbol"]))
    )

    for event in primary_events:
        event_id = str(event["event_id"])
        if entry_by_event(entry_ledger, event_id) is not None:
            continue
        entry_session = str(event["planned_entry_session"])
        calendar_entry = sessions_by_date.get(entry_session)
        if calendar_entry is None:
            raise H024OutcomeAdvanceError(
                f"{event_id}: planned entry session disappeared from reviewed calendar"
            )
        if not _session_completed(calendar_entry, as_of=as_of, now_utc=now_utc):
            pending["ENTRY_SESSION_NOT_COMPLETE"] += 1
            continue
        benchmark = index_bar(entry_session)
        if benchmark is None:
            pending["ENTRY_BENCHMARK_ARCHIVE_PENDING"] += 1
            continue
        archive_ready, stock = stock_bar(str(event["symbol"]), entry_session)
        if not archive_ready:
            pending["ENTRY_UDIFF_ARCHIVE_PENDING"] += 1
            continue
        record = build_entry_record(
            event=event,
            stock_bar=stock,
            benchmark_bar=benchmark,
            observed_at_utc=utc_now_text(),
        )
        entry_ledger = append_entry(entry_ledger, record)
        new_entry_statuses[
            str(record["status"])
            if record["status"] == "READY"
            else f"BLOCKED:{record['block_reason']}"
        ] += 1

    action_client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    for event in primary_events:
        event_id = str(event["event_id"])
        entry = entry_by_event(entry_ledger, event_id)
        if entry is None:
            continue
        for horizon in HORIZONS:
            if outcome_exists(outcome_ledger, event_id, horizon):
                continue
            exit_session = horizon_exit_session(
                calendar,
                entry_session=str(event["planned_entry_session"]),
                horizon=horizon,
            )
            if exit_session is None:
                pending["CALENDAR_EXTENSION_REQUIRED"] += 1
                continue
            if not _session_completed(exit_session, as_of=as_of, now_utc=now_utc):
                pending[f"H{horizon}_NOT_MATURE"] += 1
                continue
            exit_day = str(exit_session["session_date"])
            benchmark = index_bar(exit_day)
            if benchmark is None:
                pending[f"H{horizon}_BENCHMARK_ARCHIVE_PENDING"] += 1
                continue
            archive_ready, stock = stock_bar(str(event["symbol"]), exit_day)
            if not archive_ready:
                pending[f"H{horizon}_UDIFF_ARCHIVE_PENDING"] += 1
                continue
            action_result = _corporate_action_audit(
                action_client,
                symbol=str(event["symbol"]),
                entry_date=str(event["planned_entry_session"]),
                exit_date=exit_day,
                raw_dir=args.raw_dir,
                event_id=event_id,
                horizon=horizon,
            )
            if action_result is None:
                pending[f"H{horizon}_CORPORATE_ACTION_SOURCE_PENDING"] += 1
                continue
            action_audit, action_url, action_hash = action_result
            record = build_outcome_record(
                event=event,
                entry_record=entry,
                horizon=horizon,
                exit_session=exit_day,
                exit_stock_bar=stock,
                exit_benchmark_bar=benchmark,
                corporate_action_audit=action_audit,
                corporate_action_source_url=action_url,
                corporate_action_raw_sha256=action_hash,
                observed_at_utc=utc_now_text(),
            )
            outcome_ledger = append_outcome(outcome_ledger, record)
            new_outcome_statuses[
                str(record["status"])
                if record["status"] == "COMPLETE"
                else f"BLOCKED:{record['block_reason']}"
            ] += 1

    validate_entry_ledger(entry_ledger)
    validate_outcome_ledger(outcome_ledger)
    _write_json(entry_path, entry_ledger)
    _write_json(outcome_path, outcome_ledger)

    report = {
        "schema_version": 1,
        "hypothesis_id": "H024",
        "started_at_utc": started_at,
        "completed_at_utc": utc_now_text(),
        "as_of_date": as_of.isoformat(),
        "primary_event_count": len(primary_events),
        "new_entry_count": int(entry_ledger["record_count"]) - start_entry_count,
        "new_outcome_count": int(outcome_ledger["record_count"]) - start_outcome_count,
        "new_entry_status_counts": dict(sorted(new_entry_statuses.items())),
        "new_outcome_status_counts": dict(sorted(new_outcome_statuses.items())),
        "pending_counts": dict(sorted(pending.items())),
        "audited_recent_non_session_dates": audited_non_sessions,
        "entry_ledger_sha256": entry_ledger["ledger_sha256"],
        "outcome_ledger_sha256": outcome_ledger["ledger_sha256"],
        "outcome_data_attached_to_event_ledger": False,
        "live_capital_allowed": False,
    }
    _write_json(args.report, report)
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
