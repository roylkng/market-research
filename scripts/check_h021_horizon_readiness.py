"""Inspect H021 20/60 session calendar readiness without opening returns."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021_first_entry_intent import CALENDAR_PATH, load_pinned_inputs
from marketlab.h021_horizon_readiness import (
    first_cohort_horizon_readiness,
    require_horizon_calendar_ready,
)
from scripts.acquire_h021_first_entry import load_and_verify_sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--require-horizon", type=int, choices=(20, 60))
    args = parser.parse_args()

    # Reverify all original source Git hashes, original intent, and calendar.
    load_pinned_inputs()
    intent, _universe = load_and_verify_sources()
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
