from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from marketlab.h003_sources import TranscriptSource, select_transcript_sources
from marketlab.h022_historical_universe import validate_reconstruction

IST = ZoneInfo("Asia/Kolkata")
RULE_ID = "H022-US001"
HYPOTHESIS_ID = "H022"
EXPECTED_MEMBER_COUNT = 211
CHALLENGE_START = date(2025, 10, 1)
CHALLENGE_END = date(2026, 9, 6)
SOURCE_WINDOW_START = date(2024, 9, 1)
SOURCE_WINDOW_END = date(2026, 9, 6)
SOURCE_CUTOFF = datetime(2026, 9, 6, 12, 21, 6, 431463, tzinfo=UTC)
RECONSTRUCTION_SHA256 = "bb9d6cd3b0399380da6bf36bc58a7c8f83f083fa2e32aa97b9b0fe700857c240"
REQUIRED_AUDIT_STATUS = "COMPLETE_NO_ADDITIONAL_PERMANENT_BASE_CHANGES"

CoverageStatus = Literal["COMPLETE", "COMPLETE_ZERO_SOURCE", "INCOMPLETE"]
MembershipStatus = Literal[
    "PRE_CHALLENGE_CONTEXT",
    "SIGNAL_ELIGIBLE",
    "CONTEXT_ONLY_NONMEMBER",
]


