"""Prepare future H021 top-decile research intent before the next NSE open.

The first Oct 9 H021-P003 intent remains authoritative, and cannot be replaced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.h021_first_entry_intent import git_blob_sha
from marketlab.h021_future_intent import (
    EXPECTED_CALENDAR_GIT_BLOB,
    EXPECTED_UNIVERSE_GIT_BLOB,
    build_future_h021_intent,
)


def _load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return data, raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--calendar", required=True, type=Path)
    parser.add_argument("--universe", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    comparison, comparison_raw = _load_json(args.comparison)
    manifest, manifest_raw = _load_json(args.manifest)
    calendar, calendar_raw = _load_json(args.calendar)
    universe, universe_raw = _load_json(args.universe)
    if git_blob_sha(calendar_raw) != EXPECTED_CALENDAR_GIT_BLOB:
        raise ValueError("official frozen NSE calendar blob hash mismatch")
    if git_blob_sha(universe_raw) != EXPECTED_UNIVERSE_GIT_BLOB:
        raise ValueError("official frozen U001 universe blob hash mismatch")

    current_day = comparison.get("current_capture_date_ist")
    if not isinstance(current_day, str) or current_day <= "2026-10-09":
        raise ValueError("the first H021-P003 cohort may not be replaced by future P005")
    expected_basename = f"{current_day}-primary-entry-intent-v2.json"
    if args.out.name != expected_basename:
        raise ValueError("output name does not match sealed H021 comparison date")
    if args.out.exists():
        raise FileExistsError("future H021 intent exists; never overwrite immutable record")

    intent = build_future_h021_intent(
        comparison, manifest, calendar, universe,
        prepared_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        comparison_raw_sha256=hashlib.sha256(comparison_raw).hexdigest(),
        manifest_raw_sha256=hashlib.sha256(manifest_raw).hexdigest(),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as out:
        json.dump(intent, out, indent=2, sort_keys=True, allow_nan=False)
        out.write("\n")
    print(json.dumps({
        "intent_id": intent["intent_id"],
        "selected_count": intent["selected_count"],
        "entry_session": intent["planned_entry"]["session_date_ist"],
        "packet_sha256": intent["packet_sha256"],
        "return_outcomes_opened": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
