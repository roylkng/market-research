"""Reproduce the original NSE 20-session liquidity for all frozen HG002 names.

No web access, no research name substitution, no execution or return labels.
It uses the already retained P036 whole-market raw UDiFF files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_28_liquidity import (
    build_twenty_day_all_28,
    validate_twenty_day_all_28,
)


def _text(packet: dict) -> str:
    return json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--output", type=Path)
    p.add_argument("--verify-existing", action="store_true")
    args = p.parse_args()
    if args.verify_existing and args.output is None:
        p.error("--verify-existing requires --output")
    report = build_twenty_day_all_28(args.repo_root)
    validate_twenty_day_all_28(report)
    encoded = _text(report)
    if args.output is not None:
        if args.verify_existing:
            if args.output.read_text(encoding="utf-8") != encoded:
                raise ValueError("28-stock official liquidity source report changed")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as f:
                f.write(encoded)

    complete = [
        {"symbol": row["symbol"], "median_turnover_cr":
         row["turnover_statistics_if_complete"]["median_daily_traded_value_inr_crore"],
         "ten_lakh_over_1pct_median":
         row["turnover_statistics_if_complete"]["ticket_to_one_percent_of_median_turnover"][
             "1000000"
         ]}
        for row in report["casework"] if row["exact_20_session_coverage_complete"]
    ]
    complete.sort(key=lambda row: row["ten_lakh_over_1pct_median"], reverse=True)
    print(json.dumps({
        "audit_id": report["audit_id"],
        "frozen_company_count": report["original_outside_u001_symbol_count"],
        "source_completed_sessions": report["original_completed_sessions"],
        "source_complete_company_count": report["complete_20_session_equity_company_count"],
        "incomplete_company_count": report["incomplete_or_changed_identity_company_count"],
        "lowest_median_turnover_examples_not_stock_ranking": complete[:8],
        "historical_turnover_is_executable_capacity": False,
        "investment_recommendations_generated": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
