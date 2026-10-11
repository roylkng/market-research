"""Reconcile original Sep29 INOXGREEN Reg31 FD shares and promoter pledge.

Exact original NSE XML SHA and dated prior QIP research remain immutable.
This is reported source evidence, not current valuation, company EV or alpha.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_sep29_fd_pledge import build_sep29_report, load_verified_reg31


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")

    raw, capture, original_qip = load_verified_reg31(args.repo_root)
    packet = build_sep29_report(raw, capture, original_qip)
    encoded = json.dumps(
        packet, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("NSE Reg31 original source reconciliation has drifted")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as fp:
                fp.write(encoded)
    print(json.dumps({
        "review_id": packet["review_id"],
        "original_xml_sha256": packet["original_nse_raw_xbrl_sha256"],
        "original_filing_report_date": packet["shareholding_report_date"],
        "original_filing_first_broadcast_utc": packet["shareholding_first_broadcast_utc"],
        "reported_basic_shares": packet["reported_paid_issued_shares"],
        "reported_fd_shares": packet["reported_fully_diluted_shares_including_esop"],
        "reported_esop_shares": packet["reported_outstanding_esop_shares"],
        "reported_promoter_pledged_shares": packet["reported_promoter_pledged_shares"],
        "reported_promoter_pledge_pct_promoter_shares": packet[
            "reported_promoter_pledge_pct_promoter_shares"
        ],
        "oct12_current_fd_verified": False,
        "valuation_authorized": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
