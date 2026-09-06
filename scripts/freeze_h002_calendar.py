#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.calendar_snapshot import build_calendar_snapshot
from marketlab.nse import NSEClient
from marketlab.runner import write_json


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze an explicit H002-D NSE cash-market calendar from exact holiday bytes."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-out", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 9, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 12, 31))
    parser.add_argument("--version", default="NSE-CM-FY27Q2-v1")
    args = parser.parse_args()

    client = NSEClient(timeout=20.0, attempts=4)
    payload, raw = client.trading_holidays_with_raw()
    captured_at = datetime.now(UTC)
    snapshot = build_calendar_snapshot(
        payload,
        raw_holiday_bytes=raw,
        start_date=args.start,
        end_date=args.end,
        captured_at=captured_at,
        version=args.version,
    )
    args.source_out.parent.mkdir(parents=True, exist_ok=True)
    args.source_out.write_bytes(raw)
    write_json(args.output, snapshot.to_dict())
    print(
        f"calendar={args.output} sessions={len(snapshot.sessions)} "
        f"unresolved_special_dates={list(snapshot.unresolved_special_dates)} "
        f"sha256={snapshot.sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
