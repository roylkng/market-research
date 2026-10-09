from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest

PACK_ID = "SS002-P009-v1"
P008_ID = "SS002-P008-v1"
P008_SHA = "94b098d24ef6c5eb3482ce4c79ec696c24a6f761a4bc0f3fe6e0e5ae7f985768"
EXPECTED_SYMBOLS = frozenset({"INOXGREEN", "KOTHARIPET", "OLAELEC", "VRLLOG"})
STATUS_CORRUPTED = "CORRUPTED_TEXT_VISUAL_REVIEW"
STATUS_UNEXTRACTED = "UNEXTRACTED_VISUAL_REVIEW"
STATUS_SPARSE = "SPARSE_TEXT_VISUAL_REVIEW"
STATUS_PRESENT = "TEXT_PRESENT_SEMANTICS_UNVERIFIED"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def page_legibility(text: str | None) -> tuple[str, dict[str, float | int | None]]:
    if text is None:
        return STATUS_UNEXTRACTED, {
            "non_whitespace_character_count": 0,
            "replacement_character_count": 0,
            "replacement_ratio": None,
            "alphanumeric_character_count": 0,
        }
    if not isinstance(text, str):
        raise TypeError("P009 page text must be string or None")
    non_whitespace = sum(not char.isspace() for char in text)
    replacement = text.count("\ufffd")
    alphanumeric = sum(char.isalnum() for char in text)
    ratio = replacement / max(non_whitespace, 1)
    metrics: dict[str, float | int | None] = {
        "non_whitespace_character_count": non_whitespace,
        "replacement_character_count": replacement,
        "replacement_ratio": ratio,
        "alphanumeric_character_count": alphanumeric,
    }
    if ratio >= 0.20:
        return STATUS_CORRUPTED, metrics
    if alphanumeric < 25:
        return STATUS_SPARSE, metrics
    return STATUS_PRESENT, metrics


def _verified_pdf_url(url: object) -> str:
    if not isinstance(url, str):
        raise AlphaContractError("P009 official URL must be string")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "nsearchives.nseindia.com", "archives.nseindia.com"
    }:
        raise AlphaContractError("P009 only allows original official NSE PDF URLs")
    return url


def build_p009_legibility_packet(p008: dict[str, Any]) -> dict[str, Any]:
    if p008.get("pack_id") != P008_ID or p008.get("pack_sha256") != P008_SHA:
        raise AlphaContractError("P009 requires exact frozen P008 reviewer packet")
    if p008.get("case_count") != 4 or p008.get("claim_count") != 35:
        raise AlphaContractError("P009 P008 case or claim count mismatch")
    for field in (
        "independent_semantic_audit_complete",
        "original_pdf_visual_review_complete",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
        "return_outcomes_opened",
    ):
        if p008.get(field) is not False:
            raise AlphaContractError(f"P009 requires P008 {field}=false")
    cases = p008.get("cases")
    if not isinstance(cases, list) or {x.get("symbol") for x in cases} != EXPECTED_SYMBOLS:
        raise AlphaContractError("P009 requires exact four P008 companies")

    output_cases = []
    states = Counter()
    claims_total = 0
    for case in sorted(cases, key=lambda row: row["symbol"]):
        symbol = case["symbol"]
        doc_id = case.get("document_id")
        original_sha = case.get("original_pdf_raw_sha256")
        if not isinstance(doc_id, str) or len(doc_id) != 64 or doc_id != original_sha:
            raise AlphaContractError(f"{symbol}: original document SHA mismatch")
        url = _verified_pdf_url(case.get("official_nse_url"))
        original_count = case.get("original_pdf_page_count")
        pages = case.get("pages")
        claims = case.get("claims")
        if not isinstance(original_count, int) or original_count < 1:
            raise AlphaContractError(f"{symbol}: original page count missing")
        if not isinstance(pages, list) or not isinstance(claims, list):
            raise TypeError(f"{symbol}: P008 pages/claims must be lists")
        by_page = {row["page_number"]: row for row in pages}
        if len(by_page) != len(pages):
            raise AlphaContractError(f"{symbol}: duplicate source page")

        rendered_pages = []
        for number in range(1, original_count + 1):
            item = by_page.get(number)
            if item is not None:
                text = item.get("source_text")
                if not isinstance(text, str):
                    raise TypeError(f"{symbol}: source text must be string")
                if _sha(text.encode("utf-8")) != item.get("source_text_sha256"):
                    raise AlphaContractError(f"{symbol}: P008 source text SHA changed")
            else:
                text = None
            status, metrics = page_legibility(text)
            states[status] += 1
            rendered_pages.append(
                {
                    "page_number": number,
                    "source_segment_id": item.get("segment_id") if item else None,
                    "source_text_sha256": item.get("source_text_sha256") if item else None,
                    "legibility_status": status,
                    "legibility_diagnostics": metrics,
                    "visual_review_required": True,
                    "visual_image_sha256": None,
                    "independent_semantic_review_complete": False,
                }
            )
        unresolved = [
            row["page_number"]
            for row in rendered_pages
            if row["legibility_status"] != STATUS_PRESENT
        ]
        expected_missing = case.get("original_pages_requiring_visual_review")
        if [
            row["page_number"]
            for row in rendered_pages
            if row["legibility_status"] == STATUS_UNEXTRACTED
        ] != expected_missing:
            raise AlphaContractError(f"{symbol}: P008 missing-page accounting changed")
        if not all(
            row.get("review_status") == "PENDING_INDEPENDENT_REVIEW"
            and row.get("semantic_support_accepted") is False
            for row in claims
        ):
            raise AlphaContractError(f"{symbol}: P008 reviewer states must remain pending")
        claims_total += len(claims)
        output_cases.append(
            {
                "symbol": symbol,
                "document_id": doc_id,
                "official_nse_url": url,
                "original_pdf_raw_sha256": original_sha,
                "original_pdf_page_count": original_count,
                "priority_visual_pages": unresolved,
                "pages": rendered_pages,
                "review_claim_count": len(claims),
                "reviewer_claims": claims,
                "independent_semantic_audit_complete": False,
                "visual_review_complete": False,
                "underwriting_ready": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )
    if sum(states.values()) != 17 or claims_total != 35:
        raise AlphaContractError("P009 17-page/35-claim accounting mismatch")
    expected_states = {
        STATUS_PRESENT: 11, STATUS_CORRUPTED: 4,
        STATUS_UNEXTRACTED: 2, STATUS_SPARSE: 0,
    }
    if any(states[status] != count for status, count in expected_states.items()):
        raise AlphaContractError("P009 frozen source-legibility distribution mismatch")
    result = {
        "schema_version": 1,
        "pack_id": PACK_ID,
        "classification": "ORIGINAL_PAGE_LEGIBILITY_QA_AND_VISUAL_REVIEW_INPUT_NOT_APPROVAL",
        "source_p008_pack_sha256": P008_SHA,
        "case_count": 4,
        "original_page_count": 17,
        "claim_count": 35,
        "legibility_state_counts": {
            status: states[status] for status in (
                STATUS_PRESENT, STATUS_CORRUPTED, STATUS_UNEXTRACTED, STATUS_SPARSE
            )
        },
        "cases": output_cases,
        "independent_semantic_audit_complete": False,
        "original_pdf_visual_review_complete": False,
        "underwriting_ready": False,
        "expected_returns_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["pack_sha256"] = digest(result)
    return result
