from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml

OUTCOME_RULE_ID = "H003-O001"
OUTCOME_RULE_SHA256 = "b808dc76e4ff54e8e6bf156e65c5495c0b9b8ce980a39feec4008f4d630d1f7b"
COHORT_ID = "FY27-Q2-2026-09-06"
REVIEW_LEDGER_SHA256 = "cb1e204685e66c37f274ac83b0c7f9729bb55401a58d1e51e6b50ac270052e4d"
CLAIM_AUDIT_SHA256 = "e5828081241005325306644765ddac64300dbc9084315325964873d65071770a"
SOURCE_BUNDLE_SHA256 = "583af88b3c070e15fe94a7782962c9e1fb1ce167e1412a08fd5c7b2f2dcaf7ee"
SOURCE_CUTOFF_UTC = "2026-09-06T12:21:06.431463Z"
EXPECTED_ACCEPTED_CLAIMS = 869

OutcomeStatus = Literal["MET", "PARTIAL", "MISSED", "LATE", "UNRESOLVED"]
OUTCOME_STATUSES = frozenset({"MET", "PARTIAL", "MISSED", "LATE", "UNRESOLVED"})

# Frozen with H003-O001 implementation before any later-source outcome review.
STOPWORDS = frozenset(
    {
        "a",
        "about",
        "after",
        "again",
        "all",
        "also",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "before",
        "being",
        "between",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "during",
        "for",
        "from",
        "full",
        "had",
        "has",
        "have",
        "in",
        "into",
        "is",
        "it",
        "its",
        "may",
        "next",
        "of",
        "on",
        "or",
        "our",
        "over",
        "per",
        "the",
        "their",
        "this",
        "to",
        "up",
        "was",
        "we",
        "were",
        "will",
        "with",
        "would",
        "year",
        "years",
    }
)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
NUMBER_PATTERN = re.compile(r"(?<![a-z])\d+(?:\.\d+)?")


class H003OutcomeError(ValueError):
    """Raised when H003 outcome evidence violates the frozen H003-O001 contract."""


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
        raise H003OutcomeError("outcome payload must contain finite JSON values") from exc
    return hashlib.sha256(raw).hexdigest()


