"""Rebuild the HG007 five-company source liquidity readiness overlay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_liquidity_readiness import (
    build_five_case_liquidity_overlay,
    load_verified_issuer_sources,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    cases, day, history, sources = load_verified_issuer_sources(args.repo_root)
    payload = build_five_case_liquidity_overlay(
        cases, day, history, sources
    )
    result = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != result:
                raise ValueError("five-company source liquidity overlay has changed")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as f:
                f.write(result)
    print(json.dumps({
        "overlay_id": payload["overlay_id"],
        "case_count": payload["company_case_count"],
        "turnover_median_inr_crore": {
            c["symbol"]: round(
                c["official_nse_historical_turnover_overlay"][
                    "median_daily_traded_value_inr_crore"
                ], 5
            )
            for c in payload["company_casework"]
        },
        "ticket_exceeds_one_pct_source_median": [
            c["symbol"] for c in payload["company_casework"]
            if c["official_nse_historical_turnover_overlay"][
                "ticket_exceeds_one_pct_of_median_daily_turnover"
            ]
        ],
        "investment_recommendations_created": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
