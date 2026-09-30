from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.alpha_announcement_features import (
    SOURCE_END,
    SOURCE_START,
    build_announcement_source_panel,
)
from marketlab.alpha_history import canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.nse import NSEClient


def _write_content_addressed(root: Path, raw: bytes) -> str:
    sha = sha256_bytes(raw)
    path = root / "raw" / "sha256" / f"{sha}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise RuntimeError(
                f"T007 announcement raw collision: {path}"
            )
    else:
        path.write_bytes(raw)
    return sha


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


def _nse_date(value: date) -> str:
    return value.strftime("%d-%m-%Y")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build frozen T007 daily whole-market NSE announcement panel"
    )
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--pause-seconds", type=float, default=0.05)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )
    payloads = {}
    hashes = {}
    day = SOURCE_START
    while day <= SOURCE_END:
        payload, raw = client.corporate_announcements_with_raw(
            None,
            from_date=_nse_date(day),
            to_date=_nse_date(day),
        )
        key = day.isoformat()
        payloads[key] = payload
        hashes[key] = _write_content_addressed(args.store, raw)
        day = date.fromordinal(day.toordinal() + 1)
        if args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

    panel = build_announcement_source_panel(
        daily_payloads=payloads,
        daily_raw_sha256=hashes,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    panel_bytes = canonical_gzip_json(panel)
    (args.output / "announcement-panel.json.gz").write_bytes(panel_bytes)

    manifest = {
        "schema_version": 1,
        "artifact_id": "AE001-T007-HISTORICAL-ANNOUNCEMENT-SOURCE-v1",
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "source_start": SOURCE_START.isoformat(),
        "source_end": SOURCE_END.isoformat(),
        "daily_source_count": panel["daily_source_count"],
        "announcement_count": panel["announcement_count"],
        "panel_sha256": panel["panel_sha256"],
        "artifact_sha256": sha256_bytes(panel_bytes),
        "d003_report_sha256": (
            "7f402beecaf90f054c93ca2ceeaa01f38fcc5cd8f7f8f6391f60791768f8a91f"
        ),
        "market_return_outcomes_opened": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "manifest.json", manifest)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
