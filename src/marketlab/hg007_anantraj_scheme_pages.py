"""Source-only original 48-page ANANTRAJ composite scheme text custody.

Reads exact official issuer PDF already retained under HG007-P024. Each page
is independently recorded, plain text SHA bound to the original P024 page
digest and length. Keyword matches are only review routing, not verified
economic balances, effective dates, court approval or investment signals.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

SOURCE_ID = "HG007-P025-ANANTRAJ-FULL-SCHEME-48-PAGE-SOURCE-TEXT-v1"
RECEIPT_PATH = Path("research/hg007/anantraj-full-scheme/original-source-v1.json")
RECEIPT_GIT_BLOB_SHA = "9c37a3303a053555552ec98467a1ab9cf190e658"
PDF_SHA256 = "76db08d6210360291e81ab7813302067acdb34206cd03561db1ce0ba7ffe528f"
PDF_PATH = Path("research/hg007/anantraj-full-scheme/raw/sha256") / f"{PDF_SHA256}.pdf"
PAGE_COUNT = 48
ORIGINAL_PDF_BYTES = 10_044_735
INDEX_ID = "HG007-P025-ANANTRAJ-PAGE-TEXT-INDEX-v1"

# Linguistic evidence-discovery labels only; no extraction of financial facts.
KEYWORD_PATTERNS: dict[str, str] = {
    "asset_allocation_mention": r"\bassets?\b|immoveable|immovable|property",
    "liability_allocation_mention": r"\bliabilit(?:y|ies)\b|\bobligations?\b",
    "borrowings_debt_mention": r"\bborrowings?\b|\bdebt\b|inter.corporate|loan",
    "contingent_guarantee_mention": r"\bcontingent\b|\bguarantees?\b",
    "encumbrance_security_mention": r"\bcharges?\b|\bmortgage\b|\bpledge\b",
    "transfer_date_mention": r"\bappointed date\b|\beffective date\b|\brecord date\b",
    "shareholder_issuance_mention": r"share exchange|equity shares|allotment|share entitlement",
    "tax_accounting_mention": r"\btax(?:es)?\b|accounting treatment|ind as",
    "undertaking_definition_mention": r"demerged undertaking|transferor undertaking|resultant company",
    "schedule_or_annexure_mention": r"\bschedule\b|\bannexure\b|appendix",
    "approvals_mention": r"stock exchange|tribunal|nclt|creditors|shareholders",
}

def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_original_scheme_source(root: Path) -> tuple[bytes, list[dict[str, Any]]]:
    receipt_raw = (root / RECEIPT_PATH).read_bytes()
    if _git_blob(receipt_raw) != RECEIPT_GIT_BLOB_SHA:
        raise ValueError("HG007 original 48-page source receipt Git blob drifted")
    receipt = json.loads(receipt_raw)
    if not isinstance(receipt, dict):
        raise TypeError("original issuer source receipt must be an object")
    source = receipt.get("source_pdf")
    if not isinstance(source, dict):
        raise TypeError("original issuer source PDF metadata missing")
    if (
        receipt.get("source_id") != (
            "HG007-P024-ANANTRAJ-AUG2026-FULL-SCHEME-ORIGINAL-PDF-v1"
        )
        or receipt.get("state") != (
            "OFFICIAL_ISSUER_SCHEME_PDF_BYTES_IDENTITY_VERIFIED_NOT_LEGALLY_APPROVED"
        )
        or receipt.get("original_pdf_bytes_acquired") is not True
        or receipt.get("regulatory_approvals_effective_date_verified") is not False
        or receipt.get("full_scheme_liabilities_assets_semantic_review_completed") is not False
        or receipt.get("portfolio_eligibility_allowed") is not False
        or receipt.get("live_capital_allowed") is not False
        or source.get("pdf_sha256") != PDF_SHA256
        or source.get("pdf_byte_count") != ORIGINAL_PDF_BYTES
        or source.get("page_count") != PAGE_COUNT
    ):
        raise ValueError("original issuer scheme identity, date or authority changed")

    pages = source.get("source_page_text_digest_provenance")
    if not isinstance(pages, list) or len(pages) != PAGE_COUNT:
        raise ValueError("original source receipt must cover exactly 48 pages")
    if [row.get("pdf_page_number") for row in pages] != list(range(1, PAGE_COUNT + 1)):
        raise ValueError("original page receipt order/coverage changed")
    if any(
        not isinstance(row.get("text_sha256"), str)
        or len(row["text_sha256"]) != 64
        or row.get("text_extraction_is_independent_audited_fact") is not False
        for row in pages
    ):
        raise ValueError("original page digests or review boundary changed")
    original = (root / PDF_PATH).read_bytes()
    if (
        len(original) != ORIGINAL_PDF_BYTES
        or _sha(original) != PDF_SHA256
        or not original.startswith(b"%PDF-")
    ):
        raise ValueError("original ANANTRAJ 48-page PDF bytes differ from official SHA")
    return original, pages


def build_page_text_evidence(
    original: bytes, source_page_receipts: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, bytes]]:
    try:
        reader = PdfReader(io.BytesIO(original), strict=False)
        count = len(reader.pages)
    except (PdfReadError, OSError, ValueError, TypeError, KeyError) as exc:
        raise ValueError("source PDF structure unreadable") from exc
    if count != PAGE_COUNT:
        raise ValueError("source PDF page count changed")
    pages: list[dict[str, Any]] = []
    files: dict[str, bytes] = {}
    for page_num, page in enumerate(reader.pages, start=1):
        try:
            extracted = page.extract_text() or ""
        except (PdfReadError, OSError, ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"PDF page {page_num} extraction failure") from exc
        original_receipt = source_page_receipts[page_num - 1]
        utf8 = extracted.encode("utf-8")
        if (
            len(extracted) != original_receipt["text_char_count"]
            or _sha(utf8) != original_receipt["text_sha256"]
            or len(extracted.strip()) < 100
        ):
            raise ValueError(f"PDF page {page_num} text differs from original P024 receipt")
        filename = f"original-page-{page_num:02d}.txt"
        files[filename] = utf8
        flags = [
            label for label, pattern in KEYWORD_PATTERNS.items()
            if re.search(pattern, extracted, flags=re.IGNORECASE)
        ]
        pages.append({
            "page_number": page_num,
            "file_name": filename,
            "source_pdf_sha256": PDF_SHA256,
            "source_page_text_sha256": _sha(utf8),
            "character_count": len(extracted),
            "utf8_bytes": len(utf8),
            "search_only_topic_labels": flags,
            "transferred_asset_liability_values_independently_verified": False,
            "page_layout_or_signatures_visually_audited": False,
            "issuer_proposed_terms_are_legal_approval": False,
        })
    if len(files) != PAGE_COUNT:
        raise ValueError("missing original source page text files")
    result = {
        "schema_version": 1,
        "index_id": INDEX_ID,
        "classification": "EXACT_48_PAGE_ORIGINAL_SCHEME_TEXT_NO_SEMANTIC_FACT_APPROVAL",
        "company": "Anant Raj Limited",
        "listed_symbol": "ANANTRAJ",
        "pdf_original_sha256": PDF_SHA256,
        "pdf_byte_count": ORIGINAL_PDF_BYTES,
        "source_receipt_git_blob_sha": RECEIPT_GIT_BLOB_SHA,
        "page_count": PAGE_COUNT,
        "pages": pages,
        "label_counts_search_only": {
            label: sum(label in page["search_only_topic_labels"] for page in pages)
            for label in KEYWORD_PATTERNS
        },
        "page_text_fully_extracted_and_sha_verified": True,
        "original_scheme_court_and_regulatory_approved": False,
        "actual_legal_scheme_effective_date_verified": False,
        "actual_record_date_entitlement_verified": False,
        "full_liability_asset_semantic_audit_completed": False,
        "transferred_liability_values_verified": False,
        "parent_subsidiary_double_counting_resolved": False,
        "equity_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    return result, files


def write_or_verify_page_evidence(
    output_dir: Path,
    index: dict[str, Any],
    pages: dict[str, bytes],
    *,
    verify_existing: bool = False,
) -> None:
    if verify_existing and not output_dir.is_dir():
        raise FileNotFoundError("original scheme page-text directory not yet anchored")
    output_dir.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(index, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    records = {"page-index-v1.json": encoded, **pages}
    for filename, raw in records.items():
        destination = output_dir / filename
        if destination.exists():
            if destination.read_bytes() != raw:
                raise ValueError(f"original issuer page source changed: {filename}")
        elif verify_existing:
            raise FileNotFoundError(f"original issuer source page missing: {filename}")
        else:
            with destination.open("xb") as handle:
                handle.write(raw)
    actual = {p.name for p in output_dir.iterdir() if p.is_file()}
    if actual != set(records):
        raise ValueError("original page-text directory contains changed/unexpected files")
