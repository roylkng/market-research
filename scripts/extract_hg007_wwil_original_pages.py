"""Materialize original BSE WWIL page text with exact source and page hashes.

Uses the SS002 deterministic original-PDF parser. A page's extracted text
is *not* an image/visual inspection or independently approved economic fact.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg007_original_pages import (
    build_original_pdf_page_packet,
    validate_original_pdf_page_packet,
)


def _serialize(packet: dict) -> str:
    return json.dumps(
        packet, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--print-pages", action="store_true")
    args = parser.parse_args()

    if args.verify_existing and args.out is None:
        parser.error("--verify-existing requires --out")
    packet = build_original_pdf_page_packet(args.repo_root)
    validate_original_pdf_page_packet(packet)
    encoded = _serialize(packet)
    if args.out is not None:
        if args.verify_existing:
            if args.out.read_text(encoding="utf-8") != encoded:
                raise ValueError("source-pinned original WWIL PDF text packet drifted")
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as output:
                output.write(encoded)

    print(json.dumps({
        "document_review_id": packet["document_review_id"],
        "original_pdf_sha256": packet["original_pdf_sha256"],
        "page_count": packet["page_count"],
        "page_text_sha256": [item["text_sha256"] for item in packet["pages"]],
        "page_text_lengths": [item["char_count"] for item in packet["pages"]],
        "original_semantic_audit_complete": False,
        "live_capital_allowed": False,
    }, sort_keys=True))
    if args.print_pages:
        for page in packet["pages"]:
            print(f"\n========== ORIGINAL PDF PAGE {page['page_number']} ==========")
            print(page["extracted_text"])
            print(f"========== END PAGE {page['page_number']} ==========\n")


if __name__ == "__main__":
    main()
