"""Build source-pinned 28-case Sep29 share and pledge evidence overlay.

Source dates and first public broadcast remain immutable; no October-current
FD or expected investment returns are inferred from Sept29 ownership.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_verified_shp_overlay import (
    build_asof_fd_governance_overlay,
    load_sources,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    sources, provenance = load_sources(args.repo_root)
    result = build_asof_fd_governance_overlay(sources, provenance)
    serialized = json.dumps(
        result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != serialized:
                raise ValueError("source-pinned original Sept29 governance packet was altered")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as output:
                output.write(serialized)
    ino = next(x for x in result["company_cases"] if x["symbol"] == "INOXGREEN")
    facts = ino["asof_29sep_exchange_source_update"]
    print(json.dumps({
        "audit_id": result["audit_id"],
        "original_28_case_count": result["original_28_case_count"],
        "source_report_date": result["original_nse_xbrl_asof_date"],
        "source_public_first_seen_at_utc": result["original_nse_xbrl_public_at_utc"],
        "sept29_fully_diluted_shares": facts["fully_diluted_shares_as_of_sep29"],
        "sept29_pledged_shares": facts["pledged_shares_at_sep29"],
        "oct09_sept29_fd_reference_inr_crore": facts[
            "sept29_fd_shares_at_oct9_price_inr_crore"
        ],
        "oct11_current_issued_and_fd_verified": False,
        "current_fair_value_or_forward_returns_permitted": False,
        "live_capital_allowed": False,
    }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
