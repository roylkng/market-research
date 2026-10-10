"""Deterministic page-wise TEXT LAYER extraction of exact original 7 Oct BSE PDF.

Not a substitute for full PDF validation, visual-page inspection, or
independent interpretation of BTA annexures. Keeps original SHA boundaries.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from pypdf import PdfReader

PDF_SHA = "541277b2c8a6d732bc77e62c6b637c98b92a5044dddeac09e34038d8d4d5d451"
PDF_PATH = Path(
    "research/hg007/wwil-bse-original/original-raw/sha256/"
    + PDF_SHA
    + ".pdf"
)
RECEIPT_PATH = Path(
    "research/hg007/wwil-bse-original/official-source-receipt-v1.json"
)
AUDIT_ID = "HG007-P004-WWIL-ORIGINAL-BSE-PAGE-TEXT-v1"
MAX_SOURCE_PAGES = 35
MAX_PAGE_CHARACTERS = 2_000_000


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def extract_original_pdf_pages(
    raw_pdf: bytes,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(raw_pdf, bytes) or len(raw_pdf) != 354999:
        raise ValueError("original PDF byte length differs from source custody receipt")
    if _sha(raw_pdf) != PDF_SHA:
        raise ValueError("original PDF SHA differs from immutable BSE custody")
    if not isinstance(receipt, dict):
        raise TypeError("source custody receipt must be object")
    if (
        receipt.get("original_pdf_sha256") != PDF_SHA
        or receipt.get("original_pdf_byte_count") != len(raw_pdf)
        or receipt.get("http_status") != 200
        or receipt.get("state") != "PDF_SOURCE_BYTES_CAPTURED_NOT_SEMANTICALLY_AUDITED"
        or receipt.get("original_page_semantic_audit_approved") is not False
        or receipt.get("live_capital_allowed") is not False
    ):
        raise ValueError("original filing source custody identity/status changed")
    try:
        reader = PdfReader(io.BytesIO(raw_pdf), strict=True)
        if reader.is_encrypted:
            raise ValueError("original filing encrypted; not automatically extractable")
        count = len(reader.pages)
        if not 1 <= count <= MAX_SOURCE_PAGES:
            raise ValueError("original BSE filing unexpected page count")
        pages = []
        for i in range(count):
            extracted = reader.pages[i].extract_text()
            if not isinstance(extracted, str):
                raise TypeError("PDF page text extractor yielded nonstring")
            if len(extracted) > MAX_PAGE_CHARACTERS:
                raise ValueError("original BSE page text exceeded bounded size")
            raw_text = extracted.encode("utf-8")
            pages.append({
                "source_page_number": i + 1,
                "text_sha256": _sha(raw_text),
                "text_length": len(extracted),
                "pypdf_text_layer": extracted,
                "independent_visual_page_review_complete": False,
                "factual_semantic_approval": False,
            })
    except (ValueError, TypeError):
        raise
    except Exception as exc:
        raise ValueError(f"original source PDF extraction failed: {type(exc).__name__}") from exc

    return {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "SHA_VERIFIED_ORIGINAL_PDF_TEXT_LAYER_NOT_SEMANTIC_APPROVAL",
        "exact_original_file_sha256": PDF_SHA,
        "original_file_byte_count": len(raw_pdf),
        "original_bse_source_url": receipt["original_source_url"],
        "captured_at_utc": receipt["captured_at_utc"],
        "page_count": count,
        "pages": pages,
        "text_layer_extraction_completed": True,
        "entire_original_page_visual_review_completed": False,
        "filing_terms_independently_semantically_audited": False,
        "funding_and_security_conversion_legally_verified": False,
        "transaction_conditions_precedent_satisfied_verified": False,
        "normalized_wwil_earnings_and_cash_flow_verified": False,
        "case_specific_valuation_authorized": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def read_original_source(root: Path) -> tuple[bytes, dict[str, Any]]:
    raw_pdf = (root / PDF_PATH).read_bytes()
    source = json.loads((root / RECEIPT_PATH).read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise TypeError("original BSE receipt JSON root must be an object")
    return raw_pdf, source


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    raw_pdf, receipt = read_original_source(args.repo_root)
    result = extract_original_pdf_pages(raw_pdf, receipt)
    serialized = json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    ) + "\n"
    if args.verify_existing:
        if args.out.read_text(encoding="utf-8") != serialized:
            raise ValueError("existing original PDF page text differs from exact source")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")
    print(json.dumps({
        "audit_id": AUDIT_ID,
        "page_count": result["page_count"],
        "page_text_lengths": [row["text_length"] for row in result["pages"]],
        "source_sha256": PDF_SHA,
        "semantic_approved": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
