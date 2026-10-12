"""Reproduce all 28 HG007 research cases with NSE EQ/BE market-source risks.

Does not download market data or imply source turnover is an executable
ticket size, a trade/return, company upside ranking, or capital permission.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_full_liquidity_overlay import (
    build_liquidity_readiness,
    load_source_packets,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    casework, original_20, alternative, source_receipts = load_source_packets(
        args.repo_root
    )
    report = build_liquidity_readiness(
        casework, original_20, alternative, provenance=source_receipts
    )
    encoded = json.dumps(
        report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("original 28-company EQ/BE liquidity overlay drifted")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
    print(json.dumps({
        "overlay_id": report["overlay_id"],
        "company_count": report["original_hg002_selected_count_preserved"],
        "complete_EQ_20days": report["twenty_session_EQ_complete_company_count"],
        "BE_series_missing_EQ_days": report[
            "twenty_session_EQ_partial_BE_verified_company_count"
        ],
        "descriptive_value_bands": {
            band: len(names)
            for band, names in report[
                "historical_cash_turnover_bands_not_investment_ranks"
            ].items()
        },
        "live_transaction_cases_below_one_crore_source_median": (
            report["direct_or_procedural_with_median_daily_turnover_below_one_crore"]
        ),
        "forward_returns_calculated": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
