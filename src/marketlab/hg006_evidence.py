from __future__ import annotations

import hashlib

from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest

CORPUS_ID = "HG006-S001-v1"
EXPECTED_D001_ID = "HG006-D001-v1"
EXPECTED_D001_SHA = "a267dab9cd646ffdc5230f1899a16a4138733413a3f05f438edf639f18ad41a5"
EXPECTED_CHRONOLOGY_COUNT = 1607
EXPECTED_HISTORICAL_EVENT_COUNT = 8896
EXPECTED_APPROVED_URL_COUNT = 8763
SHARD_COUNT = 8
SHARD_IDS = tuple(f"S{index:02d}" for index in range(SHARD_COUNT))


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def validate_d001_census(census: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if census.get("census_id") != EXPECTED_D001_ID:
        raise AlphaContractError("HG006 S001 requires frozen D001 census")
    if census.get("census_sha256") != EXPECTED_D001_SHA:
        raise AlphaContractError("HG006 S001 D001 census SHA mismatch")
    if census.get("historical_chronology_count") != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 S001 historical chronology count mismatch")
    if census.get("feasibility_pass") is not True:
        raise AlphaContractError("HG006 S001 requires passed D001 census")
    if census.get("completion_probabilities_assigned") is not False:
        raise AlphaContractError("HG006 S001 refuses probability-bearing D001 census")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if census.get(field) is not False:
            raise AlphaContractError(f"HG006 S001 requires D001 {field}=false")

    events = census.get("events")
    chronologies = census.get("chronologies")
    if not isinstance(events, list) or not isinstance(chronologies, list):
        raise AlphaContractError("HG006 S001 D001 event/chronology rows unavailable")
    if len(chronologies) != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 S001 chronology rows incomplete")
    return events, chronologies


def url_shard_id(source_url: str) -> str:
    if not source_url:
        raise AlphaContractError("HG006 S001 source URL required for sharding")
    url_sha = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
    value = int(url_sha[:16], 16) % SHARD_COUNT
    return f"S{value:02d}"


def historical_evidence_topology(
    census: dict[str, Any],
    *,
    strict_counts: bool = True,
) -> dict[str, Any]:
    events, chronologies = validate_d001_census(census)
    event_by_id: dict[str, dict[str, Any]] = {}
    for row in events:
        if not isinstance(row, dict):
            raise TypeError("HG006 S001 D001 event rows must be objects")
        event_id = _clean(row.get("announcement_id"))
        if not event_id or event_id in event_by_id:
            raise AlphaContractError("HG006 S001 D001 event IDs must be unique")
        event_by_id[event_id] = row

    historical_event_ids: set[str] = set()
    chronology_by_id: dict[str, dict[str, Any]] = {}
    event_to_chronologies: dict[str, set[str]] = defaultdict(set)
    event_to_families: dict[str, set[str]] = defaultdict(set)
    for chronology in chronologies:
        if not isinstance(chronology, dict):
            raise TypeError("HG006 S001 chronology rows must be objects")
        chronology_id = _clean(chronology.get("chronology_id"))
        symbol = _clean(chronology.get("symbol")).upper()
        family = _clean(chronology.get("family"))
        event_ids = chronology.get("announcement_ids")
        if (
            not chronology_id
            or chronology_id in chronology_by_id
            or not symbol
            or not family
            or not isinstance(event_ids, list)
            or not event_ids
        ):
            raise AlphaContractError("HG006 S001 chronology identity is incomplete")
        ids = [str(value) for value in event_ids]
        if len(ids) != len(set(ids)):
            raise AlphaContractError(f"{chronology_id}: duplicate event IDs")
        if any(event_id not in event_by_id for event_id in ids):
            raise AlphaContractError(f"{chronology_id}: unknown D001 event")
        chronology_by_id[chronology_id] = chronology
        historical_event_ids.update(ids)
        for event_id in ids:
            event_to_chronologies[event_id].add(chronology_id)
            event_to_families[event_id].add(family)

    by_url: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {
            "event_ids": set(),
            "chronology_ids": set(),
            "symbols": set(),
            "families": set(),
        }
    )
    event_states = []
    for event_id in sorted(historical_event_ids):
        event = event_by_id[event_id]
        url = _clean(event.get("approved_attachment_url"))
        symbol = _clean(event.get("symbol")).upper()
        if url:
            item = by_url[url]
            item["event_ids"].add(event_id)
            item["chronology_ids"].update(event_to_chronologies[event_id])
            item["symbols"].add(symbol)
            item["families"].update(event_to_families[event_id])
            state = "APPROVED_URL"
        else:
            state = "NO_APPROVED_ATTACHMENT"
        event_states.append(
            {
                "announcement_id": event_id,
                "symbol": symbol,
                "attachment_state": state,
                "source_url": url or None,
                "chronology_ids": sorted(event_to_chronologies[event_id]),
                "families": sorted(event_to_families[event_id]),
            }
        )

    requests = []
    shard_counts: Counter[str] = Counter()
    for url, values in sorted(by_url.items()):
        shard_id = url_shard_id(url)
        shard_counts[shard_id] += 1
        requests.append(
            {
                "source_url": url,
                "shard_id": shard_id,
                "event_ids": sorted(values["event_ids"]),
                "chronology_ids": sorted(values["chronology_ids"]),
                "symbols": sorted(values["symbols"]),
                "families": sorted(values["families"]),
            }
        )

    if strict_counts:
        if len(historical_event_ids) != EXPECTED_HISTORICAL_EVENT_COUNT:
            raise AlphaContractError(
                "HG006 S001 historical event count differs from frozen source audit"
            )
        if len(requests) != EXPECTED_APPROVED_URL_COUNT:
            raise AlphaContractError(
                "HG006 S001 approved URL count differs from frozen source audit"
            )

    return {
        "historical_event_ids": sorted(historical_event_ids),
        "chronology_by_id": chronology_by_id,
        "event_states": event_states,
        "requests": requests,
        "shard_counts": dict(sorted(shard_counts.items())),
    }


