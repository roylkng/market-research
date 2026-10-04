from __future__ import annotations

import copy
import hashlib

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss002_llm_contract import (
    CONTRACT_ID,
    build_prompt_envelope,
    extraction_template,
    validate_extraction,
)


def _segments() -> list[dict]:
    texts = [
        "The company proposes a buyback at INR 500 per equity share.",
        "The record date is 15 October 2026.",
    ]
    return [
        {
            "segment_id": f"page:{index}",
            "text": text,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
        for index, text in enumerate(texts, start=1)
    ]


def _valid_output() -> dict:
    output = extraction_template(
        document_id="doc1",
        event_ids=["event1"],
        symbols=["TEST"],
    )
    output["economic_relevance"] = "DIRECT_LISTED_SECURITY"
    output["transaction_families"] = ["BUYBACK"]
    output["transaction_stage"] = "PROPOSAL"
    output["facts"]["security_economics"]["offer_price_per_share"] = {
        "status": "EXPLICIT",
        "value": 500,
        "unit": "INR_PER_SHARE",
        "evidence_segment_ids": ["page:1"],
    }
    output["facts"]["dates"]["record_date"] = {
        "status": "EXPLICIT",
        "value": "2026-10-15",
        "unit": "ISO_DATE",
        "evidence_segment_ids": ["page:2"],
    }
    output["provenance"] = {
        "provider_runtime": "TEST_RUNTIME",
        "model_id": "TEST_MODEL",
        "model_config_sha256": "a" * 64,
        "prompt_contract_id": CONTRACT_ID,
        "prompt_sha256": "b" * 64,
        "input_document_id": "doc1",
        "input_segment_manifest_sha256": "c" * 64,
        "raw_model_response_sha256": "d" * 64,
    }
    return output


def test_prompt_envelope_binds_segment_text_hashes() -> None:
    prompt = build_prompt_envelope(
        document_id="doc1",
        source_url="https://nsearchives.nseindia.com/test.pdf",
        event_ids=["event1"],
        symbols=["TEST"],
        category_hints=["BUYBACK"],
        segments=_segments(),
        segment_manifest_sha256="c" * 64,
    )
    assert prompt["request"]["document_id"] == "doc1"
    assert len(prompt["prompt_sha256"]) == 64
    assert "Do not estimate valuation" in prompt["system"]


def test_valid_extraction_is_sealed_research_only() -> None:
    sealed = validate_extraction(
        _valid_output(),
        input_document_id="doc1",
        allowed_event_ids={"event1"},
        allowed_symbols={"TEST"},
        allowed_segment_ids={"page:1", "page:2"},
        expected_segment_manifest_sha256="c" * 64,
    )
    assert len(sealed["validated_structured_output_sha256"]) == 64
    assert sealed["portfolio_eligibility_allowed"] is False
    assert sealed["live_capital_allowed"] is False


def test_explicit_fact_requires_supplied_evidence() -> None:
    output = _valid_output()
    output["facts"]["security_economics"]["offer_price_per_share"][
        "evidence_segment_ids"
    ] = ["page:999"]
    with pytest.raises(AlphaContractError, match="unknown evidence"):
        validate_extraction(
            output,
            input_document_id="doc1",
            allowed_event_ids={"event1"},
            allowed_symbols={"TEST"},
            allowed_segment_ids={"page:1", "page:2"},
            expected_segment_manifest_sha256="c" * 64,
        )


def test_unknown_fact_cannot_carry_model_guess() -> None:
    output = _valid_output()
    fact = output["facts"]["consideration"]["total_consideration"]
    fact["value"] = 1_000_000
    with pytest.raises(AlphaContractError, match="UNKNOWN fact must have null value"):
        validate_extraction(
            output,
            input_document_id="doc1",
            allowed_event_ids={"event1"},
            allowed_symbols={"TEST"},
            allowed_segment_ids={"page:1", "page:2"},
            expected_segment_manifest_sha256="c" * 64,
        )


def test_model_cannot_introduce_new_event_or_symbol() -> None:
    output = _valid_output()
    output["event_ids"] = ["event1", "invented"]
    with pytest.raises(AlphaContractError, match="event IDs differ"):
        validate_extraction(
            output,
            input_document_id="doc1",
            allowed_event_ids={"event1"},
            allowed_symbols={"TEST"},
            allowed_segment_ids={"page:1", "page:2"},
            expected_segment_manifest_sha256="c" * 64,
        )


def test_forbidden_investment_prediction_field_is_rejected_anywhere() -> None:
    output = _valid_output()
    output["facts"]["business_economics"]["target_price"] = {
        "status": "EXPLICIT",
        "value": 900,
        "unit": "INR",
        "evidence_segment_ids": ["page:1"],
    }
    with pytest.raises(AlphaContractError, match="forbidden output fields"):
        validate_extraction(
            output,
            input_document_id="doc1",
            allowed_event_ids={"event1"},
            allowed_symbols={"TEST"},
            allowed_segment_ids={"page:1", "page:2"},
            expected_segment_manifest_sha256="c" * 64,
        )


def test_prompt_rejects_tampered_segment_hash() -> None:
    segments = copy.deepcopy(_segments())
    segments[0]["text_sha256"] = "0" * 64
    with pytest.raises(AlphaContractError, match="text SHA mismatch"):
        build_prompt_envelope(
            document_id="doc1",
            source_url="https://nsearchives.nseindia.com/test.pdf",
            event_ids=["event1"],
            symbols=["TEST"],
            category_hints=["BUYBACK"],
            segments=segments,
            segment_manifest_sha256="c" * 64,
        )
