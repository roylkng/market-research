"""Capture an official NSE announcement clock, not an automated stage forecast.

The first observation can begin only after Oct 14 00:00 UTC. HTTP/source
failures are retained as honest receipts. No access-control bypass,
fallback search page, proxy, LLM judgment or stock recommendation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.hg008_intraday_discovery import (
    PILOT_ID,
    build_intraday_discovery,
    expected_window,
    validate_discovery_packet,
)
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.ss002_daily_capture import deterministic_gzip


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def capture_once(
    *,
    observed_at_utc: str,
    acquire,
    out_dir: Path,
) -> dict[str, Any]:
    first, last = expected_window(observed_at_utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "pilot_id": PILOT_ID,
        "attempted_at_utc": observed_at_utc,
        "requested_from": first.strftime("%d-%m-%Y"),
        "requested_to": last.strftime("%d-%m-%Y"),
        "source_url": "https://www.nseindia.com/api/corporate-announcements",
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "state": None,
        "original_source_sha256": None,
        "packet_sha256": None,
        "candidate_count": 0,
        "failure_reason": None,
        "source_had_manual_stage_review": False,
        "first_seen_forecast_published": False,
        "return_outcomes_opened": False,
        "live_capital_allowed": False,
    }
    try:
        decoded, raw = acquire(
            from_date=first.strftime("%d-%m-%Y"),
            to_date=last.strftime("%d-%m-%Y"),
        )
        packet = build_intraday_discovery(
            source=decoded,
            original_raw=raw,
            request_start=first,
            request_end=last,
            observed_at_utc=_now(),
        )
        validate_discovery_packet(packet)
        zipped = deterministic_gzip(raw)
        source_sha = hashlib.sha256(raw).hexdigest()
        raw_path = out_dir / "original" / "sha256" / f"{source_sha}.json.gz"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        if raw_path.exists() and raw_path.read_bytes() != zipped:
            raise ValueError("original source snapshot immutable SHA conflict")
        raw_path.write_bytes(zipped)
        if raw_path.read_bytes() != zipped:
            raise ValueError("original source bytes failed retention")
        output = out_dir / "source-clock.json"
        output.write_text(
            json.dumps(packet, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        receipt.update(
            state="ORIGINAL_NSE_INTRADAY_ANNOUNCEMENTS_CAPTURED_SOURCE_ONLY",
            original_source_sha256=source_sha,
            packet_sha256=packet["packet_sha256"],
            candidate_count=packet["category_candidate_count"],
        )
    except (NSEAcquisitionError, ValueError, TypeError) as exc:
        receipt.update(
            state="SOURCE_UNAVAILABLE_OR_SCHEMA_BLOCKED_NO_FORECAST",
            failure_reason=f"{type(exc).__name__}:{str(exc)[:400]}",
        )
    (out_dir / "receipt.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    observed = _now()
    expected_window(observed)
    client = NSEClient(timeout=12.0, attempts=2)
    record = capture_once(
        observed_at_utc=observed,
        acquire=client.corporate_announcements_with_raw,
        out_dir=args.out_dir,
    )
    print(json.dumps(record, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
