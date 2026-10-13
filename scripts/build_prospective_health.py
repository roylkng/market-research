from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.prospective_health import (
    build_prospective_health_summary,
    health_clock_markers,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write(path: Path, payload: object) -> None:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build derived MarketLab prospective health snapshot"
    )
    parser.add_argument("--as-of-date")
    parser.add_argument("--as-of-utc", help="Real UTC snapshot timestamp; derives close and source-due gates")
    parser.add_argument("--after-market-close", action="store_true")
    parser.add_argument("--sc001-source-cutoff-passed", action="store_true", default=None)
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--sc001-ledger", type=Path, required=True)
    parser.add_argument("--sc002-ledger", type=Path, required=True)
    parser.add_argument("--sc003-ledger", type=Path, required=True)
    parser.add_argument("--rm001-sc001-size-ledger", type=Path, required=True)
    parser.add_argument("--rm001-sc002-industry-ledger", type=Path, required=True)
    parser.add_argument("--t004-decision-ledger", type=Path, required=True)
    parser.add_argument("--t004-outcome-ledger", type=Path, required=True)
    parser.add_argument("--t004-readiness", type=Path, required=True)
    parser.add_argument("--t006-decision-ledger", type=Path, required=True)
    parser.add_argument("--t006-outcome-ledger", type=Path, required=True)
    parser.add_argument("--c002-forecast-ledger", type=Path, required=True)
    parser.add_argument("--c002-outcome-ledger", type=Path, required=True)
    parser.add_argument("--h024-summary", type=Path, required=True)
    parser.add_argument("--t012-trial-ledger", type=Path)
    parser.add_argument("--t012-decision-ledger", type=Path)
    parser.add_argument("--t012-outcome-ledger", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.as_of_utc is not None:
        if args.after_market_close or args.sc001_source_cutoff_passed is not None:
            raise ValueError(
                "realtime --as-of-utc must not be combined with manual clock flags"
            )
        clock = health_clock_markers(args.as_of_utc)
        if args.as_of_date is not None and args.as_of_date != clock["as_of_date"]:
            raise ValueError("as-of date differs from observed IST calendar date")
        session_day = str(clock["as_of_date"])
        after_close = bool(clock["after_market_close"])
        sc001_due = bool(clock["sc001_source_cutoff_passed"])
    else:
        if args.as_of_date is None:
            raise ValueError("an explicit --as-of-date or --as-of-utc is required")
        session_day = args.as_of_date
        after_close = args.after_market_close
        sc001_due = args.sc001_source_cutoff_passed
    summary = build_prospective_health_summary(
        as_of_date=session_day,
        after_market_close=after_close,
        sc001_source_cutoff_passed=sc001_due,
        calendar=load_calendar_snapshot(args.calendar),
        sc001_ledger=_load(args.sc001_ledger),
        sc002_ledger=_load(args.sc002_ledger),
        sc003_ledger=_load(args.sc003_ledger),
        rm001_sc001_size_ledger=_load(args.rm001_sc001_size_ledger),
        rm001_sc002_industry_ledger=_load(
            args.rm001_sc002_industry_ledger
        ),
        t004_decision_ledger=_load(args.t004_decision_ledger),
        t004_outcome_ledger=_load(args.t004_outcome_ledger),
        t004_readiness=_load(args.t004_readiness),
        t006_decision_ledger=_load(args.t006_decision_ledger),
        t006_outcome_ledger=_load(args.t006_outcome_ledger),
        c002_forecast_ledger=_load(args.c002_forecast_ledger),
        c002_outcome_ledger=_load(args.c002_outcome_ledger),
        h024_summary=_load(args.h024_summary),
        t012_trial_ledger=(
            None if args.t012_trial_ledger is None else _load(args.t012_trial_ledger)
        ),
        t012_decision_ledger=(
            None if args.t012_decision_ledger is None
            else _load(args.t012_decision_ledger)
        ),
        t012_outcome_ledger=(
            None if args.t012_outcome_ledger is None
            else _load(args.t012_outcome_ledger)
        ),
    )
    _write(args.output, summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
