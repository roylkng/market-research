from __future__ import annotations

import hashlib
import io
import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import yaml
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from marketlab.h003_sources import SOURCE_RULE_ID, SOURCE_RULE_SHA256

CONTENT_RULE_ID = "H003-T001"
CONTENT_RULE_SHA256 = "e48d621c1ce45147a68577a156629e86b706ab6be4b1ebc232d2a745a2f8b3bb"
SOURCE_BUNDLE_SHA256 = "583af88b3c070e15fe94a7782962c9e1fb1ce167e1412a08fd5c7b2f2dcaf7ee"
COHORT_ID = "FY27-Q2-2026-09-06"
DECISION_TIMESTAMP_UTC = "2026-09-06T12:21:06.431463Z"
PARSER_ID = "pypdf-text-v1"
MIN_PAGE_COUNT = 2
MIN_NONEMPTY_PAGE_COUNT = 2
MIN_EXTRACTED_CHAR_COUNT = 5000
ALLOWED_SOURCE_HOSTS = frozenset(
    {"nsearchives.nseindia.com", "archives.nseindia.com"}
)

ContentStatus = Literal[
    "CONTENT_READY",
    "INSUFFICIENT_TEXT",
    "UNREADABLE",
    "FETCH_FAILED",
]


class H003ContentError(ValueError):
    """Raised when frozen H003 transcript content cannot be verified safely."""


@dataclass(frozen=True)
class FrozenTranscriptSource:
    source_id: str
    symbol: str
    seq_id: str
    exchange_published_at_utc: str
    attachment_url: str
    discovery_row_sha256: str


