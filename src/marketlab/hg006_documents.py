from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_attachments import (
    approved_attachment_url,
    detect_document_family,
)

CORPUS_ID = "HG006-D001A-P1-v1"
EXPECTED_D001_ID = "HG006-D001-v1"
EXPECTED_D001_SHA = "a267dab9cd646ffdc5230f1899a16a4138733413a3f05f438edf639f18ad41a5"
EXPECTED_EVENT_COUNT = 9733
EXPECTED_CHRONOLOGY_COUNT = 1607
EXPECTED_SELECTED_CHRONOLOGY_COUNT = 1043
SHARD_COUNT = 8
SELECTED_FAMILIES = frozenset(
    {"SCHEME_REORGANISATION", "PREFERENTIAL_WARRANT"}
)


@dataclass(frozen=True)
class HistoricalAttachmentRequest:
    source_url: str
    event_ids: tuple[str, ...]
    chronology_ids: tuple[str, ...]
    symbols: tuple[str, ...]
    families: tuple[str, ...]


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def shard_for_url(source_url: str) -> int:
    raw = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
    return int(raw[:8], 16) % SHARD_COUNT


def _validate_d001(census: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    if census.get("census_id") != EXPECTED_D001_ID:
        raise AlphaContractError("HG006 D001A requires frozen D001 census")
    if census.get("census_sha256") != EXPECTED_D001_SHA:
        raise AlphaContractError("HG006 D001A D001 census SHA mismatch")
    if census.get("retained_event_count") != EXPECTED_EVENT_COUNT:
        raise AlphaContractError("HG006 D001A retained event count mismatch")
    if census.get("historical_chronology_count") != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 D001A chronology count mismatch")
    for field in (
        "completion_probabilities_assigned",
        "expected_returns_calculated",
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if census.get(field) is not False:
            raise AlphaContractError(f"HG006 D001A requires D001 {field}=false")
    events = census.get("events")
    chronologies = census.get("chronologies")
    if not isinstance(events, list) or len(events) != EXPECTED_EVENT_COUNT:
        raise AlphaContractError("HG006 D001A D001 events unavailable")
    if not isinstance(chronologies, list) or len(chronologies) != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 D001A D001 chronologies unavailable")
    return events, chronologies


def selected_source_population(census: dict[str, Any]) -> dict[str, Any]:
    events, chronologies = _validate_d001(census)
    selected_chronologies = [
        row
        for row in chronologies
        if isinstance(row, dict) and row.get("family") in SELECTED_FAMILIES
    ]
    if len(selected_chronologies) != EXPECTED_SELECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError(
            "HG006 D001A selected chronology count mismatch"
        )

    chronology_by_id: dict[str, dict] = {}
    event_to_chronologies: dict[str, set[str]] = defaultdict(set)
    for row in selected_chronologies:
        chronology_id = _clean(row.get("chronology_id"))
        if not chronology_id or chronology_id in chronology_by_id:
            raise AlphaContractError("HG006 D001A chronology IDs must be unique")
        chronology_by_id[chronology_id] = row
        announcement_ids = row.get("announcement_ids")
        if not isinstance(announcement_ids, list):
            raise AlphaContractError("HG006 D001A chronology announcement IDs unavailable")
        for event_id in announcement_ids:
            value = _clean(event_id)
            if not value:
                raise AlphaContractError("HG006 D001A empty event ID in chronology")
            event_to_chronologies[value].add(chronology_id)

    selected_events: list[dict] = []
    seen_event_ids: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            raise TypeError("HG006 D001A event must be object")
        event_id = _clean(event.get("announcement_id"))
        if event_id not in event_to_chronologies:
            continue
        if event_id in seen_event_ids:
            raise AlphaContractError("HG006 D001A selected event IDs must be unique")
        seen_event_ids.add(event_id)
        families = event.get("historical_discrete_families")
        if (
            not isinstance(families, list)
            or not set(families).intersection(SELECTED_FAMILIES)
        ):
            raise AlphaContractError(
                f"HG006 D001A selected event lacks selected family: {event_id}"
            )
        selected_events.append(event)

    missing = set(event_to_chronologies) - seen_event_ids
    if missing:
        raise AlphaContractError(
            f"HG006 D001A chronology events missing from D001: {len(missing)}"
        )

    return {
        "events": sorted(
            selected_events,
            key=lambda row: (
                str(row.get("exchange_published_at_utc") or ""),
                str(row.get("symbol") or ""),
                str(row.get("announcement_id") or ""),
            ),
        ),
        "chronologies": sorted(
            selected_chronologies,
            key=lambda row: (
                str(row.get("family") or ""),
                str(row.get("symbol") or ""),
                str(row.get("chronology_id") or ""),
            ),
        ),
        "event_to_chronologies": event_to_chronologies,
    }


def build_attachment_requests(
    census: dict[str, Any],
) -> tuple[list[HistoricalAttachmentRequest], list[dict[str, Any]]]:
    selected = selected_source_population(census)
    event_to_chronologies = selected["event_to_chronologies"]
    by_url: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {
            "event_ids": set(),
            "chronology_ids": set(),
            "symbols": set(),
            "families": set(),
        }
    )
    event_states: list[dict[str, Any]] = []

    for event in selected["events"]:
        event_id = _clean(event.get("announcement_id"))
        symbol = _clean(event.get("symbol")).upper()
        families = set(event.get("historical_discrete_families") or [])
        selected_families = sorted(families.intersection(SELECTED_FAMILIES))
        raw_url = _clean(event.get("approved_attachment_url"))
        url = approved_attachment_url(raw_url)
        if raw_url and url is None:
            raise AlphaContractError(
                f"HG006 D001A D001 approved URL is invalid: {event_id}"
            )
        chronology_ids = sorted(event_to_chronologies[event_id])
        if url is None:
            state = "NO_APPROVED_ATTACHMENT"
        else:
            state = "APPROVED_URL"
            item = by_url[url]
            item["event_ids"].add(event_id)
            item["chronology_ids"].update(chronology_ids)
            item["symbols"].add(symbol)
            item["families"].update(selected_families)

        event_states.append(
            {
                "announcement_id": event_id,
                "symbol": symbol,
                "families": selected_families,
                "chronology_ids": chronology_ids,
                "attachment_state": state,
                "source_url": url,
            }
        )

    requests = [
        HistoricalAttachmentRequest(
            source_url=url,
            event_ids=tuple(sorted(values["event_ids"])),
            chronology_ids=tuple(sorted(values["chronology_ids"])),
            symbols=tuple(sorted(values["symbols"])),
            families=tuple(sorted(values["families"])),
        )
        for url, values in sorted(by_url.items())
    ]
    return requests, sorted(
        event_states,
        key=lambda row: row["announcement_id"],
    )


def attachment_evidence(
    request: HistoricalAttachmentRequest,
    *,
    raw: bytes | None,
    error: str | None,
) -> dict[str, Any]:
    if raw is None:
        if not error:
            raise AlphaContractError("HG006 D001A failed fetch requires error")
        return {
            "source_url": request.source_url,
            "shard_id": shard_for_url(request.source_url),
            "status": "FETCH_FAILED",
            "document_id": None,
            "raw_sha256": None,
            "raw_byte_count": None,
            "document_family": None,
            "event_ids": list(request.event_ids),
            "chronology_ids": list(request.chronology_ids),
            "symbols": list(request.symbols),
            "families": list(request.families),
            "error": error,
        }

    sha = hashlib.sha256(raw).hexdigest()
    return {
        "source_url": request.source_url,
        "shard_id": shard_for_url(request.source_url),
        "status": "READY",
        "document_id": sha,
        "raw_sha256": sha,
        "raw_byte_count": len(raw),
        "document_family": detect_document_family(raw, request.source_url),
        "event_ids": list(request.event_ids),
        "chronology_ids": list(request.chronology_ids),
        "symbols": list(request.symbols),
        "families": list(request.families),
        "error": None,
    }


def build_historical_document_corpus(
    census: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    *,
    captured_at_utc: str,
) -> dict[str, Any]:
    requests, event_states = build_attachment_requests(census)
    selected = selected_source_population(census)
    expected_urls = {row.source_url for row in requests}
    by_url: dict[str, dict[str, Any]] = {}
    for row in evidence_rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 D001A evidence row must be object")
        url = _clean(row.get("source_url"))
        if not url or url in by_url:
            raise AlphaContractError("HG006 D001A evidence URLs must be unique")
        by_url[url] = row
    if set(by_url) != expected_urls:
        raise AlphaContractError("HG006 D001A URL evidence accounting mismatch")

    ready_rows = [row for row in evidence_rows if row.get("status") == "READY"]
    ready_url_count = len(ready_rows)
    unique_url_count = len(requests)
    ready_url_ratio = ready_url_count / unique_url_count if unique_url_count else 1.0

    ready_event_ids: set[str] = set()
    ready_chronology_ids: set[str] = set()
    document_ids: set[str] = set()
    family_counts: Counter[str] = Counter()
    for row in ready_rows:
        document_id = _clean(row.get("document_id"))
        if not document_id or document_id != _clean(row.get("raw_sha256")):
            raise AlphaContractError("HG006 D001A READY document identity mismatch")
        document_ids.add(document_id)
        ready_event_ids.update(str(value) for value in row.get("event_ids", []))
        ready_chronology_ids.update(
            str(value) for value in row.get("chronology_ids", [])
        )
        family_counts[str(row.get("document_family") or "UNKNOWN")] += 1

    attachment_event_ids = {
        row["announcement_id"]
        for row in event_states
        if row["attachment_state"] == "APPROVED_URL"
    }
    attachment_ready_event_count = len(attachment_event_ids)
    ready_event_ratio = (
        len(ready_event_ids) / attachment_ready_event_count
        if attachment_ready_event_count
        else 1.0
    )

    event_url_map = {
        row["announcement_id"]: row.get("source_url")
        for row in event_states
    }
    evidence_by_url = by_url
    chronology_rows = []
    selected_attachment_ready_chronology_count = 0
    chronology_with_success_count = 0
    chronology_state_counts: Counter[str] = Counter()

    for chronology in selected["chronologies"]:
        chronology_id = str(chronology["chronology_id"])
        event_ids = [str(value) for value in chronology["announcement_ids"]]
        urls = sorted(
            {
                str(event_url_map[event_id])
                for event_id in event_ids
                if event_url_map.get(event_id)
            }
        )
        successful = [
            evidence_by_url[url]
            for url in urls
            if evidence_by_url[url].get("status") == "READY"
        ]
        failed_count = len(urls) - len(successful)
        if not urls:
            state = "NO_APPROVED_ATTACHMENT"
        else:
            selected_attachment_ready_chronology_count += 1
            if len(successful) == len(urls):
                state = "READY_DOCUMENT_EVIDENCE"
            elif successful:
                state = "DOCUMENT_FETCH_PARTIAL"
            else:
                state = "DOCUMENT_FETCH_FAILED"
            if successful:
                chronology_with_success_count += 1
        chronology_state_counts[state] += 1
        chronology_rows.append(
            {
                "chronology_id": chronology_id,
                "symbol": chronology.get("symbol"),
                "family": chronology.get("family"),
                "event_count": len(event_ids),
                "approved_url_count": len(urls),
                "successful_url_count": len(successful),
                "failed_url_count": failed_count,
                "document_ids": sorted(
                    {
                        str(row["document_id"])
                        for row in successful
                    }
                ),
                "source_state": state,
            }
        )

    chronology_success_ratio = (
        chronology_with_success_count / selected_attachment_ready_chronology_count
        if selected_attachment_ready_chronology_count
        else 1.0
    )
    gates = {
        "exact_selected_chronology_accounting": (
            len(chronology_rows) == EXPECTED_SELECTED_CHRONOLOGY_COUNT
        ),
        "exact_selected_event_accounting": (
            len(event_states) == len(selected["events"])
        ),
        "complete_approved_url_accounting": len(by_url) == unique_url_count,
        "minimum_unique_url_fetch_success_95pct": ready_url_ratio >= 0.95,
        "minimum_attachment_ready_event_resolution_95pct": ready_event_ratio >= 0.95,
        "minimum_attachment_ready_chronology_resolution_95pct": (
            chronology_success_ratio >= 0.95
        ),
        "deterministic_ready_document_identity": all(
            row.get("document_id") == row.get("raw_sha256")
            for row in ready_rows
        ),
        "approved_hosts_only": all(
            approved_attachment_url(row.get("source_url")) is not None
            for row in evidence_rows
        ),
    }

    output = {
        "schema_version": 1,
        "corpus_id": CORPUS_ID,
        "classification": "HISTORICAL_PRIORITY_FAMILY_OFFICIAL_DOCUMENT_CORPUS_NOT_PROBABILITY",
        "captured_at_utc": captured_at_utc,
        "source_d001_census_sha256": EXPECTED_D001_SHA,
        "selected_families": sorted(SELECTED_FAMILIES),
        "selected_chronology_count": len(chronology_rows),
        "selected_event_count": len(event_states),
        "attachment_ready_event_count": attachment_ready_event_count,
        "unique_approved_url_count": unique_url_count,
        "ready_url_count": ready_url_count,
        "ready_url_ratio": ready_url_ratio,
        "ready_event_count": len(ready_event_ids),
        "ready_event_ratio": ready_event_ratio,
        "attachment_ready_chronology_count": selected_attachment_ready_chronology_count,
        "chronology_with_successful_document_count": chronology_with_success_count,
        "chronology_success_ratio": chronology_success_ratio,
        "unique_document_id_count": len(document_ids),
        "document_family_counts": dict(sorted(family_counts.items())),
        "chronology_state_counts": dict(sorted(chronology_state_counts.items())),
        "fetch_failure_count": unique_url_count - ready_url_count,
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_historical_text_extraction": all(gates.values()),
        "event_states": event_states,
        "chronologies": sorted(
            chronology_rows,
            key=lambda row: (
                str(row["family"]),
                str(row["symbol"]),
                str(row["chronology_id"]),
            ),
        ),
        "documents": sorted(
            evidence_rows,
            key=lambda row: str(row["source_url"]),
        ),
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "expected_returns_calculated": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["corpus_sha256"] = digest(output)
    return output
