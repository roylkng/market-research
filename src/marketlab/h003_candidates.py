from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import pypdf
import yaml
from pypdf import PdfReader
from pypdf.errors import PdfReadError

EXTRACTION_RULE_ID = "H003-E001"
EXTRACTION_RULE_SHA256 = "363880e2a7798f69c5c70f14716ec1e8830e7234c2f7996895f95c6f886db335"
SOURCE_RULE_ID = "H003-C001"
SOURCE_RULE_SHA256 = "a48e9cd1e1d56b69429696168fb1a2097b288d3179c7830ac79cbd8582835f0e"
SOURCE_BUNDLE_SHA256 = "583af88b3c070e15fe94a7782962c9e1fb1ce167e1412a08fd5c7b2f2dcaf7ee"
COHORT_ID = "FY27-Q2-2026-09-06"
DECISION_TIMESTAMP_UTC = "2026-09-06T12:21:06.431463Z"
PARSER_VERSION = "h003_pdf_text_v1"
PARSER_LIBRARY_VERSION = "6.17.0"
CANDIDATE_VERSION = "h003_future_commitment_candidate_v1"
EXPECTED_MEMBER_COUNT = 100
EXPECTED_SOURCE_COUNT = 794
ALLOWED_ATTACHMENT_HOSTS = frozenset(
    {"nsearchives.nseindia.com", "archives.nseindia.com"}
)

FUTURE_MARKERS = (
    "we will",
    "we expect",
    "we target",
    "our target",
    "we aim",
    "we plan",
    "we intend",
    "we anticipate",
    "we should",
    "we are targeting",
    "we are aiming",
    "we are planning",
    "guidance",
    "targeting",
    "aiming for",
    "plan to",
    "expect to",
    "expected to",
)
DEADLINE_MARKERS = (
    "by fy",
    "in fy",
    "during fy",
    "this fiscal",
    "next fiscal",
    "this year",
    "next year",
    "this quarter",
    "next quarter",
    "by the end",
    "by end",
    "within",
    "over the next",
    "in the next",
    "by march",
    "by june",
    "by september",
    "by december",
    "q1",
    "q2",
    "q3",
    "q4",
    "h1",
    "h2",
)
EXCLUDE_MARKERS = (
    "safe harbor",
    "safe harbour",
    "forward-looking statements",
    "forward looking statements",
    "may differ materially",
    "no obligation to update",
    "operator:",
    "moderator:",
)
QUANTITATIVE_REGEX = (
    r"(?i)(?:₹|rs\.?|inr|usd|\$)?\s*\d[\d,]*(?:\.\d+)?\s*"
    r"(?:%|percent|bps|crore|cr\b|million|billion|mn\b|bn\b|mt\b|kt\b|"
    r"mw\b|gw\b|units?|stores?|outlets?|plants?|days?|months?|years?|x\b)?"
)
QUANTITATIVE_PATTERN = re.compile(QUANTITATIVE_REGEX)

SourceStatus = Literal["TEXT_READY", "NO_TEXT", "FETCH_ERROR", "PARSE_ERROR"]
ReviewDisposition = Literal["UNREVIEWED", "ACCEPTED", "REJECTED"]


