"""Reconcile two original NSE XBRLs on fixed net promoter shares versus QIP dilution.

The printed result is *not* a current pledge change or portfolio signal.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_promoter_net_ownership import build_primary_promoter_reconciliation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.output is None:
        parser.error("--verify-existing requires --output")

    result = build_primary_promoter_reconciliation(args.repo_root)
    serialized = json.dumps(
        result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.output is not None:
        if args.verify_existing:
            if args.output.read_text(encoding="utf-8") != serialized:
                raise ValueError("two-source promoter reconciliation result was altered")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as target:
                target.write(serialized)
    print(json.dumps({
        "review_id": result["review_id"],
        "source_june_shares": result["promoter_group_reported_shares_june"],
        "source_sept29_shares": result["promoter_group_reported_shares_sept29"],
        "net_reported_change": result[
            "net_change_in_reported_promoter_group_shares_between_filings"
        ],
        "qip_issued_shares": result["qip_issued_basic_share_increase"],
        "sep29_pledged_shares": result["promoter_group_pledged_shares_reported_sept29"],
        "no_gross_trades_proven": False,
        "capital_authorized": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
