"""Bind every original Anant Raj 48-page scheme page to its original PDF SHA.

Produces 48 short, individually retrievable source-text files and one index.
Page-topic tags are search aids, not legal/financial conclusions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_anantraj_scheme_pages import (
    build_page_text_evidence,
    load_original_scheme_source,
    write_or_verify_page_evidence,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()

    original, source_page_receipts = load_original_scheme_source(args.repo_root)
    result, pages = build_page_text_evidence(original, source_page_receipts)
    write_or_verify_page_evidence(
        args.output_dir, result, pages, verify_existing=args.verify_existing
    )
    summary = {
        "index_id": result["index_id"],
        "pdf_original_sha256": result["pdf_original_sha256"],
        "page_count": result["page_count"],
        "keyword_counts_search_only": result["label_counts_search_only"],
        "all_pages_verifiable": result["page_text_fully_extracted_and_sha_verified"],
        "asset_liability_values_independently_verified": False,
        "scheme_effective_date_verified": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    print(json.dumps(summary, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
