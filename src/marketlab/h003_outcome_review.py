from __future__ import annotations

from dataclasses import asdict
from typing import Any

from marketlab.h003_outcomes import (
    OUTCOME_RULE_ID,
    OUTCOME_RULE_SHA256,
    BlindOutcomePassage,
    BlindOutcomePayload,
    build_outcome_review_decision,
)
from marketlab.h003_review_batches import canonical_hash, validate_packet


class H003OutcomeReviewError(ValueError):
    """Raised when a blind H003 outcome judgment batch violates its frozen contract."""


def validate_source_batch(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(document, dict):
        raise H003OutcomeReviewError("source review batch must be an object")
    if document.get("schema_version") != 1:
        raise H003OutcomeReviewError("source review batch schema changed")
    if document.get("outcome_rule_id") != OUTCOME_RULE_ID:
        raise H003OutcomeReviewError("source review batch outcome rule id changed")
    if document.get("outcome_rule_sha256") != OUTCOME_RULE_SHA256:
        raise H003OutcomeReviewError("source review batch outcome rule hash changed")
    if document.get("private_binding_accessed") is not False:
        raise H003OutcomeReviewError("source review batch reports private-binding access")
    if document.get("market_outcomes_included") is not False:
        raise H003OutcomeReviewError("source review batch contains market outcomes")
    if document.get("live_capital_allowed") is not False:
        raise H003OutcomeReviewError("source review batch must keep live capital disabled")

    declared = document.get("batch_sha256")
    unsigned = dict(document)
    unsigned.pop("batch_sha256", None)
    if not isinstance(declared, str) or declared != canonical_hash(unsigned):
        raise H003OutcomeReviewError("source review batch canonical hash mismatch")

    packets = document.get("packets")
    if not isinstance(packets, list):
        raise H003OutcomeReviewError("source review batch packets must be a list")
    if document.get("packet_count") != len(packets):
        raise H003OutcomeReviewError("source review batch packet_count mismatch")
    by_id: dict[str, dict[str, Any]] = {}
    for packet in packets:
        packet_id = validate_packet(packet)
        if packet_id in by_id:
            raise H003OutcomeReviewError(f"duplicate packet in source batch: {packet_id}")
        by_id[packet_id] = packet
    return by_id


def packet_from_dict(document: dict[str, Any]) -> BlindOutcomePayload:
    validate_packet(document)
    evidence_payload = document.get("evidence")
    if not isinstance(evidence_payload, list):
        raise H003OutcomeReviewError("packet evidence must be a list")
    try:
        evidence = tuple(BlindOutcomePassage(**item) for item in evidence_payload)
        fields = dict(document)
        fields["evidence"] = evidence
        return BlindOutcomePayload(**fields)
    except (TypeError, ValueError) as exc:
        raise H003OutcomeReviewError(
            f"could not reconstruct blind packet {document.get('packet_id')}: {exc}"
        ) from exc


def compile_judgment_batch(
    source_batch: dict[str, Any],
    judgment_batch: dict[str, Any],
) -> dict[str, Any]:
    packets = validate_source_batch(source_batch)
    if not isinstance(judgment_batch, dict):
        raise H003OutcomeReviewError("judgment batch must be an object")
    if judgment_batch.get("schema_version") != 1:
        raise H003OutcomeReviewError("judgment batch schema changed")
    if judgment_batch.get("outcome_rule_id") != OUTCOME_RULE_ID:
        raise H003OutcomeReviewError("judgment batch outcome rule id changed")
    if judgment_batch.get("outcome_rule_sha256") != OUTCOME_RULE_SHA256:
        raise H003OutcomeReviewError("judgment batch outcome rule hash changed")
    if judgment_batch.get("source_batch_number") != source_batch.get("batch_number"):
        raise H003OutcomeReviewError("judgment batch number does not match source batch")
    if judgment_batch.get("source_batch_sha256") != source_batch.get("batch_sha256"):
        raise H003OutcomeReviewError("judgment batch does not bind the source batch")
    if judgment_batch.get("private_binding_accessed") is not False:
        raise H003OutcomeReviewError("judgment batch reports private-binding access")
    if judgment_batch.get("market_outcomes_accessed") is not False:
        raise H003OutcomeReviewError("judgment batch reports market-outcome access")
    if judgment_batch.get("live_capital_allowed") is not False:
        raise H003OutcomeReviewError("judgment batch must keep live capital disabled")

    reviewer_version = judgment_batch.get("reviewer_version")
    reviewed_at_utc = judgment_batch.get("reviewed_at_utc")
    if not isinstance(reviewer_version, str) or not reviewer_version.strip():
        raise H003OutcomeReviewError("judgment batch reviewer_version is required")
    if not isinstance(reviewed_at_utc, str) or not reviewed_at_utc.strip():
        raise H003OutcomeReviewError("judgment batch reviewed_at_utc is required")

    judgments = judgment_batch.get("judgments")
    if not isinstance(judgments, list):
        raise H003OutcomeReviewError("judgments must be a list")
    by_packet: dict[str, dict[str, Any]] = {}
    for judgment in judgments:
        if not isinstance(judgment, dict):
            raise H003OutcomeReviewError("judgment must be an object")
        packet_id = judgment.get("packet_id")
        if not isinstance(packet_id, str) or packet_id not in packets:
            raise H003OutcomeReviewError(f"judgment references unknown packet: {packet_id}")
        if packet_id in by_packet:
            raise H003OutcomeReviewError(f"duplicate judgment: {packet_id}")
        if judgment.get("blind_payload_sha256") != packets[packet_id].get("payload_sha256"):
            raise H003OutcomeReviewError(f"blind payload hash mismatch: {packet_id}")
        by_packet[packet_id] = judgment

    missing = sorted(set(packets) - set(by_packet))
    extra = sorted(set(by_packet) - set(packets))
    if missing or extra:
        raise H003OutcomeReviewError(
            f"judgment coverage incomplete: missing={len(missing)}, extra={len(extra)}"
        )

    decisions = []
    for packet_id in sorted(packets):
        packet = packet_from_dict(packets[packet_id])
        judgment = by_packet[packet_id]
        decision = build_outcome_review_decision(
            packet=packet,
            status=judgment.get("status"),
            evidence_passage_ids=judgment.get("evidence_passage_ids", []),
            observed_value=judgment.get("observed_value"),
            observed_unit=judgment.get("observed_unit"),
            timing_interpretation=judgment.get("timing_interpretation"),
            normalized_observation=str(judgment.get("normalized_observation") or ""),
            reviewer_version=reviewer_version,
            reviewed_at_utc=reviewed_at_utc,
        )
        decisions.append(decision.to_dict())

    unsigned = {
        "schema_version": 1,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "source_batch_number": source_batch["batch_number"],
        "source_batch_sha256": source_batch["batch_sha256"],
        "reviewer_version": reviewer_version,
        "reviewed_at_utc": reviewed_at_utc,
        "decision_count": len(decisions),
        "decisions": decisions,
        "private_binding_accessed": False,
        "market_outcomes_accessed": False,
        "live_capital_allowed": False,
    }
    return {**unsigned, "decision_batch_sha256": canonical_hash(unsigned)}


def decision_status_counts(document: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for decision in document.get("decisions", []):
        status = str(decision.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def source_batch_as_dict(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise H003OutcomeReviewError("source batch must deserialize to an object")
    return document


def compiled_decisions_as_dict(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise H003OutcomeReviewError("compiled decisions must deserialize to an object")
    return document
