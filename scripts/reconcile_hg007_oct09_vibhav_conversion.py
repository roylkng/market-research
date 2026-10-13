"""Publish reproducible Oct9 Vibhav minority stake correction for 28 cases.

No prospective-return labels, acquisition close certification or capital.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_vibhav_conversion_stage import (
    load_pinned_sources,
    reconcile_oct09_status,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    inputs, receipts = load_pinned_sources(args.repo_root)
    result = reconcile_oct09_status(inputs, receipts)
    encoded = json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("original dated conversion overlay changed")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
    print(json.dumps({
        "review_id": result["review_id"],
        "original_28_count": len(result["casework_with_current_vepl_milestone"]),
        "post_conversion_vepl_equity_status": result[
            "oct09_completed_equity_milestone"
        ]["vepl_deposit_to_equity_conversion_completed"],
        "post_conversion_parent_pct": result[
            "oct09_completed_equity_milestone"
        ]["issuer_reported_vibhav_ownership_pct"],
        "wwil_bta_legal_close_verified": result[
            "oct09_completed_equity_milestone"
        ]["wwil_underlying_business_transfer_closing_proven"],
        "expected_returns": result["expected_returns_calculated"],
        "live_capital_allowed": result["live_capital_allowed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
