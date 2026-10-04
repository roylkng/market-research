from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.events import sha256_bytes
from marketlab.nse import NSEClient
from marketlab.ss002_special_situations import (
    WINDOW_END,
    WINDOW_START,
    build_special_situation_census,
)


def _retain(root: Path, day: date, raw: bytes) -> str:
    sha = sha256_bytes(raw)
    path = root / "daily-announcements" / "sha256" / f"{sha}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"SS002 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha


def _nse_date(day: date) -> str:
    return day.strftime("%d-%m-%Y")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen SS002-D001 special-situation announcement census"
    )
    parser.add_argument("--ss001-census", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--pause-seconds", type=float, default=0.05)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ss001 = json.loads(args.ss001_census.read_text(encoding="utf-8"))
    if not isinstance(ss001, dict):
        raise TypeError("SS002 SS001 census input must be an object")

    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    payloads: dict[str, object] = {}
    hashes: dict[str, str] = {}

    total_days = (WINDOW_END - WINDOW_START).days + 1
    for offset in range(total_days):
        day = date.fromordinal(WINDOW_START.toordinal() + offset)
        payload, raw = client.corporate_announcements_with_raw(
            None,
            from_date=_nse_date(day),
            to_date=_nse_date(day),
        )
        key = day.isoformat()
        payloads[key] = payload
        hashes[key] = _retain(args.raw_dir, day, raw)
        if offset == 0 or (offset + 1) % 25 == 0 or offset + 1 == total_days:
            count = len(payload) if isinstance(payload, list) else len(payload.get("data", []))
            print(
                f"[announcements] {offset + 1:03d}/{total_days} "
                f"{key} rows={count} sha={hashes[key][:12]}",
                flush=True,
            )
        if args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

    census = build_special_situation_census(
        ss001_census=ss001,
        daily_payloads=payloads,
        daily_raw_sha256=hashes,
        generated_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ss002-d001-census.json").write_text(
        json.dumps(
            census,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = {
        key: value
        for key, value in census.items()
        if key not in {"events", "daily_raw_sha256", "daily_source_row_counts", "daily_candidate_counts"}
    }
    (args.output / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
