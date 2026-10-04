from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest

CORPUS_ID = "SS002-D002-v1"
EXPECTED_P2_ID = "SS002-D001-P2-v1"
EXPECTED_P2_SHA = "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071"
EXPECTED_CURRENT_EVENT_COUNT = 1666
EXPECTED_ATTACHMENT_READY_COUNT = 1659
APPROVED_HOSTS = frozenset(
    {"nsearchives.nseindia.com", "archives.nseindia.com"}
)


class SS002AttachmentError(ValueError):
    """Raised when a special-situation attachment cannot be bound safely."""


@dataclass(frozen=True)
class AttachmentRequest:
    source_url: str
    event_ids: tuple[str, ...]
    symbols: tuple[str, ...]
    categories: tuple[str, ...]


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def approved_attachment_url(value: object) -> str | None:
    raw = _clean(value)
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in APPROVED_HOSTS:
        return None
    return raw


def validate_p2_census(census: dict[str, Any]) -> list[dict[str, Any]]:
    if census.get("census_id") != EXPECTED_P2_ID:
        raise AlphaContractError("SS002 D002 requires frozen P2 census")
    if census.get("census_sha256") != EXPECTED_P2_SHA:
        raise AlphaContractError("SS002 D002 P2 census SHA mismatch")
    if census.get("current_investable_event_count") != EXPECTED_CURRENT_EVENT_COUNT:
        raise AlphaContractError("SS002 D002 current event count mismatch")
    if census.get("current_attachment_ready_count") != EXPECTED_ATTACHMENT_READY_COUNT:
        raise AlphaContractError("SS002 D002 attachment-ready count mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if census.get(field) is not False:
            raise AlphaContractError(f"SS002 D002 requires P2 {field}=false")
    rows = census.get("events")
    if not isinstance(rows, list):
        raise AlphaContractError("SS002 D002 P2 events unavailable")
    return rows


def build_attachment_requests(census: dict[str, Any]) -> tuple[list[AttachmentRequest], list[dict[str, Any]]]:
    events = validate_p2_census(census)
    by_url: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"event_ids": set(), "symbols": set(), "categories": set()}
    )
    event_states = []
    seen_events: set[str] = set()

    for event in events:
        if not isinstance(event, dict):
            raise TypeError("SS002 D002 event rows must be objects")
        if event.get("mapping_state") != "CURRENT_INVESTABLE_IDENTITY":
            continue
        event_id = _clean(event.get("announcement_id"))
        symbol = _clean(event.get("symbol")).upper()
        if not event_id or not symbol:
            raise AlphaContractError("SS002 D002 current event lacks identity")
        if event_id in seen_events:
            raise AlphaContractError(f"SS002 D002 duplicate current event: {event_id}")
        seen_events.add(event_id)

        raw_url = _clean(event.get("approved_attachment_url"))
        url = approved_attachment_url(raw_url)
        categories = event.get("special_situation_categories")
        if not isinstance(categories, list):
            raise AlphaContractError(f"{event_id}: category list unavailable")

        if event.get("attachment_state") == "READY":
            if url is None:
                raise AlphaContractError(f"{event_id}: READY attachment URL is invalid")
            by_url[url]["event_ids"].add(event_id)
            by_url[url]["symbols"].add(symbol)
            by_url[url]["categories"].update(str(value) for value in categories)
            state = "APPROVED_URL"
        elif event.get("attachment_state") == "ABSENT":
            if raw_url:
                raise AlphaContractError(f"{event_id}: ABSENT attachment carries URL")
            state = "NO_ATTACHMENT"
        else:
            state = "ATTACHMENT_NOT_APPROVED"

        event_states.append(
            {
                "announcement_id": event_id,
                "symbol": symbol,
                "attachment_state": state,
                "source_url": url,
            }
        )

    if len(event_states) != EXPECTED_CURRENT_EVENT_COUNT:
        raise AlphaContractError("SS002 D002 current event accounting mismatch")

    requests = [
        AttachmentRequest(
            source_url=url,
            event_ids=tuple(sorted(values["event_ids"])),
            symbols=tuple(sorted(values["symbols"])),
            categories=tuple(sorted(values["categories"])),
        )
        for url, values in sorted(by_url.items())
    ]
    ready_events = sum(row["attachment_state"] == "APPROVED_URL" for row in event_states)
    if ready_events != EXPECTED_ATTACHMENT_READY_COUNT:
        raise AlphaContractError("SS002 D002 approved URL event count mismatch")
    return requests, sorted(event_states, key=lambda row: row["announcement_id"])


def detect_document_family(raw: bytes, source_url: str) -> str:
    if not raw:
        raise SS002AttachmentError("empty attachment bytes")
    if raw.startswith(b"%PDF-"):
        return "PDF"
    if raw.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "ZIP_CONTAINER"

    prefix = raw[:8192]
    try:
        text = prefix.decode("utf-8-sig", errors="strict").lstrip().casefold()
    except UnicodeDecodeError:
        text = ""
    if text.startswith("<?xml") or "<xbrl" in text[:512] or "<xhtml" in text[:512]:
        return "XML_OR_XHTML"
    if "<html" in text[:1024] or "<!doctype html" in text[:1024]:
        return "HTML"
    if text:
        printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in text)
        if printable / max(len(text), 1) >= 0.95:
            return "PLAIN_TEXT"

    suffix = urlparse(source_url).path.casefold()
    if suffix.endswith((".xml", ".xhtml")):
        return "XML_OR_XHTML"
    if suffix.endswith((".html", ".htm")):
        return "HTML"
    return "OTHER_BINARY"


