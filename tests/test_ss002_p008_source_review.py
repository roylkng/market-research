from __future__ import annotations

import copy
import hashlib

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss002_p008_source_review import (
    P003_ID,
    P003_SHA,
    P006_ID,
    P006_SHA,
    build_p008_source_review,
)

ACTIVE = ("INOXGREEN", "KOTHARIPET", "OLAELEC", "VRLLOG")
CLAIM_COUNTS = (11, 5, 12, 7)


def _sources() -> dict:
    catalog = []
    documents = {}
    cases = []
    for symbol, n in zip(ACTIVE, CLAIM_COUNTS, strict=True):
        doc_id = f"doc-{symbol}"
        url = f"https://nsearchives.nseindia.com/{symbol}.pdf"
        text = f"{symbol} official share transaction evidence."
        segment_id = f"{doc_id}:pdf:page:0001"
        segment = {
            "segment_id": segment_id,
            "locator": {"page_number": 1},
            "text": text,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
        empty = 1 if symbol == "VRLLOG" else 0
        documents[doc_id] = {
            "document_id": doc_id,
            "source_url": url,
            "segment_manifest_sha256": f"segment-manifest-{symbol}",
            "segments": [segment],
        }
        catalog.append({
            "extraction_state": "READY",
            "document_id": doc_id,
            "source_url": url,
            "raw_sha256": doc_id,
        })
        cases.append({
            "symbol": symbol,
            "document_id": doc_id,
            "source_url": url,
            "source_segment_manifest_sha256": f"segment-manifest-{symbol}",
            "active_transaction_research_lens": True,
            "source_page_count": 1 + empty,
            "source_empty_page_count": empty,
            "source_failed_page_count": 0,
            "explicit_fact_count": n,
            "claims": [
                {
                    "field_path": f"security_economics.field_{i}",
                    "extracted_value": i,
                    "extracted_unit": "INR",
                    "citation_integrity_verified": True,
                    "cited_segments": [{
                        "segment_id": segment_id,
                        "segment_text_sha256": segment["text_sha256"],
                    }],
                }
                for i in range(n)
            ],
            "research_lane": "TRANSACTION_REVIEW",
        })
    for symbol in ("PVRINOX", "PREMEXPLN", "SAMBHV", "TVSSRICHAK"):
        cases.append({"symbol": symbol, "active_transaction_research_lens": False})

    return {
        "p003_corpus": {
            "corpus_id": P003_ID,
            "corpus_sha256": P003_SHA,
            "documents": catalog,
            "return_outcomes_opened": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        },
        "p003_documents": documents,
        "p006_casebook": {
            "pack_id": P006_ID,
            "pack_sha256": P006_SHA,
            "case_count": 8,
            "explicit_fact_count": 52,
            "cases": cases,
            "independent_semantic_audit_complete": False,
            "return_outcomes_opened": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        },
    }


def test_four_case_review_packet_is_never_an_independent_approval() -> None:
    out = build_p008_source_review(**_sources())
    assert out["case_count"] == 4
    assert out["claim_count"] == 35
    assert out["empty_page_count"] == 1
    assert out["independent_semantic_audit_complete"] is False
    assert out["underwriting_ready_count"] == 0
    assert out["portfolio_eligibility_allowed"] is False
    vr = next(x for x in out["cases"] if x["symbol"] == "VRLLOG")
    assert vr["original_pages_requiring_visual_review"] == [2]
    assert all(x["review_status"] == "PENDING_INDEPENDENT_REVIEW" for x in vr["claims"])


def test_changed_original_page_sha_is_rejected() -> None:
    sources = _sources()
    first = sources["p003_documents"][f"doc-{ACTIVE[0]}"]
    first["segments"][0]["text"] = "tampered"
    with pytest.raises(AlphaContractError, match="source-page text identity invalid"):
        build_p008_source_review(**sources)


def test_missing_original_pdf_page_is_not_silently_accepted() -> None:
    sources = _sources()
    first = sources["p006_casebook"]["cases"][0]
    first["source_page_count"] = 2
    with pytest.raises(AlphaContractError, match="PDF text/empty/failed page accounting mismatch"):
        build_p008_source_review(**sources)


def test_cited_segment_sha_change_fails_closed() -> None:
    sources = _sources()
    sources["p006_casebook"]["cases"][0]["claims"][0]["cited_segments"][0][
        "segment_text_sha256"
    ] = "0" * 64
    with pytest.raises(AlphaContractError, match="unknown or changed text"):
        build_p008_source_review(**sources)


def test_selection_is_exact_and_cannot_be_enlarged() -> None:
    sources = copy.deepcopy(_sources())
    sources["p006_casebook"]["cases"][-1]["active_transaction_research_lens"] = True
    with pytest.raises(AlphaContractError, match="frozen four-case selection"):
        build_p008_source_review(**sources)