def shard_requests(census: dict[str, Any], shard_id: str) -> list[dict[str, Any]]:
    if shard_id not in SHARD_IDS:
        raise AlphaContractError(f"HG006 S001 unknown shard: {shard_id}")
    topology = historical_evidence_topology(census)
    return [
        row
        for row in topology["requests"]
        if row["shard_id"] == shard_id
    ]


def seal_shard_manifest(
    *,
    census: dict[str, Any],
    shard_id: str,
    evidence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = shard_requests(census, shard_id)
    expected_urls = {row["source_url"] for row in expected}
    rows_by_url: dict[str, dict[str, Any]] = {}
    for row in evidence_rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 S001 evidence rows must be objects")
        url = _clean(row.get("source_url"))
        if not url or url in rows_by_url:
            raise AlphaContractError("HG006 S001 shard evidence URLs must be unique")
        rows_by_url[url] = row
    if set(rows_by_url) != expected_urls:
        raise AlphaContractError("HG006 S001 shard URL accounting mismatch")

    ready = sum(row.get("fetch_state") == "READY" for row in evidence_rows)
    text_ready = sum(
        row.get("fetch_state") == "READY"
        and row.get("extraction_state") == "READY"
        for row in evidence_rows
    )
    output = {
        "schema_version": 1,
        "corpus_id": CORPUS_ID,
        "shard_id": shard_id,
        "source_d001_census_sha256": EXPECTED_D001_SHA,
        "expected_url_count": len(expected),
        "evidence_url_count": len(evidence_rows),
        "ready_url_count": ready,
        "text_ready_url_count": text_ready,
        "rows": sorted(evidence_rows, key=lambda row: str(row["source_url"])),
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["shard_sha256"] = digest(output)
    return output


def combine_historical_evidence(
    *,
    census: dict[str, Any],
    shard_manifests: list[dict[str, Any]],
    document_rows: list[dict[str, Any]],
    captured_at_utc: str,
) -> dict[str, Any]:
    topology = historical_evidence_topology(census)
    expected_requests = topology["requests"]
    expected_urls = {row["source_url"] for row in expected_requests}
    request_by_url = {row["source_url"]: row for row in expected_requests}

    if len(shard_manifests) != SHARD_COUNT:
        raise AlphaContractError("HG006 S001 requires eight shard manifests")
    shard_ids = [str(row.get("shard_id") or "") for row in shard_manifests]
    if sorted(shard_ids) != list(SHARD_IDS):
        raise AlphaContractError("HG006 S001 shard manifest set mismatch")

    manifest_urls: set[str] = set()
    for manifest in shard_manifests:
        if manifest.get("corpus_id") != CORPUS_ID:
            raise AlphaContractError("HG006 S001 shard corpus identity mismatch")
        rows = manifest.get("rows")
        if not isinstance(rows, list):
            raise AlphaContractError("HG006 S001 shard rows unavailable")
        for row in rows:
            url = _clean(row.get("source_url"))
            if url in manifest_urls:
                raise AlphaContractError("HG006 S001 URL appears in multiple shards")
            if url_shard_id(url) != manifest["shard_id"]:
                raise AlphaContractError("HG006 S001 URL assigned to wrong shard")
            manifest_urls.add(url)
    if manifest_urls != expected_urls:
        raise AlphaContractError("HG006 S001 combined shard URL coverage mismatch")

    row_by_url: dict[str, dict[str, Any]] = {}
    for row in document_rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 S001 document rows must be objects")
        url = _clean(row.get("source_url"))
        if not url or url in row_by_url:
            raise AlphaContractError("HG006 S001 document URL rows must be unique")
        row_by_url[url] = row
    if set(row_by_url) != expected_urls:
        raise AlphaContractError("HG006 S001 document URL coverage mismatch")

    ready_url_count = 0
    fetched_document_ids: set[str] = set()
    text_ready_document_ids: set[str] = set()
    pdf_document_ids: set[str] = set()
    pdf_text_ready_ids: set[str] = set()
    chronology_ready_docs: dict[str, set[str]] = defaultdict(set)
    chronology_text_docs: dict[str, set[str]] = defaultdict(set)
    by_document: dict[str, dict[str, Any]] = {}

    for url in sorted(expected_urls):
        row = row_by_url[url]
        request = request_by_url[url]
        if row.get("fetch_state") != "READY":
            continue
        ready_url_count += 1
        document_id = _clean(row.get("document_id"))
        raw_sha = _clean(row.get("raw_sha256"))
        if not document_id or document_id != raw_sha:
            raise AlphaContractError("HG006 S001 READY raw document identity mismatch")
        fetched_document_ids.add(document_id)
        family = _clean(row.get("document_family"))
        if family == "PDF":
            pdf_document_ids.add(document_id)
        if row.get("extraction_state") == "READY":
            text_ready_document_ids.add(document_id)
            if family == "PDF":
                pdf_text_ready_ids.add(document_id)

        for chronology_id in request["chronology_ids"]:
            chronology_ready_docs[chronology_id].add(document_id)
            if row.get("extraction_state") == "READY":
                chronology_text_docs[chronology_id].add(document_id)

        doc = by_document.setdefault(
            document_id,
            {
                "document_id": document_id,
                "document_family": family,
                "source_urls": set(),
                "event_ids": set(),
                "chronology_ids": set(),
                "symbols": set(),
                "families": set(),
                "extraction_state": row.get("extraction_state"),
                "segment_manifest_sha256": row.get("segment_manifest_sha256"),
                "segment_content_sha256": row.get("segment_content_sha256"),
                "segment_count": row.get("segment_count"),
                "text_artifact_paths": set(),
            },
        )
        if doc["document_family"] != family:
            raise AlphaContractError("HG006 S001 document family conflict")
        if (
            doc["extraction_state"] != row.get("extraction_state")
            or doc["segment_content_sha256"] != row.get("segment_content_sha256")
            or doc["segment_count"] != row.get("segment_count")
        ):
            raise AlphaContractError("HG006 S001 duplicate document extraction conflict")
        if str(url) < min(doc["source_urls"] or {str(url)}):
            doc["segment_manifest_sha256"] = row.get("segment_manifest_sha256")
        doc["source_urls"].add(url)
        doc["event_ids"].update(request["event_ids"])
        doc["chronology_ids"].update(request["chronology_ids"])
        doc["symbols"].update(request["symbols"])
        doc["families"].update(request["families"])
        if row.get("text_artifact_path"):
            doc["text_artifact_paths"].add(str(row["text_artifact_path"]))

    chronologies = topology["chronology_by_id"]
    chronology_rows = []
    attachment_chronology_count = 0
    ready_chronology_count = 0
    text_ready_chronology_count = 0
    for chronology_id, chronology in sorted(chronologies.items()):
        has_attachment = bool(chronology.get("has_approved_attachment"))
        if has_attachment:
            attachment_chronology_count += 1
        ready_docs = sorted(chronology_ready_docs.get(chronology_id, set()))
        text_docs = sorted(chronology_text_docs.get(chronology_id, set()))
        if ready_docs:
            ready_chronology_count += 1
        if text_docs:
            text_ready_chronology_count += 1
        chronology_rows.append(
            {
                "chronology_id": chronology_id,
                "symbol": chronology.get("symbol"),
                "family": chronology.get("family"),
                "has_approved_attachment": has_attachment,
                "ready_document_ids": ready_docs,
                "text_ready_document_ids": text_docs,
                "evidence_state": (
                    "TEXT_READY"
                    if text_docs
                    else "DOCUMENT_READY_NO_TEXT"
                    if ready_docs
                    else "NO_FETCHED_DOCUMENT"
                    if has_attachment
                    else "NO_APPROVED_ATTACHMENT"
                ),
            }
        )

    unique_url_count = len(expected_urls)
    fetch_ratio = ready_url_count / unique_url_count
    chronology_fetch_ratio = (
        ready_chronology_count / attachment_chronology_count
        if attachment_chronology_count
        else 1.0
    )
    unique_document_count = len(fetched_document_ids)
    text_ratio = (
        len(text_ready_document_ids) / unique_document_count
        if unique_document_count
        else 0.0
    )
    pdf_text_ratio = (
        len(pdf_text_ready_ids) / len(pdf_document_ids)
        if pdf_document_ids
        else 1.0
    )

    documents = []
    for document_id, row in sorted(by_document.items()):
        documents.append(
            {
                **row,
                "source_urls": sorted(row["source_urls"]),
                "event_ids": sorted(row["event_ids"]),
                "chronology_ids": sorted(row["chronology_ids"]),
                "symbols": sorted(row["symbols"]),
                "families": sorted(row["families"]),
                "text_artifact_paths": sorted(row["text_artifact_paths"]),
            }
        )

    threshold_passes = {
        "complete_chronology_accounting": len(chronology_rows) == EXPECTED_CHRONOLOGY_COUNT,
        "complete_frozen_url_sharding": len(manifest_urls) == EXPECTED_APPROVED_URL_COUNT,
        "minimum_unique_url_fetch_success_95pct": fetch_ratio >= 0.95,
        "minimum_attachment_chronology_fetch_95pct": chronology_fetch_ratio >= 0.95,
        "minimum_fetched_document_text_ready_90pct": text_ratio >= 0.90,
        "minimum_pdf_text_ready_92pct": pdf_text_ratio >= 0.92,
    }

    output = {
        "schema_version": 1,
        "corpus_id": CORPUS_ID,
        "classification": "HISTORICAL_OFFICIAL_DOCUMENT_TEXT_EVIDENCE_NOT_OUTCOME",
        "captured_at_utc": captured_at_utc,
        "source_d001_census_sha256": EXPECTED_D001_SHA,
        "historical_chronology_count": EXPECTED_CHRONOLOGY_COUNT,
        "historical_event_count": EXPECTED_HISTORICAL_EVENT_COUNT,
        "unique_approved_url_count": unique_url_count,
        "ready_url_count": ready_url_count,
        "ready_url_ratio": fetch_ratio,
        "attachment_chronology_count": attachment_chronology_count,
        "ready_chronology_count": ready_chronology_count,
        "ready_chronology_ratio_of_attachment_ready": chronology_fetch_ratio,
        "unique_fetched_document_count": unique_document_count,
        "text_ready_document_count": len(text_ready_document_ids),
        "text_ready_document_ratio": text_ratio,
        "pdf_document_count": len(pdf_document_ids),
        "pdf_text_ready_document_count": len(pdf_text_ready_ids),
        "pdf_text_ready_ratio": pdf_text_ratio,
        "shard_counts": topology["shard_counts"],
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_hg006_l001": all(threshold_passes.values()),
        "chronologies": chronology_rows,
        "documents": documents,
        "event_states": topology["event_states"],
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["corpus_sha256"] = digest(output)
    return output
