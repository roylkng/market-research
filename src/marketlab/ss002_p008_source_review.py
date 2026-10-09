from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest

PACK_ID = "SS002-P008-v1"
P003_ID = "SS002-P003-v1"
P003_SHA = "7abbe52043b7ef3de89cb617d4fba2b181c3d8c4978df7a29ea557eab54469f7"
P006_ID = "SS002-P006-v1"
P006_SHA = "e4ff14a24c204471ad6fee037fe93afbddce66e9f46119707f4d9f4fdb8603e7"
EXPECTED_SYMBOLS = frozenset({"VRLLOG", "OLAELEC", "INOXGREEN", "KOTHARIPET"})


def _validate(source: dict[str, Any], label: str) -> None:
    for field in ("portfolio_eligibility_allowed", "live_capital_allowed", "return_outcomes_opened"):
        if source.get(field) is not False:
            raise AlphaContractError(f"{label} requires {field}=false")


def _documents(corpus: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows = corpus.get("documents")
    if not isinstance(rows, list):
        raise TypeError("P003 documents must be a list")
    index = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("extraction_state") != "READY":
            continue
        key = (str(row.get("document_id") or ""), str(row.get("source_url") or ""))
        if not all(key) or key in index:
            raise AlphaContractError("P008 P003 READY document identities missing/repeated")
        index[key] = row
    return index


def build_p008_source_review(
    *,
    p003_corpus: dict[str, Any],
    p003_documents: dict[str, dict[str, Any]],
    p006_casebook: dict[str, Any],
) -> dict[str, Any]:
    if p003_corpus.get("corpus_id") != P003_ID or p003_corpus.get("corpus_sha256") != P003_SHA:
        raise AlphaContractError("P008 requires exact frozen P003")
    if p006_casebook.get("pack_id") != P006_ID or p006_casebook.get("pack_sha256") != P006_SHA:
        raise AlphaContractError("P008 requires exact frozen P006")
    _validate(p003_corpus, "P003")
    _validate(p006_casebook, "P006")
    if p006_casebook.get("case_count") != 8 or p006_casebook.get("explicit_fact_count") != 52:
        raise AlphaContractError("P008 P006 case accounting mismatch")
    if p006_casebook.get("independent_semantic_audit_complete") is not False:
        raise AlphaContractError("P008 P006 independent review must be pending")
    cases = p006_casebook.get("cases")
    if not isinstance(cases, list):
        raise TypeError("P006 cases must be a list")
    selected = [row for row in cases if row.get("active_transaction_research_lens") is True]
    if len(selected) != 4 or {row.get("symbol") for row in selected} != EXPECTED_SYMBOLS:
        raise AlphaContractError("P008 frozen four-case selection mismatch")
    if set(p003_documents) != {row["document_id"] for row in selected}:
        raise AlphaContractError("P008 must receive exactly four selected documents")

    index = _documents(p003_corpus)
    outputs = []
    total_claims = 0
    total_segments = 0
    empty_pages = 0
    for case in sorted(selected, key=lambda row: row["symbol"]):
        sym = str(case["symbol"])
        doc_id = str(case["document_id"])
        url = str(case["source_url"])
        source = p003_documents[doc_id]
        catalog = index.get((doc_id, url))
        if not isinstance(source, dict) or catalog is None:
            raise AlphaContractError(f"{sym}: missing exact P003 document")
        if source.get("document_id") != doc_id or source.get("source_url") != url:
            raise AlphaContractError(f"{sym}: P003 document identity mismatch")
        if case.get("source_segment_manifest_sha256") != source.get("segment_manifest_sha256"):
            raise AlphaContractError(f"{sym}: segment-manifest mismatch")
        if catalog.get("raw_sha256") != doc_id:
            raise AlphaContractError(f"{sym}: original PDF bytes are not SHA-bound")

        original_pages = case.get("source_page_count")
        empty = case.get("source_empty_page_count")
        failed = case.get("source_failed_page_count")
        if any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in (original_pages, empty, failed)):
            raise AlphaContractError(f"{sym}: source PDF page accounting missing")
        segments = source.get("segments")
        if not isinstance(segments, list):
            raise TypeError(f"{sym}: P003 segments must be list")
        seen = set()
        pages = []
        for row in segments:
            if not isinstance(row, dict):
                raise TypeError(f"{sym}: P003 segment must be object")
            sid = row.get("segment_id")
            page = row.get("locator", {}).get("page_number")
            content = row.get("text")
            sha = row.get("text_sha256")
            if (
                not isinstance(sid, str) or not sid
                or not isinstance(page, int) or page < 1 or page > original_pages
                or not isinstance(content, str) or not isinstance(sha, str)
                or hashlib.sha256(content.encode("utf-8")).hexdigest() != sha
                or page in seen
            ):
                raise AlphaContractError(f"{sym}: source-page text identity invalid")
            seen.add(page)
            pages.append({
                "page_number": page,
                "segment_id": sid,
                "source_text_sha256": sha,
                "source_text": content,
                "claimed_semantic_accuracy_verified": False,
            })
        if len(pages) + empty + failed != original_pages:
            raise AlphaContractError(f"{sym}: PDF text/empty/failed page accounting mismatch")
        missing_pages = sorted(set(range(1, original_pages + 1)) - seen)
        if len(missing_pages) != empty + failed:
            raise AlphaContractError(f"{sym}: missing visual page accounting mismatch")
        by_segment = {row["segment_id"]: row for row in pages}

        claims = case.get("claims")
        if not isinstance(claims, list) or case.get("explicit_fact_count") != len(claims):
            raise AlphaContractError(f"{sym}: P006 claims missing")
        review_claims = []
        for claim in claims:
            if not isinstance(claim, dict) or claim.get("citation_integrity_verified") is not True:
                raise AlphaContractError(f"{sym}: P006 claim identity unavailable")
            citations = claim.get("cited_segments")
            if not isinstance(citations, list) or not citations:
                raise AlphaContractError(f"{sym}: explicit claim missing citations")
            for cite in citations:
                sid = cite.get("segment_id")
                if sid not in by_segment or cite.get("segment_text_sha256") != by_segment[sid]["source_text_sha256"]:
                    raise AlphaContractError(f"{sym}: extracted claim cites unknown or changed text")
            review_claims.append({
                "field_path": claim.get("field_path"),
                "extracted_value": claim.get("extracted_value"),
                "extracted_unit": claim.get("extracted_unit"),
                "cited_segment_ids": [c["segment_id"] for c in citations],
                "review_status": "PENDING_INDEPENDENT_REVIEW",
                "reviewer_id": None,
                "review_finding": None,
                "semantic_support_accepted": False,
            })
        total_claims += len(review_claims)
        total_segments += len(pages)
        empty_pages += empty
        outputs.append({
            "symbol": sym,
            "isin": case.get("isin"),
            "document_id": doc_id,
            "official_nse_url": url,
            "original_pdf_raw_sha256": catalog["raw_sha256"],
            "source_segment_manifest_sha256": source["segment_manifest_sha256"],
            "research_lane": case.get("research_lane"),
            "original_pdf_page_count": original_pages,
            "text_extracted_page_count": len(pages),
            "empty_extracted_page_count": empty,
            "failed_extracted_page_count": failed,
            "original_pages_requiring_visual_review": missing_pages,
            "all_original_pdf_pages_must_be_independently_reviewed": True,
            "pages": sorted(pages, key=lambda x: x["page_number"]),
            "claims": review_claims,
            "original_source_independent_semantic_review_complete": False,
            "underwriting_ready": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        })
    if total_claims != 35:
        raise AlphaContractError(f"P008 expected 35 active-case claims, found {total_claims}")
    out = {
        "schema_version": 1,
        "pack_id": PACK_ID,
        "classification": "UNREVIEWED_FULL_ORIGINAL_PAGE_AND_CLAIM_PACKET",
        "source_p003_corpus_sha256": P003_SHA,
        "source_p006_casebook_sha256": P006_SHA,
        "case_count": len(outputs),
        "claim_count": total_claims,
        "extracted_page_segment_count": total_segments,
        "empty_page_count": empty_pages,
        "case_symbols": [row["symbol"] for row in outputs],
        "cases": outputs,
        "independent_semantic_audit_complete": False,
        "original_pdf_visual_review_complete": False,
        "share_action_clearance_proven": False,
        "underwriting_ready_count": 0,
        "expected_returns_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    out["pack_sha256"] = digest(out)
    return out
