"""Materialize audited INOXGREEN Sep QIP share-count correction, no trading.

Inputs are original NSE Sep 29 QIP PDF/receipt, frozen HG005 October 1
market reference and SS002 October 9 official price. All content-hashed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_qip_capitalization import (
    build_qip_denominator_audit,
    load_verified_source_references,
)


def _encode(report: dict) -> str:
    return json.dumps(
        report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")

    old, oct9, qip, provenance = load_verified_source_references(args.repo_root)
    corrected = build_qip_denominator_audit(
        old, oct9, qip, provenance=provenance
    )
    encoded = _encode(corrected)
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("post-QIP source-verified denominator result was modified")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as output:
                output.write(encoded)

    old_cap = corrected["frozen_hg005_oct1_historical_result_not_modified"]
    cap = corrected["post_qip_basic_share_capital_sensitivities"]
    print(json.dumps({
        "audit_id": corrected["audit_id"],
        "original_qip_pdf_sha256": provenance["qip_original_pdf"]["sha256"],
        "old_oct1_march_fd_cap_cr": old_cap["reported_old_market_cap_inr_crore"],
        "corrected_oct1_post_qip_basic_cap_cr": cap["2026-10-01"][
            "implied_post_qip_basic_market_cap_inr_crore"
        ],
        "corrected_oct9_post_qip_basic_cap_cr": cap["2026-10-09"][
            "implied_post_qip_basic_market_cap_inr_crore"
        ],
        "verified_current_fully_diluted_cap": False,
        "valuation_multiple_or_target_price_authorized": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
