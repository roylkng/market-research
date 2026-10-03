from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.pf001_schedule import next_pending_pf001_session


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve the oldest completed but unprocessed PF001 NSE session"
    )
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--state", type=Path, action="append", required=True)
    parser.add_argument(
        "--now",
        help="Optional offset-aware ISO timestamp for deterministic replay",
    )
    args = parser.parse_args()

    calendar = load_calendar_snapshot(args.calendar)
    states = [_load(path) for path in args.state]
    now = datetime.now(UTC) if args.now is None else datetime.fromisoformat(args.now)
    session = next_pending_pf001_session(
        calendar,
        states=states,
        now=now,
    )
    last_session = states[0].get("last_session_date")
    report = {
        "state": "PENDING" if session is not None else "CAUGHT_UP",
        "session_date": session,
        "last_session_date": last_session,
        "calendar_version": calendar.version,
        "calendar_sha256": calendar.sha256,
    }
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
