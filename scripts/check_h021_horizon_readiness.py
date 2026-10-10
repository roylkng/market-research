"""Check first H021 20/60-session NSE calendar without opening outcomes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021_first_entry_intent import (
    CALENDAR_PATH,
    build_first_entry_intent,
    git_blob_sha,
    load_pinned_inputs,
)
from marketlab.h021_horizon_readiness import (
    first_cohort_horizon_readiness,
    require_horizon_calendar_ready,
)

INTENT_PATH = Path(
    "research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json"
)
INTENT_BLOB_SHA = "e25f77e1c845456473e624899d4748e306b1225b"


def load_first_intent() -> dict:
    comparison, calendar = load_pinned_inputs()
    raw_intent = INTENT_PATH.read_bytes()
    if git_blob_sha(raw_intent) != INTENT_BLOB_SHA:
        raise ValueError("first H021 original entry intent Git blob changed")
    stored = json.loads(raw_intent)
    if stored != build_first_entry_intent(comparison, calendar):
        raise ValueError("first H021 intent cannot be reproduced from pinned sources")
    return stored


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--require-horizon", type=int, choices=(20, 60))
    args = parser.parse_args()

    intent = load_first_intent()
    snapshot = load_calendar_snapshot(CALENDAR_PATH)
    result = first_cohort_horizon_readiness(intent, snapshot)
    if args.require_horizon is not None:
        require_horizon_calendar_ready(result, args.require_horizon)

    serialized = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
