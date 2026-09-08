from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import marketlab.h003_review as review
from marketlab.h003_deadlines import canonicalize_target_deadline
from marketlab.h003_review import (
    REVIEW_RULE_ID,
    REVIEW_RULE_SHA256,
    BlindReviewPayload,
    H003ReviewError,
    NormalizedClaimDraft,
    ReviewDecision,
    load_and_validate_review_rule,
    load_complete_candidate_corpus,
    write_review_ledger,
)

IST = ZoneInfo("Asia/Kolkata")
DEADLINE_RULE_ID = "H003-D001"


def _canonical_hash(payload: Any) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _blind_payload_from_dict(document: dict[str, Any]) -> BlindReviewPayload:
    payload = dict(document)
    for field in (
        "redacted_page_context",
        "future_markers",
        "deadline_markers",
        "quantitative_tokens",
        "domain_markers",
    ):
        value = payload.get(field)
        if not isinstance(value, list):
            raise H003ReviewError(f"blind payload {field} must be a list")
        payload[field] = tuple(str(item) for item in value)
    try:
        result = BlindReviewPayload(**payload)
    except TypeError as exc:
        raise H003ReviewError(f"invalid blind payload: {exc}") from exc
    unsigned = result.to_dict()
    declared = unsigned.pop("payload_sha256", None)
    if (
        result.schema_version != 1
        or result.review_rule_id != REVIEW_RULE_ID
        or result.review_rule_sha256 != REVIEW_RULE_SHA256
        or declared != _canonical_hash(unsigned)
    ):
        raise H003ReviewError(f"blind payload identity/hash mismatch: {result.candidate_id}")
    return result


def load_blind_payloads(path: Path) -> tuple[BlindReviewPayload, ...]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise H003ReviewError(f"could not read blind review payloads {path}: {exc}") from exc
    if not isinstance(document, list):
        raise H003ReviewError("blind review payload root must be a list")
    payloads = tuple(
        _blind_payload_from_dict(item) for item in document if isinstance(item, dict)
    )
    if len(payloads) != len(document):
        raise H003ReviewError("blind review payload list contains a non-object item")
    candidate_ids = [payload.candidate_id for payload in payloads]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise H003ReviewError("blind review payload list contains duplicate candidate ids")
    return payloads


def _decision_from_dict(document: dict[str, Any]) -> ReviewDecision:
    payload = dict(document)
    normalized = payload.pop("normalized_claim", None)
    if normalized is not None:
        if not isinstance(normalized, dict):
            raise H003ReviewError("review decision normalized_claim must be an object or null")
        try:
            normalized_claim = NormalizedClaimDraft(**normalized)
        except TypeError as exc:
            raise H003ReviewError(f"invalid normalized claim draft: {exc}") from exc
    else:
        normalized_claim = None
    try:
        return ReviewDecision(**payload, normalized_claim=normalized_claim)
    except TypeError as exc:
        raise H003ReviewError(f"invalid review decision: {exc}") from exc


def _load_decision_file(path: Path) -> tuple[ReviewDecision, ...]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise H003ReviewError(f"could not read review decisions {path}: {exc}") from exc
    if not isinstance(document, list):
        raise H003ReviewError(f"review decision file root must be a list: {path}")
    decisions = tuple(
        _decision_from_dict(item) for item in document if isinstance(item, dict)
    )
    if len(decisions) != len(document):
        raise H003ReviewError(f"review decision file contains a non-object item: {path}")
    return decisions


def load_decisions(mechanical_path: Path, semantic_dir: Path) -> tuple[ReviewDecision, ...]:
    decisions = list(_load_decision_file(mechanical_path))
    if not semantic_dir.exists() or not semantic_dir.is_dir():
        raise H003ReviewError(f"semantic decision directory is missing: {semantic_dir}")
    semantic_files = sorted(
        path for path in semantic_dir.glob("*.json") if path.name != "manifest.json"
    )
    if not semantic_files:
        raise H003ReviewError("semantic decision directory contains no decision files")
    for path in semantic_files:
        decisions.extend(_load_decision_file(path))
    candidate_ids = [decision.candidate_id for decision in decisions]
    duplicates = sorted(
        candidate_id
        for candidate_id, count in Counter(candidate_ids).items()
        if count > 1
    )
    if duplicates:
        raise H003ReviewError(
            f"duplicate candidate decisions across mechanical/semantic files: {duplicates[:10]}"
        )
    return tuple(decisions)


