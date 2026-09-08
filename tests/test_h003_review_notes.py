from __future__ import annotations

from copy import deepcopy

import pytest

from marketlab.h003_outcomes import OUTCOME_RULE_ID, OUTCOME_RULE_SHA256
from marketlab.h003_review_batches import canonical_hash
from marketlab.h003_review_notes import (
    SOURCE_BLIND_PACKAGE_SHA256,
    WORKSET_ID,
    H003ReviewNotesError,
    compile_review_notes,
)


def make_packet(packet_id: str, *, evidence: bool) -> dict[str, object]:
    passages = []
    if evidence:
        passages = [
            {
                "passage_id": "H003P-" + "1" * 24,
                "source_alias": "EVIDENCE_SOURCE_001",
                "exchange_published_at_utc": "2026-04-01T10:00:00Z",
                "page_number": 1,
                "line_start": 10,
                "line_end": 11,
                "text": "The target was achieved during the stated period.",
                "retrieval_score": 4.0,
            }
        ]
    packet: dict[str, object] = {
        "schema_version": 1,
        "payload_sha256": "",
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "packet_id": packet_id,
        "source_date": "2025-01-01",
        "normalized_claim": "Deliver the target during FY26.",
        "claim_type": "target",
        "metric": "target",
        "unit": "%",
        "target_min": 10.0,
        "target_max": None,
        "target_deadline": "2026-03-31",
        "target_horizon": None,
        "evidence": passages,
    }
    unsigned = dict(packet)
    unsigned.pop("payload_sha256")
    packet["payload_sha256"] = canonical_hash(unsigned)
    return packet


def fixtures() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    manual = make_packet("H003O-" + "a" * 24, evidence=True)
    safe = make_packet("H003O-" + "b" * 24, evidence=False)
    source_unsigned: dict[str, object] = {
        "schema_version": 1,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "source_blind_package_sha256": SOURCE_BLIND_PACKAGE_SHA256,
        "source_blind_file_sha256": "c" * 64,
        "batch_number": 5,
        "packet_count": 2,
        "packets": [manual, safe],
        "private_binding_accessed": False,
        "market_outcomes_included": False,
        "live_capital_allowed": False,
    }
    source = {**source_unsigned, "batch_sha256": canonical_hash(source_unsigned)}
    workset = {
        "schema_version": 1,
        "workset_id": WORKSET_ID,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "source_blind_package_sha256": SOURCE_BLIND_PACKAGE_SHA256,
        "source_batch_number": 5,
        "source_batch_sha256": source["batch_sha256"],
        "manual_card_count": 1,
        "safe_unresolved_count": 1,
        "manual_cards": [
            {
                "packet_id": manual["packet_id"],
                "blind_payload_sha256": manual["payload_sha256"],
                "source_date": manual["source_date"],
                "normalized_claim": manual["normalized_claim"],
                "claim_type": manual["claim_type"],
                "metric": manual["metric"],
                "unit": manual["unit"],
                "target_min": manual["target_min"],
                "target_max": manual["target_max"],
                "target_deadline": manual["target_deadline"],
                "target_horizon": manual["target_horizon"],
                "evidence": [
                    {"passage_id": row["passage_id"], "text": row["text"]}
                    for row in manual["evidence"]
                ],
            }
        ],
        "safe_unresolved": [
            {
                "packet_id": safe["packet_id"],
                "blind_payload_sha256": safe["payload_sha256"],
                "reason": "EMPTY_EVIDENCE_NO_NEGATIVE_INFERENCE",
            }
        ],
        "evidence_text_transformed": False,
        "private_binding_accessed": False,
        "market_outcomes_accessed": False,
        "live_capital_allowed": False,
    }
    notes = {
        "schema_version": 1,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "workset_id": WORKSET_ID,
        "source_blind_package_sha256": SOURCE_BLIND_PACKAGE_SHA256,
        "source_batch_number": 5,
        "source_batch_sha256": source["batch_sha256"],
        "reviewed_at_utc": "2026-09-08T20:50:00Z",
        "private_binding_accessed": False,
        "market_outcomes_accessed": False,
        "live_capital_allowed": False,
        "notes": [
            {
                "packet_id": manual["packet_id"],
                "status": "MET",
                "evidence_passage_ids": ["H003P-" + "1" * 24],
                "observed_value": 10.0,
                "observed_unit": "%",
                "timing_interpretation": "Explicitly achieved within the stated period.",
                "normalized_observation": "Later evidence explicitly reports target achievement.",
            }
        ],
    }
    return source, workset, notes


def test_compiles_manual_and_safe_packets() -> None:
    source, workset, notes = fixtures()
    judgments, decisions = compile_review_notes(source, workset, notes)
    assert len(judgments["judgments"]) == 2
    assert len(decisions["decisions"]) == 2
    statuses = {row["packet_id"]: row["status"] for row in decisions["decisions"]}
    assert statuses["H003O-" + "a" * 24] == "MET"
    assert statuses["H003O-" + "b" * 24] == "UNRESOLVED"
    safe = next(row for row in decisions["decisions"] if row["status"] == "UNRESOLVED")
    assert safe["evidence_passage_ids"] == []
    assert safe["observed_value"] is None


def test_missing_manual_note_fails_closed() -> None:
    source, workset, notes = fixtures()
    notes["notes"] = []
    with pytest.raises(H003ReviewNotesError, match="coverage incomplete"):
        compile_review_notes(source, workset, notes)


def test_note_cannot_cite_outside_manual_card() -> None:
    source, workset, notes = fixtures()
    notes["notes"][0]["evidence_passage_ids"] = ["H003P-" + "9" * 24]
    with pytest.raises(H003ReviewNotesError, match="outside manual card"):
        compile_review_notes(source, workset, notes)


def test_workset_evidence_must_remain_lossless() -> None:
    source, workset, notes = fixtures()
    broken = deepcopy(workset)
    broken["manual_cards"][0]["evidence"][0]["text"] = "summarized"
    with pytest.raises(H003ReviewNotesError, match="not lossless"):
        compile_review_notes(source, broken, notes)


def test_notes_must_bind_exact_source_batch() -> None:
    source, workset, notes = fixtures()
    notes["source_batch_sha256"] = "f" * 64
    with pytest.raises(H003ReviewNotesError, match="do not bind source batch"):
        compile_review_notes(source, workset, notes)
