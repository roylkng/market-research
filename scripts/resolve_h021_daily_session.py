"""Select a completed H021 daily source session without look-ahead or backfill.

Normal capture keeps the preregistered three attempts per session. A separate
optional source-recovery mode offers *two additional next-day attempts* only
when original SHA-anchored receipts show official NSE reports were HTTP 404
NOT_PUBLISHED, never when access was restricted or raw data were malformed.

Later acquisition must retain its true UTC time and the SAME session date.
This changes source transport, not H021 selection, horizons or returns.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021_daily_prices import (
    CALENDAR_SHA256,
    official_market_transport_ready,
)
from marketlab.marketdata import index_snapshot_url, udiff_url

FIRST_FUTURE_SESSION = "2026-10-13"
MAX_AUTOMATED_ATTEMPTS = 3
MAX_DELAYED_PUBLICATION_RECOVERY_ATTEMPTS = 2
MAX_RECOVERY_AGE_DAYS = 7
IST = ZoneInfo("Asia/Kolkata")
ATTEMPT_ID = "H021-P008-OFFICIAL-SOURCE-ATTEMPT-v1"


def _as_utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be an aware ISO timestamp")
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO timestamp") from exc
    if stamp.tzinfo is None:
        raise ValueError(f"{field} must include timezone")
    return stamp.astimezone(UTC)


def _previous_missing_report_is_official_404(
    *,
    receipt: dict[str, Any],
    session_date: str,
    official_close: datetime,
) -> tuple[bool, datetime]:
    """An invalid/forged prior receipt cannot grant the recovery exception."""
    if not isinstance(receipt, dict):
        raise TypeError("source attempt must be a JSON object")
    if receipt.get("id") != ATTEMPT_ID or receipt.get("session_date") != session_date:
        raise ValueError("previous H021 source attempt identity/date is invalid")
    observed = _as_utc(receipt.get("recorded_at_utc"), field="attempt recorded_at_utc")
    if observed < official_close:
        raise ValueError("previous H021 attempt was recorded before market close")
    if receipt.get("horizon_returns_opened") is not False:
        raise ValueError("H021 attempt must not contain forward return outcomes")
    if receipt.get("live_capital_allowed") is not False:
        raise ValueError("H021 attempt must not authorize live capital")
    index = receipt.get("source_index")
    stock = receipt.get("source_stock")
    if not isinstance(index, dict) or not isinstance(stock, dict):
        raise TypeError("prior attempt must have original stock/index source receipts")

    missing = False
    for kind, data, expected_url in (
        ("index", index, index_snapshot_url(date.fromisoformat(session_date))),
        ("stock", stock, udiff_url(date.fromisoformat(session_date))),
    ):
        if data.get("url") != expected_url:
            raise ValueError(f"{kind}: original NSE report URL changed")
        timestamp = _as_utc(
            data.get("captured_at_utc"), field=f"{kind} original captured_at_utc"
        )
        if not official_close <= timestamp <= observed:
            raise ValueError(f"{kind}: impossible original exchange capture chronology")
        state = data.get("status")
        status_code = data.get("http_status")
        sha = data.get("sha256")
        if state == "NOT_PUBLISHED":
            if status_code != 404 or sha is not None or data.get("byte_count") is not None:
                raise ValueError(f"{kind}: 404 receipt cannot contain original bytes")
            missing = True
        elif state == "OK":
            if (
                status_code != 200
                or not isinstance(sha, str)
                or len(sha) != 64
                or any(char not in "0123456789abcdef" for char in sha)
                or type(data.get("byte_count")) is not int
                or data["byte_count"] <= 0
            ):
                raise ValueError(f"{kind}: original successful NSE file SHA receipt invalid")
        elif state in ("ACCESS_BLOCKED", "FETCH_FAILED"):
            # Never schedule extra access against denied NSE endpoints.
            return False, observed
        else:
            raise ValueError(f"{kind}: unknown official original source status")
    if not missing:
        # If both original files were already source-complete, a late recovery
        # would hide a parser/data-integrity problem, not publication delay.
        return False, observed
    return True, observed


def _eligible_delayed_publication_recovery(
    *,
    root: Path,
    session_date: str,
    official_close: datetime,
    as_of_utc: datetime,
) -> tuple[bool, int]:
    attempts = sorted((root / "attempts").glob(f"{session_date}-*.json"))
    count = len(attempts)
    if not MAX_AUTOMATED_ATTEMPTS <= count < (
        MAX_AUTOMATED_ATTEMPTS + MAX_DELAYED_PUBLICATION_RECOVERY_ATTEMPTS
    ):
        return False, count
    elapsed_days = (as_of_utc.astimezone(IST).date() - date.fromisoformat(session_date)).days
    if not 1 <= elapsed_days <= MAX_RECOVERY_AGE_DAYS:
        return False, count
    latest_recorded = official_close
    for attempt in attempts:
        receipt = json.loads(attempt.read_text(encoding="utf-8"))
        eligible, timestamp = _previous_missing_report_is_official_404(
            receipt=receipt, session_date=session_date, official_close=official_close
        )
        if not eligible:
            return False, count
        if timestamp > latest_recorded:
            latest_recorded = timestamp
    # At most one delayed retry on a given local day. This avoids creating
    # multiple 404 requests during the same short publication-delay window.
    if latest_recorded.astimezone(IST).date() >= as_of_utc.astimezone(IST).date():
        return False, count
    return True, count


def resolve_session(
    calendar: Any,
    observations_root: Path,
    *,
    as_of_utc: datetime,
    allow_delayed_publication_recovery: bool = False,
) -> dict[str, Any]:
    if as_of_utc.tzinfo is None:
        raise ValueError("as-of time must be timezone-aware")
    current = as_of_utc.astimezone(UTC)
    if calendar.sha256 != CALENDAR_SHA256:
        raise ValueError("original H021 NSE source calendar changed")
    if type(allow_delayed_publication_recovery) is not bool:
        raise TypeError("delayed-source-recovery switch must be boolean")

    skipped: list[dict[str, Any]] = []
    complete = 0
    first_cohort_partial_transport_days = []
    recovery_candidates: list[tuple[str, datetime, int]] = []
    for session in calendar.sessions:
        day = session.session_date
        if day < FIRST_FUTURE_SESSION:
            continue
        close = datetime.fromisoformat(session.close_timestamp_utc).astimezone(UTC)
        if close > current:
            break
        record = observations_root / f"{day}-v1.json"
        if record.exists():
            payload = json.loads(record.read_text(encoding="utf-8"))
            if not official_market_transport_ready(payload):
                raise ValueError("sealed H021 market file lacks independently verified transport")
            if payload["session_date_ist"] != day:
                raise ValueError("unexpected sealed H021 daily market source date")
            if payload["capture_state"] == "SOURCE_COMPLETE":
                complete += 1
            else:
                first_cohort_partial_transport_days.append(day)
            continue
        attempts = len(list((observations_root / "attempts").glob(f"{day}-*.json")))
        if attempts >= MAX_AUTOMATED_ATTEMPTS:
            skipped.append({
                "session_date": day,
                "state": "SOURCE_UNRESOLVED_AFTER_BOUNDED_RETRIES",
                "attempts": attempts,
            })
            if allow_delayed_publication_recovery:
                recovery_candidates.append((day, close, attempts))
            continue
        return {
            "schema_version": 1,
            "state": "CAPTURE",
            "session_date": day,
            "capture_mode": "NORMAL_AFTER_COMPLETED_EXCHANGE_CLOSE",
            "attempts_so_far": attempts,
            "maximum_automatic_attempts": MAX_AUTOMATED_ATTEMPTS,
            "previous_complete_sessions": complete,
            "first_cohort_partial_but_transport_ready_sessions": (
                first_cohort_partial_transport_days
            ),
            "unresolved_past_sessions": skipped,
            "outcomes_opened": False,
            "live_capital_allowed": False,
        }

    if allow_delayed_publication_recovery:
        for day, close, count in recovery_candidates:
            eligible, observed_count = _eligible_delayed_publication_recovery(
                root=observations_root,
                session_date=day,
                official_close=close,
                as_of_utc=current,
            )
            if not eligible:
                continue
            if observed_count != count:
                raise ValueError("attempt count changed during recovery eligibility check")
            return {
                "schema_version": 1,
                "state": "CAPTURE",
                "session_date": day,
                "capture_mode": "DELAYED_ORIGINAL_NSE_404_RECOVERY_NOT_BACKFILL",
                "attempts_so_far": count,
                "maximum_automatic_attempts": (
                    MAX_AUTOMATED_ATTEMPTS + MAX_DELAYED_PUBLICATION_RECOVERY_ATTEMPTS
                ),
                "previous_complete_sessions": complete,
                "first_cohort_partial_but_transport_ready_sessions": (
                    first_cohort_partial_transport_days
                ),
                "unresolved_past_sessions": skipped,
                "outcomes_opened": False,
                "live_capital_allowed": False,
            }

    return {
        "schema_version": 1,
        "state": "NO_COMPLETED_PENDING_SESSION",
        "session_date": None,
        "capture_mode": None,
        "previous_complete_sessions": complete,
        "first_cohort_partial_but_transport_ready_sessions": (
            first_cohort_partial_transport_days
        ),
        "unresolved_past_sessions": skipped,
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--observations-dir", type=Path, required=True)
    parser.add_argument("--allow-delayed-publication-recovery", action="store_true")
    args = parser.parse_args()
    snapshot = load_calendar_snapshot(args.calendar)
    result = resolve_session(
        snapshot,
        args.observations_dir,
        as_of_utc=datetime.now(UTC),
        allow_delayed_publication_recovery=args.allow_delayed_publication_recovery,
    )
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