def _source_date(candidate) -> str:
    timestamp = datetime.fromisoformat(candidate.exchange_published_at_utc.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise H003ReviewError(
            f"candidate publication timestamp lacks timezone: {candidate.candidate_id}"
        )
    return timestamp.astimezone(IST).date().isoformat()


def build_summary(ledger) -> dict[str, Any]:
    reason_counts = dict(
        sorted(Counter(decision.reason_code for decision in ledger.decisions).items())
    )
    reviewer_counts = dict(
        sorted(Counter(decision.reviewer_version for decision in ledger.decisions).items())
    )
    metrics = dict(sorted(Counter(claim.metric for claim in ledger.accepted_claims).items()))
    claim_types = dict(
        sorted(Counter(claim.claim_type for claim in ledger.accepted_claims).items())
    )
    unsigned = {
        "schema_version": 2,
        "review_rule_id": ledger.review_rule_id,
        "review_rule_sha256": ledger.review_rule_sha256,
        "deadline_rule_id": DEADLINE_RULE_ID,
        "candidate_report_sha256": ledger.candidate_report_sha256,
        "review_ledger_sha256": ledger.ledger_sha256,
        "candidate_count": ledger.candidate_count,
        "reviewed_count": ledger.reviewed_count,
        "accepted_count": ledger.accepted_count,
        "rejected_count": ledger.rejected_count,
        "complete": ledger.complete,
        "reason_counts": reason_counts,
        "reviewer_counts": reviewer_counts,
        "accepted_claim_type_counts": claim_types,
        "accepted_metric_counts": metrics,
        "claim_outcome_count": 0,
        "live_capital_allowed": False,
    }
    return {**unsigned, "summary_sha256": _canonical_hash(unsigned)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze complete H003-V001 blind judgments while canonicalizing only "
            "deadline syntax at source-identity binding time."
        )
    )
    parser.add_argument("--candidate-report", type=Path, required=True)
    parser.add_argument("--review-rule", type=Path, required=True)
    parser.add_argument("--blind-payloads", type=Path, required=True)
    parser.add_argument("--mechanical-decisions", type=Path, required=True)
    parser.add_argument("--semantic-decisions-dir", type=Path, required=True)
    parser.add_argument("--ledger-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--deadline-audit-out", type=Path, required=True)
    args = parser.parse_args()

    load_and_validate_review_rule(args.review_rule)
    corpus = load_complete_candidate_corpus(args.candidate_report)
    blind_payloads = load_blind_payloads(args.blind_payloads)
    decisions = load_decisions(args.mechanical_decisions, args.semantic_decisions_dir)

    decision_by_candidate = {decision.candidate_id: decision for decision in decisions}
    deadline_rows: list[dict[str, Any]] = []
    resolution_by_candidate = {}
    for candidate_id in sorted(decision_by_candidate):
        decision = decision_by_candidate[candidate_id]
        if decision.disposition != "ACCEPTED":
            continue
        if decision.normalized_claim is None:
            raise H003ReviewError(f"accepted decision lost claim draft: {candidate_id}")
        candidate = corpus.candidates_by_id[candidate_id]
        source_date = _source_date(candidate)
        resolution = canonicalize_target_deadline(
            decision.normalized_claim.target_deadline,
            source_date,
        )
        resolution_by_candidate[candidate_id] = resolution
        deadline_rows.append(
            {
                "candidate_id": candidate_id,
                "decision_id": decision.decision_id,
                **resolution.to_dict(),
            }
        )

    # Keep every original ReviewDecision byte-for-byte/hash-equivalent. Only the
    # ManagementClaim representation receives a canonical ledger date. Claim IDs
    # remain derived from the original blind-review draft, not the canonical form.
    original_management_claim = review._management_claim

    def canonical_management_claim(candidate, decision_id, draft):
        resolution = resolution_by_candidate[candidate.candidate_id]
        target_horizon = draft.target_horizon
        if resolution.canonical_deadline is None and draft.target_deadline:
            target_horizon = target_horizon or f"deadline_text={draft.target_deadline}"
        canonical_draft = replace(
            draft,
            target_deadline=resolution.canonical_deadline,
            target_horizon=target_horizon,
        )
        claim = original_management_claim(candidate, decision_id, canonical_draft)
        raw_claim_id = review._claim_id(candidate.candidate_id, decision_id, draft)
        claim = replace(claim, claim_id=raw_claim_id, claim_hash=None)
        return replace(claim, claim_hash=claim.computed_hash())

    review._management_claim = canonical_management_claim
    try:
        ledger = review.freeze_review_ledger(corpus, list(decisions), list(blind_payloads))
    finally:
        review._management_claim = original_management_claim

    if len(ledger.accepted_claims) != ledger.accepted_count:
        raise H003ReviewError("accepted claim count diverges from accepted decisions")

    write_review_ledger(args.ledger_out, ledger)
    summary = build_summary(ledger)
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    status_counts = dict(sorted(Counter(row["status"] for row in deadline_rows).items()))
    audit_unsigned = {
        "schema_version": 1,
        "deadline_rule_id": DEADLINE_RULE_ID,
        "review_rule_id": REVIEW_RULE_ID,
        "review_rule_sha256": REVIEW_RULE_SHA256,
        "accepted_claim_count": ledger.accepted_count,
        "deadline_status_counts": status_counts,
        "canonical_deadline_count": sum(
            row["canonical_deadline"] is not None for row in deadline_rows
        ),
        "deferred_deadline_count": sum(
            str(row["status"]).startswith("DEFERRED_") for row in deadline_rows
        ),
        "rows": deadline_rows,
        "live_capital_allowed": False,
    }
    audit = {**audit_unsigned, "audit_sha256": _canonical_hash(audit_unsigned)}
    args.deadline_audit_out.parent.mkdir(parents=True, exist_ok=True)
    args.deadline_audit_out.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    print(json.dumps({key: audit[key] for key in (
        "deadline_rule_id",
        "accepted_claim_count",
        "canonical_deadline_count",
        "deferred_deadline_count",
        "deadline_status_counts",
        "audit_sha256",
    )}, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
