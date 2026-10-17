"""Strict byte-backed provenance gate for P019 scenario arithmetic.

A digest is a content-integrity check, not proof of the issuer, date, audited
scope, owner-cash attribution or calibrated probabilities. This gate requires
all of these to be independently reviewed before invoking scenario arithmetic.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256

from marketlab.hg009_p019_expectations import Case, evaluate


@dataclass(frozen=True)
class SourceEvidence:
    role: str
    source_id: str
    original_bytes: bytes
    expected_sha256: str
    published_utc: str
    issuer_symbol: str
    review_status: str
    reviewed_scope: str


REQUIRED_ROLES = frozenset({
    "price", "fully_diluted_shares", "parent_owner_cash", "probability_calibration"
})


def _valid_utc(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo is not None and dt.utcoffset() == UTC.utcoffset(dt) else None


def evaluate_with_provenance(
    case: Case, evidence: Mapping[str, SourceEvidence], *, decision_cutoff_utc: str,
) -> dict:
    """Fail closed on unverifiable historical inputs. Never authorizes capital."""
    reasons: list[str] = []
    cutoff_instant = _valid_utc(decision_cutoff_utc)
    if cutoff_instant is None:
        return {"status": "ABSTAIN", "symbol": case.symbol,
                "reasons": ["exact_decision_cutoff_required"], "investment_authorized": False}
    try:
        cutoff = date.fromisoformat(case.as_of)
    except (TypeError, ValueError):
        return {"status": "ABSTAIN", "symbol": case.symbol,
                "reasons": ["invalid_as_of_date"], "investment_authorized": False}
    if cutoff_instant.date() != cutoff:
        reasons.append("decision_cutoff_date_inconsistent")
    if set(evidence) != REQUIRED_ROLES:
        reasons.append("required_evidence_roles_missing_or_extra")
    for role in sorted(REQUIRED_ROLES):
        item = evidence.get(role)
        if item is None:
            reasons.append(f"{role}_missing")
            continue
        if item.role != role or not item.source_id or item.issuer_symbol != case.symbol:
            reasons.append(f"{role}_identity_mismatch")
        if (not isinstance(item.original_bytes, bytes)
                or len(item.expected_sha256) != 64
                or sha256(item.original_bytes).hexdigest() != item.expected_sha256):
            reasons.append(f"{role}_original_bytes_unverified")
        t = _valid_utc(item.published_utc)
        if t is None or t > cutoff_instant:
            reasons.append(f"{role}_post_cutoff_or_invalid_publication")
        if item.review_status != "INDEPENDENTLY_REVIEWED":
            reasons.append(f"{role}_review_incomplete")
        if item.reviewed_scope != role:
            reasons.append(f"{role}_scope_not_verified")
    if reasons:
        return {"status": "ABSTAIN", "symbol": case.symbol,
                "reasons": sorted(set(reasons)), "investment_authorized": False}
    # Verified source custody alone cannot prove actual economic mapping.
    result = evaluate(case)
    result["decision_cutoff_utc"] = decision_cutoff_utc
    result["source_bytes_integrity_checked"] = True
    result["source_content_economic_truth_verified_by_code"] = False
    result["investment_authorized"] = False
    return result
