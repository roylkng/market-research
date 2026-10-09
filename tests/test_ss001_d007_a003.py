from __future__ import annotations

import hashlib

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss001_d007_a003 import (
    LEDGER_ID,
    build_independent_review_ledger,
)


def _packet(available: int = 229) -> dict:
    rows = []
    for i in range(229):
        text = f"Official NSE issuer page {i}. Equity shares issued on record date."
        rows.append({
            "request_id": f"request-{i:03d}",
            "document_id": f"document-{i % 70:02d}",
            "symbol": f"ISSUER{i % 12:02d}",
            "segment_id": f"page:{i:03d}",
            "source_page_text": text,
            "source_page_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "response_status": (
                "PENDING_INDEPENDENT_REVIEW" if i < available else "MISSING_INFERENCE"
            ),
            "validated_extraction_sha256": "a" * 64 if i < available else None,
        })
    packet = {
        "schema_version": 1,
        "audit_id": "SS001-D007-A002-v1",
        "classification": "INDEPENDENT_REVIEW_WORK_PACKET_NOT_AUDIT_VERDICT",
        "source_queue_sha256": (
            "59929004bcc5a5eae4491cadc237aa1bb26b822102d56b5b50cf61fb6b667618"
        ),
        "selection_sha256": (
            "79e106f1d0b27810d06bd1c9e1bd192b967ef185393690ba0608354a698bbe86"
        ),
        "selected_page_count": 229,
        "selected_model_response_count": available,
        "pending_selected_response_count": 229 - available,
        "response_coverage_complete": available == 229,
        "independent_semantic_audit_complete": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
        "rows": rows,
    }
    packet["packet_sha256"] = digest(packet)
    return packet


def _review(page: dict, *, with_issue: bool = False) -> dict:
    return {
        "request_id": page["request_id"],
        "reviewer_id": "independent-reviewer-01",
        "reviewer_attests_independence": True,
        "reviewed_at_utc": "2026-10-09T14:00:00Z",
        "source_page_text_sha256": page["source_page_text_sha256"],
        "validated_extraction_sha256": page["validated_extraction_sha256"],
        "verdict": "ISSUES_FOUND" if with_issue else "PASS",
        "findings": (
            [{
                "category": "OMITTED_MATERIAL_TERM",
                "severity": "MATERIAL",
                "segment_id": page["segment_id"],
                "source_excerpt": "Equity shares issued",
                "explanation": "The model omitted an explicit issuer equity issuance.",
                "field_path": "business_economics.dilution_or_new_share_count_description",
            }]
            if with_issue else []
        ),
    }


def _annotations(packet: dict, reviews: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "audit_id": LEDGER_ID,
        "source_packet_sha256": packet["packet_sha256"],
        "reviews": reviews,
    }


def test_no_inference_produces_pending_ledger_not_audit() -> None:
    packet = _packet(0)
    ledger = build_independent_review_ledger(packet, _annotations(packet, []))
    assert ledger["missing_inference_page_count"] == 229
    assert ledger["reviewer_recorded_status"] == "SOURCE_INFERENCE_MISSING"
    assert ledger["reviewer_recorded_sample_complete"] is False
    assert ledger["independent_semantic_audit_complete"] is False
    assert ledger["share_action_clearance_proven"] is False


def test_partial_review_is_not_a_completed_audit() -> None:
    packet = _packet()
    ledger = build_independent_review_ledger(
        packet,
        _annotations(packet, [_review(packet["rows"][0])]),
    )
    assert ledger["reviewed_page_count"] == 1
    assert ledger["unreviewed_available_page_count"] == 228
    assert ledger["reviewer_recorded_status"] == "REVIEW_INCOMPLETE"
    assert ledger["portfolio_eligibility_allowed"] is False


