"""Reconcile original 48-page ANANTRAJ cloud demerger terms and unknowns."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_anantraj_scheme_terms import build_source_clause_review


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    result = build_source_clause_review(args.repo_root)
    encoded = json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("original 48-page scheme clause audit was modified")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as dst:
                dst.write(encoded)
    print(json.dumps({
        "audit_id": result["review_id"],
        "source_page_count": 48,
        "source_clauses": result["reviewed_specific_legal_clause_count"],
        "authorized_illustrative_shares": result["conditional_capital_reconciliation"][
            "newco_authorized_ordinary_share_capacity_in_draft"
        ],
        "asset_and_liability_values_verified": False,
        "court_scheme_effective": False,
        "capital_or_returns_authorized": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
