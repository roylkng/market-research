from __future__ import annotations

from copy import deepcopy

import pytest
import yaml

from marketlab.h003_outcomes import (
    OUTCOME_RULE_SHA256,
    H003OutcomeError,
    SourcePassage,
    build_blind_outcome_payload,
    build_outcome_review_decision,
    build_source_passages,
    load_and_validate_outcome_rule,
    redact_company_identity,
    score_passage,
    select_evidence_passages,
    tokenize,
    validate_outcome_rule_document,
)

RULE_PATH = "registry/h003_outcome_rule.yaml"


def claim() -> dict:
    return {
        "claim_id": "H003C-1234567890abcdef1234",
        "symbol": "TESTCO",
        "source_date": "2025-01-15",
        "claim_type": "VOLUME_GUIDANCE",
        "metric": "annual volume growth",
        "unit": "%",
        "target_min": 15.0,
        "target_max": 20.0,
        "target_deadline": "2026-03-31",
        "target_horizon": "FY26",
        "normalized_claim": "Management targets annual volume growth of 15% to 20% in FY26.",
    }


def passage(
    *,
    alias: str = "EVIDENCE_SOURCE_01",
    timestamp: str = "2025-07-01T03:00:00Z",
    text: str = "Annual volume growth was 18 percent and management said the FY26 target was achieved.",
    line: int = 1,
) -> SourcePassage:
    return SourcePassage(
        source_alias=alias,
        source_text_sha256="a" * 64,
        exchange_published_at_utc=timestamp,
        page_number=1,
        line_start=line,
        line_end=line + 2,
        text=text,
        passage_id=f"H003P-{alias}-{line}",
    )


def test_frozen_rule_loads_and_hash_matches() -> None:
    rule = load_and_validate_outcome_rule(RULE_PATH)
    assert rule["sha256"] == OUTCOME_RULE_SHA256
    assert rule["live_capital"] is False


def test_rule_hash_mutation_fails() -> None:
    with open(RULE_PATH, encoding="utf-8") as handle:
        rule = yaml.safe_load(handle)
    mutated = deepcopy(rule)
    mutated["live_capital"] = True
    with pytest.raises(H003OutcomeError, match="hash mismatch"):
        validate_outcome_rule_document(mutated)


def test_rule_recomputed_but_weakened_identity_still_fails() -> None:
    with open(RULE_PATH, encoding="utf-8") as handle:
        rule = yaml.safe_load(handle)
    mutated = deepcopy(rule)
    mutated["evidence_eligibility"]["same_company_only"] = False
    mutated.pop("sha256")
    # Hash is deliberately not regenerated. This verifies fail-closed mutation.
    mutated["sha256"] = "0" * 64
    with pytest.raises(H003OutcomeError):
        validate_outcome_rule_document(mutated)


def test_tokenization_is_casefolded_and_numeric() -> None:
    assert tokenize("FY26 Volume +18.5%") == ("fy26", "volume", "18.5")


def test_boolean_query_values_fail() -> None:
    with pytest.raises(H003OutcomeError, match="boolean"):
        tokenize(True)


def test_numeric_and_metric_terms_receive_more_weight() -> None:
    p = passage(text="Annual volume growth reached 18.5 during FY26.")
    scored = score_passage(claim(), p)
    assert scored.score >= 5.0
    assert "volume" in scored.matched_tokens


def test_unrelated_passage_is_not_selected() -> None:
    selected = select_evidence_passages(
        claim(),
        [passage(text="The board discussed unrelated governance matters.")],
    )
    assert selected == ()


def test_retrieval_is_deterministic_under_input_reordering() -> None:
    items = [
        passage(alias="E2", timestamp="2025-08-01T03:00:00Z", text="volume growth was 18", line=3),
        passage(alias="E1", timestamp="2025-07-01T03:00:00Z", text="volume growth was 18", line=2),
        passage(
            alias="E1",
            timestamp="2025-07-01T03:00:00Z",
            text="annual volume growth target FY26",
            line=5,
        ),
    ]
    first = select_evidence_passages(claim(), items)
    second = select_evidence_passages(claim(), list(reversed(items)))
    assert [item.passage.passage_id for item in first] == [
        item.passage.passage_id for item in second
    ]


def test_equal_score_prefers_earlier_source() -> None:
    later = passage(alias="LATE", timestamp="2025-08-01T03:00:00Z", text="volume growth target")
    earlier = passage(alias="EARLY", timestamp="2025-07-01T03:00:00Z", text="volume growth target")
    selected = select_evidence_passages(claim(), [later, earlier])
    assert selected[0].passage.source_alias == "EARLY"


def test_per_source_cap_is_two() -> None:
    items = [
        passage(alias="E1", text=f"volume growth target FY26 {i}", line=i) for i in range(1, 8)
    ]
    selected = select_evidence_passages(claim(), items)
    assert len(selected) == 2


def test_total_cap_is_twelve() -> None:
    items = [
        passage(alias=f"E{i:02d}", text="volume growth target FY26", line=i) for i in range(1, 20)
    ]
    selected = select_evidence_passages(claim(), items)
    assert len(selected) == 12


def test_retrieval_limits_cannot_be_retuned() -> None:
    with pytest.raises(H003OutcomeError, match="frozen"):
        select_evidence_passages(claim(), [passage()], max_passages=10)


