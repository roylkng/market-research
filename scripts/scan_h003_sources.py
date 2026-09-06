from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from marketlab.events import sha256_bytes
from marketlab.h003_sources import (
    H003SourceError,
    WINDOW_END,
    WINDOW_START,
    build_coverage_bundle,
    build_coverage_record,
    incomplete_coverage_record,
    write_coverage_bundle,
)
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.universe import load_universe_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan frozen U001 for H003 official transcript coverage")
    parser.add_argument("--universe", required=True)
    parser.add_argument("--store", default=".marketlab")
    parser.add_argument("--out", required=True)
    parser.add_argument("--pause-seconds", type=float, default=0.10)
    return parser.parse_args()


def retain_discovery(root: Path, symbol: str, raw: bytes) -> str:
    digest = sha256_bytes(raw)
    path = root / "h003-discovery" / "raw" / "sha256" / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise RuntimeError("content-addressed H003 discovery collision")
    else:
        path.write_bytes(raw)
    index = root / "h003-discovery" / "symbols" / f"{symbol.upper()}.json"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(
        json.dumps({"symbol": symbol.upper(), "discovery_sha256": digest}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return digest


def main() -> int:
    args = parse_args()
    universe = load_universe_snapshot(args.universe)
    client = NSEClient(timeout=25.0, attempts=4)
    store = Path(args.store)
    records = []

    total = len(universe.members)
    for index, member in enumerate(universe.members, start=1):
        captured = datetime.now(UTC)
        try:
            payload, raw = client.corporate_announcements_with_raw(
                member.symbol,
                from_date=WINDOW_START.strftime("%d-%m-%Y"),
                to_date=WINDOW_END.strftime("%d-%m-%Y"),
            )
            retain_discovery(store, member.symbol, raw)
            record = build_coverage_record(
                payload,
                raw,
                symbol=member.symbol,
                captured_at=captured,
            )
        except (NSEAcquisitionError, H003SourceError, RuntimeError) as exc:
            record = incomplete_coverage_record(
                symbol=member.symbol,
                captured_at=captured,
                reason=f"{type(exc).__name__}: {exc}",
            )
        records.append(record)
        print(
            f"[{index:03d}/{total:03d}] {member.symbol}: "
            f"{record.coverage_status} sources={record.source_count}"
            + (f" reason={record.incomplete_reason}" if record.incomplete_reason else "")
        )
        if args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

    generated = datetime.now(UTC)
    bundle = build_coverage_bundle(records, universe=universe, generated_at=generated)
    write_coverage_bundle(args.out, bundle)
    counts = Counter(record.coverage_status for record in records)
    summary = {
        "cohort_id": bundle.cohort_id,
        "member_count": bundle.member_count,
        "complete_count": bundle.complete_count,
        "complete_zero_source_count": bundle.complete_zero_source_count,
        "incomplete_count": bundle.incomplete_count,
        "transcript_source_count": bundle.transcript_source_count,
        "coverage_status_counts": dict(sorted(counts.items())),
        "bundle_sha256": bundle.bundle_sha256,
        "window_start": WINDOW_START.isoformat(),
        "window_end": WINDOW_END.isoformat(),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