def _parse_timestamp(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise H003OutcomeError(f"invalid {field}: {value!r}") from exc
    if parsed.tzinfo is None:
        raise H003OutcomeError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def validate_outcome_rule_document(document: dict[str, Any]) -> str:
    if not isinstance(document, dict):
        raise H003OutcomeError("H003 outcome rule root must be a mapping")
    declared = document.get("sha256")
    if not isinstance(declared, str) or len(declared) != 64:
        raise H003OutcomeError("H003 outcome rule must declare SHA-256")
    unsigned = dict(document)
    unsigned.pop("sha256", None)
    actual = _canonical_hash(unsigned)
    if declared != actual or declared != OUTCOME_RULE_SHA256:
        raise H003OutcomeError(
            f"H003 outcome rule hash mismatch: declared={declared}, recomputed={actual}"
        )
    if (
        document.get("schema_version") != 1
        or document.get("id") != OUTCOME_RULE_ID
        or document.get("status") != "FROZEN"
        or document.get("cohort_id") != COHORT_ID
        or document.get("live_capital") is not False
    ):
        raise H003OutcomeError("H003 outcome rule identity/status changed")

    inputs = document.get("immutable_inputs")
    if not isinstance(inputs, dict) or (
        inputs.get("review_ledger_sha256") != REVIEW_LEDGER_SHA256
        or inputs.get("claim_audit_sha256") != CLAIM_AUDIT_SHA256
        or inputs.get("source_bundle_sha256") != SOURCE_BUNDLE_SHA256
        or inputs.get("source_cutoff_utc") != SOURCE_CUTOFF_UTC
        or inputs.get("accepted_claim_count") != EXPECTED_ACCEPTED_CLAIMS
    ):
        raise H003OutcomeError("H003 outcome immutable inputs changed")

    eligibility = document.get("evidence_eligibility")
    if not isinstance(eligibility, dict):
        raise H003OutcomeError("H003 outcome evidence_eligibility is missing")
    required_true = (
        "same_company_only",
        "strictly_after_claim_source_publication",
        "at_or_before_source_cutoff",
        "exchange_source_only",
        "source_hash_verification_required",
    )
    if any(eligibility.get(key) is not True for key in required_true):
        raise H003OutcomeError("H003 outcome source eligibility weakened")
    required_false = (
        "missing_later_mention_is_failure",
        "outside_web_or_manual_source_substitution_allowed",
        "price_return_benchmark_or_future_market_data_allowed",
    )
    if any(eligibility.get(key) is not False for key in required_false):
        raise H003OutcomeError("H003 outcome anti-leakage rule weakened")

    blind = document.get("blind_review")
    if not isinstance(blind, dict):
        raise H003OutcomeError("H003 outcome blind_review is missing")
    for key in (
        "company_identity_visible",
        "symbol_visible",
        "source_url_or_exchange_sequence_visible",
        "market_outcomes_visible",
    ):
        if blind.get(key) is not False:
            raise H003OutcomeError(f"H003 outcome blind field changed: {key}")
    for key in (
        "original_normalized_commitment_visible",
        "original_timing_language_visible",
        "later_evidence_publication_dates_visible",
        "later_evidence_text_visible",
        "review_decisions_frozen_before_return_data_access",
    ):
        if blind.get(key) is not True:
            raise H003OutcomeError(f"H003 outcome review requirement changed: {key}")

    retrieval = document.get("retrieval")
    if not isinstance(retrieval, dict) or (
        retrieval.get("method") != "DETERMINISTIC_LEXICAL_V1"
        or retrieval.get("tokenization") != "CASEFOLD_ALPHANUMERIC"
        or retrieval.get("max_passages_per_claim") != 12
        or retrieval.get("max_passages_per_source") != 2
        or retrieval.get("minimum_nonstopword_overlap") != 1
        or retrieval.get("numeric_tokens_weight") != 3.0
        or retrieval.get("metric_tokens_weight") != 2.0
        or retrieval.get("other_query_tokens_weight") != 1.0
        or retrieval.get("recency_tiebreak") != "EARLIER_SOURCE_FIRST"
        or retrieval.get("zero_match_behavior") != "EMPTY_EVIDENCE_PACKET"
        or retrieval.get("retrieval_parameters_may_change_after_review") is not False
    ):
        raise H003OutcomeError("H003 outcome retrieval contract changed")

    outcomes = document.get("outcomes")
    if not isinstance(outcomes, dict) or set(outcomes.get("allowed", ())) != OUTCOME_STATUSES:
        raise H003OutcomeError("H003 outcome status set changed")
    if outcomes.get("no_negative_inference_from_silence") is not True:
        raise H003OutcomeError("H003 outcome silence rule changed")
    if outcomes.get("ambiguous_timing_forces_unresolved") is not True:
        raise H003OutcomeError("H003 ambiguous timing rule changed")
    if outcomes.get("conflicting_evidence_forces_unresolved") is not True:
        raise H003OutcomeError("H003 conflicting evidence rule changed")

    independence = document.get("independence")
    if not isinstance(independence, dict) or (
        independence.get("primary_unit") != "STRICT_PROMISE_FAMILY"
        or independence.get("strict_repeated_family_count") != 2
        or independence.get("strict_repeated_claim_count") != 4
        or independence.get("primary_family_representative") != "EARLIEST_SOURCE_PUBLICATION"
        or independence.get("broad_family_collapse") != "SENSITIVITY_ONLY"
        or independence.get("broad_repeated_family_count") != 7
        or independence.get("broad_repeated_claim_count") != 14
        or independence.get("material_sensitivity_to_broad_collapse") != "ROBUSTNESS_FAIL"
    ):
        raise H003OutcomeError("H003 outcome independence contract changed")

    feature = document.get("feature_contract")
    if not isinstance(feature, dict) or (
        set(feature.get("resolved_outcomes", ())) != {"MET", "PARTIAL", "MISSED", "LATE"}
        or feature.get("unresolved_excluded_from_denominator") is not True
        or feature.get("minimum_resolved_prior_families") != 3
        or feature.get("prior_met_rate_formula") != "MET / (MET + PARTIAL + MISSED + LATE)"
        or feature.get("claim_type_weighting") != "NONE"
        or feature.get("only_outcomes_observable_by_asof_enter_feature") is not True
        or feature.get("family_counted_once") is not True
    ):
        raise H003OutcomeError("H003 outcome feature contract changed")
    return actual


def load_and_validate_outcome_rule(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    validate_outcome_rule_document(document)
    return document


def tokenize(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, bool):
        raise H003OutcomeError("boolean cannot be tokenized as an outcome-query value")
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise H003OutcomeError("outcome-query numeric value must be finite")
        text = format(float(value), ".12g")
    else:
        text = str(value).casefold()
    return tuple(TOKEN_PATTERN.findall(text))


def _query_weights(claim: dict[str, Any]) -> dict[str, float]:
    required = ("normalized_claim", "metric", "claim_type")
    if any(not str(claim.get(field) or "").strip() for field in required):
        raise H003OutcomeError("claim lacks frozen retrieval query fields")

    weights: dict[str, float] = {}
    metric_tokens = {token for token in tokenize(claim["metric"]) if token not in STOPWORDS}
    for token in metric_tokens:
        weights[token] = max(weights.get(token, 0.0), 2.0)

    numeric_tokens: set[str] = set()
    for field in ("target_min", "target_max"):
        numeric_tokens.update(tokenize(claim.get(field)))
    for token in NUMBER_PATTERN.findall(str(claim.get("normalized_claim") or "")):
        numeric_tokens.add(token)
    for token in numeric_tokens:
        weights[token] = max(weights.get(token, 0.0), 3.0)

    for field in (
        "normalized_claim",
        "claim_type",
        "unit",
        "target_deadline",
        "target_horizon",
    ):
        for token in tokenize(claim.get(field)):
            if token in STOPWORDS:
                continue
            weights[token] = max(weights.get(token, 0.0), 1.0)
    return weights


@dataclass(frozen=True)
class SourcePassage:
    source_alias: str
    source_text_sha256: str
    exchange_published_at_utc: str
    page_number: int
    line_start: int
    line_end: int
    text: str
    passage_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_source_passages(
    *,
    source_alias: str,
    source_text_sha256: str,
    exchange_published_at_utc: str,
    canonical_text: str,
) -> tuple[SourcePassage, ...]:
    if not source_alias.strip():
        raise H003OutcomeError("source_alias is required")
    if len(source_text_sha256) != 64:
        raise H003OutcomeError("source_text_sha256 must be SHA-256")
    _parse_timestamp(exchange_published_at_utc, field="exchange_published_at_utc")

    passages: list[SourcePassage] = []
    seen: set[str] = set()
    for page_number, page_text in enumerate(canonical_text.split("\f"), start=1):
        lines = tuple(line.strip() for line in page_text.splitlines() if line.strip())
        for start in range(len(lines)):
            end = min(len(lines), start + 3)
            text = " ".join(lines[start:end])
            normalized = " ".join(text.split())
            if not normalized:
                continue
            dedupe_key = normalized.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            identity = {
                "source_text_sha256": source_text_sha256,
                "page_number": page_number,
                "line_start": start + 1,
                "line_end": end,
                "text": normalized,
            }
            passages.append(
                SourcePassage(
                    source_alias=source_alias,
                    source_text_sha256=source_text_sha256,
                    exchange_published_at_utc=_parse_timestamp(
                        exchange_published_at_utc,
                        field="exchange_published_at_utc",
                    )
                    .isoformat()
                    .replace("+00:00", "Z"),
                    page_number=page_number,
                    line_start=start + 1,
                    line_end=end,
                    text=normalized,
                    passage_id="H003P-" + _canonical_hash(identity)[:24],
                )
            )
    return tuple(passages)


@dataclass(frozen=True)
class ScoredPassage:
    passage: SourcePassage
    score: float
    matched_tokens: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passage": self.passage.to_dict(),
            "score": self.score,
            "matched_tokens": list(self.matched_tokens),
        }


def score_passage(claim: dict[str, Any], passage: SourcePassage) -> ScoredPassage:
    weights = _query_weights(claim)
    passage_tokens = set(tokenize(passage.text))
    matched = tuple(sorted(token for token in weights if token in passage_tokens))
    score = sum(weights[token] for token in matched)
    return ScoredPassage(passage=passage, score=score, matched_tokens=matched)


def select_evidence_passages(
    claim: dict[str, Any],
    passages: Sequence[SourcePassage],
    *,
    max_passages: int = 12,
    max_per_source: int = 2,
) -> tuple[ScoredPassage, ...]:
    if max_passages != 12 or max_per_source != 2:
        raise H003OutcomeError("H003-O001 retrieval limits are frozen at 12/2")
    weighted_query = _query_weights(claim)
    query_nonstop = set(weighted_query)
    scored: list[ScoredPassage] = []
    for passage in passages:
        candidate = score_passage(claim, passage)
        overlap = query_nonstop.intersection(candidate.matched_tokens)
        if len(overlap) < 1:
            continue
        scored.append(candidate)
    scored.sort(
        key=lambda item: (
            -item.score,
            _parse_timestamp(
                item.passage.exchange_published_at_utc,
                field="passage.exchange_published_at_utc",
            ),
            item.passage.source_alias,
            item.passage.page_number,
            item.passage.line_start,
            item.passage.passage_id,
        )
    )
    selected: list[ScoredPassage] = []
    source_counts: dict[str, int] = {}
    for item in scored:
        alias = item.passage.source_alias
        if source_counts.get(alias, 0) >= max_per_source:
            continue
        selected.append(item)
        source_counts[alias] = source_counts.get(alias, 0) + 1
        if len(selected) == max_passages:
            break
    return tuple(selected)


def redact_company_identity(value: str, redaction_terms: Sequence[str]) -> str:
    result = value
    terms = sorted(
        {str(term).strip() for term in redaction_terms if str(term).strip()},
        key=len,
        reverse=True,
    )
    for term in terms:
        pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
        result = re.sub(pattern, "[COMPANY]", result, flags=re.IGNORECASE)
    return result


@dataclass(frozen=True)
class BlindOutcomePassage:
    passage_id: str
    source_alias: str
    exchange_published_at_utc: str
    page_number: int
    line_start: int
    line_end: int
    text: str
    retrieval_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BlindOutcomePayload:
    schema_version: int
    payload_sha256: str
    outcome_rule_id: str
    outcome_rule_sha256: str
    packet_id: str
    source_date: str
    normalized_claim: str
    claim_type: str
    metric: str
    unit: str | None
    target_min: float | None
    target_max: float | None
    target_deadline: str | None
    target_horizon: str | None
    evidence: tuple[BlindOutcomePassage, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = [item.to_dict() for item in self.evidence]
        return payload


def build_blind_outcome_payload(
    claim: dict[str, Any],
    selected: Sequence[ScoredPassage],
    *,
    redaction_terms: Sequence[str],
) -> BlindOutcomePayload:
    claim_id = str(claim.get("claim_id") or "")
    if not claim_id.startswith("H003C-"):
        raise H003OutcomeError("claim_id is not a frozen H003 claim id")
    packet_id = "H003O-" + _canonical_hash({"rule": OUTCOME_RULE_SHA256, "claim_id": claim_id})[:24]
    evidence = tuple(
        BlindOutcomePassage(
            passage_id=item.passage.passage_id,
            source_alias=item.passage.source_alias,
            exchange_published_at_utc=item.passage.exchange_published_at_utc,
            page_number=item.passage.page_number,
            line_start=item.passage.line_start,
            line_end=item.passage.line_end,
            text=redact_company_identity(item.passage.text, redaction_terms),
            retrieval_score=item.score,
        )
        for item in selected
    )
    provisional = BlindOutcomePayload(
        schema_version=1,
        payload_sha256="",
        outcome_rule_id=OUTCOME_RULE_ID,
        outcome_rule_sha256=OUTCOME_RULE_SHA256,
        packet_id=packet_id,
        source_date=str(claim["source_date"]),
        normalized_claim=redact_company_identity(str(claim["normalized_claim"]), redaction_terms),
        claim_type=str(claim["claim_type"]),
        metric=str(claim["metric"]),
        unit=None if claim.get("unit") is None else str(claim["unit"]),
        target_min=claim.get("target_min"),
        target_max=claim.get("target_max"),
        target_deadline=claim.get("target_deadline"),
        target_horizon=claim.get("target_horizon"),
        evidence=evidence,
    )
    unsigned = provisional.to_dict()
    unsigned.pop("payload_sha256", None)
    return replace(provisional, payload_sha256=_canonical_hash(unsigned))


@dataclass(frozen=True)
class OutcomeReviewDecision:
    schema_version: int
    decision_id: str
    outcome_rule_id: str
    outcome_rule_sha256: str
    packet_id: str
    blind_payload_sha256: str
    status: OutcomeStatus
    evidence_passage_ids: tuple[str, ...]
    observed_value: float | None
    observed_unit: str | None
    timing_interpretation: str | None
    normalized_observation: str
    reviewer_version: str
    reviewed_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_passage_ids"] = list(self.evidence_passage_ids)
        return payload


def build_outcome_review_decision(
    *,
    packet: BlindOutcomePayload,
    status: OutcomeStatus,
    evidence_passage_ids: Sequence[str],
    observed_value: float | None,
    observed_unit: str | None,
    timing_interpretation: str | None,
    normalized_observation: str,
    reviewer_version: str,
    reviewed_at_utc: str,
) -> OutcomeReviewDecision:
    if status not in OUTCOME_STATUSES:
        raise H003OutcomeError(f"invalid H003 outcome status: {status}")
    if not reviewer_version.strip():
        raise H003OutcomeError("reviewer_version is required")
    if not normalized_observation.strip():
        raise H003OutcomeError("normalized_observation is required")
    reviewed = _parse_timestamp(reviewed_at_utc, field="reviewed_at_utc")
    available_ids = {item.passage_id for item in packet.evidence}
    evidence_ids = tuple(dict.fromkeys(str(item) for item in evidence_passage_ids))
    if any(item not in available_ids for item in evidence_ids):
        raise H003OutcomeError("decision cites passage outside the blind packet")
    if status == "UNRESOLVED":
        if observed_value is not None:
            raise H003OutcomeError("UNRESOLVED cannot assert observed_value")
    elif not evidence_ids:
        raise H003OutcomeError("resolved outcome requires cited blind evidence")
    if observed_value is not None:
        if isinstance(observed_value, bool) or not isinstance(observed_value, (int, float)):
            raise H003OutcomeError("observed_value must be numeric")
        if not math.isfinite(float(observed_value)):
            raise H003OutcomeError("observed_value must be finite")
    provisional = OutcomeReviewDecision(
        schema_version=1,
        decision_id="",
        outcome_rule_id=OUTCOME_RULE_ID,
        outcome_rule_sha256=OUTCOME_RULE_SHA256,
        packet_id=packet.packet_id,
        blind_payload_sha256=packet.payload_sha256,
        status=status,
        evidence_passage_ids=evidence_ids,
        observed_value=observed_value,
        observed_unit=observed_unit,
        timing_interpretation=timing_interpretation,
        normalized_observation=normalized_observation.strip(),
        reviewer_version=reviewer_version.strip(),
        reviewed_at_utc=reviewed.isoformat().replace("+00:00", "Z"),
    )
    unsigned = provisional.to_dict()
    unsigned.pop("decision_id", None)
    return replace(provisional, decision_id="H003OD-" + _canonical_hash(unsigned)[:24])