@dataclass(frozen=True)
class TranscriptContentRecord:
    schema_version: int
    content_id: str
    rule_id: str
    rule_sha256: str
    source_rule_id: str
    source_rule_sha256: str
    source_bundle_sha256: str
    cohort_id: str
    source_id: str
    symbol: str
    exchange_published_at_utc: str
    attachment_url: str
    fetched_at_utc: str
    status: ContentStatus
    parser_id: str
    raw_sha256: str | None
    raw_path: str | None
    text_sha256: str | None
    text_path: str | None
    page_count: int | None
    nonempty_page_count: int | None
    extracted_char_count: int | None
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TranscriptContentBundle:
    schema_version: int
    bundle_sha256: str
    rule_id: str
    rule_sha256: str
    source_bundle_sha256: str
    cohort_id: str
    generated_at_utc: str
    source_count: int
    status_counts: dict[str, int]
    company_count_with_content_ready: int
    company_count_with_3plus_content_ready: int
    company_count_with_6plus_content_ready: int
    records: tuple[TranscriptContentRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["records"] = [record.to_dict() for record in self.records]
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
        raise H003ContentError("H003 content payload must contain finite JSON values") from exc
    return hashlib.sha256(raw).hexdigest()


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise H003ContentError("H003 content timestamp must include timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def validate_content_rule_document(document: dict[str, Any]) -> str:
    if not isinstance(document, dict):
        raise H003ContentError("H003 content rule root must be a mapping")
    declared = document.get("sha256")
    if not isinstance(declared, str) or len(declared) != 64:
        raise H003ContentError("H003 content rule must declare SHA-256")
    unsigned = dict(document)
    unsigned.pop("sha256", None)
    actual = _canonical_hash(unsigned)
    if actual != declared or declared != CONTENT_RULE_SHA256:
        raise H003ContentError(
            f"H003 content rule hash mismatch: declared={declared}, recomputed={actual}"
        )
    if document.get("id") != CONTENT_RULE_ID:
        raise H003ContentError("unexpected H003 content rule id")
    if document.get("status") != "FROZEN":
        raise H003ContentError("H003 content rule must remain FROZEN")
    if document.get("live_capital") is not False:
        raise H003ContentError("H003 content rule must keep live_capital: false")
    if document.get("cohort_id") != COHORT_ID:
        raise H003ContentError("H003 content rule cohort changed")
    if document.get("source_rule_id") != SOURCE_RULE_ID:
        raise H003ContentError("H003 content rule source rule id changed")
    if document.get("source_rule_sha256") != SOURCE_RULE_SHA256:
        raise H003ContentError("H003 content rule source rule hash changed")
    if document.get("source_bundle_sha256") != SOURCE_BUNDLE_SHA256:
        raise H003ContentError("H003 content rule source bundle hash changed")
    if document.get("decision_timestamp_utc") != DECISION_TIMESTAMP_UTC:
        raise H003ContentError("H003 content rule decision timestamp changed")
    return actual


def load_and_validate_content_rule(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    validate_content_rule_document(document)
    return document


def load_frozen_sources(path: str | Path) -> tuple[FrozenTranscriptSource, ...]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise H003ContentError(f"could not read H003 source bundle {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise H003ContentError("H003 source bundle root must be an object")
    declared = document.get("bundle_sha256")
    unsigned = dict(document)
    unsigned.pop("bundle_sha256", None)
    if declared != SOURCE_BUNDLE_SHA256 or _canonical_hash(unsigned) != declared:
        raise H003ContentError("H003 source bundle does not match frozen content rule")
    if document.get("rule_id") != SOURCE_RULE_ID:
        raise H003ContentError("H003 source bundle rule id mismatch")
    if document.get("rule_sha256") != SOURCE_RULE_SHA256:
        raise H003ContentError("H003 source bundle rule hash mismatch")
    if document.get("cohort_id") != COHORT_ID:
        raise H003ContentError("H003 source bundle cohort mismatch")
    if document.get("incomplete_count") != 0:
        raise H003ContentError("H003 source bundle contains incomplete coverage")

    sources: list[FrozenTranscriptSource] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    records = document.get("records")
    if not isinstance(records, list):
        raise H003ContentError("H003 source bundle records must be a list")
    for record in records:
        if not isinstance(record, dict):
            raise H003ContentError("H003 source coverage record must be an object")
        record_sources = record.get("sources")
        if not isinstance(record_sources, list):
            raise H003ContentError("H003 coverage record sources must be a list")
        if int(record.get("source_count", -1)) != len(record_sources):
            raise H003ContentError("H003 source_count does not match source list")
        for item in record_sources:
            if not isinstance(item, dict):
                raise H003ContentError("H003 transcript source must be an object")
            source = FrozenTranscriptSource(
                source_id=str(item.get("source_id") or ""),
                symbol=str(item.get("symbol") or "").upper(),
                seq_id=str(item.get("seq_id") or ""),
                exchange_published_at_utc=str(item.get("exchange_published_at_utc") or ""),
                attachment_url=str(item.get("attachment_url") or ""),
                discovery_row_sha256=str(item.get("discovery_row_sha256") or ""),
            )
            if not all(
                (
                    source.source_id,
                    source.symbol,
                    source.seq_id,
                    source.exchange_published_at_utc,
                    source.attachment_url,
                    source.discovery_row_sha256,
                )
            ):
                raise H003ContentError("H003 transcript source is missing identity fields")
            parsed = urlparse(source.attachment_url)
            if (
                parsed.scheme != "https"
                or (parsed.hostname or "").lower() not in ALLOWED_SOURCE_HOSTS
            ):
                raise H003ContentError(
                    f"H003 transcript source URL is outside frozen NSE hosts: {source.attachment_url}"
                )
            if source.source_id in seen_ids:
                raise H003ContentError(f"duplicate H003 source id: {source.source_id}")
            if source.attachment_url in seen_urls:
                raise H003ContentError(
                    f"duplicate H003 attachment URL: {source.attachment_url}"
                )
            seen_ids.add(source.source_id)
            seen_urls.add(source.attachment_url)
            sources.append(source)
    expected_count = int(document.get("transcript_source_count", -1))
    if len(sources) != expected_count:
        raise H003ContentError(
            f"H003 source bundle transcript count mismatch: {len(sources)} != {expected_count}"
        )
    return tuple(sources)


def extract_pdf_text(raw_pdf: bytes) -> tuple[tuple[str, ...], str]:
    if not raw_pdf:
        raise H003ContentError("H003 transcript PDF bytes are empty")
    try:
        reader = PdfReader(io.BytesIO(raw_pdf))
        page_texts = tuple((page.extract_text() or "") for page in reader.pages)
    except (PyPdfError, ValueError, TypeError) as exc:
        raise H003ContentError(f"H003 transcript PDF extraction failed: {exc}") from exc
    text = "\n".join(page_texts)
    return page_texts, text


def classify_extracted_text(page_texts: tuple[str, ...], text: str) -> ContentStatus:
    page_count = len(page_texts)
    nonempty_page_count = sum(bool(value.strip()) for value in page_texts)
    extracted_char_count = len(text.strip())
    if (
        page_count >= MIN_PAGE_COUNT
        and nonempty_page_count >= MIN_NONEMPTY_PAGE_COUNT
        and extracted_char_count >= MIN_EXTRACTED_CHAR_COUNT
    ):
        return "CONTENT_READY"
    return "INSUFFICIENT_TEXT"


def _record_digest(record: TranscriptContentRecord) -> str:
    payload = record.to_dict()
    payload.pop("content_id", None)
    return _canonical_hash(payload)


class TranscriptContentStore:
    """Content-addressed raw PDFs, extracted text and immutable extraction records."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _write_once(self, path: Path, raw: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != raw:
                raise H003ContentError("content-addressed H003 content collision")
            return
        path.write_bytes(raw)

    def record_success(
        self,
        source: FrozenTranscriptSource,
        raw_pdf: bytes,
        *,
        fetched_at: datetime,
    ) -> TranscriptContentRecord:
        fetched = _iso_utc(fetched_at)
        raw_digest = hashlib.sha256(raw_pdf).hexdigest()
        raw_path = self.root / "h003-content" / "raw" / "sha256" / f"{raw_digest}.pdf"
        self._write_once(raw_path, raw_pdf)
        try:
            page_texts, text = extract_pdf_text(raw_pdf)
        except H003ContentError as exc:
            return self.record_failure(
                source,
                fetched_at=fetched_at,
                status="UNREADABLE",
                error=str(exc),
                raw_sha256=raw_digest,
                raw_path=str(raw_path),
            )
        text_bytes = text.encode("utf-8")
        text_digest = hashlib.sha256(text_bytes).hexdigest()
        text_path = self.root / "h003-content" / "text" / "sha256" / f"{text_digest}.txt"
        self._write_once(text_path, text_bytes)
        status = classify_extracted_text(page_texts, text)
        provisional = TranscriptContentRecord(
            schema_version=1,
            content_id="",
            rule_id=CONTENT_RULE_ID,
            rule_sha256=CONTENT_RULE_SHA256,
            source_rule_id=SOURCE_RULE_ID,
            source_rule_sha256=SOURCE_RULE_SHA256,
            source_bundle_sha256=SOURCE_BUNDLE_SHA256,
            cohort_id=COHORT_ID,
            source_id=source.source_id,
            symbol=source.symbol,
            exchange_published_at_utc=source.exchange_published_at_utc,
            attachment_url=source.attachment_url,
            fetched_at_utc=fetched,
            status=status,
            parser_id=PARSER_ID,
            raw_sha256=raw_digest,
            raw_path=str(raw_path),
            text_sha256=text_digest,
            text_path=str(text_path),
            page_count=len(page_texts),
            nonempty_page_count=sum(bool(value.strip()) for value in page_texts),
            extracted_char_count=len(text.strip()),
            error=None,
        )
        return replace(provisional, content_id=_record_digest(provisional))

    def record_failure(
        self,
        source: FrozenTranscriptSource,
        *,
        fetched_at: datetime,
        status: Literal["UNREADABLE", "FETCH_FAILED"],
        error: str,
        raw_sha256: str | None = None,
        raw_path: str | None = None,
    ) -> TranscriptContentRecord:
        if not error.strip():
            raise H003ContentError("H003 content failure requires error detail")
        provisional = TranscriptContentRecord(
            schema_version=1,
            content_id="",
            rule_id=CONTENT_RULE_ID,
            rule_sha256=CONTENT_RULE_SHA256,
            source_rule_id=SOURCE_RULE_ID,
            source_rule_sha256=SOURCE_RULE_SHA256,
            source_bundle_sha256=SOURCE_BUNDLE_SHA256,
            cohort_id=COHORT_ID,
            source_id=source.source_id,
            symbol=source.symbol,
            exchange_published_at_utc=source.exchange_published_at_utc,
            attachment_url=source.attachment_url,
            fetched_at_utc=_iso_utc(fetched_at),
            status=status,
            parser_id=PARSER_ID,
            raw_sha256=raw_sha256,
            raw_path=raw_path,
            text_sha256=None,
            text_path=None,
            page_count=None,
            nonempty_page_count=None,
            extracted_char_count=None,
            error=error,
        )
        return replace(provisional, content_id=_record_digest(provisional))


def build_content_bundle(
    records: list[TranscriptContentRecord], *, generated_at: datetime
) -> TranscriptContentBundle:
    if generated_at.tzinfo is None:
        raise H003ContentError("H003 content bundle generated_at must include timezone")
    seen: set[str] = set()
    for record in records:
        if record.source_id in seen:
            raise H003ContentError(f"duplicate H003 content source id: {record.source_id}")
        seen.add(record.source_id)
        if record.rule_id != CONTENT_RULE_ID or record.rule_sha256 != CONTENT_RULE_SHA256:
            raise H003ContentError("H003 content record rule mismatch")
        if _record_digest(record) != record.content_id:
            raise H003ContentError("H003 content record hash mismatch")
    if len(records) != 794:
        raise H003ContentError(f"H003 content scan must cover all 794 frozen sources: {len(records)}")

    status_counts: dict[str, int] = {}
    ready_by_symbol: dict[str, int] = {}
    for record in records:
        status_counts[record.status] = status_counts.get(record.status, 0) + 1
        if record.status == "CONTENT_READY":
            ready_by_symbol[record.symbol] = ready_by_symbol.get(record.symbol, 0) + 1
    ordered = tuple(sorted(records, key=lambda item: (item.symbol, item.exchange_published_at_utc)))
    provisional = TranscriptContentBundle(
        schema_version=1,
        bundle_sha256="",
        rule_id=CONTENT_RULE_ID,
        rule_sha256=CONTENT_RULE_SHA256,
        source_bundle_sha256=SOURCE_BUNDLE_SHA256,
        cohort_id=COHORT_ID,
        generated_at_utc=_iso_utc(generated_at),
        source_count=len(ordered),
        status_counts=dict(sorted(status_counts.items())),
        company_count_with_content_ready=len(ready_by_symbol),
        company_count_with_3plus_content_ready=sum(value >= 3 for value in ready_by_symbol.values()),
        company_count_with_6plus_content_ready=sum(value >= 6 for value in ready_by_symbol.values()),
        records=ordered,
    )
    payload = provisional.to_dict()
    payload.pop("bundle_sha256", None)
    return replace(provisional, bundle_sha256=_canonical_hash(payload))


def write_content_bundle(path: str | Path, bundle: TranscriptContentBundle) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
