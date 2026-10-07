from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg006_evidence_pack import (
    MAX_ADDITIONAL_DOCUMENTS,
    _document_hit_summary,
    _iso_timestamp,
    _select_segments,
)
from marketlab.hg006_text import extract_verified_document
from marketlab.ss002_attachments import approved_attachment_url

TEXT_CORPUS_ID = "HG006-D001B-P2-v1"
EVIDENCE_PACK_ID = "HG006-S003-v1"
EXPECTED_SOURCE_CORPUS_ID = "HG006-D001A-P1-v1"
EXPECTED_SOURCE_CORPUS_SHA = (
    "3d47f24a5cbd4f551eae577ad0ed32fde7f5f15567ce775f60c0bb51ee9989dd"
)
EXPECTED_D001_ID = "HG006-D001-v1"
EXPECTED_D001_SHA = (
    "a267dab9cd646ffdc5230f1899a16a4138733413a3f05f438edf639f18ad41a5"
)
EXPECTED_CHRONOLOGY_COUNT = 1043
EXPECTED_ATTACHMENT_READY_CHRONOLOGY_COUNT = 1038
EXPECTED_DOCUMENT_COUNT = 5353
SHARD_COUNT = 16
PRIORITY_FAMILIES = frozenset(
    {"PREFERENTIAL_WARRANT", "SCHEME_REORGANISATION"}
)


def shard_for_document_id(document_id: str) -> int:
    if len(document_id) != 64:
        raise AlphaContractError("HG006 P2 document_id must be SHA-256")
    try:
        return int(document_id[:8], 16) % SHARD_COUNT
    except ValueError as exc:
        raise AlphaContractError("HG006 P2 document_id must be hex") from exc


