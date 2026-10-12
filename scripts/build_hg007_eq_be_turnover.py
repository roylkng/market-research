"""Replay the source-pinned 28-name original EQ/BE traded-value crosswalk.

An observed BE trade-for-trade value is NOT an EQ-series executable fill,
holding-period return, strategy authorization, or price impact estimate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_eq_be_turnover import (
    build_mixed_series_context,
    load_frozen_sources,
    validate_mixed_series_context,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    old, missing, receipts = load_frozen_sources(args.repo_root)
    result = build_mixed_series_context(old, missing, provenance=receipts)
    validate_mixed_series_context(result)
    content = json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != content:
                raise ValueError("mixed NSE settlement historical source changed")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as file:
                file.write(content)
    print(json.dumps({
        "audit_id": result["audit_id"],
        "original_companies": result["original_company_selection_count"],
        "eq_only_source_complete": result["original_eq_only_complete_company_count"],
        "mixed_eq_be_original_company_count": result["original_mixed_eq_be_company_count"],
        "mixed_case_summary": [
            {
                "symbol": row["symbol"],
                "eq_days": row["source_eq_count"],
                "be_days": row["source_be_count"],
                "median_daily_mixed_traded_value_inr_crore": row[
                    "mixed_series_turnover_statistics"
                ]["median_mixed_eq_be_daily_value_inr_crore"],
            }
            for row in result["company_context"]
            if row["settlement_regime"] == "MIXED_EQ_AND_BE_TRADE_FOR_TRADE_HISTORICAL_TURNOVER"
        ],
        "broker_execution_proven": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
