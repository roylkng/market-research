"""Build immutable 28-company casework overlay with QIP capital-base warning."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_capital_readiness import (
    build_capital_readiness_overlay,
    load_casework_with_qip,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    board, qip, receipts = load_casework_with_qip(args.repo_root)
    result = build_capital_readiness_overlay(
        board, qip, source_receipts=receipts
    )
    encoded = json.dumps(
        result, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("casework capital readiness overlay altered")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
    print(json.dumps({
        "overlay_id": result["overlay_id"],
        "original_company_count": result["original_hg007_cohort_count_preserved"],
        "newly_flagged_stale_share_denominator": result["capital_denominator_stale_symbols"],
        "other_companies_not_rechecked_for_capital_basis": result[
            "capital_denominator_unreviewed_others"
        ],
        "approved_investment_rankings": result["investment_opportunities_ranked"],
        "live_capital_allowed": result["live_capital_allowed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
