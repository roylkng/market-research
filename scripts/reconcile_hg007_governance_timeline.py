"""Reconcile exact GF001 and P013 NSE pledge facts without lookahead or advice."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_governance_timeline import (
    load_original_source_states,
    reconcile_gov_publication_timeline,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    originals, receipts = load_original_source_states(args.repo_root)
    report = reconcile_gov_publication_timeline(originals, receipts)
    encoded = json.dumps(
        report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("original NSE publication chronology changed")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
    print(json.dumps({
        "event_review_id": report["event_review_id"],
        "oct4_pledge_boolean": report["oct4_lookahead_correct_source"][
            "INOXGREEN_pledge_boolean"
        ],
        "oct8_pledged_shares_disclosed": report["oct8_later_primary_governance_publication"][
            "INOXGREEN_promoter_named_pledged_shares"
        ],
        "oct8_filing_first_public_utc": report["oct8_later_primary_governance_publication"][
            "original_first_public_utc"
        ],
        "promoter_shares_sold_proven": report["conditional_promoter_fraction_reconciliation"][
            "promoter_sold_or_bought_shares_proven"
        ],
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
