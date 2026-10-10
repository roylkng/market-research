"""Page-source-backed custody of NPST June-2026 earnings and Reg32 disclosures.

Only the two exact 11-Aug-2026 BSE PDF originals already captured and
issuer/quarter verified by HG007-P018. Their page text and SHA-256
locators are reproducible, but financial facts and source table semantics
remain unapproved until a separate independent analyst review.

The third 11-Aug monitoring attachment has contradictory March/June
period text and is NOT silently pulled into this Q1 evidence record.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

EXTRACTION_ID = "HG007-P019-NPST-JUNE-2026-ORIGINAL-PDF-PAGE-SPINE-v1"
P018_CASE_ID = "HG007-P018-NPST-ORIGINAL-Q1FY27-FILING-SOURCE-BUNDLE-v1"
ROOT = Path("research/hg007/npst-aug2026-originals")
SOURCE_BOUNDARIES = {
    "2026-08-11-investor-presentation": {
        "sha256": "5afd8b272e7bd2f7f3fad549aa1270e4899e1d24c8d982268cab16a17bbe2225",
        "receipt_blob": "c626b459562f1d25b91d8a178d17d0cc7d56b043",
        "page_count": 22,
        "file_size_bytes": 4_868_023,
        "family": "INVESTOR_PRESENTATION_Q1FY27",
    },
    "2026-08-11-june-reg32-use-of-funds": {
        "sha256": "79010c968b0fe8359f685d27a203c891a8e35f684a73b86a67cf78ee46b54013",
        "receipt_blob": "003c821ec49ce5a331768350a77c1678119baec3",
        "page_count": 3,
        "file_size_bytes": 6_447_208,
        "family": "REG32_JUNE_2026_VARIATION_AND_USE_OF_PROCEEDS",
    },
}
EXTRACTED_PAGE_CHAR_LIMIT = 120_000
KEYWORDS = (
    "ebitda",
    "earnings before interest",
    "operating profit",
    "unutilized",
    "unutilised",
    "utilisation",
    "utilization",
    "use of funds",
    "proceeds",
    "18.79",
    "264.36",
    "₹",
)


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _receipt(raw: bytes, filename: str, original: dict[str, Any]) -> dict:
    if _git_blob(raw) != original["receipt_blob"]:
        raise ValueError(f"{filename}: original immutable BSE source receipt changed")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError("original BSE source receipt must be JSON object")
    if (
        value.get("case_id") != P018_CASE_ID
        or value.get("source_kind") != filename
        or value.get("filing_family") != original["family"]
        or value.get("source_declared_reporting_period") != "2026-06-30"
        or value.get("source_declared_filing_date") != "2026-08-11"
        or value.get("status") != "ORIGINAL_PDF_BYTE_AND_PAGE_STRUCTURE_CAPTURED"
        or value.get("original_raw_sha256") != original["sha256"]
        or value.get("original_raw_byte_count") != original["file_size_bytes"]
        or value.get("original_issuer_and_period_identity_gate_passed") is not True
        or value.get("original_pdf_text_economic_facts_approved") is not False
        or value.get("live_capital_allowed") is not False
    ):
        raise ValueError("not the exact original issuer/June-2026 source receipt")
    return value


def _page_text(raw: bytes, original: dict) -> list[str]:
    try:
        pdf = PdfReader(io.BytesIO(raw), strict=False)
        if len(pdf.pages) != original["page_count"]:
            raise ValueError("BSE original PDF page count does not match receipt")
        result = [page.extract_text() or "" for page in pdf.pages]
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise ValueError("BSE original PDF page extraction failed") from exc
    if any(len(text) > EXTRACTED_PAGE_CHAR_LIMIT for text in result):
        raise ValueError("source page text exceeds bounded review contract")
    return result


def _excerpts(page_text: str, page_number: int, sha: str) -> list[dict[str, Any]]:
    folded = page_text.casefold()
    snippets: list[dict[str, Any]] = []
    for needle in KEYWORDS:
        pos = folded.find(needle.casefold())
        if pos >= 0:
            start = max(0, pos - 95)
            end = min(len(page_text), pos + len(needle) + 130)
            snippets.append({
                "keyword": needle,
                "page_number": page_number,
                "source_page_sha256": sha,
                "text_excerpt_first_occurrence": " ".join(page_text[start:end].split()),
                "excerpt_is_not_a_verified_financial_value": True,
            })
    return snippets


def build_npst_original_page_evidence(repo_root: Path) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for source_id, contract in SOURCE_BOUNDARIES.items():
        base = repo_root / ROOT / source_id
        original_receipt = _receipt(
            (base / "original-receipt-v1.json").read_bytes(), source_id, contract
        )
        source_bytes = (
            base / "raw" / "sha256" / f"{contract['sha256']}.pdf"
        ).read_bytes()
        if (
            len(source_bytes) != contract["file_size_bytes"]
            or hashlib.sha256(source_bytes).hexdigest() != contract["sha256"]
            or not source_bytes.startswith(b"%PDF-")
        ):
            raise ValueError(f"{source_id}: original full PDF binary SHA or byte count changed")
        text_pages = _page_text(source_bytes, contract)
        previous = original_receipt.get("original_pdf_page_evidence")
        if (
            not isinstance(previous, dict)
            or previous.get("page_count") != len(text_pages)
            or previous.get("page_text_sha256") != [
                hashlib.sha256(x.encode("utf-8")).hexdigest() for x in text_pages
            ]
        ):
            raise ValueError(f"{source_id}: original source P018 page SHA mismatch")

        pages: list[dict[str, Any]] = []
        term_snippets: list[dict[str, Any]] = []
        for index, page_text in enumerate(text_pages, 1):
            digest = hashlib.sha256(page_text.encode("utf-8")).hexdigest()
            hits = _excerpts(page_text, index, digest)
            term_snippets.extend(hits)
            pages.append({
                "page_number_one_based": index,
                "source_document_sha256": contract["sha256"],
                "extracted_text_sha256": digest,
                "extracted_char_count": len(page_text),
                "extracted_text": page_text,
                "financial_table_semantics_independently_verified": False,
            })
        results.append({
            "source_id": source_id,
            "filing_family": contract["family"],
            "reporting_period": "2026-06-30",
            "filing_date": "2026-08-11",
            "original_bse_url": original_receipt["original_bse_url"],
            "original_source_sha256": contract["sha256"],
            "source_receipt_git_blob_sha": contract["receipt_blob"],
            "original_pdf_pages": contract["page_count"],
            "pages": pages,
            "search_snippet_first_occurrence_by_page_keyword": term_snippets,
            "independent_original_semantic_financial_review_complete": False,
        })

    if len(results) != 2 or sum(len(x["pages"]) for x in results) != 25:
        raise ValueError("exact two documents and 25 original source pages required")
    return {
        "schema_version": 1,
        "source_evidence_id": EXTRACTION_ID,
        "classification": "SOURCE_ORIGINAL_PDF_PAGE_TEXT_NOT_APPROVED_EARNINGS_OR_FUNDING",
        "company": "Network People Services Technologies Limited",
        "nse_symbol": "NPST",
        "reporting_period": "2026-06-30",
        "document_count": len(results),
        "original_page_count": 25,
        "original_documents": results,
        "ambiguous_march_monitoring_attachment_excluded": True,
        "actual_quarterly_ebitda_figure_approved": False,
        "unused_funds_balance_approved": False,
        "unspent_proceeds_to_earnings_conversion_proven": False,
        "cash_flow_and_share_dilution_verified": False,
        "hg005_50pct_stock_uplift_scenario_converted_into_forecast": False,
        "stock_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def validate_npst_source_packet(record: dict[str, Any]) -> None:
    if (
        record.get("schema_version") != 1
        or record.get("source_evidence_id") != EXTRACTION_ID
        or record.get("document_count") != 2
        or record.get("original_page_count") != 25
        or record.get("ambiguous_march_monitoring_attachment_excluded") is not True
    ):
        raise ValueError("unrecognized source-only NPST June 2026 page spine")
    documents = record.get("original_documents")
    if not isinstance(documents, list) or {x.get("source_id") for x in documents} != set(SOURCE_BOUNDARIES):
        raise ValueError("NPST source document family changed or incomplete")
    for doc in documents:
        contract = SOURCE_BOUNDARIES[doc["source_id"]]
        if len(doc.get("pages", [])) != contract["page_count"]:
            raise ValueError("page source count changed")
        for i, page in enumerate(doc["pages"], 1):
            text = page.get("extracted_text")
            if (
                page.get("page_number_one_based") != i
                or not isinstance(text, str)
                or page.get("source_document_sha256") != contract["sha256"]
                or hashlib.sha256(text.encode("utf-8")).hexdigest()
                != page.get("extracted_text_sha256")
                or page.get("financial_table_semantics_independently_verified") is not False
            ):
                raise ValueError("source PDF original page SHA or locator changed")
    for flag in (
        "actual_quarterly_ebitda_figure_approved",
        "unused_funds_balance_approved",
        "unspent_proceeds_to_earnings_conversion_proven",
        "cash_flow_and_share_dilution_verified",
        "hg005_50pct_stock_uplift_scenario_converted_into_forecast",
        "stock_expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if record.get(flag) is not False:
            raise ValueError(f"original page extraction cannot authorize {flag}")
