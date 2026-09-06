#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from marketlab.events import EventStore
from marketlab.expectations import ExpectationStore
from marketlab.nse import NSEClient
from marketlab.preparation import (
    PreparationStore,
    build_preparation_report,
    freeze_complete_bundle,
    prepare_symbol,
    write_json,
)
from marketlab.universe import load_universe_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare point-in-time H002 expectations for one frozen U001 cohort."
    )
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--baseline-period-end", default="2025-09-30")
    parser.add_argument("--store", type=Path, default=Path(".marketlab"))
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--bundle-out", type=Path)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--retry-captured", action="store_true")
    args = parser.parse_args()

    universe = load_universe_snapshot(args.universe)
    client = NSEClient(timeout=20.0, attempts=4)
    event_store = EventStore(args.store)
    expectation_store = ExpectationStore(args.store)
    preparation_store = PreparationStore(args.store)
    datetime.now(UTC)

    for index, member in enumerate(universe.members, start=1):
        existing = preparation_store.latest(universe.cohort_id, member.symbol)
        if existing is not None and existing.outcome == "CAPTURED" and not args.retry_captured:
            print(f"[{index:03d}/{len(universe.members):03d}] {member.symbol}: already CAPTURED")
            continue
        attempt = prepare_symbol(
            client,
            universe=universe,
            symbol=member.symbol,
            baseline_period_end=args.baseline_period_end,
            attempted_at=datetime.now(UTC),
            event_store=event_store,
            expectation_store=expectation_store,
            preparation_store=preparation_store,
        )
        print(
            f"[{index:03d}/{len(universe.members):03d}] {member.symbol}: "
            f"{attempt.outcome}/{attempt.reason_code}"
        )

    generated_at = datetime.now(UTC)
    report = build_preparation_report(
        universe=universe,
        preparation_store=preparation_store,
        baseline_period_end=args.baseline_period_end,
        generated_at=generated_at,
    )
    write_json(args.report_out, report.to_dict())
    print(
        f"report: {report.captured_count}/{report.member_count} captured; "
        f"freeze_ready={report.freeze_ready}; sha256={report.report_sha256}"
    )

    if args.freeze:
        if args.bundle_out is None:
            parser.error("--freeze requires --bundle-out")
        bundle = freeze_complete_bundle(
            universe=universe,
            expectation_store=expectation_store,
            preparation_store=preparation_store,
            baseline_period_end=args.baseline_period_end,
            generated_at=generated_at,
        )
        write_json(args.bundle_out, bundle.to_dict())
        print(f"bundle: {args.bundle_out}; sha256={bundle.bundle_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
