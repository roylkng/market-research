"""Materialize HG009 outcome-clock protocol before future price observation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg009_p004_clock import (
    build_hg009_outcome_clock,
    load_p004_inputs,
    validate_hg009_outcome_clock,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path("research/hg009/hg009-p004-2026-outcome-clock-v1.json"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.repo_root
    calendar, source, selected, controls = load_p004_inputs(root)
    report = build_hg009_outcome_clock(
        calendar=calendar,
        original=source,
        selected=selected,
        controls=controls,
    )
    validate_hg009_outcome_clock(
        report,
        calendar=calendar,
        original=source,
        selected=selected,
        controls=controls,
    )
    blob = json.dumps(
        report, indent=2, sort_keys=True,
        ensure_ascii=False, allow_nan=False,
    ) + "\n"
    dest = root / args.output
    if args.check:
        if not dest.is_file() or dest.read_text(encoding="utf-8") != blob:
            raise SystemExit("HG009 P004 frozen official NSE clock changed")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.read_text(encoding="utf-8") != blob:
            raise SystemExit("HG009 P004 original protocol cannot be overwritten")
        dest.write_text(blob, encoding="utf-8")
    print(json.dumps({
        "state": "VERIFIED" if args.check else "FROZEN_BEFORE_FIRST_ENTRY",
        "id": report["protocol_id"],
        "sha256": report["protocol_sha256"],
        "first_entry": report["first_eligible_entry_session"],
        "horizon_states": {
            k: v["state"] for k, v in report["planned_horizon_status"].items()
        },
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