def _validate_source_corpus(corpus: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    if corpus.get("corpus_id") != EXPECTED_SOURCE_CORPUS_ID:
        raise AlphaContractError("HG006 P2 requires frozen D001A-P1 corpus")
    if corpus.get("corpus_sha256") != EXPECTED_SOURCE_CORPUS_SHA:
        raise AlphaContractError("HG006 P2 D001A-P1 corpus SHA mismatch")
    if corpus.get("selected_chronology_count") != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 P2 source chronology count mismatch")
    if corpus.get("unique_document_id_count") != EXPECTED_DOCUMENT_COUNT:
        raise AlphaContractError("HG006 P2 source document count mismatch")
    if (
        corpus.get("attachment_ready_chronology_count")
        != EXPECTED_ATTACHMENT_READY_CHRONOLOGY_COUNT
    ):
        raise AlphaContractError("HG006 P2 source attachment-ready chronology mismatch")
    for field in (
        "historical_terminal_labels_opened",
        "completion_probabilities_assigned",
        "expected_returns_calculated",
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if corpus.get(field) is not False:
            raise AlphaContractError(f"HG006 P2 requires source {field}=false")

    documents = corpus.get("documents")
    chronologies = corpus.get("chronologies")
    if not isinstance(documents, list):
        raise AlphaContractError("HG006 P2 source documents unavailable")
    if not isinstance(chronologies, list) or len(chronologies) != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 P2 source chronologies unavailable")
    return documents, chronologies


def _validate_d001(d001: dict[str, Any]) -> list[dict[str, Any]]:
    if d001.get("census_id") != EXPECTED_D001_ID:
        raise AlphaContractError("HG006 S003 requires frozen D001 census")
    if d001.get("census_sha256") != EXPECTED_D001_SHA:
        raise AlphaContractError("HG006 S003 D001 census SHA mismatch")
    for field in (
        "completion_probabilities_assigned",
        "expected_returns_calculated",
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if d001.get(field) is not False:
            raise AlphaContractError(f"HG006 S003 requires D001 {field}=false")
    chronologies = d001.get("chronologies")
    if not isinstance(chronologies, list):
        raise AlphaContractError("HG006 S003 D001 chronologies unavailable")
    rows = [
        row
        for row in chronologies
        if isinstance(row, dict) and row.get("family") in PRIORITY_FAMILIES
    ]
    if len(rows) != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 S003 priority chronology count mismatch")
    return rows


def group_ready_documents(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "source_urls": set(),
            "chronology_ids": set(),
            "event_ids": set(),
            "symbols": set(),
            "families": set(),
            "document_family": "",
        }
    )
    for row in documents:
        if not isinstance(row, dict) or row.get("status") != "READY":
            continue
        document_id = str(row.get("document_id") or "")
        raw_sha = str(row.get("raw_sha256") or "")
        source_url = str(row.get("source_url") or "")
        document_family = str(row.get("document_family") or "")
        if (
            len(document_id) != 64
            or document_id != raw_sha
            or approved_attachment_url(source_url) is None
            or not document_family
        ):
            raise AlphaContractError("HG006 P2 READY source document is invalid")
        item = grouped[document_id]
        if item["document_family"] and item["document_family"] != document_family:
            raise AlphaContractError(
                f"HG006 P2 document family conflict: {document_id}"
            )
        item["document_family"] = document_family
        item["source_urls"].add(source_url)
        item["chronology_ids"].update(str(v) for v in row.get("chronology_ids", []))
        item["event_ids"].update(str(v) for v in row.get("event_ids", []))
        item["symbols"].update(str(v) for v in row.get("symbols", []))
        item["families"].update(str(v) for v in row.get("families", []))

    requests = []
    for document_id, item in sorted(grouped.items()):
        chronology_ids = sorted(item["chronology_ids"])
        event_ids = sorted(item["event_ids"])
        source_urls = sorted(item["source_urls"])
        symbols = sorted(item["symbols"])
        families = sorted(item["families"])
        if (
            not chronology_ids
            or not event_ids
            or not source_urls
            or not symbols
            or not set(families).issubset(PRIORITY_FAMILIES)
        ):
            raise AlphaContractError(
                f"HG006 P2 grouped document metadata incomplete: {document_id}"
            )
        requests.append(
            {
                "document_id": document_id,
                "shard_id": shard_for_document_id(document_id),
                "source_urls": source_urls,
                "document_family": item["document_family"],
                "chronology_ids": chronology_ids,
                "event_ids": event_ids,
                "symbols": symbols,
                "families": families,
            }
        )
    return requests


def full_document_requests(source_corpus: dict[str, Any]) -> list[dict[str, Any]]:
    documents, chronologies = _validate_source_corpus(source_corpus)
    chronology_ids = {
        str(row.get("chronology_id") or "")
        for row in chronologies
        if isinstance(row, dict)
    }
    if "" in chronology_ids or len(chronology_ids) != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 P2 source chronology IDs invalid")

    requests = group_ready_documents(documents)
    if len(requests) != EXPECTED_DOCUMENT_COUNT:
        raise AlphaContractError(
            f"HG006 P2 expected {EXPECTED_DOCUMENT_COUNT} document requests, "
            f"got {len(requests)}"
        )
    referenced = {
        chronology_id
        for request in requests
        for chronology_id in request["chronology_ids"]
    }
    if not referenced.issubset(chronology_ids):
        raise AlphaContractError("HG006 P2 document references unknown chronology")
    if len(referenced) != EXPECTED_ATTACHMENT_READY_CHRONOLOGY_COUNT:
        raise AlphaContractError(
            "HG006 P2 document chronology coverage differs from frozen source"
        )
    return requests


def build_full_text_corpus(
    *,
    source_corpus: dict[str, Any],
    extraction_rows: list[dict[str, Any]],
    captured_at_utc: str,
) -> dict[str, Any]:
    _, source_chronologies = _validate_source_corpus(source_corpus)
    requests = full_document_requests(source_corpus)
    expected = {row["document_id"]: row for row in requests}
    if len(expected) != EXPECTED_DOCUMENT_COUNT:
        raise AlphaContractError("HG006 P2 duplicate expected document identity")

    by_id: dict[str, dict[str, Any]] = {}
    for row in extraction_rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 P2 extraction rows must be objects")
        document_id = str(row.get("document_id") or "")
        if document_id not in expected or document_id in by_id:
            raise AlphaContractError("HG006 P2 extraction identity mismatch")
        if row.get("shard_id") != expected[document_id]["shard_id"]:
            raise AlphaContractError("HG006 P2 extraction shard mismatch")
        by_id[document_id] = row
    if set(by_id) != set(expected):
        raise AlphaContractError("HG006 P2 extraction rows incomplete")

    reproduced_count = 0
    ready_count = 0
    segment_ids: set[str] = set()
    segment_count = 0
    total_text_chars = 0
    state_counts: Counter[str] = Counter()
    shard_counts: Counter[int] = Counter()
    chronology_text_ready: set[str] = set()
    manifest_rows = []

    for request in requests:
        row = by_id[request["document_id"]]
        shard_counts[int(row["shard_id"])] += 1
        if row.get("hash_reproduced") is True:
            reproduced_count += 1
        state = str(row.get("extraction_state") or "UNKNOWN")
        state_counts[state] += 1
        if state == "READY":
            ready_count += 1
            chronology_text_ready.update(str(v) for v in request["chronology_ids"])
        segments = row.get("segments")
        if not isinstance(segments, list):
            raise AlphaContractError("HG006 P2 segments must be list")
        if state == "READY" and not segments:
            raise AlphaContractError("HG006 P2 READY document lacks segments")
        if state != "READY" and segments:
            raise AlphaContractError("HG006 P2 non-READY document carries segments")
        for segment in segments:
            if not isinstance(segment, dict):
                raise TypeError("HG006 P2 segment must be object")
            segment_id = str(segment.get("segment_id") or "")
            text = segment.get("text")
            text_sha = str(segment.get("text_sha256") or "")
            if (
                not segment_id
                or not isinstance(text, str)
                or len(text_sha) != 64
                or hashlib.sha256(text.encode("utf-8")).hexdigest() != text_sha
            ):
                raise AlphaContractError("HG006 P2 invalid text segment")
            if segment_id in segment_ids:
                raise AlphaContractError("HG006 P2 duplicate global segment ID")
            segment_ids.add(segment_id)
            segment_count += 1
            total_text_chars += len(text)

        manifest_rows.append(
            {
                "document_id": request["document_id"],
                "shard_id": row["shard_id"],
                "source_urls": request["source_urls"],
                "selected_source_url": row.get("selected_source_url"),
                "document_family": request["document_family"],
                "chronology_ids": request["chronology_ids"],
                "event_ids": request["event_ids"],
                "symbols": request["symbols"],
                "families": request["families"],
                "hash_reproduced": row.get("hash_reproduced"),
                "extraction_state": state,
                "segment_manifest_sha256": row.get("segment_manifest_sha256"),
                "segment_count": len(segments),
                "segment_ids": [str(seg["segment_id"]) for seg in segments],
            }
        )

    source_state_by_chronology = {
        str(row.get("chronology_id") or ""): str(row.get("source_state") or "")
        for row in source_chronologies
        if isinstance(row, dict)
    }
    if len(source_state_by_chronology) != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 P2 source chronology accounting invalid")

    chronology_states: Counter[str] = Counter()
    chronology_rows = []
    for chronology_id, source_state in sorted(source_state_by_chronology.items()):
        if chronology_id in chronology_text_ready:
            state = "TEXT_READY"
        elif source_state == "NO_APPROVED_ATTACHMENT":
            state = "NO_APPROVED_ATTACHMENT"
        else:
            state = "DOCUMENT_PRESENT_TEXT_FAILED"
        chronology_states[state] += 1
        chronology_rows.append(
            {
                "chronology_id": chronology_id,
                "source_state": source_state,
                "text_state": state,
            }
        )

    document_count = len(requests)
    reproduced_ratio = reproduced_count / document_count
    ready_ratio = ready_count / reproduced_count if reproduced_count else 0.0
    chronology_text_ratio = (
        chronology_states["TEXT_READY"]
        / EXPECTED_ATTACHMENT_READY_CHRONOLOGY_COUNT
    )
    gates = {
        "complete_1043_chronology_accounting": (
            len(chronology_rows) == EXPECTED_CHRONOLOGY_COUNT
        ),
        "complete_5353_document_accounting": (
            len(by_id) == EXPECTED_DOCUMENT_COUNT
        ),
        "minimum_hash_reproduction_95pct": reproduced_ratio >= 0.95,
        "minimum_text_ready_90pct": ready_ratio >= 0.90,
        "minimum_attachment_ready_chronology_text_coverage_95pct": (
            chronology_text_ratio >= 0.95
        ),
        "deterministic_segment_identity": segment_count == len(segment_ids),
    }

    output = {
        "schema_version": 1,
        "corpus_id": TEXT_CORPUS_ID,
        "classification": "FULL_PRIORITY_HISTORICAL_TEXT_CORPUS_NOT_PROBABILITY",
        "captured_at_utc": captured_at_utc,
        "source_document_corpus_sha256": EXPECTED_SOURCE_CORPUS_SHA,
        "chronology_count": EXPECTED_CHRONOLOGY_COUNT,
        "attachment_ready_chronology_count": (
            EXPECTED_ATTACHMENT_READY_CHRONOLOGY_COUNT
        ),
        "selected_document_count": EXPECTED_DOCUMENT_COUNT,
        "hash_reproduced_document_count": reproduced_count,
        "hash_reproduced_ratio": reproduced_ratio,
        "text_ready_document_count": ready_count,
        "text_ready_ratio_of_reproduced": ready_ratio,
        "chronology_state_counts": dict(sorted(chronology_states.items())),
        "attachment_ready_chronology_text_ready_ratio": chronology_text_ratio,
        "segment_count": segment_count,
        "total_text_char_count": total_text_chars,
        "extraction_state_counts": dict(sorted(state_counts.items())),
        "document_counts_by_shard": {
            str(key): value for key, value in sorted(shard_counts.items())
        },
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_full_stage_evidence_pack": all(gates.values()),
        "chronologies": chronology_rows,
        "documents": sorted(manifest_rows, key=lambda row: row["document_id"]),
        "expanded_population_terminal_labels_opened": False,
        "expanded_population_completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["corpus_sha256"] = digest(output)
    return output


def build_full_stage_evidence_pack(
    *,
    d001: dict[str, Any],
    text_summary: dict[str, Any],
    text_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    chronology_rows = _validate_d001(d001)
    if text_summary.get("corpus_id") != TEXT_CORPUS_ID:
        raise AlphaContractError("HG006 S003 requires frozen D001B-P2 corpus")
    if text_summary.get("chronology_count") != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 S003 text chronology count mismatch")
    if text_summary.get("feasibility_pass") is not True:
        raise AlphaContractError("HG006 S003 requires passed D001B-P2 corpus")
    for field in (
        "expanded_population_terminal_labels_opened",
        "expanded_population_completion_probabilities_assigned",
        "return_outcomes_opened",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if text_summary.get(field) is not False:
            raise AlphaContractError(f"HG006 S003 requires D001B-P2 {field}=false")

    selected_by_id = {
        str(row["chronology_id"]): row
        for row in chronology_rows
    }
    if len(selected_by_id) != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 S003 chronology IDs must be unique")

    events = d001.get("events")
    if not isinstance(events, list):
        raise AlphaContractError("HG006 S003 D001 events unavailable")
    event_index: dict[str, dict[str, Any]] = {}
    for row in events:
        if not isinstance(row, dict):
            raise TypeError("HG006 S003 D001 event must be object")
        event_id = str(row.get("announcement_id") or "")
        if not event_id or event_id in event_index:
            raise AlphaContractError("HG006 S003 D001 event IDs must be unique")
        event_index[event_id] = row

    docs_by_chronology: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_doc_ids: set[str] = set()
    for row in text_rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 S003 text row must be object")
        doc_id = str(row.get("document_id") or "")
        if not doc_id or doc_id in seen_doc_ids:
            raise AlphaContractError("HG006 S003 document IDs must be unique")
        seen_doc_ids.add(doc_id)
        chronology_ids = row.get("chronology_ids")
        if not isinstance(chronology_ids, list):
            raise AlphaContractError("HG006 S003 chronology_ids unavailable")
        for chronology_id_raw in chronology_ids:
            chronology_id = str(chronology_id_raw)
            if chronology_id in selected_by_id:
                docs_by_chronology[chronology_id].append(row)

    evidence_rows = []
    state_counts: Counter[str] = Counter()
    total_retained_docs = 0
    total_retained_segments = 0

    for chronology_id, chronology in sorted(selected_by_id.items()):
        symbol = str(chronology["symbol"])
        family = str(chronology["family"])
        chronology_event_ids = {str(v) for v in chronology["announcement_ids"]}
        source_docs = docs_by_chronology.get(chronology_id, [])

        doc_rows = []
        for doc in source_docs:
            if doc.get("extraction_state") != "READY":
                continue
            if symbol not in {str(v) for v in doc.get("symbols", [])}:
                raise AlphaContractError(
                    f"HG006 S003 document crosses symbol: {chronology_id}"
                )
            if family not in {str(v) for v in doc.get("families", [])}:
                raise AlphaContractError(
                    f"HG006 S003 document crosses family: {chronology_id}"
                )
            linked_event_ids = sorted(
                chronology_event_ids.intersection(
                    str(v) for v in doc.get("event_ids", [])
                )
            )
            if not linked_event_ids:
                raise AlphaContractError(
                    f"HG006 S003 document has no chronology event link: {chronology_id}"
                )
            timestamps = [
                _iso_timestamp(event_index[event_id]["exchange_published_at_utc"])
                for event_id in linked_event_ids
            ]
            timestamp = min(timestamps)
            segments = doc.get("segments")
            if not isinstance(segments, list):
                raise AlphaContractError("HG006 S003 READY doc segments unavailable")
            hits = _document_hit_summary(segments)
            doc_rows.append(
                {
                    "document_id": str(doc["document_id"]),
                    "chronology_timestamp_utc": timestamp,
                    "event_ids": linked_event_ids,
                    "segment_source_count": len(segments),
                    "hit_summary": hits,
                    "segments": segments,
                    "segment_manifest_sha256": str(
                        doc.get("segment_manifest_sha256") or ""
                    ),
                }
            )

        if not doc_rows:
            state = "TEXT_UNAVAILABLE"
            retained_docs: list[dict[str, Any]] = []
        else:
            state = "EVIDENCE_READY"
            doc_rows.sort(
                key=lambda row: (
                    row["chronology_timestamp_utc"],
                    row["document_id"],
                )
            )
            keep_ids = {
                doc_rows[0]["document_id"],
                doc_rows[-1]["document_id"],
            }
            keep_ids.update(
                row["document_id"]
                for row in doc_rows
                if row["hit_summary"]["terminal_match"]
            )
            candidates = [
                row
                for row in doc_rows
                if row["document_id"] not in keep_ids
                and row["hit_summary"]["total_phrase_occurrences"] > 0
            ]
            candidates.sort(
                key=lambda row: (
                    -int(row["hit_summary"]["distinct_group_count"]),
                    -int(row["hit_summary"]["total_phrase_occurrences"]),
                    row["chronology_timestamp_utc"],
                    row["document_id"],
                )
            )
            keep_ids.update(
                row["document_id"]
                for row in candidates[:MAX_ADDITIONAL_DOCUMENTS]
            )
            retained_docs = []
            for row in doc_rows:
                if row["document_id"] not in keep_ids:
                    continue
                selected_segments = _select_segments(row["segments"])
                if not selected_segments:
                    raise AlphaContractError(
                        "HG006 S003 retained document has no selected segment"
                    )
                retained_docs.append(
                    {
                        "document_id": row["document_id"],
                        "chronology_timestamp_utc": row[
                            "chronology_timestamp_utc"
                        ],
                        "event_ids": row["event_ids"],
                        "segment_manifest_sha256": row[
                            "segment_manifest_sha256"
                        ],
                        "source_segment_count": row["segment_source_count"],
                        "hit_summary": row["hit_summary"],
                        "selected_segments": selected_segments,
                    }
                )

        total_retained_docs += len(retained_docs)
        total_retained_segments += sum(
            len(row["selected_segments"]) for row in retained_docs
        )
        state_counts[state] += 1
        evidence = {
            "chronology_id": chronology_id,
            "symbol": symbol,
            "family": family,
            "source_event_count": int(chronology["event_count"]),
            "source_document_count": len(source_docs),
            "text_ready_source_document_count": len(doc_rows),
            "evidence_state": state,
            "retained_document_count": len(retained_docs),
            "retained_documents": retained_docs,
        }
        evidence["chronology_evidence_sha256"] = digest(evidence)
        evidence_rows.append(evidence)

    unavailable = [
        row["chronology_id"]
        for row in evidence_rows
        if row["evidence_state"] == "TEXT_UNAVAILABLE"
    ]
    gates = {
        "complete_1043_chronology_accounting": (
            len(evidence_rows) == EXPECTED_CHRONOLOGY_COUNT
        ),
        "minimum_95pct_evidence_ready": (
            state_counts["EVIDENCE_READY"]
            / EXPECTED_ATTACHMENT_READY_CHRONOLOGY_COUNT
            >= 0.95
        ),
        "retained_documents_have_segments": all(
            all(doc["selected_segments"] for doc in row["retained_documents"])
            for row in evidence_rows
            if row["evidence_state"] == "EVIDENCE_READY"
        ),
    }

    output = {
        "schema_version": 1,
        "pack_id": EVIDENCE_PACK_ID,
        "classification": "FULL_PRIORITY_HISTORICAL_STAGE_EVIDENCE_PACK_NOT_LABELS",
        "source_d001_census_sha256": EXPECTED_D001_SHA,
        "source_text_corpus_sha256": text_summary.get("corpus_sha256"),
        "chronology_count": len(evidence_rows),
        "state_counts": dict(sorted(state_counts.items())),
        "text_unavailable_chronology_ids": sorted(unavailable),
        "retained_document_count": total_retained_docs,
        "retained_segment_count": total_retained_segments,
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_full_historical_l001": all(gates.values()),
        "chronologies": evidence_rows,
        "expanded_population_terminal_labels_opened": False,
        "expanded_population_completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["pack_sha256"] = digest(output)
    return output


__all__ = [
    "SHARD_COUNT",
    "TEXT_CORPUS_ID",
    "EVIDENCE_PACK_ID",
    "shard_for_document_id",
    "full_document_requests",
    "build_full_text_corpus",
    "build_full_stage_evidence_pack",
    "extract_verified_document",
]
