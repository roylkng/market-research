from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

HYPOTHESIS_ID = "H022"
RULE_ID = "H022-UF001"
FEATURE_VERSION = "management_forward_information_delta_v1"
SOURCE_REPORT_SHA256 = "45f58e5f0ee72c477ed042fd56be54b4b7c297b78532a011350a44d0a68da861"
SOURCE_BUNDLE_SHA256 = "85d30df9286712c362102865c22ec3a27907e85599bd70d0c053bc95554cb34c"
CANDIDATE_RULE_ID = "H003-E002"
CANDIDATE_RULE_SHA256 = "5aff200d6a2222a7cde972ad341bc43b927d9c5b6d26a58766893980515c24a2"
EXPECTED_SOURCE_COUNT = 1558
EXPECTED_CANDIDATE_COUNT = 5090
CHALLENGE_START = date(2025, 10, 1)
CHALLENGE_END = date(2026, 9, 6)


class ExpandedFeatureError(ValueError):
    """Raised when the expanded H022 feature panel cannot be frozen safely."""


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
        raise ExpandedFeatureError(
            "expanded H022 feature payload must contain finite JSON values"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ExpandedFeatureError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ExpandedFeatureError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise ExpandedFeatureError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def validate_source_report(document: dict[str, Any]) -> None:
    if document.get("hypothesis_id") != HYPOTHESIS_ID:
        raise ExpandedFeatureError("expanded candidate report hypothesis changed")
    if document.get("rule_id") != "H022-UE001":
        raise ExpandedFeatureError("expanded candidate report extraction rule changed")
    if document.get("source_bundle_sha256") != SOURCE_BUNDLE_SHA256:
        raise ExpandedFeatureError("expanded source bundle digest changed")
    if document.get("candidate_rule_id") != CANDIDATE_RULE_ID:
        raise ExpandedFeatureError("candidate rule id changed")
    if document.get("candidate_rule_sha256") != CANDIDATE_RULE_SHA256:
        raise ExpandedFeatureError("candidate rule digest changed")
    if document.get("processed_source_count") != EXPECTED_SOURCE_COUNT:
        raise ExpandedFeatureError("expanded source count changed")
    if document.get("candidate_count") != EXPECTED_CANDIDATE_COUNT:
        raise ExpandedFeatureError("expanded candidate count changed")
    if document.get("source_status_counts") != {"TEXT_READY": EXPECTED_SOURCE_COUNT}:
        raise ExpandedFeatureError("expanded source status coverage changed")
    if document.get("complete") is not True or document.get("freeze_blockers") != []:
        raise ExpandedFeatureError("expanded candidate report is not complete")
    if document.get("outcome_data_attached") is not False:
        raise ExpandedFeatureError("expanded candidate report contains outcomes")
    stored = document.get("report_sha256")
    unsigned = dict(document)
    unsigned.pop("report_sha256", None)
    if stored != SOURCE_REPORT_SHA256 or _canonical_hash(unsigned) != stored:
        raise ExpandedFeatureError("expanded candidate report hash mismatch")
    records = document.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_SOURCE_COUNT:
        raise ExpandedFeatureError("expanded candidate report record coverage changed")


def _metrics(record: dict[str, Any]) -> dict[str, float | int]:
    candidates = record.get("candidates")
    if not isinstance(candidates, list):
        raise ExpandedFeatureError("candidate list is missing")
    if record.get("candidate_count") != len(candidates):
        raise ExpandedFeatureError("candidate count mismatch")
    text_chars = record.get("text_char_count")
    if not isinstance(text_chars, int) or isinstance(text_chars, bool) or text_chars <= 0:
        raise ExpandedFeatureError("text_char_count must be positive")
    deadline_count = 0
    domains: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ExpandedFeatureError("candidate row must be an object")
        deadlines = candidate.get("deadline_markers")
        domain_markers = candidate.get("domain_markers")
        if not isinstance(deadlines, list) or not isinstance(domain_markers, list):
            raise ExpandedFeatureError("candidate marker lists are invalid")
        if deadlines:
            deadline_count += 1
        domains.update(str(marker).strip().casefold() for marker in domain_markers if str(marker).strip())
    count = len(candidates)
    scale = 10_000.0 / text_chars
    return {
        "candidate_count": count,
        "text_char_count": text_chars,
        "deadline_candidate_count": deadline_count,
        "unique_domain_count": len(domains),
        "forward_commitment_density_per_10k_chars": count * scale,
        "deadline_candidate_density_per_10k_chars": deadline_count * scale,
        "domain_breadth_density_per_10k_chars": len(domains) * scale,
        "deadline_share": deadline_count / count if count else 0.0,
    }


def _delta(current: object, prior: object) -> float:
    value = float(current) - float(prior)
    if not math.isfinite(value):
        raise ExpandedFeatureError("non-finite feature delta")
    return value


def build_expanded_feature_panel(document: dict[str, Any]) -> dict[str, Any]:
    validate_source_report(document)
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in document["records"]:
        if not isinstance(record, dict):
            raise ExpandedFeatureError("source record must be an object")
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            raise ExpandedFeatureError("source symbol is missing")
        membership = record.get("membership_status")
        eligible = record.get("signal_eligible")
        if membership not in {
            "PRE_CHALLENGE_CONTEXT",
            "SIGNAL_ELIGIBLE",
            "CONTEXT_ONLY_NONMEMBER",
        }:
            raise ExpandedFeatureError(f"invalid membership status: {membership}")
        if eligible is not (membership == "SIGNAL_ELIGIBLE"):
            raise ExpandedFeatureError("membership and signal eligibility disagree")
        by_symbol[symbol].append(record)

    rows: list[dict[str, Any]] = []
    no_prior_count = 0
    ambiguous_prior_count = 0
    feature_signal_count = 0
    evaluation_signal_count = 0

    for symbol in sorted(by_symbol):
        grouped: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
        for source in by_symbol[symbol]:
            published = _timestamp(
                source.get("exchange_published_at_utc"),
                f"{source.get('source_id')}.exchange_published_at_utc",
            )
            grouped[published].append(source)
        prior_group: list[dict[str, Any]] | None = None
        for published in sorted(grouped):
            current_group = sorted(grouped[published], key=lambda item: str(item["source_id"]))
            for source in current_group:
                current = _metrics(source)
                membership = str(source["membership_status"])
                row: dict[str, Any] = {
                    "schema_version": 1,
                    "hypothesis_id": HYPOTHESIS_ID,
                    "feature_rule_id": RULE_ID,
                    "feature_version": FEATURE_VERSION,
                    "symbol": symbol,
                    "source_id": source["source_id"],
                    "exchange_published_at_utc": published.isoformat().replace("+00:00", "Z"),
                    "membership_status": membership,
                    "source_signal_eligible": bool(source["signal_eligible"]),
                    "feature_status": None,
                    "evaluation_eligible": False,
                    "prior_source_id": None,
                    "prior_exchange_published_at_utc": None,
                    "primary_signal": None,
                    "current": current,
                    "prior": None,
                    "deltas": None,
                }
                if prior_group is None:
                    row["feature_status"] = "NO_SIGNAL_NO_PRIOR_TRANSCRIPT"
                    no_prior_count += 1
                elif len(prior_group) != 1:
                    row["feature_status"] = "NO_SIGNAL_AMBIGUOUS_PRIOR_TIMESTAMP"
                    ambiguous_prior_count += 1
                else:
                    prior_source = prior_group[0]
                    prior = _metrics(prior_source)
                    deltas = {
                        "forward_commitment_density_delta": _delta(
                            current["forward_commitment_density_per_10k_chars"],
                            prior["forward_commitment_density_per_10k_chars"],
                        ),
                        "deadline_candidate_density_delta": _delta(
                            current["deadline_candidate_density_per_10k_chars"],
                            prior["deadline_candidate_density_per_10k_chars"],
                        ),
                        "domain_breadth_density_delta": _delta(
                            current["domain_breadth_density_per_10k_chars"],
                            prior["domain_breadth_density_per_10k_chars"],
                        ),
                        "deadline_share_delta": _delta(
                            current["deadline_share"], prior["deadline_share"]
                        ),
                    }
                    evaluation_eligible = (
                        bool(source["signal_eligible"])
                        and CHALLENGE_START <= published.date() <= CHALLENGE_END
                    )
                    row.update(
                        {
                            "feature_status": "SIGNAL",
                            "evaluation_eligible": evaluation_eligible,
                            "prior_source_id": prior_source["source_id"],
                            "prior_exchange_published_at_utc": prior_source[
                                "exchange_published_at_utc"
                            ],
                            "primary_signal": deltas[
                                "forward_commitment_density_delta"
                            ],
                            "prior": prior,
                            "deltas": deltas,
                        }
                    )
                    feature_signal_count += 1
                    if evaluation_eligible:
                        evaluation_signal_count += 1
                rows.append(row)
            prior_group = current_group

    rows.sort(
        key=lambda row: (
            row["exchange_published_at_utc"], row["symbol"], row["source_id"]
        )
    )
    panel: dict[str, Any] = {
        "schema_version": 1,
        "hypothesis_id": HYPOTHESIS_ID,
        "feature_rule_id": RULE_ID,
        "feature_version": FEATURE_VERSION,
        "source_report_sha256": SOURCE_REPORT_SHA256,
        "source_bundle_sha256": SOURCE_BUNDLE_SHA256,
        "candidate_rule_id": CANDIDATE_RULE_ID,
        "candidate_rule_sha256": CANDIDATE_RULE_SHA256,
        "record_count": len(rows),
        "feature_signal_count": feature_signal_count,
        "challenge_evaluation_signal_count": evaluation_signal_count,
        "no_prior_count": no_prior_count,
        "ambiguous_prior_count": ambiguous_prior_count,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
        "records": rows,
    }
    panel["panel_sha256"] = _canonical_hash(panel)
    return panel


def validate_expanded_feature_panel(panel: dict[str, Any]) -> None:
    stored = panel.get("panel_sha256")
    unsigned = dict(panel)
    unsigned.pop("panel_sha256", None)
    if stored != _canonical_hash(unsigned):
        raise ExpandedFeatureError("expanded feature panel hash mismatch")
    if panel.get("source_report_sha256") != SOURCE_REPORT_SHA256:
        raise ExpandedFeatureError("expanded feature panel source report changed")
    if panel.get("record_count") != EXPECTED_SOURCE_COUNT:
        raise ExpandedFeatureError("expanded feature panel row count changed")
    if panel.get("outcome_data_attached") is not False:
        raise ExpandedFeatureError("expanded feature panel contains outcomes")
    records = panel.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_SOURCE_COUNT:
        raise ExpandedFeatureError("expanded feature panel record coverage changed")
    forbidden = {"stock_return", "benchmark_return", "future_return", "price"}
    for row in records:
        if not isinstance(row, dict):
            raise ExpandedFeatureError("feature row must be an object")
        if forbidden.intersection(row):
            raise ExpandedFeatureError("expanded feature row contains outcome/price field")
