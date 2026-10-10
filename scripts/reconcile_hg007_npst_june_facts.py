"""Materialize NPST original Q1 FY27 and June Regulation 32 fact bridge.

Do not interpret unused proceeds as cash or four quarterly EBITDA periods as
validated annual earnings. All outputs remain strictly research-only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_npst_june_facts import (
    build_npst_financial_and_funding_ledger,
    load_npst_originals,
)


def _encoded(payload: dict) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")

    originals, hurdle, receipts = load_npst_originals(args.repo_root)
    report = build_npst_financial_and_funding_ledger(
        originals, hurdle, receipts
    )
    data = _encoded(report)
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != data:
                raise ValueError("original NPST June quarter reported-facts ledger drifted")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as dst:
                dst.write(data)

    funding = report["fundraising"]
    quarter = report["financials_q1fy27_consolidated_issuer_presentation"]
    print(json.dumps({
        "review_id": report["review_id"],
        "raised_cr": funding["raised_inr_crore"],
        "utilised_through_june_cr": funding["total_utilised_through_june_inr_crore"],
        "derived_unused_allocation_not_bank_cash_cr": funding[
            "derived_remaining_allocation_not_bank_balance_inr_crore"
        ],
        "q1fy27_reported_table_ebitda_cr": quarter["ebitda_financial_tables_inr_crore"],
        "different_graphic_ebitda_cr": quarter["ebitda_graphic_discrepancy_inr_crore"],
        "standalone_and_audited_statement_reconciled": quarter[
            "standalone_to_consolidated_and_audited_statement_reconciled"
        ],
        "future_expected_returns": report["probability_weighted_expected_return_calculated"],
        "portfolio_eligibility": report["portfolio_eligibility_allowed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