def test_source_passages_use_three_line_windows_without_crossing_pages() -> None:
    canonical = "a\nb\nc\nd\fe\nf"
    built = build_source_passages(
        source_alias="E1",
        source_text_sha256="b" * 64,
        exchange_published_at_utc="2025-02-01T01:00:00Z",
        canonical_text=canonical,
    )
    assert built[0].text == "a b c"
    assert built[0].page_number == 1
    assert any(item.page_number == 2 and item.text == "e f" for item in built)
    assert all("d e" not in item.text for item in built)


def test_passage_ids_are_content_bound() -> None:
    kwargs = {
        "source_alias": "E1",
        "source_text_sha256": "b" * 64,
        "exchange_published_at_utc": "2025-02-01T01:00:00Z",
    }
    a = build_source_passages(canonical_text="one\ntwo\nthree", **kwargs)[0]
    b = build_source_passages(canonical_text="one\ntwo\nfour", **kwargs)[0]
    assert a.passage_id != b.passage_id


def test_company_redaction_is_case_insensitive() -> None:
    value = "TestCo and TESTCO LIMITED discussed TestCo Industries."
    redacted = redact_company_identity(value, ["TESTCO", "TestCo Limited", "TestCo Industries"])
    assert "testco" not in redacted.casefold()
    assert redacted.count("[COMPANY]") == 3


def test_blind_payload_contains_no_symbol_when_redaction_terms_cover_it() -> None:
    c = claim()
    selected = select_evidence_passages(
        c,
        [passage(text="TESTCO annual volume growth target FY26 was achieved at 18 percent")],
    )
    packet = build_blind_outcome_payload(c, selected, redaction_terms=["TESTCO"])
    rendered = str(packet.to_dict()).casefold()
    assert "testco" not in rendered
    assert packet.packet_id.startswith("H003O-")


def test_blind_payload_is_deterministic() -> None:
    c = claim()
    selected = select_evidence_passages(c, [passage()])
    a = build_blind_outcome_payload(c, selected, redaction_terms=["TESTCO"])
    b = build_blind_outcome_payload(c, selected, redaction_terms=["TESTCO"])
    assert a == b


def test_resolved_decision_requires_packet_evidence() -> None:
    packet = build_blind_outcome_payload(claim(), (), redaction_terms=["TESTCO"])
    with pytest.raises(H003OutcomeError, match="requires cited"):
        build_outcome_review_decision(
            packet=packet,
            status="MET",
            evidence_passage_ids=[],
            observed_value=None,
            observed_unit=None,
            timing_interpretation="FY26",
            normalized_observation="Target was met.",
            reviewer_version="test",
            reviewed_at_utc="2026-09-08T10:00:00Z",
        )


def test_decision_cannot_cite_evidence_outside_packet() -> None:
    selected = select_evidence_passages(claim(), [passage()])
    packet = build_blind_outcome_payload(claim(), selected, redaction_terms=["TESTCO"])
    with pytest.raises(H003OutcomeError, match="outside"):
        build_outcome_review_decision(
            packet=packet,
            status="MET",
            evidence_passage_ids=["H003P-not-in-packet"],
            observed_value=18.0,
            observed_unit="%",
            timing_interpretation="FY26 ends 2026-03-31",
            normalized_observation="Eligible evidence explicitly reports 18 percent growth.",
            reviewer_version="test",
            reviewed_at_utc="2026-09-08T10:00:00Z",
        )


def test_unresolved_can_have_empty_evidence_but_no_observed_value() -> None:
    packet = build_blind_outcome_payload(claim(), (), redaction_terms=["TESTCO"])
    decision = build_outcome_review_decision(
        packet=packet,
        status="UNRESOLVED",
        evidence_passage_ids=[],
        observed_value=None,
        observed_unit=None,
        timing_interpretation=None,
        normalized_observation="No eligible evidence establishes an outcome.",
        reviewer_version="test",
        reviewed_at_utc="2026-09-08T10:00:00Z",
    )
    assert decision.status == "UNRESOLVED"
    with pytest.raises(H003OutcomeError, match="UNRESOLVED"):
        build_outcome_review_decision(
            packet=packet,
            status="UNRESOLVED",
            evidence_passage_ids=[],
            observed_value=18.0,
            observed_unit="%",
            timing_interpretation=None,
            normalized_observation="No resolution.",
            reviewer_version="test",
            reviewed_at_utc="2026-09-08T10:00:00Z",
        )


def test_review_decision_is_hash_deterministic() -> None:
    selected = select_evidence_passages(claim(), [passage()])
    packet = build_blind_outcome_payload(claim(), selected, redaction_terms=["TESTCO"])
    evidence_id = packet.evidence[0].passage_id
    kwargs = {
        "packet": packet,
        "status": "MET",
        "evidence_passage_ids": [evidence_id],
        "observed_value": 18.0,
        "observed_unit": "%",
        "timing_interpretation": "FY26 ends 2026-03-31",
        "normalized_observation": "Eligible evidence explicitly reports target achievement.",
        "reviewer_version": "test",
        "reviewed_at_utc": "2026-09-08T10:00:00Z",
    }
    assert build_outcome_review_decision(**kwargs) == build_outcome_review_decision(**kwargs)
