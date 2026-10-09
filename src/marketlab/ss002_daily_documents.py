from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_attachments import approved_attachment_url, detect_document_family
from marketlab.ss002_text import extract_document_text, seal_extraction_row

CORPUS_ID = "SS002-P003-v1"
INBOX_ID = "SS002-P002-v1"
INBOX_SHA256 = "1c2b89cb89ee7c83fb5720b95152eab704d3575547ce924366f4df7f5888c84f"
EXPECTED_EVENTS = 54
EXPECTED_DOCUMENT_EVENTS = 36
EXPECTED_CURRENT_SYMBOLS = 30
MAX_ATTACHMENT_BYTES = 60 * 1024 * 1024


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_inbox(inbox: dict[str, Any]) -> list[dict[str, Any]]:
    if inbox.get("inbox_id") != INBOX_ID or inbox.get("inbox_sha256") != INBOX_SHA256:
        raise AlphaContractError("SS002 P003 frozen source inbox identity mismatch")
    if digest({key: value for key, value in inbox.items() if key != "inbox_sha256"}) != INBOX_SHA256:
        raise AlphaContractError("SS002 P003 source inbox contents fail SHA verification")
    if inbox.get("source_event_count") != EXPECTED_EVENTS:
        raise AlphaContractError("SS002 P003 requires exactly 54 source events")
    if inbox.get("document_intake_ready_count") != EXPECTED_DOCUMENT_EVENTS:
        raise AlphaContractError("SS002 P003 requires exactly 36 official-document events")
    for field in (
        "model_inference_executed",
        "economic_relevance_verified",
        "return_outcomes_opened",
        "share_action_clearance_proven",
        "market_capitalization_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if inbox.get(field) is not False:
            raise AlphaContractError(f"SS002 P003 requires source {field}=false")
    events = inbox.get("events")
    if not isinstance(events, list) or len(events) != EXPECTED_EVENTS:
        raise AlphaContractError("SS002 P003 source event rows unavailable")
    return events


def prepare_document_requests(
    inbox: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events = validate_inbox(inbox)
    by_url: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"event_ids": set(), "symbols": set(), "categories": set()}
    )
    event_states: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    current_symbols: set[str] = set()

    for event in events:
        if not isinstance(event, dict):
            raise TypeError("SS002 P003 source events must be objects")
        event_id = event.get("announcement_id")
        symbol = event.get("symbol")
        if (
            not isinstance(event_id, str)
            or not event_id
            or not isinstance(symbol, str)
            or not symbol
            or event_id in seen_ids
        ):
            raise AlphaContractError("SS002 P003 duplicate or incomplete event identity")
        seen_ids.add(event_id)
        state = event.get("document_intake_state")
        mapped = event.get("mapping_state")
        url = event.get("approved_attachment_url")
        categories = event.get("category_hints_only")

        if not isinstance(categories, list) or not all(
            isinstance(category, str) and category for category in categories
        ):
            raise AlphaContractError("SS002 P003 category hints are invalid")

        if state == "DOCUMENT_INTAKE_READY":
            if (
                mapped != "SYMBOL_IN_EQ_MASTER_AT_CAPTURE"
                or not isinstance(event.get("isin_at_capture"), str)
                or not event["isin_at_capture"]
            ):
                raise AlphaContractError("SS002 P003 ready event missing exact capture identity")
            if approved_attachment_url(url) is None:
                raise AlphaContractError("SS002 P003 official URL unavailable or invalid")
            if event.get("exact_historical_identity_match") is not True:
                raise AlphaContractError("SS002 P003 source-day issuer continuity unresolved")
            by_url[str(url)]["event_ids"].add(event_id)
            by_url[str(url)]["symbols"].add(symbol)
            by_url[str(url)]["categories"].update(categories)
            current_symbols.add(symbol)
        elif state != "NO_APPROVED_CURRENT_ATTACHMENT":
            raise AlphaContractError("SS002 P003 unknown source document-intake state")

        event_states.append(
            {
                "announcement_id": event_id,
                "symbol": symbol,
                "isin_at_capture": event.get("isin_at_capture"),
                "source_day_ist": event.get("source_day_ist"),
                "exchange_published_at_utc": event.get("exchange_published_at_utc"),
                "source_lag_state": event.get("source_lag_state"),
                "mapping_state": mapped,
                "category_hints_only": sorted(categories),
                "research_attention_state": event.get("research_attention_state"),
                "source_document_state": state,
                "official_source_url": url if state == "DOCUMENT_INTAKE_READY" else None,
                "economic_relevance_verified": False,
                "market_capitalization_calculated": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    requests = [
        {
            "source_url": url,
            "event_ids": sorted(values["event_ids"]),
            "symbols": sorted(values["symbols"]),
            "category_hints_only": sorted(values["categories"]),
        }
        for url, values in sorted(by_url.items())
    ]
    if len(event_states) != EXPECTED_EVENTS:
        raise AlphaContractError("SS002 P003 source event accounting incomplete")
    if sum(e["source_document_state"] == "DOCUMENT_INTAKE_READY" for e in event_states) != EXPECTED_DOCUMENT_EVENTS:
        raise AlphaContractError("SS002 P003 wrong ready document event count")
    if len(current_symbols) != EXPECTED_CURRENT_SYMBOLS:
        raise AlphaContractError("SS002 P003 current symbol count changed")
    return requests, sorted(event_states, key=lambda item: item["announcement_id"])


def extract_official_attachment(
    request: dict[str, Any],
    *,
    raw: bytes | None,
    fetched_at_utc: str,
    error: str | None = None,
    canonical_extraction: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    source_url = request["source_url"]
    if approved_attachment_url(source_url) is None:
        raise AlphaContractError("SS002 P003 attachment URL outside official NSE hosts")
    parsed_time = datetime.fromisoformat(fetched_at_utc)
    if parsed_time.tzinfo is None:
        raise AlphaContractError("SS002 P003 fetch timestamp must be timezone aware")

    common = {
        "source_url": source_url,
        "event_ids": request["event_ids"],
        "symbols": request["symbols"],
        "category_hints_only": request["category_hints_only"],
        "fetched_at_utc": fetched_at_utc,
        "source_snapshot_relation": "DOCUMENT_REFETCHED_AFTER_ANNOUNCEMENT",
    }
    if raw is None:
        if not error:
            raise AlphaContractError("SS002 P003 failed fetch requires explicit reason")
        return (
            {
                **common,
                "status": "FETCH_FAILED",
                "document_id": None,
                "raw_sha256": None,
                "raw_byte_count": None,
                "document_family": None,
                "extraction_state": "NOT_FETCHED",
                "text_segment_count": 0,
                "segment_manifest_sha256": None,
                "error": error,
            },
            None,
        )

    document_id = _sha(raw)
    if len(raw) > MAX_ATTACHMENT_BYTES:
        return (
            {
                **common,
                "status": "SIZE_LIMIT",
                "document_id": document_id,
                "raw_sha256": document_id,
                "raw_byte_count": len(raw),
                "document_family": None,
                "extraction_state": "NOT_PARSED_OVERSIZED",
                "text_segment_count": 0,
                "segment_manifest_sha256": None,
                "error": "DOCUMENT_EXCEEDS_60_MIB",
            },
            None,
        )
    family = detect_document_family(raw, source_url)
    if canonical_extraction is not None:
        if (
            canonical_extraction.get("document_id") != document_id
            or canonical_extraction.get("d002_family") != family
        ):
            raise AlphaContractError("SS002 P003 reused text has different document bytes or family")
        expected = seal_extraction_row(
            {
                key: value
                for key, value in canonical_extraction.items()
                if key != "segment_manifest_sha256"
            }
        )
        if expected["segment_manifest_sha256"] != canonical_extraction.get("segment_manifest_sha256"):
            raise AlphaContractError("SS002 P003 reused text manifest SHA mismatch")
        extracted = canonical_extraction
    else:
        extracted = extract_document_text(
            document_id=document_id,
            raw=raw,
            d002_family=family,
            source_url=source_url,
        )
    return (
        {
            **common,
            "status": "READY",
            "document_id": document_id,
            "raw_sha256": document_id,
            "raw_byte_count": len(raw),
            "document_family": family,
            "extraction_state": extracted["extraction_state"],
            "text_segment_count": len(extracted["segments"]),
            "segment_manifest_sha256": extracted["segment_manifest_sha256"],
            "segment_source_url": extracted["source_url"],
            "error": None,
        },
        extracted,
    )


def build_daily_document_corpus(
    inbox: dict[str, Any],
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    requests, event_states = prepare_document_requests(inbox)
    expected = {req["source_url"]: req for req in requests}
    by_url: dict[str, dict[str, Any]] = {}
    for row in documents:
        if not isinstance(row, dict):
            raise TypeError("SS002 P003 document rows must be objects")
        url = row.get("source_url")
        if not isinstance(url, str) or url in by_url:
            raise AlphaContractError("SS002 P003 duplicate or invalid document URL")
        if url not in expected:
            raise AlphaContractError("SS002 P003 document from non-source URL")
        if (
            row.get("event_ids") != expected[url]["event_ids"]
            or row.get("symbols") != expected[url]["symbols"]
            or row.get("category_hints_only") != expected[url]["category_hints_only"]
        ):
            raise AlphaContractError("SS002 P003 event-document mapping differs from source")
        by_url[url] = row
    if set(by_url) != set(expected):
        raise AlphaContractError("SS002 P003 incomplete approved URL accounting")

    by_event_document = {}
    for event in event_states:
        url = event["official_source_url"]
        if url:
            record = by_url[url]
            event["document_id"] = record["document_id"]
            event["document_byte_state"] = record["status"]
            event["document_text_state"] = record["extraction_state"]
            by_event_document[event["announcement_id"]] = record["document_id"]
        else:
            event["document_id"] = None
            event["document_byte_state"] = "NOT_IN_SCOPE"
            event["document_text_state"] = "NOT_IN_SCOPE"

    ready_urls = [row for row in documents if row["status"] == "READY"]
    ready_text_urls = [
        row for row in ready_urls
        if row.get("extraction_state") == "READY" and row.get("text_segment_count", 0) > 0
    ]
    for row in ready_urls:
        if row.get("document_id") != row.get("raw_sha256"):
            raise AlphaContractError("SS002 P003 document SHA mismatch")
        if not isinstance(row.get("segment_manifest_sha256"), str):
            raise AlphaContractError("SS002 P003 document segment manifest SHA missing")

    fetched_ratio = len(ready_urls) / len(requests) if requests else 0.0
    text_ratio = len(ready_text_urls) / len(ready_urls) if ready_urls else 0.0
    gates = {
        "all_54_source_events_retained": len(event_states) == EXPECTED_EVENTS,
        "all_36_current_document_events_retained": len(by_event_document) == EXPECTED_DOCUMENT_EVENTS,
        "minimum_official_url_fetch_95pct": fetched_ratio >= 0.95,
        "minimum_text_ready_among_fetched_80pct": text_ratio >= 0.80,
        "ready_documents_have_sha_and_segment_manifest": all(
            row.get("document_id") == row.get("raw_sha256")
            and isinstance(row.get("segment_manifest_sha256"), str)
            for row in ready_urls
        ),
        "approved_official_hosts_only": all(approved_attachment_url(url) is not None for url in by_url),
    }

    counts = Counter(row["extraction_state"] for row in documents)
    output = {
        "schema_version": 1,
        "corpus_id": CORPUS_ID,
        "classification": "NEW_DAILY_NSE_DOCUMENT_TEXT_EVIDENCE_NOT_INVESTMENT_RESEARCH",
        "source_p002_inbox_sha256": INBOX_SHA256,
        "source_event_count": len(event_states),
        "current_document_event_count": len(by_event_document),
        "approved_unique_url_count": len(requests),
        "fetched_url_count": len(ready_urls),
        "fetched_url_ratio": fetched_ratio,
        "text_ready_url_count": len(ready_text_urls),
        "text_ready_ratio_of_fetched": text_ratio,
        "unique_document_id_count": len({
            row["document_id"] for row in ready_urls
        }),
        "extraction_state_counts": dict(sorted(counts.items())),
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_evidence_bound_l001": all(gates.values()),
        "event_states": event_states,
        "documents": sorted(documents, key=lambda row: row["source_url"]),
        "model_inference_executed": False,
        "economic_relevance_verified": False,
        "return_outcomes_opened": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["corpus_sha256"] = digest(output)
    return output
