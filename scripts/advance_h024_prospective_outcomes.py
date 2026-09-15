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
    new_entry_ledger,
    new_outcome_ledger,
    outcome_exists,
    validate_entry_ledger,
    validate_outcome_ledger,
)
from marketlab.h024_prospective import validate_calendar
from marketlab.h024_sessions import (
    append_session,
    build_session_record,
    new_session_ledger,
    observed_horizon_exit_session,
    validate_session_ledger,
)
from marketlab.marketdata import index_snapshot_url, udiff_url
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.pf001_marketdata import (
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
    try:
        parsed = parse_pf001_nifty500_index(raw, session_date=session_date)
    except PF001MarketDataMissingRow:
        return None
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


def _advance_observed_sessions(
    http: requests.Session,
    *,
    session_ledger: dict[str, Any],
    as_of: date,
    raw_dir: Path,
    attempts: int,
    timeout: float,
    recheck_days: int,
) -> tuple[dict[str, Any], list[str]]:
    validate_session_ledger(session_ledger)
    if session_ledger["records"]:
        latest = date.fromisoformat(str(session_ledger["records"][-1]["session_date"]))
        start = max(
            PROSPECTIVE_START_DATE,
            latest - timedelta(days=recheck_days - 1),
        )
    else:
        start = PROSPECTIVE_START_DATE
    observed_now: list[str] = []
    cursor = start
    while cursor <= as_of:
        bar = _index_bar(
            http,
            session_date=cursor,
            raw_dir=raw_dir,
            attempts=attempts,
            timeout=timeout,
        )
        if bar is not None:
            before = int(session_ledger["record_count"])
            session_ledger = append_session(
                session_ledger,
                build_session_record(
                    benchmark_bar=bar,
                    observed_at_utc=utc_now_text(),
                ),
            )
            if int(session_ledger["record_count"]) > before:
                observed_now.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return session_ledger, observed_now


def _verify_reviewed_calendar_against_observed(
    *, calendar: dict[str, Any], session_ledger: dict[str, Any]
) -> None:
    reviewed = validate_calendar(calendar)
    reviewed_dates = {str(row["session_date"]) for row in reviewed}
    if not reviewed_dates:
        raise H024OutcomeAdvanceError("reviewed H024 calendar contains no sessions")
    minimum = min(reviewed_dates)
    maximum = max(reviewed_dates)
    special_observed = sorted(
        str(row["session_date"])
        for row in session_ledger["records"]
        if minimum <= str(row["session_date"]) <= maximum
        and str(row["session_date"]) not in reviewed_dates
    )
    if special_observed:
        raise H024OutcomeAdvanceError(
            "official Nifty 500 evidence exposes session(s) absent from reviewed H024 calendar: "
            + ",".join(special_observed)
        )


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
    parser.add_argument("--session-recheck-days", type=int, default=14)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.attempts < 1 or args.timeout_seconds <= 0 or args.session_recheck_days < 1:
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
    reviewed_sessions = validate_calendar(calendar)
    reviewed_by_date = {str(row["session_date"]): row for row in reviewed_sessions}
    event_ledger = _load_json(args.state_dir / "event-ledger.json")
    validate_event_ledger(event_ledger)
    session_path = args.state_dir / "session-ledger.json"
    entry_path = args.state_dir / "entry-ledger.json"
    outcome_path = args.state_dir / "outcome-ledger.json"
    session_ledger = _load_or_initialize(session_path, new_session_ledger)
    entry_ledger = _load_or_initialize(entry_path, new_entry_ledger)
    outcome_ledger = _load_or_initialize(outcome_path, new_outcome_ledger)
    validate_session_ledger(session_ledger)
    validate_entry_ledger(entry_ledger)
    validate_outcome_ledger(outcome_ledger)

    started_at = utc_now_text()
    start_session_count = int(session_ledger["record_count"])
    start_entry_count = int(entry_ledger["record_count"])
    start_outcome_count = int(outcome_ledger["record_count"])
    pending: Counter[str] = Counter()
    new_entry_statuses: Counter[str] = Counter()
    new_outcome_statuses: Counter[str] = Counter()

    http = requests.Session()
    http.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    session_ledger, new_session_dates = _advance_observed_sessions(
        http,
        session_ledger=session_ledger,
        as_of=as_of,
        raw_dir=args.raw_dir,
        attempts=args.attempts,
        timeout=args.timeout_seconds,
        recheck_days=args.session_recheck_days,
    )
    _verify_reviewed_calendar_against_observed(
        calendar=calendar,
        session_ledger=session_ledger,
    )
    observed_by_date = {
        str(row["session_date"]): row for row in session_ledger["records"]
    }
    stock_cache: dict[tuple[str, str], tuple[bool, dict[str, Any] | None]] = {}

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
        if entry_session not in reviewed_by_date:
            raise H024OutcomeAdvanceError(
                f"{event_id}: planned entry session disappeared from reviewed calendar"
            )
        observed = observed_by_date.get(entry_session)
        if observed is None:
            pending["ENTRY_SESSION_NOT_YET_OBSERVED_COMPLETE"] += 1
            continue
        archive_ready, stock = stock_bar(str(event["symbol"]), entry_session)
        if not archive_ready:
            pending["ENTRY_UDIFF_ARCHIVE_PENDING"] += 1
            continue
        record = build_entry_record(
            event=event,
            stock_bar=stock,
            benchmark_bar=dict(observed["benchmark_bar"]),
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
            exit_observation = observed_horizon_exit_session(
                session_ledger,
                entry_session=str(event["planned_entry_session"]),
                horizon=horizon,
            )
            if exit_observation is None:
                pending[f"H{horizon}_NOT_MATURE"] += 1
                continue
            exit_day = str(exit_observation["session_date"])
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
                exit_benchmark_bar=dict(exit_observation["benchmark_bar"]),
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

    validate_session_ledger(session_ledger)
    validate_entry_ledger(entry_ledger)
    validate_outcome_ledger(outcome_ledger)
    _write_json(session_path, session_ledger)
    _write_json(entry_path, entry_ledger)
    _write_json(outcome_path, outcome_ledger)

    report = {
        "schema_version": 1,
        "hypothesis_id": "H024",
        "started_at_utc": started_at,
        "completed_at_utc": utc_now_text(),
        "as_of_date": as_of.isoformat(),
        "primary_event_count": len(primary_events),
        "new_observed_session_count": (
            int(session_ledger["record_count"]) - start_session_count
        ),
        "new_observed_session_dates": new_session_dates,
        "new_entry_count": int(entry_ledger["record_count"]) - start_entry_count,
        "new_outcome_count": int(outcome_ledger["record_count"]) - start_outcome_count,
        "new_entry_status_counts": dict(sorted(new_entry_statuses.items())),
        "new_outcome_status_counts": dict(sorted(new_outcome_statuses.items())),
        "pending_counts": dict(sorted(pending.items())),
        "session_ledger_sha256": session_ledger["ledger_sha256"],
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
