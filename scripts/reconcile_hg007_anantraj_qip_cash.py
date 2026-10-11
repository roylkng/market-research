"""Reproduce the original NSE 21-page Anant Raj June QIP cash/debt case.

No current bank balance, demerger transfer amount, earnings forecast,
company-completion probability or portfolio order is calculated.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_anantraj_qip_cash_ledger import build_qip_scheme_cash_review


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    payload = build_qip_scheme_cash_review(args.repo_root)
    encoded = json.dumps(
        payload, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("Anant Raj original QIP/de-merger source ledger changed")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as out:
                out.write(encoded)
    print(json.dumps({
        "review_id": payload["review_id"],
        "original_nse_pdf_sha256": payload["original_nse_pdf_sha256"],
        "qip_gross_inr_cr": payload["reported_QIP_gross_proceeds_inr_crore"],
        "qip_used_june_inr_cr": payload["reported_cumulative_used_by_june30_inr_crore"],
        "qip_unutilized_june_inr_cr": payload["reported_unused_by_june30_inr_crore"],
        "cloud_allocated_june_inr_cr": 440.0,
        "cloud_used_june_inr_cr": payload["historical_cloud_spend_for_subsidiary_inr_crore"],
        "cloud_unutilized_june_inr_cr": payload[
            "historical_cloud_qip_unused_allocation_inr_crore"
        ],
        "fdr_difference_inr_cr": payload[
            "fdr_less_unutilized_report_discrepancy_inr_crore"
        ],
        "pro_forma_newco_cash_verified": False,
        "legal_transfer_completed": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
