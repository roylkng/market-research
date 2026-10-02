from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_futures import fo_udiff_url
from marketlab.alpha_prospective_sources import validate_source_ledger
from marketlab.alpha_sc003_preopen import (
    SC003_P1_PROTOCOL,
    append_sc003_probe,
    latest_sc001_eligible_target,
    next_frozen_trading_session,
    preopen_readiness_summary,
    target_ready_observed,
    validate_sc003_ledger,
)
from marketlab.calendar_snapshot import load_calendar_snapshot


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write(path: Path, payload: object) -> None:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe previous completed-session NSE FO source for SC003"
    )
    parser.add_argument("--observation-date", type=date.fromisoformat)
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--sc001-ledger", type=Path, required=True)
    parser.add_argument("--sc003-ledger", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sc001 = _load(args.sc001_ledger)
    validate_source_ledger(sc001)
    sc003 = _load(args.sc003_ledger)
    validate_sc003_ledger(sc003)

    calendar = load_calendar_snapshot(args.calendar)
    target = latest_sc001_eligible_target(sc001)
    target_session = str(target["session_date"])
    target_close_timestamp_utc, cutoff_session_date = (
        next_frozen_trading_session(
            calendar,
            target_session_date=target_session,
        )
    )
    now = datetime.now(UTC)
    observation_date = (
        args.observation_date.isoformat()
        if args.observation_date is not None
        else now.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()
    )
    if target_ready_observed(sc003, target_session):
        summary = preopen_readiness_summary(sc003)
        _write(args.summary, summary)
        print(
            json.dumps(
                {
                    "state": "TARGET_READY_ALREADY_OBSERVED",
                    "target_session_date": target_session,
                    "observation_date": observation_date,
                    "changed": False,
                    "summary_sha256": summary["summary_sha256"],
                },
                sort_keys=True,
            )
        )
        return 0

    source_url = fo_udiff_url(date.fromisoformat(target_session))
    raw = http_fetcher(
        attempts=args.attempts,
        timeout=args.timeout_seconds,
    )(source_url)
    captured = datetime.now(UTC)

    updated, attempt = append_sc003_probe(
        sc003,
        sc001_attempt=target,
        observation_date=observation_date,
        captured_at_utc=captured.isoformat(),
        source_url=source_url,
        raw=raw,
        cutoff_session_date=cutoff_session_date,
        frozen_calendar_sha256=calendar.sha256,
        frozen_calendar_version=calendar.version,
        target_close_timestamp_utc=target_close_timestamp_utc,
        protocol=SC003_P1_PROTOCOL,
    )
    if attempt is None:
        raise RuntimeError("SC003 unexpectedly returned no attempt")

    if raw is not None:
        raw_path = Path(str(attempt["raw_repo_path"]))
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        if raw_path.exists() and raw_path.read_bytes() != raw:
            raise RuntimeError(f"SC003 raw path collision: {raw_path}")
        raw_path.write_bytes(raw)

    _write(args.sc003_ledger, updated)
    validate_sc003_ledger(updated)
    summary = preopen_readiness_summary(updated)
    _write(args.summary, summary)

    print(
        json.dumps(
            {
                "state": "CAPTURED",
                "changed": True,
                "target_session_date": target_session,
                "observation_date": observation_date,
                "cutoff_session_date": cutoff_session_date,
                "captured_at_utc": attempt["captured_at_utc"],
                "source_status": attempt["source_status"],
                "ready_before_preopen_cutoff": attempt[
                    "ready_before_preopen_cutoff"
                ],
                "attempt_sha256": attempt["attempt_sha256"],
                "ledger_sha256": updated["ledger_sha256"],
                "summary_sha256": summary["summary_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
