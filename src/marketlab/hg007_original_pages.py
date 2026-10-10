"""Extract and page-bind the original Oct-7 WWIL BSE PDF already held in Git.

This produces a review packet containing exactly the original PDF's *text*
page numbers. The parser is shared with SS002. It does not claim visual
page review, financing verification, BTA completion, or investment merit.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from marketlab.ss002_text import _pdf_segments

EXPECTED_SHA = "541277b2c8a6d732bc77e62c6b637c98b92a5044dddeac09e34038d8d4d5d451"
ORIGINAL_PATH = Path(
    "research/hg007/wwil-bse-original/original-raw/sha256/"
    + EXPECTED_SHA
    + ".pdf"
)
RECEIPT_PATH = Path("research/hg007/wwil-bse-original/official-source-receipt-v1.json")
PILOT_PATH = Path("research/ss002-p004-native-eight-document-decisions-v1.json")
CASE_ID = "HG007-P004-2026-10-07-WWIL-ORIGINAL-PDF-PAGES-v1"
MAX_PAGES = 24
MAX_PAGE_CHARS = 100_000


def _original_bytes(path: Path, expected_sha: str) -> bytes:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha or not raw.startswith(b"%PDF-"):
        raise ValueError("PDF raw bytes fail pinned official original SHA and envelope")
    return raw


def _read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise TypeError(f"expected object: {path}")
    return obj


def build_original_pdf_page_packet(repo_root: Path) -> dict[str, Any]:
    source_raw = _original_bytes(repo_root / ORIGINAL_PATH, EXPECTED_SHA)
    receipt = _read_json(repo_root / RECEIPT_PATH)
    if (
        receipt.get("case_id") != "HG007-P003-INOXGREEN-WWIL-ORIGINAL-BSE-SOURCE-v1"
        or receipt.get("state") != "PDF_SOURCE_BYTES_CAPTURED_NOT_SEMANTICALLY_AUDITED"
        or receipt.get("original_pdf_sha256") != EXPECTED_SHA
        or receipt.get("original_pdf_byte_count") != len(source_raw)
        or receipt.get("http_status") != 200
        or receipt.get("original_page_semantic_audit_approved") is not False
        or receipt.get("live_capital_allowed") is not False
    ):
        raise ValueError("P003 original PDF receipt identity/approval boundary changed")

    pilot = _read_json(repo_root / PILOT_PATH)
    rows = pilot.get("document_rows")
    if not isinstance(rows, list) or len(rows) != 8:
        raise ValueError("SS002 original eight-document native extraction count changed")
    matches = [
        row
        for row in rows
        if row.get("symbol") == "INOXGREEN" and row.get("document_id") == EXPECTED_SHA
    ]
    if len(matches) != 1 or matches[0].get("semantic_audit_status") != (
        "PENDING_INDEPENDENT_SOURCE_REVIEW"
    ):
        raise ValueError("SS002 original WWIL source linkage was altered")

    segments, metadata = _pdf_segments(
        source_raw, document_id=EXPECTED_SHA, prefix="HG007-P004"
    )
    pages = metadata.get("page_count")
    if (
        not isinstance(pages, int)
        or pages < 2
        or pages > MAX_PAGES
        or metadata.get("failed_page_count") != 0
        or metadata.get("empty_page_count") != 0
        or metadata.get("text_page_count") != pages
        or len(segments) != pages
    ):
        raise ValueError("original BSE PDF pages insufficiently text-readable")
    text_pages = []
    for page_idx, segment in enumerate(segments, start=1):
        if (
            segment.get("kind") != "PDF_PAGE"
            or segment.get("locator", {}).get("page_number") != page_idx
            or segment.get("segment_id") != f"HG007-P004:pdf:page:{page_idx:04d}"
        ):
            raise ValueError("original PDF page ordering or locator does not match")
        content = segment.get("text")
        if (
            not isinstance(content, str)
            or not 50 <= len(content) <= MAX_PAGE_CHARS
            or hashlib.sha256(content.encode("utf-8")).hexdigest() != segment["text_sha256"]
        ):
            raise ValueError("PDF page contains blank/corrupted text or changed source SHA")
        text_pages.append({
            "page_number": page_idx,
            "extracted_text": content,
            "text_sha256": segment["text_sha256"],
            "char_count": segment["char_count"],
            "segment_id": segment["segment_id"],
            "source_document_sha256": EXPECTED_SHA,
            "page_visual_reviewed": False,
            "economic_facts_independently_semantically_approved": False,
        })
    first_page = text_pages[0]["extracted_text"].casefold()
    all_text = "\n".join(item["extracted_text"] for item in text_pages).casefold()
    if (
        "inox green" not in first_page
        or "7th october, 2026" not in first_page
        or "wind world" not in all_text
        or "vibhav" not in all_text
        or "550" not in all_text
    ):
        raise ValueError("PDF text does not resemble pinned 7 Oct issuer/transaction")

    payload: dict[str, Any] = {
        "schema_version": 1,
        "document_review_id": CASE_ID,
        "classification": "PINNED_ORIGINAL_PDF_TEXT_SOURCE_ONLY_NOT_SEMANTIC_APPROVAL",
        "original_pdf_sha256": EXPECTED_SHA,
        "original_pdf_path": str(ORIGINAL_PATH),
        "original_source_url": receipt["original_source_url"],
        "original_source_captured_at_utc": receipt["captured_at_utc"],
        "original_pdf_byte_count": len(source_raw),
        "ss002_original_document_id_reconciled": True,
        "ss002_pilot_semantic_review_pending": True,
        "page_count": pages,
        "pages": text_pages,
        "page_visual_review_complete": False,
        "original_semantic_audit_complete": False,
        "transfer_completed_verified": False,
        "funding_term_classes_verified": False,
        "normalized_ebitda_verified": False,
        "expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    return payload


def validate_original_pdf_page_packet(packet: dict[str, Any]) -> None:
    if (
        packet.get("schema_version") != 1
        or packet.get("document_review_id") != CASE_ID
        or packet.get("original_pdf_sha256") != EXPECTED_SHA
        or packet.get("ss002_original_document_id_reconciled") is not True
    ):
        raise ValueError("wrong P004 source identity")
    pages = packet.get("pages")
    if not isinstance(pages, list) or len(pages) != packet.get("page_count"):
        raise ValueError("P004 page count invalid")
    for idx, page in enumerate(pages, 1):
        raw_text = page.get("extracted_text")
        if (
            page.get("page_number") != idx
            or not isinstance(raw_text, str)
            or page.get("text_sha256") != hashlib.sha256(raw_text.encode()).hexdigest()
        ):
            raise ValueError("P004 page text SHA/page locator invalid")
    for flag in (
        "page_visual_review_complete",
        "original_semantic_audit_complete",
        "transfer_completed_verified",
        "funding_term_classes_verified",
        "normalized_ebitda_verified",
        "expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if packet.get(flag) is not False:
            raise ValueError(f"source page packet cannot authorize {flag}")
