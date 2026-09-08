from __future__ import annotations

from typing import Any

from marketlab.h003_outcome_review import compile_judgment_batch, validate_source_batch
from marketlab.h003_outcomes import OUTCOME_RULE_ID, OUTCOME_RULE_SHA256

WORKSET_ID = "H003-O001-MANUAL-WORKSET-V1"
SOURCE_BLIND_PACKAGE_SHA256 = "70240c328f1812866b53e97f94b867335eb668f37918e952223d17f9e3fa9b24"
REVIEWER_VERSION = "h003-o001-blind-manual-review-v1"
SAFE_REASON = "EMPTY_EVIDENCE_NO_NEGATIVE_INFERENCE"


class H003ReviewNotesError(ValueError):
    """Raised when compact blind review notes cannot be compiled safely."""


def _require_false(document: dict[str, Any], key: str) -> None:
    if document.get(key) is not False:
        raise H003ReviewNotesError(f"{key} must be false")


def _validate_workset(
    source_batch: dict[str, Any], workset: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    packets = validate_source_batch(source_batch)
    if not isinstance(workset, dict):
        raise H003ReviewNotesError("manual review workset must be an object")
    if workset.get("schema_version") != 1 or workset.get("workset_id") != WORKSET_ID:
        raise H003ReviewNotesError("unexpected H003 manual review workset")
    if workset.get("outcome_rule_id") != OUTCOME_RULE_ID:
        raise H003ReviewNotesError("workset outcome rule id changed")
    if workset.get("outcome_rule_sha256") != OUTCOME_RULE_SHA256:
        raise H003ReviewNotesError("workset outcome rule hash changed")
    if workset.get("source_blind_package_sha256") != SOURCE_BLIND_PACKAGE_SHA256:
        raise H003ReviewNotesError("workset is not bound to the zero-contact package")
    if workset.get("source_batch_number") != source_batch.get("batch_number"):
        raise H003ReviewNotesError("workset batch number does not match source batch")
    if workset.get("source_batch_sha256") != source_batch.get("batch_sha256"):
        raise H003ReviewNotesError("workset does not bind the source batch")
    if workset.get("evidence_text_transformed") is not False:
        raise H003ReviewNotesError("workset evidence text must be verbatim")
    _require_false(workset, "private_binding_accessed")
    _require_false(workset, "market_outcomes_accessed")
    _require_false(workset, "live_capital_allowed")

    manual_payload = workset.get("manual_cards")
    safe_payload = workset.get("safe_unresolved")
    if not isinstance(manual_payload, list) or not isinstance(safe_payload, list):
        raise H003ReviewNotesError("workset card collections must be lists")

    manual: dict[str, dict[str, Any]] = {}
    for card in manual_payload:
        if not isinstance(card, dict):
            raise H003ReviewNotesError("manual workset card must be an object")
        packet_id = card.get("packet_id")
        if not isinstance(packet_id, str) or packet_id not in packets:
            raise H003ReviewNotesError(f"manual card references unknown packet: {packet_id}")
        if packet_id in manual:
            raise H003ReviewNotesError(f"duplicate manual card: {packet_id}")
        packet = packets[packet_id]
        if card.get("blind_payload_sha256") != packet.get("payload_sha256"):
            raise H003ReviewNotesError(f"manual card payload hash mismatch: {packet_id}")
        evidence = card.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise H003ReviewNotesError(f"manual card must retain evidence: {packet_id}")
        expected = [
            {"passage_id": row["passage_id"], "text": row["text"]}
            for row in packet["evidence"]
        ]
        if evidence != expected:
            raise H003ReviewNotesError(f"manual card evidence is not lossless: {packet_id}")
        manual[packet_id] = card

    safe: dict[str, dict[str, Any]] = {}
    for row in safe_payload:
        if not isinstance(row, dict):
            raise H003ReviewNotesError("safe-unresolved row must be an object")
        packet_id = row.get("packet_id")
        if not isinstance(packet_id, str) or packet_id not in packets:
            raise H003ReviewNotesError(f"safe row references unknown packet: {packet_id}")
        if packet_id in safe:
            raise H003ReviewNotesError(f"duplicate safe row: {packet_id}")
        packet = packets[packet_id]
        if packet.get("evidence") != []:
            raise H003ReviewNotesError(f"safe row unexpectedly has evidence: {packet_id}")
        if row.get("blind_payload_sha256") != packet.get("payload_sha256"):
            raise H003ReviewNotesError(f"safe row payload hash mismatch: {packet_id}")
        if row.get("reason") != SAFE_REASON:
            raise H003ReviewNotesError(f"safe row reason changed: {packet_id}")
        safe[packet_id] = row

    if set(manual).intersection(safe):
        raise H003ReviewNotesError("packet appears in both manual and safe workset partitions")
    if set(manual).union(safe) != set(packets):
        raise H003ReviewNotesError("workset does not exactly cover source batch")
    if workset.get("manual_card_count") != len(manual):
        raise H003ReviewNotesError("manual_card_count mismatch")
    if workset.get("safe_unresolved_count") != len(safe):
        raise H003ReviewNotesError("safe_unresolved_count mismatch")
    return manual, safe


def compile_review_notes(
    source_batch: dict[str, Any],
    workset: dict[str, Any],
    notes: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    manual, safe = _validate_workset(source_batch, workset)
    if not isinstance(notes, dict):
        raise H003ReviewNotesError("review notes must be an object")
    if notes.get("schema_version") != 1:
        raise H003ReviewNotesError("review notes schema changed")
    if notes.get("outcome_rule_id") != OUTCOME_RULE_ID:
        raise H003ReviewNotesError("review notes outcome rule id changed")
    if notes.get("outcome_rule_sha256") != OUTCOME_RULE_SHA256:
        raise H003ReviewNotesError("review notes outcome rule hash changed")
    if notes.get("workset_id") != WORKSET_ID:
        raise H003ReviewNotesError("review notes workset id changed")
    if notes.get("source_batch_number") != source_batch.get("batch_number"):
        raise H003ReviewNotesError("review notes batch number does not match source batch")
    if notes.get("source_batch_sha256") != source_batch.get("batch_sha256"):
        raise H003ReviewNotesError("review notes do not bind source batch")
    if notes.get("source_blind_package_sha256") != SOURCE_BLIND_PACKAGE_SHA256:
        raise H003ReviewNotesError("review notes are not bound to zero-contact package")
    _require_false(notes, "private_binding_accessed")
    _require_false(notes, "market_outcomes_accessed")
    _require_false(notes, "live_capital_allowed")

    reviewed_at = notes.get("reviewed_at_utc")
    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        raise H003ReviewNotesError("reviewed_at_utc is required")
    payload = notes.get("notes")
    if not isinstance(payload, list):
        raise H003ReviewNotesError("notes must be a list")

    by_packet: dict[str, dict[str, Any]] = {}
    for note in payload:
        if not isinstance(note, dict):
            raise H003ReviewNotesError("review note must be an object")
        packet_id = note.get("packet_id")
        if not isinstance(packet_id, str) or packet_id not in manual:
            raise H003ReviewNotesError(f"note references non-manual packet: {packet_id}")
        if packet_id in by_packet:
            raise H003ReviewNotesError(f"duplicate review note: {packet_id}")
        cited = note.get("evidence_passage_ids", [])
        if not isinstance(cited, list):
            raise H003ReviewNotesError(f"evidence_passage_ids must be a list: {packet_id}")
        available = {row["passage_id"] for row in manual[packet_id]["evidence"]}
        if any(item not in available for item in cited):
            raise H003ReviewNotesError(f"note cites passage outside manual card: {packet_id}")
        by_packet[packet_id] = note

    missing = sorted(set(manual) - set(by_packet))
    if missing:
        raise H003ReviewNotesError(f"manual review coverage incomplete: missing={len(missing)}")

    judgments: list[dict[str, Any]] = []
    for packet_id in sorted(manual):
        note = by_packet[packet_id]
        judgments.append(
            {
                "packet_id": packet_id,
                "blind_payload_sha256": manual[packet_id]["blind_payload_sha256"],
                "status": note.get("status"),
                "evidence_passage_ids": note.get("evidence_passage_ids", []),
                "observed_value": note.get("observed_value"),
                "observed_unit": note.get("observed_unit"),
                "timing_interpretation": note.get("timing_interpretation"),
                "normalized_observation": str(note.get("normalized_observation") or ""),
            }
        )
    for packet_id in sorted(safe):
        judgments.append(
            {
                "packet_id": packet_id,
                "blind_payload_sha256": safe[packet_id]["blind_payload_sha256"],
                "status": "UNRESOLVED",
                "evidence_passage_ids": [],
                "observed_value": None,
                "observed_unit": None,
                "timing_interpretation": (
                    "No eligible later evidence was available in the frozen source corpus; "
                    "H003-O001 forbids negative inference from silence."
                ),
                "normalized_observation": (
                    "No later evidence. The commitment remains unresolved and does not "
                    "enter the resolved management-delivery denominator."
                ),
            }
        )

    judgment_batch = {
        "schema_version": 1,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "source_batch_number": source_batch["batch_number"],
        "source_batch_sha256": source_batch["batch_sha256"],
        "reviewer_version": REVIEWER_VERSION,
        "reviewed_at_utc": reviewed_at,
        "private_binding_accessed": False,
        "market_outcomes_accessed": False,
        "live_capital_allowed": False,
        "judgments": sorted(judgments, key=lambda row: str(row["packet_id"])),
    }
    decision_batch = compile_judgment_batch(source_batch, judgment_batch)
    return judgment_batch, decision_batch
