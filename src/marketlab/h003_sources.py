from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import yaml

from marketlab.events import sha256_bytes
from marketlab.preparation import _parse_exchange_timestamp
from marketlab.universe import UniverseSnapshot

SOURCE_RULE_ID = "H003-C001"
SOURCE_RULE_SHA256 = "3e4de432a4fb10c9b7cb09a711bf3078e1e92d4970ecbc2b6d69afc1ff0a870a"
COHORT_ID = "FY27-Q2-2026-09-06"
DECISION_DATE = date(2026, 9, 6)
WINDOW_START = date(2024, 9, 1)
WINDOW_END = DECISION_DATE
ALLOWED_ATTACHMENT_HOSTS = frozenset(
    {"nsearchives.nseindia.com", "archives.nseindia.com"}
)
INCLUDE_ALL = ("transcript",)
INCLUDE_ANY = (
    "earnings call",
    "financial results",
    "quarter ended",
    "quarter and year ended",
    "analyst meet",
    "conference call",
)
EXCLUDE_ANY = (
    "annual general meeting",
    "agm transcript",
    "investor day",
    "ai day",
)

CoverageStatus = Literal["COMPLETE", "COMPLETE_ZERO_SOURCE", "INCOMPLETE"]


class H003SourceError(ValueError):
    """Raised when H003 transcript coverage cannot be established without guessing."""


