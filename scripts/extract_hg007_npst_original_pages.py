"""Materialize original Q1 FY27 NPST BSE issuer PDF pages, no economic claims."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_npst_original_pages import (
    build_npst_original_page_evidence,
    validate_npst_source_packet,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--print-matches", action="store_true")
    args = parser.parse_args()
    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    packet = build_npst_original_page_evidence(args.repo_root)
    validate_npst_source_packet(packet)
    text = json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != text:
                raise ValueError("NPST original PDF page content changed from immutable source")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as target:
                target.write(text)

    print(json.dumps({
        "source_evidence_id": packet["source_evidence_id"],
        "source_document_count": packet["document_count"],
        "source_original_page_count": packet["original_page_count"],
        "source_document_sha256": [
            row["original_source_sha256"] for row in packet["original_documents"]
        ],
        "unspent_balance_and_ebitda_semantic_approval": False,
        "ambiguous_monitoring_excluded": True,
        "live_capital_allowed": False,
    }, sort_keys=True))
    if args.print_matches:
        for doc in packet["original_documents"]:
            print("\n==== SOURCE:", doc["source_id"], "====")
            for item in doc["search_snippet_first_occurrence_by_page_keyword"]:
                print(json.dumps(item, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
