from __future__ import annotations

from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_llm_contract import build_prompt_envelope

SELECTION_ID = "HG003-D001-v1"
EXPECTED_HG002_ID = "HG002-D001-v1"
EXPECTED_HG002_SHA = "3937b8cb83ef819ff956af4afebb80cd81d8ef233c1e4dd5b6d3688541a48db1"
EXPECTED_P2_ID = "SS002-D001-P2-v1"
EXPECTED_P2_SHA = "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071"
EXPECTED_D3_ID = "SS002-D003-v1"
EXPECTED_D3_SHA = "92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce"

EXPECTED_SYMBOL_COUNT = 28
EXPECTED_THREAD_COUNT = 35
EXPECTED_READY_THREAD_COUNT = 34
EXPECTED_UNRESOLVED_THREAD_ID = "HINDCOPPER::OFFER_FOR_SALE"


def _require_research_only(payload: dict[str, Any], label: str) -> None:
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if payload.get(field) is not False:
            raise AlphaContractError(f"HG003 D001 requires {label} {field}=false")


def _validate_inputs(
    hg002: dict[str, Any],
    p2: dict[str, Any],
    d3: dict[str, Any],
) -> None:
    if (
        hg002.get("cohort_id") != EXPECTED_HG002_ID
        or hg002.get("cohort_sha256") != EXPECTED_HG002_SHA
    ):
        raise AlphaContractError("HG003 D001 HG002 source mismatch")
    if (
        p2.get("census_id") != EXPECTED_P2_ID
        or p2.get("census_sha256") != EXPECTED_P2_SHA
    ):
        raise AlphaContractError("HG003 D001 P2 source mismatch")
    if (
        d3.get("corpus_id") != EXPECTED_D3_ID
        or d3.get("corpus_sha256") != EXPECTED_D3_SHA
    ):
        raise AlphaContractError("HG003 D001 D3 source mismatch")
    _require_research_only(hg002, "HG002")
    _require_research_only(p2, "P2")
    _require_research_only(d3, "D3")


