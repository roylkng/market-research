"""Rebuild the frozen HG007 28-company evidence-acquisition board from original sources.

No web/network requests, no price refresh, no future returns and no trading.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_casework import build_casework_board, load_exact_sources


def _serialize(payload: object) -> str:
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

    sources, receipts = load_exact_sources(args.repo_root)
    result = build_casework_board(sources, receipts)
    serialized = _serialize(result)
    if args.out is not None:
        output = args.out
        if args.verify_existing:
            if output.read_text(encoding="utf-8") != serialized:
                raise ValueError("HG007 casework changed from exact frozen sources")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(serialized, encoding="utf-8")
    print(json.dumps({
        "casework_id": result["casework_id"],
        "source_membership_count": result["source_membership_count"],
        "active_direct": result["source_active_direct_catalyst_count"],
        "procedural": result["source_procedural_direct_review_count"],
        "nonlive_or_pending": result["source_nonlive_or_pending_count"],
        "source_economic_context_case_count": result["source_economic_context_case_count"],
        "current_publishable_company_probability_count": (
            result["current_case_specific_survivor_probability_surface_count"]
        ),
        "october_newer_unaudited_case_count": len(
            result["newer_october_pilot_cases_needing_stage_reconciliation"]
        ),
        "approved_stock_recommendation_count": result["approved_stock_recommendation_count"],
        "live_capital_allowed": result["live_capital_allowed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