def attachment_evidence(
    request: AttachmentRequest,
    *,
    raw: bytes | None,
    error: str | None,
) -> dict[str, Any]:
    if raw is None:
        if not error:
            raise SS002AttachmentError("failed attachment requires error")
        return {
            "source_url": request.source_url,
            "status": "FETCH_FAILED",
            "document_id": None,
            "raw_sha256": None,
            "raw_byte_count": None,
            "document_family": None,
            "event_ids": list(request.event_ids),
            "symbols": list(request.symbols),
            "categories": list(request.categories),
            "error": error,
        }
    sha = hashlib.sha256(raw).hexdigest()
    family = detect_document_family(raw, request.source_url)
    return {
        "source_url": request.source_url,
        "status": "READY",
        "document_id": sha,
        "raw_sha256": sha,
        "raw_byte_count": len(raw),
        "document_family": family,
        "filename_suffix": urlparse(request.source_url).path.rsplit(".", 1)[-1].lower()
        if "." in urlparse(request.source_url).path.rsplit("/", 1)[-1]
        else "",
        "leading_signature_hex": raw[:16].hex(),
        "event_ids": list(request.event_ids),
        "symbols": list(request.symbols),
        "categories": list(request.categories),
        "error": None,
    }


def build_attachment_corpus(
    census: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    *,
    captured_at_utc: str,
) -> dict[str, Any]:
    requests, event_states = build_attachment_requests(census)
    expected_urls = {request.source_url for request in requests}
    by_url: dict[str, dict[str, Any]] = {}
    for row in evidence_rows:
        if not isinstance(row, dict):
            raise TypeError("SS002 D002 evidence rows must be objects")
        url = _clean(row.get("source_url"))
        if not url or url in by_url:
            raise AlphaContractError("SS002 D002 evidence URLs must be unique")
        by_url[url] = row
    if set(by_url) != expected_urls:
        raise AlphaContractError("SS002 D002 URL evidence accounting mismatch")

    ready_urls = [row for row in evidence_rows if row.get("status") == "READY"]
    ready_url_count = len(ready_urls)
    unique_url_count = len(requests)
    url_ready_ratio = ready_url_count / unique_url_count if unique_url_count else 1.0

    ready_event_ids: set[str] = set()
    family_counts: Counter[str] = Counter()
    document_ids: set[str] = set()
    for row in ready_urls:
        document_id = _clean(row.get("document_id"))
        raw_sha = _clean(row.get("raw_sha256"))
        if not document_id or document_id != raw_sha:
            raise AlphaContractError("SS002 D002 READY document identity mismatch")
        document_ids.add(document_id)
        family_counts[str(row.get("document_family") or "")] += 1
        event_ids = row.get("event_ids")
        if not isinstance(event_ids, list):
            raise AlphaContractError("SS002 D002 READY event_ids unavailable")
        ready_event_ids.update(str(value) for value in event_ids)

    event_ready_ratio = len(ready_event_ids) / EXPECTED_ATTACHMENT_READY_COUNT
    threshold_passes = {
        "complete_current_event_accounting": len(event_states) == EXPECTED_CURRENT_EVENT_COUNT,
        "minimum_unique_url_fetch_success_95pct": url_ready_ratio >= 0.95,
        "minimum_attachment_ready_event_resolution_95pct": event_ready_ratio >= 0.95,
        "deterministic_ready_document_identity": all(
            row.get("document_id") == row.get("raw_sha256")
            for row in ready_urls
        ),
        "approved_hosts_only": all(
            approved_attachment_url(row.get("source_url")) is not None
            for row in evidence_rows
        ),
    }

    output = {
        "schema_version": 1,
        "corpus_id": CORPUS_ID,
        "classification": "OFFICIAL_SPECIAL_SITUATION_DOCUMENT_CORPUS_NOT_ALPHA",
        "captured_at_utc": captured_at_utc,
        "source_p2_census_sha256": EXPECTED_P2_SHA,
        "current_event_count": EXPECTED_CURRENT_EVENT_COUNT,
        "attachment_ready_event_count": EXPECTED_ATTACHMENT_READY_COUNT,
        "unique_approved_url_count": unique_url_count,
        "ready_url_count": ready_url_count,
        "ready_url_ratio": url_ready_ratio,
        "ready_event_count": len(ready_event_ids),
        "ready_event_ratio_of_attachment_ready": event_ready_ratio,
        "unique_document_id_count": len(document_ids),
        "document_family_counts": dict(sorted(family_counts.items())),
        "fetch_failure_count": unique_url_count - ready_url_count,
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_text_extraction": all(threshold_passes.values()),
        "event_states": event_states,
        "documents": sorted(evidence_rows, key=lambda row: str(row["source_url"])),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["corpus_sha256"] = digest(output)
    return output
