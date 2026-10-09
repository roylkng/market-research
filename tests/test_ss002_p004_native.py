from __future__ import annotations

import hashlib

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss002_p004_native import materialize_one
from marketlab.ss002_text import seal_extraction_row


def _fixture() -> tuple[dict, dict, dict]:
    document_id = "a" * 64
    text = "Example Limited announces a proposed buyback at INR 320 per share."
    segment = {
        "kind": "PDF_PAGE",
        "segment_id": f"{document_id}:pdf:page:0001",
        "locator": {"page_number": 1},
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "char_count": len(text),
        "utf8_byte_count": len(text.encode("utf-8")),
    }
    extracted = seal_extraction_row(
        {
            "document_id": document_id,
            "source_url": "https://nsearchives.nseindia.com/corporate/example.pdf",
            "d002_family": "PDF",
            "extraction_state": "READY",
            "details": {},
            "segments": [segment],
        }
    )
    source = {
        "document_id": document_id,
        "status": "READY",
        "extraction_state": "READY",
        "source_url": extracted["source_url"],
        "segment_manifest_sha256": extracted["segment_manifest_sha256"],
        "symbols": ["EXAMPLE"],
        "event_ids": ["E1"],
        "category_hints_only": ["BUYBACK"],
    }
    decision = {
        "document_id": document_id,
        "symbol": "EXAMPLE",
        "economic_relevance": "DIRECT_LISTED_SECURITY",
        "transaction_families": ["BUYBACK"],
        "transaction_stage": "PUBLIC_ANNOUNCEMENT",
        "facts": [
            [
                "security_economics",
                "offer_price_per_share",
                320,
                "INR_PER_SHARE",
                [1],
            ]
        ],
        "unresolved_questions": [],
        "contradictions_within_document": [],
        "extraction_caveats": [],
        "semantic_audit_status": "PENDING_INDEPENDENT_SOURCE_REVIEW",
        "case_assessment": "Source-bound proposed buyback.",
    }
    return decision, source, extracted


def test_native_fact_is_bound_to_exact_p003_page() -> None:
    decision, source, extracted = _fixture()
    result = materialize_one(decision, source=source, extraction=extracted)
    fact = result["validated_extraction"]["facts"]["security_economics"][
        "offer_price_per_share"
    ]
    assert fact["value"] == 320
    assert fact["evidence_segment_ids"] == [
        source["document_id"] + ":pdf:page:0001"
    ]
    assert result["semantic_audit_status"] == "PENDING_INDEPENDENT_SOURCE_REVIEW"
    assert result["validated_extraction"]["portfolio_eligibility_allowed"] is False


def test_unavailable_source_page_fails_closed() -> None:
    decision, source, extracted = _fixture()
    decision["facts"][0][4] = [2]
    with pytest.raises(AlphaContractError, match="cites unavailable page"):
        materialize_one(decision, source=source, extraction=extracted)


def test_tampered_text_hash_fails_closed() -> None:
    decision, source, extracted = _fixture()
    extracted["segments"][0]["text"] = "tampered"
    with pytest.raises(AlphaContractError, match="segment text SHA mismatch"):
        materialize_one(decision, source=source, extraction=extracted)


def test_semantic_audit_cannot_be_precleared() -> None:
    decision, source, extracted = _fixture()
    decision["semantic_audit_status"] = "PASS"
    with pytest.raises(AlphaContractError, match="semantic audit must remain pending"):
        materialize_one(decision, source=source, extraction=extracted)
