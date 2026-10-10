"""Reproduce source-image-bound NPST Q1 and Reg32 table crosswalk.

Five original source-image SHA-256s and the earlier financial ledger are
necessary. No audited statements, price target or live capital is inferred.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_npst_visual_crosswalk import (
    build_visual_quality_crosswalk,
    load_visual_and_funding_evidence,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    p020, images, receipts = load_visual_and_funding_evidence(args.repo_root)
    result = build_visual_quality_crosswalk(p020, images, receipts)
    data = json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != data:
                raise ValueError("NPST original source image visual crosswalk altered")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as handle:
                handle.write(data)
    print(json.dumps({
        "review_id": result["review_id"],
        "visually_checked_pages": result["checked_source_visual_page_count"],
        "reg32_table_columns_align_with_numbers": result[
            "confirmed_reg32_table_column_alignment"
        ],
        "q1fy27_ebitda_tables_inr_cr": result[
            "confirmed_q1fy27_two_table_ebitda_inr_crore"
        ],
        "q1fy27_ebitda_graphic_inr_cr": result[
            "source_graphic_q1fy27_ebitda_inr_crore"
        ],
        "q1fy27_other_income_inr_cr": result["q1fy27_other_income_inr_cr"],
        "q1fy27_other_expenses_inr_cr": result["q1fy27_other_expenses_inr_cr"],
        "actual_cash_and_sustainable_income_verified": False,
        "portfolio_eligibility_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
