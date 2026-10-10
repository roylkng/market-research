"""Reproduce bounded issuer-source facts from exact original WWIL PDF pages.

Review scope is original PDF *text*. Cash consideration and loan repayment
priority are verified as issuer statements, not independently verified
business economics. No confidence, target price or capital authorization.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_wwil_terms_review import (
    build_text_facts,
    load_verified_page_text,
)


def _serialize(value: dict) -> str:
    return json.dumps(
        value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")

    original_pages = load_verified_page_text(args.repo_root)
    result = build_text_facts(original_pages)
    serialized = _serialize(result)
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != serialized:
                raise ValueError("frozen issuer fact packet does not match original pages")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as handle:
                handle.write(serialized)
    print(json.dumps({
        "id": result["review_id"],
        "original_pdf_sha256": result["source_original_pdf_sha256"],
        "page_count": result["source_pdf_page_count"],
        "issuer_reported_fact_count": result["disclosed_term_count"],
        "parent_annual_intercompany_coupon_simple_cr": result[
            "arithmetic_crosschecks"
        ]["parent_200cr_annual_nominal_12pct_intragroup_coupon_inr_crore"],
        "original_source_50cr_conversion_optional": True,
        "visual_review_complete": result["page_image_visual_review_complete"],
        "bta_transfer_complete": result["wwil_transfer_legally_completed_verified"],
        "expected_returns_calculated": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