class ExpandedSourceError(ValueError):
    """Raised when the expanded H022 source corpus cannot be frozen safely."""


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
        raise ExpandedSourceError(
            "expanded-source payload must contain finite JSON values"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ExpandedSourceError("timestamp must include timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ExpandedSourceError(f"invalid transcript timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise ExpandedSourceError("transcript timestamp must include timezone")
    return parsed.astimezone(UTC)


def validate_membership_inputs(
    reconstruction: dict[str, Any], audit: dict[str, Any]
) -> None:
    validate_reconstruction(reconstruction)
    if reconstruction.get("reconstruction_sha256") != RECONSTRUCTION_SHA256:
        raise ExpandedSourceError("historical membership reconstruction digest changed")
    if reconstruction.get("expanded_union_member_count") != EXPECTED_MEMBER_COUNT:
        raise ExpandedSourceError("expanded historical union member count changed")
    if audit.get("audit_status") != REQUIRED_AUDIT_STATUS:
        raise ExpandedSourceError("ad-hoc membership audit is not complete")
    if audit.get("additional_permanent_base_change_count") != 0:
        raise ExpandedSourceError("unexpected additional permanent base membership change")
    if audit.get("expanded_nifty200_union_ready_for_transcript_replay") is not True:
        raise ExpandedSourceError("historical union is not ready for transcript replay")
    if audit.get("outcome_data_attached") is not False:
        raise ExpandedSourceError("membership audit unexpectedly contains outcomes")


def _union_symbols(reconstruction: dict[str, Any]) -> tuple[str, ...]:
    members = reconstruction.get("expanded_union_members")
    if not isinstance(members, list) or len(members) != EXPECTED_MEMBER_COUNT:
        raise ExpandedSourceError("expanded union member list changed")
    symbols: list[str] = []
    seen: set[str] = set()
    for row in members:
        if not isinstance(row, dict):
            raise ExpandedSourceError("expanded union member must be an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol or symbol in seen:
            raise ExpandedSourceError(f"invalid/duplicate expanded union symbol: {symbol}")
        seen.add(symbol)
        symbols.append(symbol)
    return tuple(sorted(symbols))


def _membership_intervals(
    reconstruction: dict[str, Any],
) -> tuple[tuple[date, date, frozenset[str]], ...]:
    intervals = reconstruction.get("membership_intervals")
    if not isinstance(intervals, list) or len(intervals) != 2:
        raise ExpandedSourceError("expanded historical reconstruction must have two intervals")
    parsed: list[tuple[date, date, frozenset[str]]] = []
    for row in intervals:
        if not isinstance(row, dict):
            raise ExpandedSourceError("membership interval must be an object")
        start = date.fromisoformat(str(row.get("start")))
        end = date.fromisoformat(str(row.get("end")))
        symbols_raw = row.get("symbols")
        if not isinstance(symbols_raw, list):
            raise ExpandedSourceError("membership interval symbols must be a list")
        symbols = frozenset(str(value).strip().upper() for value in symbols_raw)
        if len(symbols) != row.get("member_count") or len(symbols) != 200:
            raise ExpandedSourceError("membership interval must contain exactly 200 symbols")
        if start > end:
            raise ExpandedSourceError("membership interval start exceeds end")
        parsed.append((start, end, symbols))
    parsed.sort(key=lambda item: item[0])
    if parsed[0][1] >= parsed[1][0]:
        raise ExpandedSourceError("membership intervals overlap")
    if parsed[0][0] != CHALLENGE_START or parsed[-1][1] != CHALLENGE_END:
        raise ExpandedSourceError("membership intervals do not exactly span challenge window")
    return tuple(parsed)


def membership_status_for_source(
    *,
    symbol: str,
    exchange_published_at_utc: str,
    reconstruction: dict[str, Any],
) -> MembershipStatus:
    published = _parse_timestamp(exchange_published_at_utc)
    local_day = published.astimezone(IST).date()
    wanted = symbol.strip().upper()
    if local_day < CHALLENGE_START:
        return "PRE_CHALLENGE_CONTEXT"
    if local_day > CHALLENGE_END:
        raise ExpandedSourceError("source publication exceeds challenge cutoff")
    matches = [
        symbols
        for start, end, symbols in _membership_intervals(reconstruction)
        if start <= local_day <= end
    ]
    if len(matches) != 1:
        raise ExpandedSourceError(
            f"publication date {local_day} maps to {len(matches)} historical membership intervals"
        )
    return "SIGNAL_ELIGIBLE" if wanted in matches[0] else "CONTEXT_ONLY_NONMEMBER"


@dataclass(frozen=True)
class ExpandedTranscriptSource:
    schema_version: int
    source_id: str
    symbol: str
    seq_id: str
    exchange_published_at_utc: str
    attachment_url: str
    announcement_description: str
    attachment_text: str
    discovery_row_sha256: str
    membership_status: MembershipStatus
    signal_eligible: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExpandedCoverageRecord:
    schema_version: int
    coverage_id: str
    rule_id: str
    symbol: str
    captured_at_utc: str
    coverage_status: CoverageStatus
    incomplete_reason: str | None
    discovery_sha256: str | None
    source_count: int
    signal_eligible_source_count: int
    context_only_source_count: int
    sources: tuple[ExpandedTranscriptSource, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sources"] = [source.to_dict() for source in self.sources]
        return payload


def _expand_source(
    source: TranscriptSource,
    reconstruction: dict[str, Any],
) -> ExpandedTranscriptSource:
    status = membership_status_for_source(
        symbol=source.symbol,
        exchange_published_at_utc=source.exchange_published_at_utc,
        reconstruction=reconstruction,
    )
    return ExpandedTranscriptSource(
        schema_version=1,
        source_id=source.source_id,
        symbol=source.symbol,
        seq_id=source.seq_id,
        exchange_published_at_utc=source.exchange_published_at_utc,
        attachment_url=source.attachment_url,
        announcement_description=source.announcement_description,
        attachment_text=source.attachment_text,
        discovery_row_sha256=source.discovery_row_sha256,
        membership_status=status,
        signal_eligible=status == "SIGNAL_ELIGIBLE",
    )


def _coverage_id(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("coverage_id", None)
    return _canonical_hash(unsigned)


def build_coverage_record(
    payload: Any,
    raw_discovery_bytes: bytes,
    *,
    symbol: str,
    captured_at: datetime,
    reconstruction: dict[str, Any],
) -> ExpandedCoverageRecord:
    if captured_at.tzinfo is None:
        raise ExpandedSourceError("coverage captured_at must include timezone")
    if not raw_discovery_bytes:
        raise ExpandedSourceError("exact discovery bytes are required")
    selected = select_transcript_sources(
        payload,
        symbol=symbol,
        window_start=SOURCE_WINDOW_START,
        window_end=SOURCE_WINDOW_END,
        cutoff_utc=SOURCE_CUTOFF,
    )
    sources = tuple(_expand_source(source, reconstruction) for source in selected)
    provisional = {
        "schema_version": 1,
        "coverage_id": "",
        "rule_id": RULE_ID,
        "symbol": symbol.strip().upper(),
        "captured_at_utc": _iso_utc(captured_at),
        "coverage_status": "COMPLETE" if sources else "COMPLETE_ZERO_SOURCE",
        "incomplete_reason": None,
        "discovery_sha256": hashlib.sha256(raw_discovery_bytes).hexdigest(),
        "source_count": len(sources),
        "signal_eligible_source_count": sum(source.signal_eligible for source in sources),
        "context_only_source_count": sum(not source.signal_eligible for source in sources),
        "sources": sources,
    }
    serializable = {
        **provisional,
        "sources": [source.to_dict() for source in sources],
    }
    provisional["coverage_id"] = _coverage_id(serializable)
    return ExpandedCoverageRecord(**provisional)


def incomplete_coverage_record(
    *, symbol: str, captured_at: datetime, reason: str
) -> ExpandedCoverageRecord:
    if captured_at.tzinfo is None:
        raise ExpandedSourceError("coverage captured_at must include timezone")
    if not reason.strip():
        raise ExpandedSourceError("incomplete coverage requires a reason")
    provisional = {
        "schema_version": 1,
        "coverage_id": "",
        "rule_id": RULE_ID,
        "symbol": symbol.strip().upper(),
        "captured_at_utc": _iso_utc(captured_at),
        "coverage_status": "INCOMPLETE",
        "incomplete_reason": reason,
        "discovery_sha256": None,
        "source_count": 0,
        "signal_eligible_source_count": 0,
        "context_only_source_count": 0,
        "sources": (),
    }
    serializable = {**provisional, "sources": []}
    provisional["coverage_id"] = _coverage_id(serializable)
    return ExpandedCoverageRecord(**provisional)


def build_coverage_bundle(
    records: list[ExpandedCoverageRecord],
    *,
    reconstruction: dict[str, Any],
    audit: dict[str, Any],
    generated_at: datetime,
    source_rule_sha256: str,
) -> dict[str, Any]:
    if generated_at.tzinfo is None:
        raise ExpandedSourceError("bundle generated_at must include timezone")
    validate_membership_inputs(reconstruction, audit)
    expected = _union_symbols(reconstruction)
    by_symbol = {record.symbol: record for record in records}
    if len(by_symbol) != len(records):
        raise ExpandedSourceError("expanded source bundle has duplicate coverage records")
    if set(by_symbol) != set(expected):
        missing = sorted(set(expected) - set(by_symbol))
        extra = sorted(set(by_symbol) - set(expected))
        raise ExpandedSourceError(
            f"expanded source bundle coverage mismatch: missing={missing}, extra={extra}"
        )
    ordered = [by_symbol[symbol] for symbol in expected]
    incomplete = sum(record.coverage_status == "INCOMPLETE" for record in ordered)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "rule_id": RULE_ID,
        "rule_sha256": source_rule_sha256,
        "hypothesis_id": HYPOTHESIS_ID,
        "membership_reconstruction_sha256": reconstruction["reconstruction_sha256"],
        "membership_audit_status": audit["audit_status"],
        "generated_at_utc": _iso_utc(generated_at),
        "member_count": len(expected),
        "complete_count": sum(record.coverage_status == "COMPLETE" for record in ordered),
        "complete_zero_source_count": sum(
            record.coverage_status == "COMPLETE_ZERO_SOURCE" for record in ordered
        ),
        "incomplete_count": incomplete,
        "transcript_source_count": sum(record.source_count for record in ordered),
        "signal_eligible_source_count": sum(
            record.signal_eligible_source_count for record in ordered
        ),
        "context_only_source_count": sum(record.context_only_source_count for record in ordered),
        "freeze_ready": incomplete == 0,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
        "records": [record.to_dict() for record in ordered],
    }
    payload["bundle_sha256"] = _canonical_hash(payload)
    return payload


def validate_coverage_bundle(
    bundle: dict[str, Any],
    *,
    reconstruction: dict[str, Any],
    audit: dict[str, Any],
) -> None:
    stored = bundle.get("bundle_sha256")
    unsigned = dict(bundle)
    unsigned.pop("bundle_sha256", None)
    if stored != _canonical_hash(unsigned):
        raise ExpandedSourceError("expanded source bundle hash mismatch")
    validate_membership_inputs(reconstruction, audit)
    if bundle.get("rule_id") != RULE_ID:
        raise ExpandedSourceError("expanded source bundle rule changed")
    if bundle.get("member_count") != EXPECTED_MEMBER_COUNT:
        raise ExpandedSourceError("expanded source bundle member count changed")
    if bundle.get("membership_reconstruction_sha256") != RECONSTRUCTION_SHA256:
        raise ExpandedSourceError("expanded source bundle reconstruction changed")
    if bundle.get("outcome_data_attached") is not False:
        raise ExpandedSourceError("expanded source bundle contains outcomes")
    if bundle.get("live_capital_allowed") is not False:
        raise ExpandedSourceError("expanded source bundle cannot authorize live capital")
    records = bundle.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_MEMBER_COUNT:
        raise ExpandedSourceError("expanded source bundle record coverage changed")
