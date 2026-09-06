from __future__ import annotations

from datetime import UTC, datetime

import pytest

from marketlab.h003_candidates import ClaimCandidate
from marketlab.h003_review import (
    ACCEPT_REASON,
    REVIEW_RULE_ID,
    CandidateCorpus,
    H003ReviewError,
    NormalizedClaimDraft,
    build_blind_review_payload,
    build_review_decision,
    freeze_review_ledger,
    load_and_validate_review_rule,
    mechanical_rejection,
)


def _candidate(
    *,
    candidate_id: str = "cand-1",
    excerpt: str = "We expect revenue growth of 15% next year.",
    line_start: int = 2,
    line_end: int = 2,
) -> ClaimCandidate:
    return ClaimCandidate(
        schema_version=2,
        candidate_id=candidate_id,
        rule_id="H003-E002",
        rule_sha256="5aff200d6a2222a7cde972ad341bc43b927d9c5b6d26a58766893980515c24a2",
        candidate_version="h003_future_commitment_candidate_v2",
        source_id=f"source-{candidate_id}",
        symbol="TEST",
        exchange_published_at_utc="2026-08-01T10:00:00Z",
        attachment_url="https://nsearchives.nseindia.com/test.pdf",
        raw_sha256="a" * 64,
        parser_version="h003_pdf_text_v1",
        page_number=3,
        line_start=line_start,
        line_end=line_end,
        excerpt=excerpt,
        future_markers=("we expect",),
        deadline_markers=("next year",),
        quantitative_tokens=("15%",),
        domain_markers=("revenue", "growth"),
        disposition="UNREVIEWED",
        disposition_reason=None,
    )


def _payload(candidate: ClaimCandidate, page_lines: tuple[str, ...]):
    return build_blind_review_payload(
        candidate,
        page_lines=page_lines,
        redaction_terms=("Test Limited", "TEST"),
    )


def test_frozen_review_rule_validates():
    document = load_and_validate_review_rule("registry/h003_review_rule.yaml")
    assert document["id"] == REVIEW_RULE_ID
    assert document["review_mode"] == "BLIND_SOURCE_CONTEXT_ONLY"
    assert document["live_capital"] is False


def test_blind_payload_redacts_company_metadata_and_preserves_locator():
    candidate = _candidate(excerpt="We expect TEST revenue growth of 15% next year.")
    payload = _payload(
        candidate,
        (
            "Analyst introduction",
            "We expect TEST revenue growth of 15% next year.",
            "Test Limited has multiple business lines.",
        ),
    )
    assert "TEST" not in payload.redacted_excerpt
    assert "Test Limited" not in " ".join(payload.redacted_page_context)
    assert payload.page_number == 3
    assert payload.line_start == 2
    assert payload.line_end == 2
    as_dict = payload.to_dict()
    assert "attachment_url" not in as_dict
    assert "exchange_published_at_utc" not in as_dict
    assert "symbol" not in as_dict


def test_question_is_mechanically_rejected_even_if_it_says_our_guidance():
    candidate = _candidate(
        excerpt="Why is our guidance only 1% to 3% for next year?",
        line_start=1,
        line_end=1,
    )
    payload = _payload(candidate, ("Why is our guidance only 1% to 3% for next year?",))
    assert mechanical_rejection(payload) == "REJECT_QUESTION_OR_NON_MANAGEMENT_SPEAKER"


def test_nearby_analyst_label_does_not_auto_reject_management_answer():
    candidate = _candidate()
    payload = _payload(
        candidate,
        (
            "Analyst: Could you discuss the outlook?",
            "We expect revenue growth of 15% next year.",
            "Management: This is our operating plan.",
        ),
    )
    assert mechanical_rejection(payload) is None


def test_reconstruction_matches_e002_600_character_truncation():
    long_tail = "x" * 700
    full = f"We expect revenue growth of 15% next year. {long_tail}"
    excerpt = full[:600].rstrip()
    candidate = _candidate(excerpt=excerpt, line_start=1, line_end=2)
    payload = _payload(
        candidate,
        ("We expect revenue growth of 15% next year.", long_tail),
    )
    assert payload.redacted_excerpt.startswith("We expect revenue growth of 15% next year")


def test_acceptance_requires_objectively_resolvable_horizon():
    draft = NormalizedClaimDraft(
        claim_type="guidance",
        metric="revenue_growth",
        unit="percent",
        target_min=15.0,
        target_max=15.0,
        target_deadline=None,
        target_horizon=None,
        normalized_claim="Revenue growth target of 15%.",
    )
    with pytest.raises(H003ReviewError, match="deadline or horizon"):
        build_review_decision(
            candidate_id="cand-1",
            blind_payload_sha256="b" * 64,
            disposition="ACCEPTED",
            reason_code=ACCEPT_REASON,
            reviewer_version="blind-review-v1",
            reviewed_at_utc="2026-09-07T00:00:00Z",
            normalized_claim=draft,
        )


