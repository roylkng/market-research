from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

CLAIM_STATUSES = {"ACTIVE", "SUPERSEDED", "CLOSED"}
OUTCOME_STATUSES = {"MET", "PARTIAL", "MISSED", "LATE", "UNRESOLVED"}
RESOLVED_OUTCOME_STATUSES = ("MET", "PARTIAL", "MISSED", "LATE")


class ClaimLedgerError(ValueError):
    """Raised when a management claim ledger violates provenance or timing rules."""


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _parse_date(value: str, *, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ClaimLedgerError(f"{field} must be ISO date YYYY-MM-DD: {value!r}") from exc


@dataclass(frozen=True)
class ManagementClaim:
    claim_id: str
    symbol: str
    source_date: str
    source_url: str
    source_type: str
    source_locator: str
    claim_type: str
    metric: str
    unit: str | None
    target_min: float | None
    target_max: float | None
    target_deadline: str | None
    target_horizon: str | None
    normalized_claim: str
    status: str = "ACTIVE"
    supersedes_claim_id: str | None = None
    claim_hash: str | None = None

    def hash_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("claim_hash", None)
        return payload

    def computed_hash(self) -> str:
        return _canonical_hash(self.hash_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["claim_hash"] = self.claim_hash or self.computed_hash()
        return payload


@dataclass(frozen=True)
class ClaimOutcome:
    outcome_id: str
    claim_id: str
    observed_date: str
    source_url: str
    source_type: str
    source_locator: str
    status: str
    observed_value: float | None
    observed_unit: str | None
    observed_is_approximate: bool
    normalized_observation: str
    outcome_hash: str | None = None

    def hash_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("outcome_hash", None)
        return payload

    def computed_hash(self) -> str:
        return _canonical_hash(self.hash_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["outcome_hash"] = self.outcome_hash or self.computed_hash()
        return payload


@dataclass(frozen=True)
class ClaimLedger:
    version: int
    mode: str
    claims: tuple[ManagementClaim, ...]
    outcomes: tuple[ClaimOutcome, ...]

    @staticmethod
    def _report(
        symbol: str,
        claims: list[ManagementClaim],
        outcomes: list[ClaimOutcome],
        *,
        as_of_date: str | None = None,
    ) -> dict[str, Any]:
        symbol = symbol.upper()
        claim_ids = {claim.claim_id for claim in claims}
        relevant_outcomes = [outcome for outcome in outcomes if outcome.claim_id in claim_ids]
        latest_by_claim: dict[str, ClaimOutcome] = {}
        for outcome in sorted(
            relevant_outcomes, key=lambda item: (item.observed_date, item.outcome_id)
        ):
            latest_by_claim[outcome.claim_id] = outcome

        counts = {status: 0 for status in sorted(OUTCOME_STATUSES)}
        for outcome in latest_by_claim.values():
            counts[outcome.status] += 1

        resolved = sum(counts[status] for status in RESOLVED_OUTCOME_STATUSES)
        met = counts["MET"]
        return {
            "symbol": symbol,
            "as_of_date": as_of_date,
            "claim_count": len(claims),
            "latest_outcome_count": len(latest_by_claim),
            "pending_without_outcome_count": len(claims) - len(latest_by_claim),
            "status_counts": counts,
            "resolved_count": resolved,
            "met_rate_resolved": (met / resolved if resolved else None),
            "claims": [
                {
                    "claim": claim.to_dict(),
                    "latest_outcome": (
                        latest_by_claim[claim.claim_id].to_dict()
                        if claim.claim_id in latest_by_claim
                        else None
                    ),
                }
                for claim in claims
            ],
        }

    def company_report(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.upper()
        claims = [claim for claim in self.claims if claim.symbol.upper() == symbol]
        return self._report(symbol, claims, list(self.outcomes))

    def company_report_as_of(self, symbol: str, as_of: str) -> dict[str, Any]:
        """Return only claim/outcome evidence that was observable by `as_of`.

        Claim lifecycle `status` is never used to decide eligibility because that
        field may be populated during later reconstruction. Timing is determined
        only by immutable source_date and observed_date values.
        """

        cutoff = _parse_date(as_of, field="as_of")
        symbol = symbol.upper()
        claims = [
            claim
            for claim in self.claims
            if claim.symbol.upper() == symbol
            and _parse_date(claim.source_date, field=f"{claim.claim_id}.source_date") <= cutoff
        ]
        claim_ids = {claim.claim_id for claim in claims}
        outcomes = [
            outcome
            for outcome in self.outcomes
            if outcome.claim_id in claim_ids
            and _parse_date(
                outcome.observed_date, field=f"{outcome.outcome_id}.observed_date"
            )
            <= cutoff
        ]
        return self._report(symbol, claims, outcomes, as_of_date=cutoff.isoformat())

    def delivery_feature_as_of(
        self,
        symbol: str,
        as_of: str,
        *,
        min_resolved_claims: int = 3,
    ) -> dict[str, Any]:
        """Compute H003 v0's simple prior on-time delivery feature.

        No weights are assigned to claim types or failure categories. The primary
        feature is simply MET / resolved, where resolved is MET/PARTIAL/MISSED/LATE.
        A company with insufficient resolved history receives NO_SIGNAL.
        """

        if min_resolved_claims < 1:
            raise ClaimLedgerError("min_resolved_claims must be at least 1")
        report = self.company_report_as_of(symbol, as_of)
        resolved = int(report["resolved_count"])
        eligible = resolved >= min_resolved_claims
        return {
            "symbol": symbol.upper(),
            "as_of_date": report["as_of_date"],
            "feature_name": "prior_management_delivery_met_rate_v1",
            "resolved_count": resolved,
            "minimum_resolved_claims": min_resolved_claims,
            "status_counts": report["status_counts"],
            "pending_without_outcome_count": report["pending_without_outcome_count"],
            "signal_state": "ELIGIBLE" if eligible else "NO_SIGNAL",
            "value": report["met_rate_resolved"] if eligible else None,
        }


def _claim_from_dict(payload: dict[str, Any]) -> ManagementClaim:
    return ManagementClaim(**payload)


def _outcome_from_dict(payload: dict[str, Any]) -> ClaimOutcome:
    return ClaimOutcome(**payload)


def validate_claim_ledger(ledger: ClaimLedger) -> list[str]:
    errors: list[str] = []
    if ledger.mode != "HISTORICAL_RECONSTRUCTION":
        errors.append("claim ledger v1 must use HISTORICAL_RECONSTRUCTION mode")

    claims_by_id: dict[str, ManagementClaim] = {}
    for claim in ledger.claims:
        if claim.claim_id in claims_by_id:
            errors.append(f"duplicate claim id: {claim.claim_id}")
            continue
        claims_by_id[claim.claim_id] = claim
        if claim.status not in CLAIM_STATUSES:
            errors.append(f"{claim.claim_id}: invalid claim status {claim.status}")
        if not claim.source_url.startswith("https://"):
            errors.append(f"{claim.claim_id}: source_url must be https")
        if not claim.source_locator.strip():
            errors.append(f"{claim.claim_id}: source_locator is required")
        try:
            source_date = _parse_date(claim.source_date, field=f"{claim.claim_id}.source_date")
            if claim.target_deadline:
                deadline = _parse_date(
                    claim.target_deadline, field=f"{claim.claim_id}.target_deadline"
                )
                if deadline < source_date:
                    errors.append(f"{claim.claim_id}: target_deadline precedes source_date")
        except ClaimLedgerError as exc:
            errors.append(str(exc))
        if (
            claim.target_min is not None
            and claim.target_max is not None
            and claim.target_min > claim.target_max
        ):
            errors.append(f"{claim.claim_id}: target_min exceeds target_max")
        expected_hash = claim.computed_hash()
        if claim.claim_hash and claim.claim_hash != expected_hash:
            errors.append(f"{claim.claim_id}: claim_hash mismatch")
        if claim.supersedes_claim_id and claim.supersedes_claim_id == claim.claim_id:
            errors.append(f"{claim.claim_id}: claim cannot supersede itself")

    seen_outcomes: set[str] = set()
    for outcome in ledger.outcomes:
        if outcome.outcome_id in seen_outcomes:
            errors.append(f"duplicate outcome id: {outcome.outcome_id}")
            continue
        seen_outcomes.add(outcome.outcome_id)
        claim = claims_by_id.get(outcome.claim_id)
        if claim is None:
            errors.append(f"{outcome.outcome_id}: unknown claim_id {outcome.claim_id}")
            continue
        if outcome.status not in OUTCOME_STATUSES:
            errors.append(f"{outcome.outcome_id}: invalid outcome status {outcome.status}")
        if not outcome.source_url.startswith("https://"):
            errors.append(f"{outcome.outcome_id}: source_url must be https")
        if not outcome.source_locator.strip():
            errors.append(f"{outcome.outcome_id}: source_locator is required")
        try:
            observed_date = _parse_date(
                outcome.observed_date, field=f"{outcome.outcome_id}.observed_date"
            )
            claim_date = _parse_date(claim.source_date, field=f"{claim.claim_id}.source_date")
            if observed_date < claim_date:
                errors.append(f"{outcome.outcome_id}: outcome precedes claim")
        except ClaimLedgerError as exc:
            errors.append(str(exc))
        if outcome.observed_value is not None and not outcome.observed_unit:
            errors.append(f"{outcome.outcome_id}: observed_unit required for numeric outcome")
        expected_hash = outcome.computed_hash()
        if outcome.outcome_hash and outcome.outcome_hash != expected_hash:
            errors.append(f"{outcome.outcome_id}: outcome_hash mismatch")

    for claim in ledger.claims:
        if claim.supersedes_claim_id and claim.supersedes_claim_id not in claims_by_id:
            errors.append(
                f"{claim.claim_id}: supersedes unknown claim {claim.supersedes_claim_id}"
            )

    return errors


def load_claim_ledger(path: str | Path) -> ClaimLedger:
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ClaimLedgerError("claim ledger root must be a mapping")
    claims = tuple(_claim_from_dict(dict(item)) for item in document.get("claims", []))
    outcomes = tuple(_outcome_from_dict(dict(item)) for item in document.get("outcomes", []))
    ledger = ClaimLedger(
        version=int(document.get("version", 0)),
        mode=str(document.get("mode", "")),
        claims=claims,
        outcomes=outcomes,
    )
    errors = validate_claim_ledger(ledger)
    if errors:
        raise ClaimLedgerError("\n".join(errors))
    return ledger
