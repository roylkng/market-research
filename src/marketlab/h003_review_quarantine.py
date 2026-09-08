from __future__ import annotations

from typing import Any

from marketlab.h003_outcome_review import validate_source_batch
from marketlab.h003_outcomes import OUTCOME_RULE_ID, OUTCOME_RULE_SHA256

QUARANTINE_REVIEWER_VERSION = "h003-o001-reviewer-contamination-exclusion-v1"
EXPECTED_INCIDENT_ID = "H003-O001-BLINDNESS-001"
EXPECTED_CONTAMINATED_BATCHES = (1, 2)


class H003ReviewQuarantineError(ValueError):
    """Raised when the frozen reviewer-contamination quarantine is violated."""


def validate_incident(document: dict[str, Any]) -> None:
    if not isinstance(document, dict):
        raise H003ReviewQuarantineError("blindness incident must be an object")
    if document.get("incident_id") != EXPECTED_INCIDENT_ID:
        raise H003ReviewQuarantineError("unexpected H003 blindness incident id")
    if document.get("outcome_rule_id") != OUTCOME_RULE_ID:
        raise H003ReviewQuarantineError("blindness incident outcome rule id changed")
    if document.get("outcome_rule_sha256") != OUTCOME_RULE_SHA256:
        raise H003ReviewQuarantineError("blindness incident outcome rule hash changed")
    contaminated = document.get("reviewer_contaminated_source_batches")
    if contaminated != list(EXPECTED_CONTAMINATED_BATCHES):
        raise H003ReviewQuarantineError("reviewer-contaminated batch set changed")
    if document.get("market_outcomes_accessed") is not False:
        raise H003ReviewQuarantineError("blindness incident reports market-outcome access")
    if document.get("private_binding_opened") is not False:
        raise H003ReviewQuarantineError("blindness incident reports private-binding access")
    if document.get("live_capital_allowed") is not False:
        raise H003ReviewQuarantineError("blindness incident must keep live capital disabled")


def quarantine_judgment_batch(
    source_batch: dict[str, Any],
    incident: dict[str, Any],
) -> dict[str, Any]:
    validate_incident(incident)
    packets = validate_source_batch(source_batch)
    batch_number = source_batch.get("batch_number")
    if batch_number not in EXPECTED_CONTAMINATED_BATCHES:
        raise H003ReviewQuarantineError(
            f"batch {batch_number} is not reviewer-contaminated and cannot be quarantined"
        )

    reviewed_at = str(incident.get("detected_at_utc") or "")
    if not reviewed_at:
        raise H003ReviewQuarantineError("blindness incident detection timestamp is required")

    judgments = []
    for packet_id in sorted(packets):
        packet = packets[packet_id]
        judgments.append(
            {
                "packet_id": packet_id,
                "blind_payload_sha256": packet["payload_sha256"],
                "status": "UNRESOLVED",
                "evidence_passage_ids": [],
                "observed_value": None,
                "observed_unit": None,
                "timing_interpretation": (
                    "Reviewer identity contamination occurred in the invalidated predecessor "
                    "blind package. This packet is excluded from resolved-outcome features "
                    "regardless of the corrected packet evidence."
                ),
                "normalized_observation": (
                    "Reviewer-contaminated exclusion. No semantic outcome judgment is made "
                    "and this packet must not contribute to the resolved management-delivery "
                    "denominator."
                ),
            }
        )

    return {
        "schema_version": 1,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "source_batch_number": batch_number,
        "source_batch_sha256": source_batch["batch_sha256"],
        "reviewer_version": QUARANTINE_REVIEWER_VERSION,
        "reviewed_at_utc": reviewed_at,
        "private_binding_accessed": False,
        "market_outcomes_accessed": False,
        "live_capital_allowed": False,
        "quarantine_incident_id": EXPECTED_INCIDENT_ID,
        "reviewer_contaminated_exclusion": True,
        "judgments": judgments,
    }