def test_complete_review_emits_claims_but_never_outcomes():
    accepted_candidate = _candidate(candidate_id="cand-a")
    rejected_candidate = _candidate(candidate_id="cand-b")
    corpus = CandidateCorpus(
        report_sha256="c" * 64,
        candidate_rule_id="H003-E002",
        candidate_rule_sha256="5aff200d6a2222a7cde972ad341bc43b927d9c5b6d26a58766893980515c24a2",
        source_bundle_sha256="583af88b3c070e15fe94a7782962c9e1fb1ce167e1412a08fd5c7b2f2dcaf7ee",
        cohort_id="FY27-Q2-2026-09-06",
        candidate_count=2,
        candidates_by_id={
            accepted_candidate.candidate_id: accepted_candidate,
            rejected_candidate.candidate_id: rejected_candidate,
        },
    )
    accepted_payload = _payload(
        accepted_candidate,
        ("Analyst question", "We expect revenue growth of 15% next year."),
    )
    rejected_payload = _payload(
        rejected_candidate,
        ("Analyst question", "We expect revenue growth of 15% next year."),
    )
    accepted = build_review_decision(
        candidate_id=accepted_candidate.candidate_id,
        blind_payload_sha256=accepted_payload.payload_sha256,
        disposition="ACCEPTED",
        reason_code=ACCEPT_REASON,
        reviewer_version="blind-review-v1",
        reviewed_at_utc=datetime(2026, 9, 7, tzinfo=UTC).isoformat(),
        normalized_claim=NormalizedClaimDraft(
            claim_type="guidance",
            metric="revenue_growth",
            unit="percent",
            target_min=15.0,
            target_max=15.0,
            target_deadline=None,
            target_horizon="next year",
            normalized_claim="Management expects revenue growth of 15% next year.",
        ),
    )
    rejected = build_review_decision(
        candidate_id=rejected_candidate.candidate_id,
        blind_payload_sha256=rejected_payload.payload_sha256,
        disposition="REJECTED",
        reason_code="REJECT_GENERIC_ASPIRATION",
        reviewer_version="blind-review-v1",
        reviewed_at_utc="2026-09-07T00:00:00Z",
        note="Synthetic rejection fixture.",
    )
    ledger = freeze_review_ledger(
        corpus,
        [accepted, rejected],
        [accepted_payload, rejected_payload],
    )
    assert ledger.complete is True
    assert ledger.accepted_count == 1
    assert ledger.rejected_count == 1
    assert len(ledger.accepted_claims) == 1
    claim = ledger.accepted_claims[0]
    assert claim.symbol == "TEST"
    assert claim.source_type == "NSE_MANAGEMENT_TRANSCRIPT"
    assert claim.target_horizon == "next year"
    assert "outcome" not in ledger.to_dict()


def test_missing_decision_blocks_review_freeze():
    candidate = _candidate(candidate_id="cand-only")
    corpus = CandidateCorpus(
        report_sha256="c" * 64,
        candidate_rule_id="H003-E002",
        candidate_rule_sha256=candidate.rule_sha256,
        source_bundle_sha256="583af88b3c070e15fe94a7782962c9e1fb1ce167e1412a08fd5c7b2f2dcaf7ee",
        cohort_id="FY27-Q2-2026-09-06",
        candidate_count=1,
        candidates_by_id={candidate.candidate_id: candidate},
    )
    with pytest.raises(H003ReviewError, match="coverage incomplete"):
        freeze_review_ledger(corpus, [], [])


def test_wrong_blind_payload_hash_blocks_freeze():
    candidate = _candidate(candidate_id="cand-bind")
    corpus = CandidateCorpus(
        report_sha256="c" * 64,
        candidate_rule_id="H003-E002",
        candidate_rule_sha256=candidate.rule_sha256,
        source_bundle_sha256="583af88b3c070e15fe94a7782962c9e1fb1ce167e1412a08fd5c7b2f2dcaf7ee",
        cohort_id="FY27-Q2-2026-09-06",
        candidate_count=1,
        candidates_by_id={candidate.candidate_id: candidate},
    )
    payload = _payload(
        candidate,
        ("Analyst question", "We expect revenue growth of 15% next year."),
    )
    decision = build_review_decision(
        candidate_id=candidate.candidate_id,
        blind_payload_sha256="0" * 64,
        disposition="REJECTED",
        reason_code="REJECT_GENERIC_ASPIRATION",
        reviewer_version="blind-review-v1",
        reviewed_at_utc="2026-09-07T00:00:00Z",
    )
    with pytest.raises(H003ReviewError, match="blind-payload hash mismatch"):
        freeze_review_ledger(corpus, [decision], [payload])