@dataclass(frozen=True)
class TranscriptSource:
    schema_version: int
    source_id: str
    symbol: str
    seq_id: str
    exchange_published_at_utc: str
    attachment_url: str
    announcement_description: str
    attachment_text: str
    discovery_row_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceCoverageRecord:
    schema_version: int
    coverage_id: str
    rule_id: str
    rule_sha256: str
    cohort_id: str
    symbol: str
    decision_date: str
    window_start: str
    window_end: str
    captured_at_utc: str
    coverage_status: CoverageStatus
    incomplete_reason: str | None
    discovery_sha256: str | None
    source_count: int
    sources: tuple[TranscriptSource, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sources"] = [item.to_dict() for item in self.sources]
        return payload


@dataclass(frozen=True)
class SourceCoverageBundle:
    schema_version: int
    bundle_sha256: str
    rule_id: str
    rule_sha256: str
    cohort_id: str
    universe_snapshot_sha256: str
    generated_at_utc: str
    member_count: int
    complete_count: int
    complete_zero_source_count: int
    incomplete_count: int
    transcript_source_count: int
    records: tuple[SourceCoverageRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["records"] = [item.to_dict() for item in self.records]
        return payload


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
        raise H003SourceError("H003 source payload must contain finite JSON values") from exc
    return hashlib.sha256(raw).hexdigest()


def validate_source_rule_document(document: dict[str, Any]) -> str:
    if not isinstance(document, dict):
        raise H003SourceError("H003 source rule root must be a mapping")
    declared = document.get("sha256")
    if not isinstance(declared, str) or len(declared) != 64:
        raise H003SourceError("H003 source rule must declare SHA-256")
    unsigned = dict(document)
    unsigned.pop("sha256", None)
    actual = _canonical_hash(unsigned)
    if actual != declared or declared != SOURCE_RULE_SHA256:
        raise H003SourceError(
            f"H003 source rule hash mismatch: declared={declared}, recomputed={actual}"
        )
    if document.get("id") != SOURCE_RULE_ID:
        raise H003SourceError("unexpected H003 source rule id")
    if document.get("status") != "FROZEN":
        raise H003SourceError("H003 source rule must remain FROZEN")
    if document.get("live_capital") is not False:
        raise H003SourceError("H003 source rule must keep live_capital: false")
    if document.get("cohort_id") != COHORT_ID:
        raise H003SourceError("H003 source rule cohort changed")
    if document.get("decision_date") != DECISION_DATE.isoformat():
        raise H003SourceError("H003 source rule decision date changed")
    return actual


def load_and_validate_source_rule(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    validate_source_rule_document(document)
    return document


def _announcement_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("records") or []
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    raise H003SourceError("NSE corporate-announcement payload is not a row list")


def _official_timestamp(row: dict[str, Any]) -> datetime:
    last_error: Exception | None = None
    for key in ("exchdisstime", "an_dt", "sort_date", "dt"):
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return _parse_exchange_timestamp(value)
        except (TypeError, ValueError) as exc:
            last_error = exc
    raise H003SourceError(
        f"announcement row has no parseable official timestamp: {last_error}"
    )


def _candidate_text(row: dict[str, Any]) -> str:
    return " ".join(
        str(value or "").strip()
        for value in (row.get("desc"), row.get("attchmntText"), row.get("attchmntFile"))
    ).casefold()


def _matches_transcript_policy(row: dict[str, Any]) -> bool:
    text = _candidate_text(row)
    if not all(token in text for token in INCLUDE_ALL):
        return False
    if not any(token in text for token in INCLUDE_ANY):
        return False
    if any(token in text for token in EXCLUDE_ANY):
        return False
    return True


def _validated_attachment_url(row: dict[str, Any]) -> str:
    value = str(row.get("attchmntFile") or "").strip()
    if not value:
        raise H003SourceError("matching transcript announcement is missing attachment URL")
    parsed = urlparse(value)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in ALLOWED_ATTACHMENT_HOSTS:
        raise H003SourceError(f"matching transcript has unsupported attachment URL: {value}")
    return value


def select_transcript_sources(
    payload: Any,
    *,
    symbol: str,
    window_start: date = WINDOW_START,
    window_end: date = WINDOW_END,
) -> tuple[TranscriptSource, ...]:
    if window_start > window_end:
        raise H003SourceError("H003 source window start exceeds end")
    wanted = symbol.strip().upper()
    if not wanted:
        raise H003SourceError("H003 source symbol is required")

    selected: list[TranscriptSource] = []
    attachment_rows: dict[str, str] = {}
    for row in _announcement_rows(payload):
        if str(row.get("symbol") or "").strip().upper() != wanted:
            continue
        if not _matches_transcript_policy(row):
            continue
        published = _official_timestamp(row)
        published_date = published.astimezone(UTC).date()
        if not (window_start <= published_date <= window_end):
            continue
        attachment_url = _validated_attachment_url(row)
        row_hash = _canonical_hash(row)
        previous = attachment_rows.get(attachment_url)
        if previous is not None:
            if previous == row_hash:
                continue
            raise H003SourceError(
                f"ambiguous duplicate transcript attachment for {wanted}: {attachment_url}"
            )
        attachment_rows[attachment_url] = row_hash
        seq_id = str(row.get("seq_id") or "").strip()
        if not seq_id:
            raise H003SourceError("matching transcript announcement is missing seq_id")
        identity = {
            "rule_id": SOURCE_RULE_ID,
            "symbol": wanted,
            "seq_id": seq_id,
            "exchange_published_at_utc": published.isoformat().replace("+00:00", "Z"),
            "attachment_url": attachment_url,
            "discovery_row_sha256": row_hash,
        }
        selected.append(
            TranscriptSource(
                schema_version=1,
                source_id=_canonical_hash(identity),
                symbol=wanted,
                seq_id=seq_id,
                exchange_published_at_utc=identity["exchange_published_at_utc"],
                attachment_url=attachment_url,
                announcement_description=str(row.get("desc") or "").strip(),
                attachment_text=str(row.get("attchmntText") or "").strip(),
                discovery_row_sha256=row_hash,
            )
        )
    selected.sort(key=lambda item: (item.exchange_published_at_utc, item.seq_id, item.attachment_url))
    return tuple(selected)


def _coverage_digest(record: SourceCoverageRecord) -> str:
    payload = record.to_dict()
    payload.pop("coverage_id", None)
    return _canonical_hash(payload)


def build_coverage_record(
    payload: Any,
    raw_discovery_bytes: bytes,
    *,
    symbol: str,
    captured_at: datetime,
) -> SourceCoverageRecord:
    if captured_at.tzinfo is None:
        raise H003SourceError("H003 source captured_at must include timezone")
    if not raw_discovery_bytes:
        raise H003SourceError("H003 exact discovery bytes are required")
    sources = select_transcript_sources(payload, symbol=symbol)
    status: CoverageStatus = "COMPLETE" if sources else "COMPLETE_ZERO_SOURCE"
    provisional = SourceCoverageRecord(
        schema_version=1,
        coverage_id="",
        rule_id=SOURCE_RULE_ID,
        rule_sha256=SOURCE_RULE_SHA256,
        cohort_id=COHORT_ID,
        symbol=symbol.upper(),
        decision_date=DECISION_DATE.isoformat(),
        window_start=WINDOW_START.isoformat(),
        window_end=WINDOW_END.isoformat(),
        captured_at_utc=captured_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        coverage_status=status,
        incomplete_reason=None,
        discovery_sha256=sha256_bytes(raw_discovery_bytes),
        source_count=len(sources),
        sources=sources,
    )
    return replace(provisional, coverage_id=_coverage_digest(provisional))


def incomplete_coverage_record(
    *,
    symbol: str,
    captured_at: datetime,
    reason: str,
) -> SourceCoverageRecord:
    if captured_at.tzinfo is None:
        raise H003SourceError("H003 source captured_at must include timezone")
    if not reason.strip():
        raise H003SourceError("incomplete H003 source coverage requires a reason")
    provisional = SourceCoverageRecord(
        schema_version=1,
        coverage_id="",
        rule_id=SOURCE_RULE_ID,
        rule_sha256=SOURCE_RULE_SHA256,
        cohort_id=COHORT_ID,
        symbol=symbol.upper(),
        decision_date=DECISION_DATE.isoformat(),
        window_start=WINDOW_START.isoformat(),
        window_end=WINDOW_END.isoformat(),
        captured_at_utc=captured_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        coverage_status="INCOMPLETE",
        incomplete_reason=reason,
        discovery_sha256=None,
        source_count=0,
        sources=(),
    )
    return replace(provisional, coverage_id=_coverage_digest(provisional))


def build_coverage_bundle(
    records: list[SourceCoverageRecord],
    *,
    universe: UniverseSnapshot,
    generated_at: datetime,
) -> SourceCoverageBundle:
    if generated_at.tzinfo is None:
        raise H003SourceError("H003 source bundle generated_at must include timezone")
    if universe.cohort_id != COHORT_ID:
        raise H003SourceError("H003 source bundle requires the frozen FY27-Q2 cohort")
    expected = [member.symbol.upper() for member in universe.members]
    by_symbol = {record.symbol.upper(): record for record in records}
    if len(by_symbol) != len(records):
        raise H003SourceError("H003 source bundle has duplicate company records")
    if set(by_symbol) != set(expected):
        raise H003SourceError("H003 source bundle does not exactly cover frozen U001")
    ordered = tuple(by_symbol[symbol] for symbol in expected)
    complete = sum(record.coverage_status == "COMPLETE" for record in ordered)
    zero = sum(record.coverage_status == "COMPLETE_ZERO_SOURCE" for record in ordered)
    incomplete = sum(record.coverage_status == "INCOMPLETE" for record in ordered)
    source_count = sum(record.source_count for record in ordered)
    provisional = SourceCoverageBundle(
        schema_version=1,
        bundle_sha256="",
        rule_id=SOURCE_RULE_ID,
        rule_sha256=SOURCE_RULE_SHA256,
        cohort_id=COHORT_ID,
        universe_snapshot_sha256=universe.sha256,
        generated_at_utc=generated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        member_count=len(expected),
        complete_count=complete,
        complete_zero_source_count=zero,
        incomplete_count=incomplete,
        transcript_source_count=source_count,
        records=ordered,
    )
    payload = provisional.to_dict()
    payload.pop("bundle_sha256", None)
    return replace(provisional, bundle_sha256=_canonical_hash(payload))


def write_coverage_bundle(path: str | Path, bundle: SourceCoverageBundle) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
