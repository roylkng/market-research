from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import yaml

from marketlab.claims import ClaimLedger, ManagementClaim, validate_claim_ledger
from marketlab.h003_candidates import (
    CANDIDATE_VERSION,
    EXCLUDE_MARKERS,
    EXTRACTION_RULE_ID,
    EXTRACTION_RULE_SHA256,
    SOURCE_BUNDLE_SHA256,
    ClaimCandidate,
    SourceExtractionRecord,
    _record_digest,
)
from marketlab.h003_candidates import (
    _canonical_hash as _candidate_canonical_hash,
)

REVIEW_RULE_ID = "H003-V001"
REVIEW_RULE_SHA256 = "8b5f3d89b04b486ab2d1e6e9508f9b2ffb69bf51781fa13cbf1db9e81bdc2244"
COHORT_ID = "FY27-Q2-2026-09-06"
DECISION_TIMESTAMP_UTC = "2026-09-06T12:21:06.431463Z"
EXPECTED_COHORT_COMPANY_COUNT = 100
EXPECTED_SOURCE_BEARING_COMPANY_COUNT = 97
FROZEN_ZERO_SOURCE_SYMBOLS = ("BHEL", "ITC", "TRENT")
IST = ZoneInfo("Asia/Kolkata")

Disposition = Literal["ACCEPTED", "REJECTED"]

ACCEPT_REASON = "ACCEPT_MEASURABLE_MANAGEMENT_COMMITMENT"
REJECT_REASON_CODES = frozenset(
    {
        "REJECT_QUESTION_OR_NON_MANAGEMENT_SPEAKER",
        "REJECT_CURRENT_OR_HISTORICAL_FACT",
        "REJECT_GENERIC_ASPIRATION",
        "REJECT_UNRELATED_CONTEXT_VALUE",
        "REJECT_NOT_OBJECTIVELY_RESOLVABLE",
        "REJECT_DUPLICATE_OR_RESTATEMENT",
        "REJECT_OTHER_WITH_EXPLICIT_NOTE",
    }
)
ALL_REASON_CODES = frozenset({ACCEPT_REASON, *REJECT_REASON_CODES})
QUESTION_PREFIXES = (
    "why",
    "what",
    "how",
    "when",
    "where",
    "who",
    "could you",
    "can you",
    "would you",
    "do you",
    "are you",
    "is it",
    "should we",
)
NON_MANAGEMENT_LABELS = ("analyst", "investor", "moderator", "operator")


class H003ReviewError(ValueError):
    """Raised when H003 candidate review violates the frozen blind-review contract."""


def _canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise H003ReviewError("review payload must contain finite JSON values") from exc
    return hashlib.sha256(raw).hexdigest()


