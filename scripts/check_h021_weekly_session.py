from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021_calendar_supersession import validate_effective_h021_calendar
from marketlab.h021_stockanalysis_acquisition import post_close_weekly_session_decision


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-date", required=True)
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    calendar = json.loads(args.calendar.read_text(encoding="utf-8"))
    if not isinstance(calendar, dict):
        raise TypeError("calendar must contain a JSON object")

    # Both a canonical digest and the reviewed effective-calendar identity are
    # required before the gate is allowed to decide about today's capture.
    load_calendar_snapshot(args.calendar)
    validate_effective_h021_calendar(calendar, capture_date_ist=args.capture_date)

    decision = post_close_weekly_session_decision(
        args.capture_date, calendar, observed_at_utc=datetime.now(UTC)
    )
    payload = asdict(decision)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
