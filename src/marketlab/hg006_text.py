from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_text import extract_document_text

CORPUS_ID = "HG006-D001B-v1"
EXPECTED_SELECTION_ID = "HG006-S001-v1"
EXPECTED_SELECTION_SHA = "4bc9659c1111f0694bbbec8754b6193116871367b78f126c39e09bc329c961f5"
EXPECTED_SELECTION_COUNT = 300
EXPECTED_SOURCE_CORPUS_ID = "HG006-D001A-P1-v1"
EXPECTED_SOURCE_CORPUS_SHA = "3d47f24a5cbd4f551eae577ad0ed32fde7f5f15567ce775f60c0bb51ee9989dd"
SHARD_COUNT = 8


def shard_for_document_id(document_id: str) -> int:
    if len(document_id) != 64:
        raise AlphaContractError("HG006 D001B document_id must be SHA-256")
    try:
        return int(document_id[:8], 16) % SHARD_COUNT
    except ValueError as exc:
        raise AlphaContractError("HG006 D001B document_id must be hex") from exc


def _validate_selection(selection: dict[str, Any]) -> list[dict[str, Any]]:
    if selection.get("selection_id") != EXPECTED_SELECTION_ID:
        raise AlphaContractError("HG006 D001B requires frozen S001 selection")
    if selection.get("selection_sha256") != EXPECTED_SELECTION_SHA:
        raise AlphaContractError("HG006 D001B selection SHA mismatch")
    if selection.get("selected_chronology_count") != EXPECTED_SELECTION_COUNT:
        raise AlphaContractError("HG006 D001B selection count mismatch")
    for field in (
        "historical_terminal_labels_opened",
        "completion_probabilities_assigned",
        "expected_returns_calculated",
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if selection.get(field) is not False:
            raise AlphaContractError(f"HG006 D001B requires S001 {field}=false")
    rows = selection.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_SELECTION_COUNT:
        raise AlphaContractError("HG006 D001B S001 rows unavailable")
    return rows


def _validate_source_corpus(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    if corpus.get("corpus_id") != EXPECTED_SOURCE_CORPUS_ID:
        raise AlphaContractError("HG006 D001B requires frozen D001A-P1 corpus")
    if corpus.get("corpus_sha256") != EXPECTED_SOURCE_CORPUS_SHA:
        raise AlphaContractError("HG006 D001B source corpus SHA mismatch")
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
            raise AlphaContractError(f"HG006 D001B requires source {field}=false")
    rows = corpus.get("documents")
    if not isinstance(rows, list):
        raise AlphaContractError("HG006 D001B source documents unavailable")
    return rows


def selected_document_requests(
    selection: dict[str, Any],
    source_corpus: dict[str, Any],
) -> list[dict[str, Any]]:
    selection_rows = _validate_selection(selection)
    source_rows = _validate_source_corpus(source_corpus)

    selected_ids = {
        str(row.get("chronology_id") or "")
        for row in selection_rows
        if isinstance(row, dict)
    }
    if "" in selected_ids or len(selected_ids) != EXPECTED_SELECTION_COUNT:
        raise AlphaContractError("HG006 D001B selected chronology IDs invalid")

    grouped: dict[str, dict[str, set[str] | str]] = defaultdict(
        lambda: {
            "urls": set(),
            "chronology_ids": set(),
            "event_ids": set(),
            "symbols": set(),
            "families": set(),
            "document_family": "",
        }
    )
    chronology_with_doc: set[str] = set()

    for row in source_rows:
        if not isinstance(row, dict) or row.get("status") != "READY":
            continue
        chronology_ids = {
            str(value)
            for value in row.get("chronology_ids", [])
            if str(value) in selected_ids
        }
        if not chronology_ids:
            continue

        document_id = str(row.get("document_id") or "")
        source_url = str(row.get("source_url") or "")
        family = str(row.get("document_family") or "")
        if len(document_id) != 64 or not source_url or not family:
            raise AlphaContractError("HG006 D001B READY source document incomplete")

        item = grouped[document_id]
        existing_family = str(item["document_family"])
        if existing_family and existing_family != family:
            raise AlphaContractError(
                f"HG006 D001B document family conflict: {document_id}"
            )
        item["document_family"] = family
        cast_urls = item["urls"]
        cast_chron = item["chronology_ids"]
        cast_events = item["event_ids"]
        cast_symbols = item["symbols"]
        cast_families = item["families"]
        assert isinstance(cast_urls, set)
        assert isinstance(cast_chron, set)
        assert isinstance(cast_events, set)
        assert isinstance(cast_symbols, set)
        assert isinstance(cast_families, set)
        cast_urls.add(source_url)
        cast_chron.update(chronology_ids)
        cast_events.update(str(value) for value in row.get("event_ids", []))
        cast_symbols.update(str(value) for value in row.get("symbols", []))
        cast_families.update(str(value) for value in row.get("families", []))
        chronology_with_doc.update(chronology_ids)

    requests = []
    for document_id, item in sorted(grouped.items()):
        urls = sorted(item["urls"])
        chronology_ids = sorted(item["chronology_ids"])
        event_ids = sorted(item["event_ids"])
        symbols = sorted(item["symbols"])
        families = sorted(item["families"])
        requests.append(
            {
                "document_id": document_id,
                "shard_id": shard_for_document_id(document_id),
                "source_urls": urls,
                "document_family": item["document_family"],
                "chronology_ids": chronology_ids,
                "event_ids": event_ids,
                "symbols": symbols,
                "families": families,
            }
        )

    return requests


def extract_verified_document(
    request: dict[str, Any],
    *,
    raw: bytes | None,
    source_url: str | None,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    document_id = str(request["document_id"])
    if raw is None or source_url is None:
        return {
            **request,
            "hash_reproduced": False,
            "selected_source_url": source_url,
            "attempts": attempts,
            "extraction_state": "HASH_REPRODUCTION_FAILED",
            "details": {},
            "segments": [],
            "segment_manifest_sha256": digest(
                {
                    "document_id": document_id,
                    "state": "HASH_REPRODUCTION_FAILED",
                    "attempts": attempts,
                }
            ),
        }

    sha = hashlib.sha256(raw).hexdigest()
    if sha != document_id:
        raise AlphaContractError("HG006 D001B accepted raw bytes do not match document_id")
    text_row = extract_document_text(
        document_id=document_id,
        raw=raw,
        d002_family=str(request["document_family"]),
        source_url=source_url,
    )
    return {
        **request,
        "hash_reproduced": True,
        "selected_source_url": source_url,
        "attempts": attempts,
        "extraction_state": text_row["extraction_state"],
        "details": text_row["details"],
        "segments": text_row["segments"],
        "segment_manifest_sha256": text_row["segment_manifest_sha256"],
    }


def build_selected_text_corpus(
    *,
    selection: dict[str, Any],
    source_corpus: dict[str, Any],
    extraction_rows: list[dict[str, Any]],
    captured_at_utc: str,
) -> dict[str, Any]:
    requests = selected_document_requests(selection, source_corpus)
    expected = {row["document_id"]: row for row in requests}
    if len(expected) != len(requests):
        raise AlphaContractError("HG006 D001B duplicate request document ID")

    by_id: dict[str, dict[str, Any]] = {}
    for row in extraction_rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 D001B extraction rows must be objects")
        doc_id = str(row.get("document_id") or "")
        if doc_id not in expected or doc_id in by_id:
            raise AlphaContractError("HG006 D001B extraction identity mismatch")
        if row.get("shard_id") != expected[doc_id]["shard_id"]:
            raise AlphaContractError("HG006 D001B shard identity mismatch")
        by_id[doc_id] = row
    if set(by_id) != set(expected):
        raise AlphaContractError("HG006 D001B extraction rows incomplete")

    selected_ids = {
        str(row["chronology_id"])
        for row in _validate_selection(selection)
    }
    chrono_any_doc: set[str] = set()
    chrono_text_ready: set[str] = set()
    reproduced_count = 0
    ready_count = 0
    segment_ids: set[str] = set()
    segment_count = 0
    total_text_chars = 0
    state_counts: Counter[str] = Counter()
    shard_counts: Counter[int] = Counter()
    manifest_rows = []

    for request in requests:
        row = by_id[request["document_id"]]
        chrono_ids = set(request["chronology_ids"])
        chrono_any_doc.update(chrono_ids)
        shard_counts[int(row["shard_id"])] += 1
        if row.get("hash_reproduced") is True:
            reproduced_count += 1
        state = str(row.get("extraction_state") or "UNKNOWN")
        state_counts[state] += 1
        if state == "READY":
            ready_count += 1
            chrono_text_ready.update(chrono_ids)
        segments = row.get("segments")
        if not isinstance(segments, list):
            raise AlphaContractError("HG006 D001B segments must be list")
        if state == "READY" and not segments:
            raise AlphaContractError("HG006 D001B READY document lacks segments")
        if state != "READY" and segments:
            raise AlphaContractError("HG006 D001B non-READY document carries segments")
        for segment in segments:
            seg_id = str(segment.get("segment_id") or "")
            text = segment.get("text")
            text_sha = str(segment.get("text_sha256") or "")
            if not seg_id or not isinstance(text, str) or len(text_sha) != 64:
                raise AlphaContractError("HG006 D001B invalid text segment")
            if seg_id in segment_ids:
                raise AlphaContractError("HG006 D001B duplicate global segment ID")
            if hashlib.sha256(text.encode("utf-8")).hexdigest() != text_sha:
                raise AlphaContractError("HG006 D001B text SHA mismatch")
            segment_ids.add(seg_id)
            segment_count += 1
            total_text_chars += len(text)

        manifest_rows.append(
            {
                "document_id": row["document_id"],
                "shard_id": row["shard_id"],
                "source_urls": row["source_urls"],
                "selected_source_url": row.get("selected_source_url"),
                "document_family": row["document_family"],
                "chronology_ids": row["chronology_ids"],
                "event_ids": row["event_ids"],
                "symbols": row["symbols"],
                "families": row["families"],
                "hash_reproduced": row.get("hash_reproduced"),
                "extraction_state": state,
                "segment_manifest_sha256": row.get("segment_manifest_sha256"),
                "segment_count": len(segments),
                "segment_ids": [str(seg["segment_id"]) for seg in segments],
            }
        )

    document_count = len(requests)
    reproduced_ratio = reproduced_count / document_count if document_count else 1.0
    ready_ratio = ready_count / reproduced_count if reproduced_count else 0.0
    chronology_text_ratio = len(chrono_text_ready) / EXPECTED_SELECTION_COUNT

    missing_any = sorted(selected_ids - chrono_any_doc)
    gates = {
        "complete_selected_chronology_accounting": not missing_any,
        "complete_selected_document_accounting": len(by_id) == document_count,
        "minimum_hash_reproduction_95pct": reproduced_ratio >= 0.95,
        "minimum_text_ready_90pct": ready_ratio >= 0.90,
        "minimum_selected_chronology_text_coverage_95pct": chronology_text_ratio >= 0.95,
        "deterministic_segment_identity": segment_count == len(segment_ids),
    }

    output = {
        "schema_version": 1,
        "corpus_id": CORPUS_ID,
        "classification": "SELECTED_HISTORICAL_CALIBRATION_TEXT_CORPUS_NOT_PROBABILITY",
        "captured_at_utc": captured_at_utc,
        "source_selection_sha256": EXPECTED_SELECTION_SHA,
        "source_document_corpus_sha256": EXPECTED_SOURCE_CORPUS_SHA,
        "selected_chronology_count": EXPECTED_SELECTION_COUNT,
        "selected_document_count": document_count,
        "hash_reproduced_document_count": reproduced_count,
        "hash_reproduced_ratio": reproduced_ratio,
        "text_ready_document_count": ready_count,
        "text_ready_ratio_of_reproduced": ready_ratio,
        "chronology_with_any_document_count": len(chrono_any_doc),
        "chronology_with_text_ready_document_count": len(chrono_text_ready),
        "chronology_text_ready_ratio": chronology_text_ratio,
        "segment_count": segment_count,
        "total_text_char_count": total_text_chars,
        "extraction_state_counts": dict(sorted(state_counts.items())),
        "selected_document_counts_by_shard": {
            str(key): value for key, value in sorted(shard_counts.items())
        },
        "missing_selected_chronology_ids": missing_any,
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_historical_l001": all(gates.values()),
        "documents": sorted(manifest_rows, key=lambda row: row["document_id"]),
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
