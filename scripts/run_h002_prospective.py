#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.frozen_bundle import load_frozen_bundle
from marketlab.nse import NSEClient
from marketlab.runner import H002CohortRunner, write_json
from marketlab.universe import load_universe_snapshot


def _as_of(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO-8601 timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("--as-of must include a timezone")
    return parsed.astimezone(UTC)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one paper-only H002-D FY27-Q2 prospective cohort iteration."
    )
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--anchor-metadata", type=Path, required=True)
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--as-of")
    args = parser.parse_args()

    as_of = _as_of(args.as_of)
    universe = load_universe_snapshot(args.universe)
    bundle = load_frozen_bundle(
        args.bundle,
        args.anchor_metadata,
        universe=universe,
    )
    calendar = load_calendar_snapshot(args.calendar)
    client = NSEClient(timeout=20.0, attempts=4)
    runner = H002CohortRunner(
        client=client,
        universe=universe,
        bundle=bundle,
        calendar_snapshot=calendar,
        store_root=args.store,
    )
    summary, report = runner.run(as_of=as_of)
    write_json(args.summary_out, summary.to_dict())
    write_json(args.report_out, report.to_dict())

    print(
        f"H002-D run {summary.run_sha256}: discovery_enabled={summary.discovery_enabled}; "
        f"outcomes={summary.outcome_counts}; report={report.report_sha256}; "
        f"completed={report.completed_count}; live_capital_allowed={report.live_capital_allowed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
