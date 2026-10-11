"""Reproduce conditional two-layer ANANTRAJ/Ashok Cloud scheme share ownership.

The original three issuer PDFs and old HG005 share proxy are
byte-for-byte Git-pinned. Results are *hypothetical*, not effective.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_anantraj_lookthrough import (
    build_conditional_ownership_lookthrough,
    load_original_ownership_sources,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")

    documents, market, source_receipts = load_original_ownership_sources(args.repo_root)
    result = build_conditional_ownership_lookthrough(
        documents, market, original_source_provenance=source_receipts
    )
    raw = json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != raw:
                raise ValueError("original source conditional economics changed")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(raw)
    hypothesis = result["illustrative_no_other_newco_share_events_scenario"]
    print(json.dumps({
        "id": result["review_id"],
        "parent_ashok_newco_shares_after_july21": (
            result["original_rights_subscription"]["parent_newco_shares_after_july21_subscription"]
        ),
        "old_hg005_fd_share_proxy": (
            result["historical_share_count_proxy"]["legacy_implied_fully_diluted_share_count"]
        ),
        "parent_retained_pct_conditional": (
            100 * hypothesis["hypothetical_parent_retained_newco_equity_fraction"]
        ),
        "direct_shareholder_pct_conditional": (
            100 * hypothesis["hypothetical_direct_ARL_shareholder_newco_fraction"]
        ),
        "demerger_effective": False,
        "future_eligible_share_count_verified": False,
        "stock_expected_return_calculated": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
