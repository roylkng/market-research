from __future__ import annotations

from copy import deepcopy

import pytest

from marketlab.h003_outcome_review import (
    H003OutcomeReviewError,
    compile_judgment_batch,
    decision_status_counts,
)
from marketlab.h003_review_batches import (
    OUTCOME_RULE_ID,
    OUTCOME_RULE_SHA256,
    canonical_hash,
)


def packet() -> dict[str, object]:
    provisional: dict[str, object] = {
        "schema_version": 1,
        "payload_sha256": "",
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "packet_id": "H003O-" + "1" * 24,
        "source_date": "2025-01-01",
        "normalized_claim": "Deliver at least 100 units in FY26.",
        "claim_type": "TARGET",
        "metric": "units",
        "unit": "units",
        "target_min": 100.0,
        "target_max": None,
        "target_deadline": None,
        "target_horizon": "FY26",
        "evidence": [
            {
                "passage_id": "H003P-" + "2" * 24,
                "source_alias": "EVIDENCE_SOURCE_001",
                "exchange_published_at_utc": "2026-04-10T10:00:00Z",
                "page_number": 2,
                "line_start": 3,
                "line_end": 5,
                "text": "FY26 delivery was 110 units.",
                "retrieval_score": 8.0,
            }
        ],
    }
    unsigned = dict(provisional)
    unsigned.pop("payload_sha256")
    provisional["payload_sha256"] = canonical_hash(unsigned)
    return provisional


def source_batch() -> dict[str, object]:
    item = packet()
    unsigned: dict[str, object] = {
        "schema_version": 1,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "source_blind_package_sha256": "a" * 64,
        "source_blind_file_sha256": "b" * 64,
        "batch_number": 1,
        "packet_count": 1,
        "packets": [item],
        "private_binding_accessed": False,
        "market_outcomes_included": False,
        "live_capital_allowed": False,
    }
    return {**unsigned, "batch_sha256": canonical_hash(unsigned)}


def judgment_batch() -> dict[str, object]:
    item = packet()
    return {
        "schema_version": 1,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "source_batch_number": 1,
        "source_batch_sha256": source_batch()["batch_sha256"],
        "reviewer_version": "test-reviewer",
        "reviewed_at_utc": "2026-09-08T10:00:00Z",
        "private_binding_accessed": False,
        "market_outcomes_accessed": False,
        "live_capital_allowed": False,
        "judgments": [
            {
                "packet_id": item["packet_id"],
                "blind_payload_sha256": item["payload_sha256"],
                "status": "MET",
                "evidence_passage_ids": ["H003P-" + "2" * 24],
                "observed_value": 110.0,
                "observed_unit": "units",
                "timing_interpretation": "FY26 completed before the evidence source.",
                "normalized_observation": "Later evidence reports 110 units in FY26.",
            }
        ],
    }


def test_compile_judgment_batch_is_deterministic() -> None:
    first = compile_judgment_batch(source_batch(), judgment_batch())
    second = compile_judgment_batch(source_batch(), judgment_batch())
    assert first == second
    assert first["decision_count"] == 1
    assert decision_status_counts(first) == {"MET": 1}
    assert first["decisions"][0]["decision_id"].startswith("H003OD-")
    assert first["private_binding_accessed"] is False
    assert first["market_outcomes_accessed"] is False
    assert first["live_capital_allowed"] is False


def test_missing_judgment_fails_closed() -> None:
    judgments = judgment_batch()
    judgments["judgments"] = []
    with pytest.raises(H003OutcomeReviewError, match="coverage incomplete"):
        compile_judgment_batch(source_batch(), judgments)


def test_wrong_blind_payload_hash_fails_closed() -> None:
    judgments = deepcopy(judgment_batch())
    judgments["judgments"][0]["blind_payload_sha256"] = "0" * 64
    with pytest.raises(H003OutcomeReviewError, match="blind payload hash mismatch"):
        compile_judgment_batch(source_batch(), judgments)


def test_private_binding_access_fails_closed() -> None:
    judgments = judgment_batch()
    judgments["private_binding_accessed"] = True
    with pytest.raises(H003OutcomeReviewError, match="private-binding access"):
        compile_judgment_batch(source_batch(), judgments)


def test_citation_outside_packet_is_rejected() -> None:
    judgments = deepcopy(judgment_batch())
    judgments["judgments"][0]["evidence_passage_ids"] = ["H003P-" + "9" * 24]
    with pytest.raises(ValueError, match="outside the blind packet"):
        compile_judgment_batch(source_batch(), judgments)
