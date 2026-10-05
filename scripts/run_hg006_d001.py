from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.events import sha256_bytes
from marketlab.hg006_historical_events import (
    SOURCE_END,
    SOURCE_START,
    build_historical_event_census,
)
from marketlab.nse import NSEClient


def _retain(root: Path, raw: bytes) -> str:
    sha = sha256_bytes(raw)
    path = root / "daily-announcements" / "sha256" / f"{sha}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"HG006 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha


def _nse_date(day: date) -> str:
    return day.strftime("%d-%m-%Y")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--pause-seconds", type=float, default=0.03)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    payloads: dict[str, object] = {}
    hashes: dict[str, str] = {}

    total = (SOURCE_END - SOURCE_START).days + 1
    for offset in range(total):
        day = date.fromordinal(SOURCE_START.toordinal() + offset)
        payload, raw = client.corporate_announcements_with_raw(
            None,
            from_date=_nse_date(day),
            to_date=_nse_date(day),
        )
        key = day.isoformat()
        payloads[key] = payload
        hashes[key] = _retain(args.raw_dir, raw)
        if offset == 0 or (offset + 1) % 50 == 0 or offset + 1 == total:
            count = len(payload) if isinstance(payload, list) else len(payload.get("data", []))
            print(
                f"[hg006] {offset + 1:04d}/{total} {key} rows={count} sha={hashes[key][:12]}",
                flush=True,
            )
        if args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

    census = build_historical_event_census(
        daily_payloads=payloads,
        daily_raw_sha256=hashes,
        generated_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "hg006-d001-census.json").write_text(
        json.dumps(census, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    summary = {
        key: value
        for key, value in census.items()
        if key
        not in {
            "events",
            "chronologies",
            "daily_raw_sha256",
            "daily_source_row_counts",
            "daily_retained_event_counts",
        }
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