def test_full_attested_pass_does_not_prove_independent_review_or_shares() -> None:
    packet = _packet()
    reviews = [_review(row) for row in packet["rows"]]
    ledger = build_independent_review_ledger(packet, _annotations(packet, reviews))
    assert ledger["reviewed_page_count"] == 229
    assert ledger["reviewer_recorded_sample_complete"] is True
    assert ledger["reviewer_recorded_status"] == (
        "REVIEWER_RECORDED_PASS_PENDING_INDEPENDENCE_VERIFICATION"
    )
    assert ledger["human_independence_verified_by_code"] is False
    assert ledger["independent_semantic_audit_complete"] is False
    assert ledger["market_capitalization_calculated"] is False
    assert ledger["live_capital_allowed"] is False


def test_finding_blocks_review_pass_even_with_full_page_coverage() -> None:
    packet = _packet()
    reviews = [_review(row, with_issue=(i == 42)) for i, row in enumerate(packet["rows"])]
    ledger = build_independent_review_ledger(packet, _annotations(packet, reviews))
    assert ledger["reviewer_recorded_status"] == "ISSUES_RECORDED_REMEDIATION_REQUIRED"
    assert ledger["finding_category_counts"]["OMITTED_MATERIAL_TERM"] == 1
    assert ledger["finding_severity_counts"]["MATERIAL"] == 1
    assert ledger["reviewer_recorded_sample_complete"] is False


def test_missing_inference_cannot_be_reviewed() -> None:
    packet = _packet(228)
    row = packet["rows"][-1]
    with pytest.raises(AlphaContractError, match="cannot review missing inference"):
        build_independent_review_ledger(
            packet, _annotations(packet, [_review(row)])
        )


def test_review_cannot_invent_source_evidence() -> None:
    packet = _packet()
    review = _review(packet["rows"][0], with_issue=True)
    review["findings"][0]["source_excerpt"] = "fabricated hidden asset"
    with pytest.raises(AlphaContractError, match="excerpt not found"):
        build_independent_review_ledger(packet, _annotations(packet, [review]))


def test_review_must_be_independently_attested_and_page_bound() -> None:
    packet = _packet()
    review = _review(packet["rows"][0])
    review["reviewer_attests_independence"] = False
    with pytest.raises(AlphaContractError, match="attestation missing"):
        build_independent_review_ledger(packet, _annotations(packet, [review]))
    review["reviewer_attests_independence"] = True
    review["validated_extraction_sha256"] = "b" * 64
    with pytest.raises(AlphaContractError, match="extraction SHA mismatch"):
        build_independent_review_ledger(packet, _annotations(packet, [review]))


def test_duplicate_review_and_unknown_request_are_rejected() -> None:
    packet = _packet()
    review = _review(packet["rows"][0])
    with pytest.raises(AlphaContractError, match="duplicate review request ID"):
        build_independent_review_ledger(
            packet, _annotations(packet, [review, review])
        )
    unknown = {**review, "request_id": "invented"}
    with pytest.raises(AlphaContractError, match="unknown review request ID"):
        build_independent_review_ledger(
            packet, _annotations(packet, [unknown])
        )


def test_source_packet_tampering_fails_closed() -> None:
    packet = _packet()
    packet["rows"][0]["source_page_text"] = "changed after selection"
    with pytest.raises(AlphaContractError, match="packet content SHA mismatch"):
        build_independent_review_ledger(packet, _annotations(packet, []))


def test_pass_with_finding_and_failure_without_finding_rejected() -> None:
    packet = _packet()
    review = _review(packet["rows"][0], with_issue=True)
    review["verdict"] = "PASS"
    with pytest.raises(AlphaContractError, match="PASS cannot carry findings"):
        build_independent_review_ledger(packet, _annotations(packet, [review]))
    review["verdict"] = "ISSUES_FOUND"
    review["findings"] = []
    with pytest.raises(AlphaContractError, match="failure must record a finding"):
        build_independent_review_ledger(packet, _annotations(packet, [review]))
