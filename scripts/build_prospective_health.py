from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.prospective_health import build_prospective_health_summary


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
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--after-market-close", action="store_true")
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--sc001-ledger", type=Path, required=True)
    parser.add_argument("--sc002-ledger", type=Path, required=True)
    parser.add_argument("--sc003-ledger", type=Path, required=True)
    parser.add_argument("--t004-decision-ledger", type=Path, required=True)
    parser.add_argument("--t004-outcome-ledger", type=Path, required=True)
    parser.add_argument("--t006-decision-ledger", type=Path, required=True)
    parser.add_argument("--t006-outcome-ledger", type=Path, required=True)
    parser.add_argument("--c002-forecast-ledger", type=Path, required=True)
    parser.add_argument("--c002-outcome-ledger", type=Path, required=True)
    parser.add_argument("--h024-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_prospective_health_summary(
        as_of_date=args.as_of_date,
        after_market_close=args.after_market_close,
        calendar=load_calendar_snapshot(args.calendar),
        sc001_ledger=_load(args.sc001_ledger),
        sc002_ledger=_load(args.sc002_ledger),
        sc003_ledger=_load(args.sc003_ledger),
        t004_decision_ledger=_load(args.t004_decision_ledger),
        t004_outcome_ledger=_load(args.t004_outcome_ledger),
        t006_decision_ledger=_load(args.t006_decision_ledger),
        t006_outcome_ledger=_load(args.t006_outcome_ledger),
        c002_forecast_ledger=_load(args.c002_forecast_ledger),
        c002_outcome_ledger=_load(args.c002_outcome_ledger),
        h024_summary=_load(args.h024_summary),
    )
    _write(args.output, summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