def _hg_threads(hg002: dict[str, Any]) -> tuple[set[str], list[tuple[str, str]]]:
    rows = hg002.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_SYMBOL_COUNT:
        raise AlphaContractError("HG003 D001 requires frozen 28-name HG002 rows")
    symbols: set[str] = set()
    threads: list[tuple[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG003 D001 HG002 rows must be objects")
        symbol = str(row.get("symbol") or "").upper()
        categories = row.get("special_situation_categories")
        if not symbol or symbol in symbols:
            raise AlphaContractError("HG003 D001 HG002 symbols must be unique")
        if not isinstance(categories, list) or not categories:
            raise AlphaContractError(f"{symbol}: special_situation_categories unavailable")
        symbols.add(symbol)
        for category in sorted({str(value) for value in categories if str(value)}):
            threads.append((symbol, category))
    if len(threads) != EXPECTED_THREAD_COUNT:
        raise AlphaContractError(
            f"HG003 D001 expected {EXPECTED_THREAD_COUNT} threads, observed {len(threads)}"
        )
    return symbols, sorted(threads)


def _event_index(p2: dict[str, Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    rows = p2.get("events")
    if not isinstance(rows, list):
        raise AlphaContractError("HG003 D001 P2 events unavailable")
    result: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG003 D001 P2 events must be objects")
        if row.get("mapping_state") != "CURRENT_INVESTABLE_IDENTITY":
            continue
        symbol = str(row.get("symbol") or "").upper()
        categories = row.get("special_situation_categories")
        if not symbol or not isinstance(categories, list):
            continue
        for category in {str(value) for value in categories if str(value)}:
            result.setdefault((symbol, category), []).append(row)
    return result


def _manifest_indexes(
    d3: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    rows = d3.get("documents")
    if not isinstance(rows, list) or len(rows) != d3.get("document_count"):
        raise AlphaContractError("HG003 D001 D3 document manifest unavailable")
    by_id: dict[str, dict[str, Any]] = {}
    by_event: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG003 D001 D3 manifest rows must be objects")
        document_id = str(row.get("document_id") or "")
        if not document_id or document_id in by_id:
            raise AlphaContractError("HG003 D001 D3 document IDs must be unique")
        by_id[document_id] = row
        event_ids = row.get("event_ids")
        if not isinstance(event_ids, list):
            raise AlphaContractError(f"{document_id}: D3 event_ids unavailable")
        for event_id in event_ids:
            by_event.setdefault(str(event_id), []).append(row)
    return by_id, by_event


def _record_index(
    manifest_by_id: dict[str, dict[str, Any]],
    document_records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for row in document_records:
        if not isinstance(row, dict):
            raise TypeError("HG003 D001 document records must be objects")
        document_id = str(row.get("document_id") or "")
        if not document_id or document_id not in manifest_by_id or document_id in records:
            raise AlphaContractError("HG003 D001 document record identity mismatch")
        records[document_id] = row
    if set(records) != set(manifest_by_id):
        raise AlphaContractError("HG003 D001 document records do not cover D3 manifest")
    return records


def _ordered_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        timestamp = str(row.get("exchange_published_at_utc") or "")
        if not timestamp:
            raise AlphaContractError("HG003 D001 event timestamp unavailable")
        grouped.setdefault(timestamp, []).append(row)
    ordered: list[dict[str, Any]] = []
    for timestamp in sorted(grouped, reverse=True):
        ordered.extend(
            sorted(
                grouped[timestamp],
                key=lambda row: str(row.get("announcement_id") or ""),
            )
        )
    return ordered


def select_hg003_threads(
    hg002: dict[str, Any],
    p2: dict[str, Any],
    d3: dict[str, Any],
    document_records: list[dict[str, Any]],
) -> dict[str, Any]:
    _validate_inputs(hg002, p2, d3)
    symbols, threads = _hg_threads(hg002)
    events = _event_index(p2)
    manifest_by_id, docs_by_event = _manifest_indexes(d3)
    records = _record_index(manifest_by_id, document_records)

    output_rows: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()

    for symbol, category in threads:
        thread_id = f"{symbol}::{category}"
        candidates = events.get((symbol, category), [])
        if not candidates:
            raise AlphaContractError(f"{thread_id}: no current P2 event")

        ready_candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        unresolved_docs: dict[str, str] = {}
        for event in candidates:
            event_id = str(event.get("announcement_id") or "")
            if not event_id:
                raise AlphaContractError(f"{thread_id}: event identity unavailable")
            manifests = docs_by_event.get(event_id, [])
            for manifest in manifests:
                document_id = str(manifest["document_id"])
                state = str(manifest.get("extraction_state") or "")
                if state == "READY":
                    ready_candidates.append((event, manifest))
                else:
                    unresolved_docs[document_id] = state or "UNKNOWN"

        selected_event = None
        selected_manifest = None
        for event in _ordered_events(candidates):
            event_id = str(event["announcement_id"])
            ready_for_event = sorted(
                (
                    manifest
                    for candidate_event, manifest in ready_candidates
                    if str(candidate_event["announcement_id"]) == event_id
                ),
                key=lambda row: str(row["document_id"]),
            )
            if ready_for_event:
                selected_event = event
                selected_manifest = ready_for_event[0]
                break

        if selected_event is None or selected_manifest is None:
            state = "TEXT_UNAVAILABLE"
            state_counts[state] += 1
            output_rows.append(
                {
                    "thread_id": thread_id,
                    "symbol": symbol,
                    "category": category,
                    "selection_state": state,
                    "candidate_event_count": len(candidates),
                    "text_ready_candidate_count": 0,
                    "selected_announcement_id": None,
                    "selected_exchange_published_at_utc": None,
                    "selected_document_id": None,
                    "source_url": None,
                    "segment_count": 0,
                    "segment_manifest_sha256": None,
                    "prompt_sha256": None,
                    "prompt_envelope": None,
                    "unresolved_document_states": dict(sorted(unresolved_docs.items())),
                    "portfolio_eligibility_allowed": False,
                    "live_capital_allowed": False,
                }
            )
            continue

        document_id = str(selected_manifest["document_id"])
        record = records[document_id]
        if record.get("extraction_state") != "READY":
            raise AlphaContractError(f"{thread_id}: selected document record is not READY")
        segments = record.get("segments")
        if not isinstance(segments, list) or not segments:
            raise AlphaContractError(f"{thread_id}: selected READY document has no segments")

        manifest_event_ids = [str(value) for value in selected_manifest.get("event_ids", [])]
        manifest_symbols = [str(value) for value in selected_manifest.get("symbols", [])]
        manifest_categories = [
            str(value) for value in selected_manifest.get("categories", [])
        ]
        prompt = build_prompt_envelope(
            document_id=document_id,
            source_url=str(selected_manifest.get("source_url") or ""),
            event_ids=manifest_event_ids,
            symbols=manifest_symbols,
            category_hints=manifest_categories,
            segments=segments,
            segment_manifest_sha256=str(
                selected_manifest.get("segment_manifest_sha256") or ""
            ),
        )
        state = "TEXT_READY"
        state_counts[state] += 1
        output_rows.append(
            {
                "thread_id": thread_id,
                "symbol": symbol,
                "category": category,
                "selection_state": state,
                "candidate_event_count": len(candidates),
                "text_ready_candidate_count": sum(
                    1
                    for event in candidates
                    if any(
                        str(doc.get("extraction_state") or "") == "READY"
                        for doc in docs_by_event.get(
                            str(event.get("announcement_id") or ""), []
                        )
                    )
                ),
                "selected_announcement_id": selected_event.get("announcement_id"),
                "selected_exchange_published_at_utc": selected_event.get(
                    "exchange_published_at_utc"
                ),
                "selected_document_id": document_id,
                "source_url": selected_manifest.get("source_url"),
                "segment_count": len(segments),
                "segment_manifest_sha256": selected_manifest.get(
                    "segment_manifest_sha256"
                ),
                "prompt_sha256": prompt["prompt_sha256"],
                "prompt_envelope": prompt,
                "unresolved_document_states": dict(sorted(unresolved_docs.items())),
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    ready_count = state_counts["TEXT_READY"]
    unresolved = [
        row["thread_id"]
        for row in output_rows
        if row["selection_state"] == "TEXT_UNAVAILABLE"
    ]
    threshold_passes = {
        "exact_hg002_symbol_count": len(symbols) == EXPECTED_SYMBOL_COUNT,
        "exact_thread_accounting": len(output_rows) == EXPECTED_THREAD_COUNT,
        "exact_text_ready_thread_count": ready_count == EXPECTED_READY_THREAD_COUNT,
        "exact_single_unresolved_thread": unresolved == [EXPECTED_UNRESOLVED_THREAD_ID],
        "all_ready_prompts_materialized": all(
            row["prompt_envelope"] is not None
            for row in output_rows
            if row["selection_state"] == "TEXT_READY"
        ),
    }

    output = {
        "schema_version": 1,
        "selection_id": SELECTION_ID,
        "classification": "HG002_COHORT_SPECIAL_SITUATION_THREAD_SELECTION_NOT_ALPHA",
        "source_hg002_cohort_sha256": EXPECTED_HG002_SHA,
        "source_p2_census_sha256": EXPECTED_P2_SHA,
        "source_d3_corpus_sha256": EXPECTED_D3_SHA,
        "symbol_count": len(symbols),
        "thread_count": len(output_rows),
        "selection_state_counts": dict(sorted(state_counts.items())),
        "unresolved_thread_ids": unresolved,
        "rows": sorted(output_rows, key=lambda row: row["thread_id"]),
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_cohort_l001": all(threshold_passes.values()),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["selection_sha256"] = digest(output)
    return output
