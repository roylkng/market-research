from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.ss002_p001_source_gaps import (
    MAX_AUTOMATED_ATTEMPTS_PER_DAY,
    append_source_failure,
    build_source_failure,
    source_attempts_for_day,
)
from marketlab.ss002_daily_capture import (
    FIRST_SOURCE_DATE,
    build_daily_capture,
    deterministic_gzip,
    raw_sha256,
)

LOCAL_TZ = ZoneInfo("Asia/Kolkata")
MAX_DAYS_PER_RUN = 7
CAPTURE_ROOT = Path("research/prospective/ss002-p001")


def _iso_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise AlphaContractError(f"P001 invalid ISO date: {value}") from exc
    if parsed.isoformat() != value:
        raise AlphaContractError("P001 date must use ISO YYYY-MM-DD")
    return parsed


def pending_source_dates(
    root: Path, *, today_ist: date, start_date: date | None, end_date: date | None
) -> list[date]:
    first = start_date or FIRST_SOURCE_DATE
    last = end_date or today_ist - timedelta(days=1)
    if first < FIRST_SOURCE_DATE or last >= today_ist:
        raise AlphaContractError("P001 dates must be after October 4 and before today IST")
    if last < first:
        raise AlphaContractError("P001 invalid source-date range")

    days: list[date] = []
    current = first
    while current <= last:
        capture_path = root / f"{current.isoformat()}-v1.json"
        if not capture_path.exists():
            # Explicit date-scoped replays are allowed to recover a prior gap.
            # Scheduled runs stop hammering a persistently blocked old date
            # after three independently retained run attempts.
            count = len(source_attempts_for_day(root, current))
            if start_date is not None or count < MAX_AUTOMATED_ATTEMPTS_PER_DAY:
                days.append(current)
                if len(days) >= MAX_DAYS_PER_RUN:
                    break
        current += timedelta(days=1)
    return days


def _write_immutable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise AlphaContractError(f"P001 immutable output collision: {path}")
        return
    path.write_bytes(data)


def _source_attempt_id() -> str:
    run = os.environ.get("GITHUB_RUN_ID")
    if run is not None:
        if not run.isdigit():
            raise ValueError("GitHub SS002 run ID is invalid")
        attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
        if not attempt.isdigit():
            raise ValueError("GitHub SS002 run attempt ID is invalid")
        return f"github-{run}-{attempt}"
    return f"local-{datetime.now(ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%S%fZ')}"


def _record_source_failure(
    root: Path, *, day: date, phase: str, exc: NSEAcquisitionError
) -> None:
    record = build_source_failure(
        source_day=day,
        recorded_at_utc=datetime.now(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z"),
        source_phase=phase,
        exception=exc,
        attempt_identity=_source_attempt_id(),
    )
    receipt = append_source_failure(root, record)
    print(
        f"P001 SOURCE_UNAVAILABLE {day.isoformat()} phase={phase} "
        f"reason={record['source_failure_reason']} "
        f"attempt={record['attempt_identity']} receipt={receipt}",
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture missing completed NSE corporate-announcement source days"
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--start-date", type=str)
    parser.add_argument("--end-date", type=str)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.repo_root.resolve()
    output_dir = root / CAPTURE_ROOT
    today_ist = datetime.now(LOCAL_TZ).date()
    start_date = _iso_date(args.start_date) if args.start_date else None
    end_date = _iso_date(args.end_date) if args.end_date else None
    dates = pending_source_dates(
        output_dir,
        today_ist=today_ist,
        start_date=start_date,
        end_date=end_date,
    )
    if not dates:
        print("P001 ALREADY_CAPTURED: no missing completed source days")
        return

    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    try:
        master_raw = client.all_equity_csv()
    except NSEAcquisitionError as exc:
        _record_source_failure(
            output_dir, day=dates[0], phase="EQUITY_MASTER_FETCH", exc=exc
        )
        return
    for source_day in dates:
        day_text = source_day.isoformat()
        dest = output_dir / f"{day_text}-v1.json"
        if dest.exists():
            raise AlphaContractError(f"P001 would overwrite captured date: {day_text}")
        try:
            payload, raw = client.corporate_announcements_with_raw(
                None,
                from_date=source_day.strftime("%d-%m-%Y"),
                to_date=source_day.strftime("%d-%m-%Y"),
            )
        except NSEAcquisitionError as exc:
            _record_source_failure(
                output_dir,
                day=source_day,
                phase="CORPORATE_ANNOUNCEMENTS_FETCH",
                exc=exc,
            )
            # A failed official endpoint is not an empty market event day.
            # Avoid repeatedly hammering the source for other dates now.
            # Subsequent scheduled runs retry or advance after the bound.
            break
        captured_at = datetime.now(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z")
        capture = build_daily_capture(
            source_day=source_day,
            announcement_payload=payload,
            announcement_raw=raw,
            equity_master_raw=master_raw,
            acquired_at_utc=captured_at,
        )
        for source_name, source_bytes in [
            ("eq_master", master_raw),
            ("announcement", raw),
        ]:
            metadata = capture["sources"][source_name]
            compressed = deterministic_gzip(source_bytes)
            if raw_sha256(source_bytes) != metadata["raw_sha256"]:
                raise AlphaContractError(f"P001 {source_name} raw hash changed")
            if raw_sha256(compressed) != metadata["gzip_sha256"]:
                raise AlphaContractError(f"P001 {source_name} gzip hash changed")
            _write_immutable(root / metadata["relative_path"], compressed)

        encoded = (
            json.dumps(capture, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            + "\n"
        ).encode("utf-8")
        _write_immutable(dest, encoded)
        print(
            f"P001 {day_text}: announcements={capture['announcement_count']} "
            f"candidates={capture['candidate_event_count']} "
            f"master_eq={capture['eq_master_identity_count_at_capture']} "
            f"sha={capture['capture_sha256']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
