from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from marketlab.h003_candidates import (
    EXTRACTION_RULE_ID,
    EXTRACTION_RULE_SHA256,
    FrozenTranscriptSource,
    SourceExtractionRecord,
)

RULE_ID = "H022-UE001"
HYPOTHESIS_ID = "H022"
SOURCE_BUNDLE_SHA256 = "85d30df9286712c362102865c22ec3a27907e85599bd70d0c053bc95554cb34c"
SOURCE_RULE_ID = "H022-US001"
SOURCE_RULE_SHA256 = "3e22fc99c90c11d5477fb81b5fe4d0f4cdf325ea2ae42817f9fc7b2c582403ab"
EXPECTED_MEMBER_COUNT = 211
EXPECTED_SOURCE_COUNT = 1558
EXPECTED_SIGNAL_ELIGIBLE_SOURCE_COUNT = 754
EXPECTED_CONTEXT_ONLY_SOURCE_COUNT = 804

MembershipStatus = Literal[
    "PRE_CHALLENGE_CONTEXT",
    "SIGNAL_ELIGIBLE",
    "CONTEXT_ONLY_NONMEMBER",
]


class ExpandedCandidateError(ValueError):
    """Raised when expanded E002 evidence cannot be frozen safely."""


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
        raise ExpandedCandidateError(
            "expanded candidate payload must contain finite JSON values"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ExpandedCandidateSource:
    source: FrozenTranscriptSource
    membership_status: MembershipStatus
    signal_eligible: bool


def load_expanded_sources(path: str | Path) -> tuple[ExpandedCandidateSource, ...]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExpandedCandidateError(f"could not read expanded source bundle: {exc}") from exc
    if not isinstance(document, dict):
        raise ExpandedCandidateError("expanded source bundle root must be an object")
    stored = document.get("bundle_sha256")
    unsigned = dict(document)
    unsigned.pop("bundle_sha256", None)
    if stored != SOURCE_BUNDLE_SHA256 or _canonical_hash(unsigned) != stored:
        raise ExpandedCandidateError("expanded source bundle hash mismatch")
    if document.get("rule_id") != SOURCE_RULE_ID or document.get("rule_sha256") != SOURCE_RULE_SHA256:
        raise ExpandedCandidateError("expanded source rule identity changed")
    if document.get("member_count") != EXPECTED_MEMBER_COUNT:
        raise ExpandedCandidateError("expanded source member count changed")
    if document.get("transcript_source_count") != EXPECTED_SOURCE_COUNT:
        raise ExpandedCandidateError("expanded transcript source count changed")
    if document.get("signal_eligible_source_count") != EXPECTED_SIGNAL_ELIGIBLE_SOURCE_COUNT:
        raise ExpandedCandidateError("signal-eligible source count changed")
    if document.get("context_only_source_count") != EXPECTED_CONTEXT_ONLY_SOURCE_COUNT:
        raise ExpandedCandidateError("context-only source count changed")
    if document.get("incomplete_count") != 0 or document.get("freeze_ready") is not True:
        raise ExpandedCandidateError("expanded source bundle is not freeze-ready")
    if document.get("outcome_data_attached") is not False:
        raise ExpandedCandidateError("expanded source bundle contains outcomes")

    rows = document.get("records")
    if not isinstance(rows, list) or len(rows) != EXPECTED_MEMBER_COUNT:
        raise ExpandedCandidateError("expanded source bundle company records changed")
    sources: list[ExpandedCandidateSource] = []
    seen_ids: set[str] = set()
    for record in rows:
        if not isinstance(record, dict):
            raise ExpandedCandidateError("expanded coverage record must be an object")
        source_rows = record.get("sources")
        if not isinstance(source_rows, list):
            raise ExpandedCandidateError("expanded coverage sources must be a list")
        for row in source_rows:
            if not isinstance(row, dict):
                raise ExpandedCandidateError("expanded source row must be an object")
            source_id = str(row.get("source_id") or "")
            if not source_id or source_id in seen_ids:
                raise ExpandedCandidateError(f"duplicate/missing source id: {source_id}")
            seen_ids.add(source_id)
            membership_status = str(row.get("membership_status") or "")
            if membership_status not in {
                "PRE_CHALLENGE_CONTEXT",
                "SIGNAL_ELIGIBLE",
                "CONTEXT_ONLY_NONMEMBER",
            }:
                raise ExpandedCandidateError(
                    f"unsupported membership status: {membership_status}"
                )
            signal_eligible = row.get("signal_eligible")
            if signal_eligible is not (membership_status == "SIGNAL_ELIGIBLE"):
                raise ExpandedCandidateError(
                    f"source {source_id}: membership/signal eligibility mismatch"
                )
            source = FrozenTranscriptSource(
                source_id=source_id,
                symbol=str(row.get("symbol") or "").strip().upper(),
                seq_id=str(row.get("seq_id") or ""),
                exchange_published_at_utc=str(row.get("exchange_published_at_utc") or ""),
                attachment_url=str(row.get("attachment_url") or ""),
                discovery_row_sha256=str(row.get("discovery_row_sha256") or ""),
            )
            sources.append(
                ExpandedCandidateSource(
                    source=source,
                    membership_status=membership_status,  # type: ignore[arg-type]
                    signal_eligible=bool(signal_eligible),
                )
            )
    if len(sources) != EXPECTED_SOURCE_COUNT:
        raise ExpandedCandidateError(
            f"expected {EXPECTED_SOURCE_COUNT} expanded sources, found {len(sources)}"
        )
    return tuple(sources)


def validate_h003_record(record: dict[str, Any]) -> None:
    stored = record.get("record_id")
    unsigned = dict(record)
    unsigned.pop("record_id", None)
    if not isinstance(stored, str) or _canonical_hash(unsigned) != stored:
        raise ExpandedCandidateError("H003 E002 extraction record hash mismatch")
    if record.get("rule_id") != EXTRACTION_RULE_ID:
        raise ExpandedCandidateError("candidate extraction rule changed")
    if record.get("rule_sha256") != EXTRACTION_RULE_SHA256:
        raise ExpandedCandidateError("candidate extraction rule hash changed")


def build_expanded_report(
    records: list[dict[str, Any]],
    *,
    source_metadata: tuple[ExpandedCandidateSource, ...],
    generated_at: datetime,
) -> dict[str, Any]:
    if generated_at.tzinfo is None:
        raise ExpandedCandidateError("report generated_at must include timezone")
    metadata = {item.source.source_id: item for item in source_metadata}
    if len(records) != EXPECTED_SOURCE_COUNT:
        raise ExpandedCandidateError(
            f"expanded report expected {EXPECTED_SOURCE_COUNT} records, got {len(records)}"
        )
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        validate_h003_record(record)
        source_id = str(record.get("source_id") or "")
        if source_id in by_id or source_id not in metadata:
            raise ExpandedCandidateError(f"unexpected/duplicate extraction source id: {source_id}")
        by_id[source_id] = record
    if set(by_id) != set(metadata):
        raise ExpandedCandidateError("expanded report source coverage mismatch")

    enriched: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    candidate_count = 0
    signal_candidate_count = 0
    context_candidate_count = 0
    candidate_symbols: set[str] = set()
    signal_candidate_symbols: set[str] = set()
    for item in source_metadata:
        record = dict(by_id[item.source.source_id])
        count = int(record.get("candidate_count") or 0)
        status = str(record.get("status") or "")
        status_counts[status] = status_counts.get(status, 0) + 1
        candidate_count += count
        if count:
            candidate_symbols.add(item.source.symbol)
        if item.signal_eligible:
            signal_candidate_count += count
            if count:
                signal_candidate_symbols.add(item.source.symbol)
        else:
            context_candidate_count += count
        record["membership_status"] = item.membership_status
        record["signal_eligible"] = item.signal_eligible
        enriched.append(record)
    enriched.sort(
        key=lambda row: (
            str(row["exchange_published_at_utc"]),
            str(row["symbol"]),
            str(row["source_id"]),
        )
    )
    blockers: list[str] = []
    non_ready = {key: value for key, value in status_counts.items() if key != "TEXT_READY"}
    if non_ready:
        blockers.append(
            "non_text_ready_sources:"
            + ",".join(f"{key}={value}" for key, value in sorted(non_ready.items()))
        )
    report: dict[str, Any] = {
        "schema_version": 1,
        "report_sha256": "",
        "hypothesis_id": HYPOTHESIS_ID,
        "rule_id": RULE_ID,
        "source_bundle_sha256": SOURCE_BUNDLE_SHA256,
        "candidate_rule_id": EXTRACTION_RULE_ID,
        "candidate_rule_sha256": EXTRACTION_RULE_SHA256,
        "generated_at_utc": generated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "expected_member_count": EXPECTED_MEMBER_COUNT,
        "expected_source_count": EXPECTED_SOURCE_COUNT,
        "processed_source_count": len(enriched),
        "processed_company_count": len({str(row["symbol"]) for row in enriched}),
        "source_status_counts": dict(sorted(status_counts.items())),
        "candidate_count": candidate_count,
        "signal_eligible_candidate_count": signal_candidate_count,
        "context_only_candidate_count": context_candidate_count,
        "companies_with_candidates": len(candidate_symbols),
        "signal_eligible_companies_with_candidates": len(signal_candidate_symbols),
        "complete": not blockers,
        "freeze_blockers": blockers,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
        "records": enriched,
    }
    unsigned = dict(report)
    unsigned.pop("report_sha256", None)
    report["report_sha256"] = _canonical_hash(unsigned)
    return report


def validate_report(report: dict[str, Any]) -> None:
    stored = report.get("report_sha256")
    unsigned = dict(report)
    unsigned.pop("report_sha256", None)
    if stored != _canonical_hash(unsigned):
        raise ExpandedCandidateError("expanded candidate report hash mismatch")
    if report.get("source_bundle_sha256") != SOURCE_BUNDLE_SHA256:
        raise ExpandedCandidateError("expanded candidate report source bundle changed")
    if report.get("candidate_rule_id") != EXTRACTION_RULE_ID:
        raise ExpandedCandidateError("expanded candidate report rule changed")
    if report.get("candidate_rule_sha256") != EXTRACTION_RULE_SHA256:
        raise ExpandedCandidateError("expanded candidate report rule hash changed")
    if report.get("processed_source_count") != EXPECTED_SOURCE_COUNT:
        raise ExpandedCandidateError("expanded candidate report source count changed")
    if report.get("outcome_data_attached") is not False:
        raise ExpandedCandidateError("expanded candidate report contains outcomes")