class H003CandidateError(ValueError):
    """Raised when H003 claim-candidate evidence cannot be reconstructed safely."""


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
        raise H003CandidateError(
            "H003 candidate payload must contain finite JSON values"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _parse_timestamp(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise H003CandidateError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H003CandidateError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _normalise_line(value: str) -> str:
    return " ".join(value.replace("\x00", " ").split())


def validate_extraction_rule_document(document: dict[str, Any]) -> str:
    if not isinstance(document, dict):
        raise H003CandidateError("H003 extraction rule root must be a mapping")
    declared = document.get("sha256")
    if not isinstance(declared, str) or len(declared) != 64:
        raise H003CandidateError("H003 extraction rule must declare SHA-256")
    unsigned = dict(document)
    unsigned.pop("sha256", None)
    actual = _canonical_hash(unsigned)
    if actual != declared or declared != EXTRACTION_RULE_SHA256:
        raise H003CandidateError(
            f"H003 extraction rule hash mismatch: declared={declared}, recomputed={actual}"
        )
    if document.get("id") != EXTRACTION_RULE_ID:
        raise H003CandidateError("unexpected H003 extraction rule id")
    if document.get("status") != "FROZEN":
        raise H003CandidateError("H003 extraction rule must remain FROZEN")
    if document.get("source_rule_id") != SOURCE_RULE_ID:
        raise H003CandidateError("H003 extraction rule source rule changed")
    if document.get("source_rule_sha256") != SOURCE_RULE_SHA256:
        raise H003CandidateError("H003 extraction rule source-rule hash changed")
    if document.get("source_bundle_sha256") != SOURCE_BUNDLE_SHA256:
        raise H003CandidateError("H003 extraction rule source bundle changed")
    if document.get("decision_timestamp_utc") != DECISION_TIMESTAMP_UTC:
        raise H003CandidateError("H003 extraction cutoff changed")
    if document.get("live_capital") is not False:
        raise H003CandidateError("H003 extraction must keep live_capital: false")
    parser = document.get("parser")
    if not isinstance(parser, dict):
        raise H003CandidateError("H003 extraction parser contract is required")
    if (
        parser.get("library") != "pypdf"
        or parser.get("library_version") != PARSER_LIBRARY_VERSION
        or parser.get("parser_version") != PARSER_VERSION
        or parser.get("ocr_allowed") is not False
        or parser.get("strict") is not False
    ):
        raise H003CandidateError("H003 extraction parser contract changed")
    candidate = document.get("candidate_rule")
    if not isinstance(candidate, dict):
        raise H003CandidateError("H003 candidate rule is required")
    expected_candidate = {
        "version": CANDIDATE_VERSION,
        "context_radius_lines": 1,
        "min_excerpt_chars": 20,
        "max_excerpt_chars": 800,
        "require_future_marker": True,
        "require_quantitative_or_deadline_marker": True,
        "future_markers": list(FUTURE_MARKERS),
        "deadline_markers": list(DEADLINE_MARKERS),
        "exclude_markers": list(EXCLUDE_MARKERS),
        "quantitative_regex": QUANTITATIVE_REGEX,
    }
    if candidate != expected_candidate:
        raise H003CandidateError("H003 candidate extraction semantics changed")
    completion = document.get("completion")
    if completion != {
        "expected_member_count": EXPECTED_MEMBER_COUNT,
        "expected_source_count": EXPECTED_SOURCE_COUNT,
        "freeze_requires_all_sources_text_ready": True,
        "no_text_blocks_freeze": True,
        "fetch_or_parse_error_blocks_freeze": True,
    }:
        raise H003CandidateError("H003 candidate completion gate changed")
    return actual


def load_and_validate_extraction_rule(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    validate_extraction_rule_document(document)
    return document


@dataclass(frozen=True)
class FrozenTranscriptSource:
    source_id: str
    symbol: str
    seq_id: str
    exchange_published_at_utc: str
    attachment_url: str
    discovery_row_sha256: str

    def identity_payload(self) -> dict[str, str]:
        return {
            "rule_id": SOURCE_RULE_ID,
            "symbol": self.symbol,
            "seq_id": self.seq_id,
            "exchange_published_at_utc": self.exchange_published_at_utc,
            "attachment_url": self.attachment_url,
            "discovery_row_sha256": self.discovery_row_sha256,
        }


def load_frozen_transcript_sources(path: str | Path) -> tuple[FrozenTranscriptSource, ...]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise H003CandidateError(f"could not read H003 source bundle {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise H003CandidateError("H003 source bundle root must be an object")
    declared = document.get("bundle_sha256")
    unsigned = dict(document)
    unsigned.pop("bundle_sha256", None)
    actual = _canonical_hash(unsigned)
    if declared != SOURCE_BUNDLE_SHA256 or actual != declared:
        raise H003CandidateError(
            f"H003 source bundle hash mismatch: declared={declared}, recomputed={actual}"
        )
    if (
        document.get("rule_id") != SOURCE_RULE_ID
        or document.get("rule_sha256") != SOURCE_RULE_SHA256
        or document.get("cohort_id") != COHORT_ID
    ):
        raise H003CandidateError("H003 source bundle identity changed")
    if (
        document.get("member_count") != EXPECTED_MEMBER_COUNT
        or document.get("transcript_source_count") != EXPECTED_SOURCE_COUNT
        or document.get("incomplete_count") != 0
    ):
        raise H003CandidateError("H003 source bundle frozen coverage changed")
    records = document.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_MEMBER_COUNT:
        raise H003CandidateError("H003 source bundle must contain 100 company records")

    cutoff = _parse_timestamp(DECISION_TIMESTAMP_UTC, field="decision_timestamp_utc")
    sources: list[FrozenTranscriptSource] = []
    seen_sources: set[str] = set()
    seen_symbols: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise H003CandidateError("H003 source coverage record must be an object")
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol or symbol in seen_symbols:
            raise H003CandidateError(f"invalid/duplicate H003 coverage symbol: {symbol}")
        seen_symbols.add(symbol)
        status = record.get("coverage_status")
        source_rows = record.get("sources")
        if not isinstance(source_rows, list):
            raise H003CandidateError(f"{symbol}: sources must be a list")
        if status == "COMPLETE_ZERO_SOURCE":
            if source_rows or record.get("source_count") != 0:
                raise H003CandidateError(f"{symbol}: zero-source record contains sources")
        elif status == "COMPLETE":
            if record.get("source_count") != len(source_rows) or not source_rows:
                raise H003CandidateError(f"{symbol}: complete source count mismatch")
        else:
            raise H003CandidateError(f"{symbol}: frozen source coverage is not complete")

        for row in source_rows:
            if not isinstance(row, dict):
                raise H003CandidateError(f"{symbol}: source row must be an object")
            source = FrozenTranscriptSource(
                source_id=str(row.get("source_id") or ""),
                symbol=symbol,
                seq_id=str(row.get("seq_id") or ""),
                exchange_published_at_utc=str(row.get("exchange_published_at_utc") or ""),
                attachment_url=str(row.get("attachment_url") or ""),
                discovery_row_sha256=str(row.get("discovery_row_sha256") or ""),
            )
            if not source.source_id or source.source_id in seen_sources:
                raise H003CandidateError(f"duplicate/missing H003 source id: {source.source_id}")
            seen_sources.add(source.source_id)
            if _canonical_hash(source.identity_payload()) != source.source_id:
                raise H003CandidateError(f"{source.source_id}: source identity mismatch")
            if _parse_timestamp(
                source.exchange_published_at_utc,
                field=f"{source.source_id}.exchange_published_at_utc",
            ) > cutoff:
                raise H003CandidateError(f"{source.source_id}: source exceeds frozen cutoff")
            parsed = urlparse(source.attachment_url)
            if (
                parsed.scheme != "https"
                or (parsed.hostname or "").lower() not in ALLOWED_ATTACHMENT_HOSTS
            ):
                raise H003CandidateError(
                    f"{source.source_id}: unsupported attachment URL {source.attachment_url}"
                )
            if (
                len(source.discovery_row_sha256) != 64
                or any(char not in "0123456789abcdef" for char in source.discovery_row_sha256)
            ):
                raise H003CandidateError(
                    f"{source.source_id}: invalid discovery row SHA-256"
                )
            sources.append(source)
    if len(sources) != EXPECTED_SOURCE_COUNT:
        raise H003CandidateError(
            f"H003 source bundle expected {EXPECTED_SOURCE_COUNT} sources, found {len(sources)}"
        )
    return tuple(sources)


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    lines: tuple[str, ...]

    def canonical_text(self) -> str:
        return "\n".join(self.lines)


@dataclass(frozen=True)
class ClaimCandidate:
    schema_version: int
    candidate_id: str
    rule_id: str
    rule_sha256: str
    candidate_version: str
    source_id: str
    symbol: str
    exchange_published_at_utc: str
    attachment_url: str
    raw_sha256: str
    parser_version: str
    page_number: int
    line_start: int
    line_end: int
    excerpt: str
    future_markers: tuple[str, ...]
    deadline_markers: tuple[str, ...]
    quantitative_tokens: tuple[str, ...]
    disposition: ReviewDisposition
    disposition_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["future_markers"] = list(self.future_markers)
        payload["deadline_markers"] = list(self.deadline_markers)
        payload["quantitative_tokens"] = list(self.quantitative_tokens)
        return payload


@dataclass(frozen=True)
class SourceExtractionRecord:
    schema_version: int
    record_id: str
    rule_id: str
    rule_sha256: str
    source_id: str
    symbol: str
    exchange_published_at_utc: str
    attachment_url: str
    status: SourceStatus
    failure_reason: str | None
    raw_sha256: str | None
    raw_byte_count: int | None
    parser_version: str
    parser_library_version: str
    page_count: int | None
    text_sha256: str | None
    text_char_count: int | None
    candidate_count: int
    candidates: tuple[ClaimCandidate, ...]
    raw_path: str | None
    text_path: str | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidates"] = [item.to_dict() for item in self.candidates]
        return payload


@dataclass(frozen=True)
class CandidateBuildReport:
    schema_version: int
    report_sha256: str
    rule_id: str
    rule_sha256: str
    source_bundle_sha256: str
    cohort_id: str
    generated_at_utc: str
    expected_member_count: int
    expected_source_count: int
    processed_source_count: int
    processed_company_count: int
    source_status_counts: dict[str, int]
    candidate_count: int
    companies_with_candidates: int
    complete: bool
    freeze_blockers: tuple[str, ...]
    records: tuple[SourceExtractionRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["freeze_blockers"] = list(self.freeze_blockers)
        payload["records"] = [item.to_dict() for item in self.records]
        return payload


class H003CandidateStore:
    """Content-addressed raw transcript and deterministic extracted-text evidence."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @staticmethod
    def _write_content_addressed(path: Path, raw: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != raw:
                raise H003CandidateError(f"content-addressed collision at {path}")
            return
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise H003CandidateError(f"content-addressed collision at {path}")
            return
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())

    def retain_raw_pdf(self, raw: bytes) -> str:
        digest = _sha256(raw)
        relative = Path("raw") / "sha256" / f"{digest}.pdf"
        self._write_content_addressed(self.root / relative, raw)
        return relative.as_posix()

    def retain_text(self, text: str) -> tuple[str, str]:
        raw = text.encode("utf-8")
        digest = _sha256(raw)
        relative = Path("text") / "sha256" / f"{digest}.txt"
        self._write_content_addressed(self.root / relative, raw)
        return digest, relative.as_posix()


def extract_pdf_pages(raw_pdf: bytes) -> tuple[tuple[ExtractedPage, ...], str]:
    if not raw_pdf:
        raise H003CandidateError("transcript PDF bytes are empty")
    if pypdf.__version__ != PARSER_LIBRARY_VERSION:
        raise H003CandidateError(
            f"pypdf version changed: expected={PARSER_LIBRARY_VERSION}, "
            f"observed={pypdf.__version__}"
        )
    try:
        reader = PdfReader(io.BytesIO(raw_pdf), strict=False)
    except (PdfReadError, OSError, ValueError) as exc:
        raise H003CandidateError(f"could not parse transcript PDF: {exc}") from exc
    if reader.is_encrypted:
        raise H003CandidateError("encrypted transcript PDF is not allowed by H003-E001")
    pages: list[ExtractedPage] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except (PdfReadError, KeyError, TypeError, ValueError) as exc:
            raise H003CandidateError(
                f"could not extract transcript page {index}: {exc}"
            ) from exc
        lines = tuple(
            normalized
            for raw_line in text.splitlines()
            if (normalized := _normalise_line(raw_line))
        )
        pages.append(ExtractedPage(page_number=index, lines=lines))
    canonical = "\f".join(page.canonical_text() for page in pages)
    return tuple(pages), canonical


def _candidate_digest_payload(
    *,
    source: FrozenTranscriptSource,
    raw_sha256: str,
    page_number: int,
    line_start: int,
    line_end: int,
    excerpt: str,
) -> dict[str, Any]:
    return {
        "rule_id": EXTRACTION_RULE_ID,
        "rule_sha256": EXTRACTION_RULE_SHA256,
        "candidate_version": CANDIDATE_VERSION,
        "source_id": source.source_id,
        "symbol": source.symbol,
        "raw_sha256": raw_sha256,
        "page_number": page_number,
        "line_start": line_start,
        "line_end": line_end,
        "excerpt": excerpt,
    }


def generate_candidates(
    source: FrozenTranscriptSource,
    *,
    raw_sha256: str,
    pages: tuple[ExtractedPage, ...],
) -> tuple[ClaimCandidate, ...]:
    results: list[ClaimCandidate] = []
    seen: set[tuple[int, str]] = set()
    for page in pages:
        lines = list(page.lines)
        for index, _line in enumerate(lines):
            start = max(0, index - 1)
            end = min(len(lines), index + 2)
            excerpt = " ".join(lines[start:end])
            if len(excerpt) < 20:
                continue
            if len(excerpt) > 800:
                excerpt = excerpt[:800].rstrip()
            lowered = excerpt.casefold()
            if any(marker in lowered for marker in EXCLUDE_MARKERS):
                continue
            future_hits = tuple(marker for marker in FUTURE_MARKERS if marker in lowered)
            if not future_hits:
                continue
            deadline_hits = tuple(marker for marker in DEADLINE_MARKERS if marker in lowered)
            quantitative_tokens = tuple(
                token.strip()
                for token in QUANTITATIVE_PATTERN.findall(excerpt)
                if token.strip()
            )
            if not deadline_hits and not quantitative_tokens:
                continue
            key = (page.page_number, excerpt.casefold())
            if key in seen:
                continue
            seen.add(key)
            line_start = start + 1
            line_end = end
            identity = _candidate_digest_payload(
                source=source,
                raw_sha256=raw_sha256,
                page_number=page.page_number,
                line_start=line_start,
                line_end=line_end,
                excerpt=excerpt,
            )
            results.append(
                ClaimCandidate(
                    schema_version=1,
                    candidate_id=_canonical_hash(identity),
                    rule_id=EXTRACTION_RULE_ID,
                    rule_sha256=EXTRACTION_RULE_SHA256,
                    candidate_version=CANDIDATE_VERSION,
                    source_id=source.source_id,
                    symbol=source.symbol,
                    exchange_published_at_utc=source.exchange_published_at_utc,
                    attachment_url=source.attachment_url,
                    raw_sha256=raw_sha256,
                    parser_version=PARSER_VERSION,
                    page_number=page.page_number,
                    line_start=line_start,
                    line_end=line_end,
                    excerpt=excerpt,
                    future_markers=future_hits,
                    deadline_markers=deadline_hits,
                    quantitative_tokens=quantitative_tokens,
                    disposition="UNREVIEWED",
                    disposition_reason=None,
                )
            )
    results.sort(key=lambda item: (item.page_number, item.line_start, item.candidate_id))
    return tuple(results)


def _record_digest(record: SourceExtractionRecord) -> str:
    payload = record.to_dict()
    payload.pop("record_id", None)
    return _canonical_hash(payload)


def extract_source(
    source: FrozenTranscriptSource,
    raw_pdf: bytes,
    *,
    store: H003CandidateStore,
) -> SourceExtractionRecord:
    raw_hash = _sha256(raw_pdf)
    raw_path = store.retain_raw_pdf(raw_pdf)
    try:
        pages, canonical_text = extract_pdf_pages(raw_pdf)
    except H003CandidateError as exc:
        provisional = SourceExtractionRecord(
            schema_version=1,
            record_id="",
            rule_id=EXTRACTION_RULE_ID,
            rule_sha256=EXTRACTION_RULE_SHA256,
            source_id=source.source_id,
            symbol=source.symbol,
            exchange_published_at_utc=source.exchange_published_at_utc,
            attachment_url=source.attachment_url,
            status="PARSE_ERROR",
            failure_reason=str(exc),
            raw_sha256=raw_hash,
            raw_byte_count=len(raw_pdf),
            parser_version=PARSER_VERSION,
            parser_library_version=pypdf.__version__,
            page_count=None,
            text_sha256=None,
            text_char_count=None,
            candidate_count=0,
            candidates=(),
            raw_path=raw_path,
            text_path=None,
        )
        return replace(provisional, record_id=_record_digest(provisional))

    text_hash, text_path = store.retain_text(canonical_text)
    if not canonical_text.strip():
        provisional = SourceExtractionRecord(
            schema_version=1,
            record_id="",
            rule_id=EXTRACTION_RULE_ID,
            rule_sha256=EXTRACTION_RULE_SHA256,
            source_id=source.source_id,
            symbol=source.symbol,
            exchange_published_at_utc=source.exchange_published_at_utc,
            attachment_url=source.attachment_url,
            status="NO_TEXT",
            failure_reason="pypdf extracted no non-whitespace text; OCR is forbidden in H003-E001",
            raw_sha256=raw_hash,
            raw_byte_count=len(raw_pdf),
            parser_version=PARSER_VERSION,
            parser_library_version=pypdf.__version__,
            page_count=len(pages),
            text_sha256=text_hash,
            text_char_count=0,
            candidate_count=0,
            candidates=(),
            raw_path=raw_path,
            text_path=text_path,
        )
        return replace(provisional, record_id=_record_digest(provisional))

    candidates = generate_candidates(source, raw_sha256=raw_hash, pages=pages)
    provisional = SourceExtractionRecord(
        schema_version=1,
        record_id="",
        rule_id=EXTRACTION_RULE_ID,
        rule_sha256=EXTRACTION_RULE_SHA256,
        source_id=source.source_id,
        symbol=source.symbol,
        exchange_published_at_utc=source.exchange_published_at_utc,
        attachment_url=source.attachment_url,
        status="TEXT_READY",
        failure_reason=None,
        raw_sha256=raw_hash,
        raw_byte_count=len(raw_pdf),
        parser_version=PARSER_VERSION,
        parser_library_version=pypdf.__version__,
        page_count=len(pages),
        text_sha256=text_hash,
        text_char_count=len(canonical_text),
        candidate_count=len(candidates),
        candidates=candidates,
        raw_path=raw_path,
        text_path=text_path,
    )
    return replace(provisional, record_id=_record_digest(provisional))


def failed_fetch_record(
    source: FrozenTranscriptSource,
    *,
    reason: str,
) -> SourceExtractionRecord:
    if not reason.strip():
        raise H003CandidateError("fetch failure requires a reason")
    provisional = SourceExtractionRecord(
        schema_version=1,
        record_id="",
        rule_id=EXTRACTION_RULE_ID,
        rule_sha256=EXTRACTION_RULE_SHA256,
        source_id=source.source_id,
        symbol=source.symbol,
        exchange_published_at_utc=source.exchange_published_at_utc,
        attachment_url=source.attachment_url,
        status="FETCH_ERROR",
        failure_reason=reason,
        raw_sha256=None,
        raw_byte_count=None,
        parser_version=PARSER_VERSION,
        parser_library_version=pypdf.__version__,
        page_count=None,
        text_sha256=None,
        text_char_count=None,
        candidate_count=0,
        candidates=(),
        raw_path=None,
        text_path=None,
    )
    return replace(provisional, record_id=_record_digest(provisional))


def build_report(
    records: list[SourceExtractionRecord],
    *,
    generated_at: datetime,
) -> CandidateBuildReport:
    if generated_at.tzinfo is None:
        raise H003CandidateError("candidate report generated_at must include timezone")
    source_ids = [record.source_id for record in records]
    if len(source_ids) != len(set(source_ids)):
        raise H003CandidateError("candidate report contains duplicate source records")
    status_counts: dict[str, int] = {}
    symbols_with_candidates: set[str] = set()
    candidate_count = 0
    for record in records:
        status_counts[record.status] = status_counts.get(record.status, 0) + 1
        candidate_count += record.candidate_count
        if record.candidate_count:
            symbols_with_candidates.add(record.symbol)
    blockers: list[str] = []
    if len(records) != EXPECTED_SOURCE_COUNT:
        blockers.append(
            f"processed_source_count:{len(records)}_expected:{EXPECTED_SOURCE_COUNT}"
        )
    non_ready = [record for record in records if record.status != "TEXT_READY"]
    if non_ready:
        counts: dict[str, int] = {}
        for record in non_ready:
            counts[record.status] = counts.get(record.status, 0) + 1
        blockers.append(
            "non_text_ready_sources:"
            + ",".join(f"{key}={value}" for key, value in sorted(counts.items()))
        )
    processed_companies = len({record.symbol for record in records})
    complete = not blockers
    provisional = CandidateBuildReport(
        schema_version=1,
        report_sha256="",
        rule_id=EXTRACTION_RULE_ID,
        rule_sha256=EXTRACTION_RULE_SHA256,
        source_bundle_sha256=SOURCE_BUNDLE_SHA256,
        cohort_id=COHORT_ID,
        generated_at_utc=generated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        expected_member_count=EXPECTED_MEMBER_COUNT,
        expected_source_count=EXPECTED_SOURCE_COUNT,
        processed_source_count=len(records),
        processed_company_count=processed_companies,
        source_status_counts=dict(sorted(status_counts.items())),
        candidate_count=candidate_count,
        companies_with_candidates=len(symbols_with_candidates),
        complete=complete,
        freeze_blockers=tuple(blockers),
        records=tuple(records),
    )
    payload = provisional.to_dict()
    payload.pop("report_sha256", None)
    return replace(provisional, report_sha256=_canonical_hash(payload))


def write_report(path: str | Path, report: CandidateBuildReport) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def deterministic_sample(
    sources: tuple[FrozenTranscriptSource, ...],
    count: int,
) -> tuple[FrozenTranscriptSource, ...]:
    if count < 1:
        raise H003CandidateError("sample count must be positive")
    if count >= len(sources):
        return sources
    if count == 1:
        return (sources[0],)
    indexes = [
        math.floor(index * (len(sources) - 1) / (count - 1))
        for index in range(count)
    ]
    return tuple(sources[index] for index in indexes)