def _parse_timestamp(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise H003ReviewError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H003ReviewError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def validate_review_rule_document(document: dict[str, Any]) -> str:
    if not isinstance(document, dict):
        raise H003ReviewError("H003 review rule root must be a mapping")
    declared = document.get("sha256")
    if not isinstance(declared, str) or len(declared) != 64:
        raise H003ReviewError("H003 review rule must declare SHA-256")
    unsigned = dict(document)
    unsigned.pop("sha256", None)
    actual = _canonical_hash(unsigned)
    if actual != declared or declared != REVIEW_RULE_SHA256:
        raise H003ReviewError(
            f"H003 review rule hash mismatch: declared={declared}, recomputed={actual}"
        )
    if document.get("schema_version") != 1 or document.get("id") != REVIEW_RULE_ID:
        raise H003ReviewError("unexpected H003 review rule identity")
    if document.get("status") != "FROZEN":
        raise H003ReviewError("H003 review rule must remain FROZEN")
    if (
        document.get("candidate_rule_id") != EXTRACTION_RULE_ID
        or document.get("candidate_rule_sha256") != EXTRACTION_RULE_SHA256
        or document.get("source_bundle_sha256") != SOURCE_BUNDLE_SHA256
        or document.get("cohort_id") != COHORT_ID
        or document.get("candidate_evidence_cutoff_utc") != DECISION_TIMESTAMP_UTC
    ):
        raise H003ReviewError("H003 review input boundary changed")
    if document.get("review_mode") != "BLIND_SOURCE_CONTEXT_ONLY":
        raise H003ReviewError("H003 review mode changed")
    if document.get("live_capital") is not False:
        raise H003ReviewError("H003 review must keep live_capital: false")
    completion = document.get("completion")
    if not isinstance(completion, dict) or any(
        completion.get(key) is not True
        for key in (
            "requires_complete_candidate_corpus",
            "requires_every_candidate_reviewed",
            "rejected_candidates_remain_in_ledger",
            "accepted_claims_are_hash_bound_to_candidate_decisions",
        )
    ):
        raise H003ReviewError("H003 review completion contract changed")
    return actual


def load_and_validate_review_rule(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    validate_review_rule_document(document)
    return document


@dataclass(frozen=True)
class CandidateCorpus:
    report_sha256: str
    candidate_rule_id: str
    candidate_rule_sha256: str
    source_bundle_sha256: str
    cohort_id: str
    candidate_count: int
    candidates_by_id: dict[str, ClaimCandidate]


def _candidate_from_dict(payload: dict[str, Any]) -> ClaimCandidate:
    document = dict(payload)
    for field in (
        "future_markers",
        "deadline_markers",
        "quantitative_tokens",
        "domain_markers",
    ):
        value = document.get(field)
        if not isinstance(value, list):
            raise H003ReviewError(f"candidate {field} must be a list")
        document[field] = tuple(str(item) for item in value)
    try:
        candidate = ClaimCandidate(**document)
    except TypeError as exc:
        raise H003ReviewError(f"invalid candidate payload: {exc}") from exc
    if (
        candidate.schema_version != 2
        or candidate.rule_id != EXTRACTION_RULE_ID
        or candidate.rule_sha256 != EXTRACTION_RULE_SHA256
        or candidate.candidate_version != CANDIDATE_VERSION
        or candidate.disposition != "UNREVIEWED"
        or candidate.disposition_reason is not None
    ):
        raise H003ReviewError(f"candidate contract mismatch: {candidate.candidate_id}")
    return candidate


def _source_record_from_dict(payload: dict[str, Any]) -> SourceExtractionRecord:
    document = dict(payload)
    candidate_payloads = document.pop("candidates", None)
    if not isinstance(candidate_payloads, list):
        raise H003ReviewError("source record candidates must be a list")
    candidates = tuple(_candidate_from_dict(item) for item in candidate_payloads)
    try:
        record = SourceExtractionRecord(**document, candidates=candidates)
    except TypeError as exc:
        raise H003ReviewError(f"invalid source extraction record: {exc}") from exc
    if record.record_id != _record_digest(record):
        raise H003ReviewError(f"source extraction record hash mismatch: {record.source_id}")
    if record.status != "TEXT_READY":
        raise H003ReviewError(
            f"complete review corpus cannot contain {record.status}: {record.source_id}"
        )
    if record.candidate_count != len(record.candidates):
        raise H003ReviewError(f"candidate count mismatch: {record.source_id}")
    return record


def load_complete_candidate_corpus(path: str | Path) -> CandidateCorpus:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise H003ReviewError(f"could not read candidate corpus {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise H003ReviewError("candidate corpus root must be an object")
    declared = document.get("report_sha256")
    unsigned = dict(document)
    unsigned.pop("report_sha256", None)
    recomputed = _candidate_canonical_hash(unsigned)
    if not isinstance(declared, str) or declared != recomputed:
        raise H003ReviewError(
            f"candidate corpus report hash mismatch: declared={declared}, recomputed={recomputed}"
        )
    if (
        document.get("rule_id") != EXTRACTION_RULE_ID
        or document.get("rule_sha256") != EXTRACTION_RULE_SHA256
        or document.get("source_bundle_sha256") != SOURCE_BUNDLE_SHA256
        or document.get("cohort_id") != COHORT_ID
        or document.get("expected_source_count") != 794
        or document.get("processed_source_count") != 794
        or document.get("expected_member_count") != EXPECTED_COHORT_COMPANY_COUNT
        or document.get("processed_company_count") != EXPECTED_SOURCE_BEARING_COMPANY_COUNT
        or document.get("complete") is not True
        or document.get("freeze_blockers") != []
        or document.get("source_status_counts") != {"TEXT_READY": 794}
    ):
        raise H003ReviewError("candidate corpus is not the complete frozen H003-E002 population")
    records_payload = document.get("records")
    if not isinstance(records_payload, list) or len(records_payload) != 794:
        raise H003ReviewError("candidate corpus must contain exactly 794 source records")
    candidates: dict[str, ClaimCandidate] = {}
    for payload in records_payload:
        if not isinstance(payload, dict):
            raise H003ReviewError("candidate source record must be an object")
        record = _source_record_from_dict(payload)
        for candidate in record.candidates:
            if candidate.candidate_id in candidates:
                raise H003ReviewError(f"duplicate candidate id: {candidate.candidate_id}")
            candidates[candidate.candidate_id] = candidate
    if document.get("candidate_count") != len(candidates):
        raise H003ReviewError("candidate corpus flattened count mismatch")
    return CandidateCorpus(
        report_sha256=declared,
        candidate_rule_id=EXTRACTION_RULE_ID,
        candidate_rule_sha256=EXTRACTION_RULE_SHA256,
        source_bundle_sha256=SOURCE_BUNDLE_SHA256,
        cohort_id=COHORT_ID,
        candidate_count=len(candidates),
        candidates_by_id=candidates,
    )


@dataclass(frozen=True)
class BlindReviewPayload:
    schema_version: int
    payload_sha256: str
    review_rule_id: str
    review_rule_sha256: str
    candidate_id: str
    evidence_sha256: str
    redacted_excerpt: str
    redacted_page_context: tuple[str, ...]
    page_number: int
    line_start: int
    line_end: int
    future_markers: tuple[str, ...]
    deadline_markers: tuple[str, ...]
    quantitative_tokens: tuple[str, ...]
    domain_markers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for field in (
            "redacted_page_context",
            "future_markers",
            "deadline_markers",
            "quantitative_tokens",
            "domain_markers",
        ):
            payload[field] = list(payload[field])
        return payload


def _redact(value: str, redaction_terms: tuple[str, ...]) -> str:
    result = value
    terms = sorted(
        {term.strip() for term in redaction_terms if isinstance(term, str) and term.strip()},
        key=len,
        reverse=True,
    )
    for term in terms:
        result = re.sub(re.escape(term), "[COMPANY]", result, flags=re.IGNORECASE)
    return result


def _candidate_evidence_hash(candidate: ClaimCandidate) -> str:
    return _canonical_hash(candidate.to_dict())


def build_blind_review_payload(
    candidate: ClaimCandidate,
    *,
    page_lines: tuple[str, ...],
    redaction_terms: tuple[str, ...] = (),
    context_radius_lines: int = 3,
) -> BlindReviewPayload:
    if candidate.rule_id != EXTRACTION_RULE_ID or candidate.rule_sha256 != EXTRACTION_RULE_SHA256:
        raise H003ReviewError("candidate does not belong to frozen H003-E002")
    if context_radius_lines < 0:
        raise H003ReviewError("context_radius_lines cannot be negative")
    if candidate.line_start < 1 or candidate.line_end < candidate.line_start:
        raise H003ReviewError("candidate line locator is invalid")
    if candidate.line_end > len(page_lines):
        raise H003ReviewError("candidate locator exceeds reconstructed page lines")
    original_excerpt = " ".join(page_lines[candidate.line_start - 1 : candidate.line_end])
    expected_excerpt = " ".join(original_excerpt.split())
    if len(expected_excerpt) > 600:
        expected_excerpt = expected_excerpt[:600].rstrip()
    if expected_excerpt != " ".join(candidate.excerpt.split()):
        raise H003ReviewError("reconstructed source lines do not match candidate excerpt")
    context_start = max(0, candidate.line_start - 1 - context_radius_lines)
    context_end = min(len(page_lines), candidate.line_end + context_radius_lines)
    redaction_terms = tuple({candidate.symbol, *redaction_terms})
    provisional = BlindReviewPayload(
        schema_version=1,
        payload_sha256="",
        review_rule_id=REVIEW_RULE_ID,
        review_rule_sha256=REVIEW_RULE_SHA256,
        candidate_id=candidate.candidate_id,
        evidence_sha256=_candidate_evidence_hash(candidate),
        redacted_excerpt=_redact(candidate.excerpt, redaction_terms),
        redacted_page_context=tuple(
            _redact(line, redaction_terms) for line in page_lines[context_start:context_end]
        ),
        page_number=candidate.page_number,
        line_start=candidate.line_start,
        line_end=candidate.line_end,
        future_markers=candidate.future_markers,
        deadline_markers=candidate.deadline_markers,
        quantitative_tokens=candidate.quantitative_tokens,
        domain_markers=candidate.domain_markers,
    )
    payload = provisional.to_dict()
    payload.pop("payload_sha256", None)
    return replace(provisional, payload_sha256=_canonical_hash(payload))


def mechanical_rejection(payload: BlindReviewPayload) -> str | None:
    text = payload.redacted_excerpt.strip()
    lowered = text.casefold()
    if any(marker in lowered for marker in EXCLUDE_MARKERS):
        return "REJECT_OTHER_WITH_EXPLICIT_NOTE"
    if "?" in text:
        return "REJECT_QUESTION_OR_NON_MANAGEMENT_SPEAKER"
    stripped = re.sub(r"^[^a-zA-Z]+", "", lowered)
    if any(stripped.startswith(prefix) for prefix in QUESTION_PREFIXES):
        return "REJECT_QUESTION_OR_NON_MANAGEMENT_SPEAKER"
    if any(
        re.search(rf"\b{re.escape(label)}\s*[:\-]", lowered)
        for label in NON_MANAGEMENT_LABELS
    ):
        return "REJECT_QUESTION_OR_NON_MANAGEMENT_SPEAKER"
    return None


@dataclass(frozen=True)
class NormalizedClaimDraft:
    claim_type: str
    metric: str
    unit: str | None
    target_min: float | None
    target_max: float | None
    target_deadline: str | None
    target_horizon: str | None
    normalized_claim: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewDecision:
    schema_version: int
    decision_id: str
    review_rule_id: str
    review_rule_sha256: str
    candidate_id: str
    blind_payload_sha256: str
    disposition: Disposition
    reason_code: str
    reviewer_version: str
    reviewed_at_utc: str
    note: str | None
    duplicate_of_candidate_id: str | None
    normalized_claim: NormalizedClaimDraft | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["normalized_claim"] = (
            None if self.normalized_claim is None else self.normalized_claim.to_dict()
        )
        return payload


def _decision_digest(decision: ReviewDecision) -> str:
    payload = decision.to_dict()
    payload.pop("decision_id", None)
    return _canonical_hash(payload)


def build_review_decision(
    *,
    candidate_id: str,
    blind_payload_sha256: str,
    disposition: Disposition,
    reason_code: str,
    reviewer_version: str,
    reviewed_at_utc: str,
    note: str | None = None,
    duplicate_of_candidate_id: str | None = None,
    normalized_claim: NormalizedClaimDraft | None = None,
) -> ReviewDecision:
    if disposition not in {"ACCEPTED", "REJECTED"}:
        raise H003ReviewError(f"invalid review disposition: {disposition}")
    if reason_code not in ALL_REASON_CODES:
        raise H003ReviewError(f"invalid review reason code: {reason_code}")
    if not reviewer_version.strip():
        raise H003ReviewError("reviewer_version is required")
    _parse_timestamp(reviewed_at_utc, field="reviewed_at_utc")
    if len(blind_payload_sha256) != 64:
        raise H003ReviewError("blind_payload_sha256 must be SHA-256")
    if disposition == "ACCEPTED":
        if reason_code != ACCEPT_REASON:
            raise H003ReviewError("accepted decision requires the acceptance reason code")
        if normalized_claim is None:
            raise H003ReviewError("accepted decision requires normalized claim fields")
        if duplicate_of_candidate_id is not None:
            raise H003ReviewError("accepted decision cannot be marked duplicate")
        if not normalized_claim.claim_type.strip() or not normalized_claim.metric.strip():
            raise H003ReviewError("accepted claim_type and metric are required")
        if not normalized_claim.normalized_claim.strip():
            raise H003ReviewError("accepted normalized_claim is required")
        if not normalized_claim.target_deadline and not normalized_claim.target_horizon:
            raise H003ReviewError("accepted claim requires a deadline or horizon")
        for value, field in (
            (normalized_claim.target_min, "target_min"),
            (normalized_claim.target_max, "target_max"),
        ):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise H003ReviewError(f"{field} must be numeric when present")
        if (
            normalized_claim.target_min is not None
            and normalized_claim.target_max is not None
            and normalized_claim.target_min > normalized_claim.target_max
        ):
            raise H003ReviewError("accepted target_min exceeds target_max")
    else:
        if reason_code == ACCEPT_REASON:
            raise H003ReviewError("rejected decision cannot use acceptance reason")
        if normalized_claim is not None:
            raise H003ReviewError("rejected decision cannot contain normalized claim fields")
        if reason_code == "REJECT_DUPLICATE_OR_RESTATEMENT" and not duplicate_of_candidate_id:
            raise H003ReviewError("duplicate rejection requires duplicate_of_candidate_id")
        if reason_code == "REJECT_OTHER_WITH_EXPLICIT_NOTE" and not (note or "").strip():
            raise H003ReviewError("other rejection requires an explicit note")
    provisional = ReviewDecision(
        schema_version=1,
        decision_id="",
        review_rule_id=REVIEW_RULE_ID,
        review_rule_sha256=REVIEW_RULE_SHA256,
        candidate_id=candidate_id,
        blind_payload_sha256=blind_payload_sha256,
        disposition=disposition,
        reason_code=reason_code,
        reviewer_version=reviewer_version,
        reviewed_at_utc=_parse_timestamp(reviewed_at_utc, field="reviewed_at_utc")
        .isoformat()
        .replace("+00:00", "Z"),
        note=note,
        duplicate_of_candidate_id=duplicate_of_candidate_id,
        normalized_claim=normalized_claim,
    )
    return replace(provisional, decision_id=_decision_digest(provisional))


@dataclass(frozen=True)
class ReviewLedger:
    schema_version: int
    ledger_sha256: str
    review_rule_id: str
    review_rule_sha256: str
    candidate_report_sha256: str
    candidate_count: int
    reviewed_count: int
    accepted_count: int
    rejected_count: int
    complete: bool
    decisions: tuple[ReviewDecision, ...]
    accepted_claims: tuple[ManagementClaim, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["decisions"] = [decision.to_dict() for decision in self.decisions]
        payload["accepted_claims"] = [claim.to_dict() for claim in self.accepted_claims]
        return payload


def _claim_id(
    candidate_id: str,
    decision_id: str,
    draft: NormalizedClaimDraft,
) -> str:
    return "H003C-" + _canonical_hash(
        {
            "candidate_id": candidate_id,
            "decision_id": decision_id,
            "normalized_claim": draft.to_dict(),
        }
    )[:20]


def _management_claim(
    candidate: ClaimCandidate,
    decision_id: str,
    draft: NormalizedClaimDraft,
) -> ManagementClaim:
    publication = _parse_timestamp(
        candidate.exchange_published_at_utc, field="candidate.exchange_published_at_utc"
    )
    source_date = publication.astimezone(IST).date().isoformat()
    claim = ManagementClaim(
        claim_id=_claim_id(candidate.candidate_id, decision_id, draft),
        symbol=candidate.symbol,
        source_date=source_date,
        source_url=candidate.attachment_url,
        source_type="NSE_MANAGEMENT_TRANSCRIPT",
        source_locator=(
            f"candidate={candidate.candidate_id};decision={decision_id};"
            f"page={candidate.page_number};lines={candidate.line_start}-{candidate.line_end}"
        ),
        claim_type=draft.claim_type,
        metric=draft.metric,
        unit=draft.unit,
        target_min=draft.target_min,
        target_max=draft.target_max,
        target_deadline=draft.target_deadline,
        target_horizon=draft.target_horizon,
        normalized_claim=draft.normalized_claim,
        status="ACTIVE",
        supersedes_claim_id=None,
        claim_hash=None,
    )
    return replace(claim, claim_hash=claim.computed_hash())


def freeze_review_ledger(
    corpus: CandidateCorpus,
    decisions: list[ReviewDecision],
    blind_payloads: list[BlindReviewPayload],
) -> ReviewLedger:
    payload_by_candidate: dict[str, BlindReviewPayload] = {}
    for blind_payload in blind_payloads:
        payload_document = blind_payload.to_dict()
        declared_payload_hash = payload_document.pop("payload_sha256", None)
        if (
            blind_payload.schema_version != 1
            or blind_payload.review_rule_id != REVIEW_RULE_ID
            or blind_payload.review_rule_sha256 != REVIEW_RULE_SHA256
            or declared_payload_hash != _canonical_hash(payload_document)
        ):
            raise H003ReviewError(
                f"invalid blind review payload: {blind_payload.candidate_id}"
            )
        candidate = corpus.candidates_by_id.get(blind_payload.candidate_id)
        if candidate is None:
            raise H003ReviewError(
                f"blind payload references unknown candidate: {blind_payload.candidate_id}"
            )
        if blind_payload.evidence_sha256 != _candidate_evidence_hash(candidate):
            raise H003ReviewError(
                f"blind payload evidence hash mismatch: {blind_payload.candidate_id}"
            )
        if blind_payload.candidate_id in payload_by_candidate:
            raise H003ReviewError(
                f"duplicate blind review payload: {blind_payload.candidate_id}"
            )
        payload_by_candidate[blind_payload.candidate_id] = blind_payload
    payload_missing = sorted(set(corpus.candidates_by_id) - set(payload_by_candidate))
    if payload_missing:
        raise H003ReviewError(
            f"blind payload coverage incomplete; missing={len(payload_missing)}"
        )

    by_candidate: dict[str, ReviewDecision] = {}
    for decision in decisions:
        if (
            decision.schema_version != 1
            or decision.review_rule_id != REVIEW_RULE_ID
            or decision.review_rule_sha256 != REVIEW_RULE_SHA256
            or decision.decision_id != _decision_digest(decision)
        ):
            raise H003ReviewError(f"invalid review decision: {decision.candidate_id}")
        if decision.candidate_id not in corpus.candidates_by_id:
            raise H003ReviewError(f"review decision references unknown candidate: {decision.candidate_id}")
        if decision.candidate_id in by_candidate:
            raise H003ReviewError(f"duplicate review decision: {decision.candidate_id}")
        blind_payload = payload_by_candidate[decision.candidate_id]
        if decision.blind_payload_sha256 != blind_payload.payload_sha256:
            raise H003ReviewError(
                f"decision blind-payload hash mismatch: {decision.candidate_id}"
            )
        by_candidate[decision.candidate_id] = decision
    missing = sorted(set(corpus.candidates_by_id) - set(by_candidate))
    extra = sorted(set(by_candidate) - set(corpus.candidates_by_id))
    if missing or extra:
        raise H003ReviewError(
            f"review coverage incomplete; missing={len(missing)}, extra={len(extra)}"
        )
    accepted_claims: list[ManagementClaim] = []
    for candidate_id in sorted(by_candidate):
        decision = by_candidate[candidate_id]
        candidate = corpus.candidates_by_id[candidate_id]
        if decision.disposition == "ACCEPTED":
            if decision.normalized_claim is None:
                raise H003ReviewError("accepted review decision lost normalized claim")
            accepted_claims.append(
                _management_claim(candidate, decision.decision_id, decision.normalized_claim)
            )
    claim_ledger = ClaimLedger(
        version=1,
        mode="HISTORICAL_RECONSTRUCTION",
        claims=tuple(accepted_claims),
        outcomes=(),
    )
    errors = validate_claim_ledger(claim_ledger)
    if errors:
        raise H003ReviewError("accepted claims violate claim ledger:\n" + "\n".join(errors))
    ordered = tuple(by_candidate[key] for key in sorted(by_candidate))
    accepted_count = sum(item.disposition == "ACCEPTED" for item in ordered)
    rejected_count = len(ordered) - accepted_count
    provisional = ReviewLedger(
        schema_version=1,
        ledger_sha256="",
        review_rule_id=REVIEW_RULE_ID,
        review_rule_sha256=REVIEW_RULE_SHA256,
        candidate_report_sha256=corpus.report_sha256,
        candidate_count=corpus.candidate_count,
        reviewed_count=len(ordered),
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        complete=True,
        decisions=ordered,
        accepted_claims=tuple(sorted(accepted_claims, key=lambda claim: claim.claim_id)),
    )
    payload = provisional.to_dict()
    payload.pop("ledger_sha256", None)
    return replace(provisional, ledger_sha256=_canonical_hash(payload))


def write_review_ledger(path: str | Path, ledger: ReviewLedger) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(ledger.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
