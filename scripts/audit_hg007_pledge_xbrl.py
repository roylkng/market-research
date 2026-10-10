"""Publish exact-source September 29 INOXGREEN pledge/FD as-of research facts.

This verifies an original original NSE shareholding XBRL and prior June,
not a post-September corporate-action ledger or future trading result.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_pledge_xbrl import (
    build_sept29_promoter_pledge_audit,
    load_original_source,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    original, sept, june = load_original_source(args.repo_root)
    packet = build_sept29_promoter_pledge_audit(original, sept, june)
    payload = json.dumps(
        packet, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != payload:
                raise ValueError("original NSE pledge proof changed from frozen source")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as output:
                output.write(payload)
    print(json.dumps({
        "audit_id": packet["audit_id"],
        "original_sha256": packet["original_xbrl_sha256"],
        "issuer_asof_date": packet["issuer_asof_date"],
        "named_pledging_promoter": packet["source_pledging_named_promoter"],
        "verified_pledged_shares_asof_date": packet["named_promoter_pledged_shares"],
        "percent_of_held_promoter_group": packet["pledged_percent_of_promoter_group"],
        "percent_of_issued_company_shares": packet["pledged_percent_of_all_issued"],
        "issued_shares": packet["listed_company_total_basic_shares"],
        "reported_fd_shares": packet["listed_company_total_fully_diluted_shares"],
        "latest_october_fd_confirmed": False,
        "portfolio_eligibility_allowed": False,
    }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
