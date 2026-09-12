from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.attribution import (
    advance_attribution,
    new_attribution_state,
    summarize_attribution,
)
from marketlab.paperfund_state import validate_fund_state


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Advance one PF001 benchmark-attribution session"
    )
    parser.add_argument("--session-date", required=True)
    parser.add_argument("--fund-state", required=True)
    parser.add_argument("--benchmark-bar", required=True)
    parser.add_argument("--benchmark-source-ref", required=True)
    parser.add_argument("--attribution-state")
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-out", required=True)
    parser.add_argument("--benchmark-name", default="NIFTY 500")
    args = parser.parse_args()

    fund_payload = _load_json(Path(args.fund_state))
    if not isinstance(fund_payload, dict):
        raise TypeError("fund-state payload must be an object")
    fund_errors = validate_fund_state(fund_payload)
    if fund_errors:
        raise ValueError({"fund_state_errors": fund_errors})

    benchmark_payload = _load_json(Path(args.benchmark_bar))
    if not isinstance(benchmark_payload, dict):
        raise TypeError("benchmark-bar payload must be an object")

    if args.attribution_state:
        attribution_payload = _load_json(Path(args.attribution_state))
        if not isinstance(attribution_payload, dict):
            raise TypeError("attribution-state payload must be an object")
        attribution = attribution_payload
    else:
        attribution = new_attribution_state(
            fund_payload,
            benchmark_name=args.benchmark_name,
            benchmark_basis="PRICE",
            benchmark_source_ref=args.benchmark_source_ref,
        )

    attribution = advance_attribution(
        attribution,
        fund_payload,
        session_date=args.session_date,
        benchmark_bar=benchmark_payload,
    )
    summary = summarize_attribution(attribution)

    _write_json(Path(args.out), attribution)
    _write_json(Path(args.summary_out), summary)


if __name__ == "__main__":
    main()
