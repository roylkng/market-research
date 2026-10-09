from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_llm_contract import build_prompt_envelope
from marketlab.ss002_special_situations import approved_attachment_url

QUEUE_ID = "SS001-D007-L001-P0-v1"
Q002_SHA = "c3c28d55b98a08c91e99b76d5ae2732f2ca24406fa12752be2f0e75fa0624f36"
D003_SHA = "92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce"
D002_SHA = "eab922954ef20a12a7635107722b4e800b59cfa56ff0659da42afb3fc22218f9"
PILOT_ISSUER_COUNT = 12
MAX_SEGMENTS = 10
MAX_TOTAL_CHARS = 32_000


def _require_closed(payload: dict[str, Any], name: str) -> None:
    for field in ("return_outcomes_opened", "portfolio_eligibility_allowed", "live_capital_allowed"):
        if payload.get(field) is not False:
            raise AlphaContractError(f"L001 P0 requires {name} {field}=false")


def _validate_sources(q002: dict[str, Any], d003: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if q002.get("binding_id") != "SS001-D007-Q002-v1" or q002.get("binding_sha256") != Q002_SHA:
        raise AlphaContractError("L001 P0 Q002 binding SHA mismatch")
    if q002.get("feasibility_pass") is not True:
        raise AlphaContractError("L001 P0 Q002 did not pass source binding")
    if q002.get("pilot_packet_count") != 50:
        raise AlphaContractError("L001 P0 requires 50 source packets")
    if q002.get("source_d003_corpus_sha256") != D003_SHA:
        raise AlphaContractError("L001 P0 Q002 D003 source SHA mismatch")
    _require_closed(q002, "Q002")
    if q002.get("share_action_clearance_proven") is not False:
        raise AlphaContractError("L001 P0 refuses share-count clearance")
    if q002.get("market_capitalization_calculated") is not False:
        raise AlphaContractError("L001 P0 refuses market capitalization")

    if d003.get("corpus_id") != "SS002-D003-v1" or d003.get("corpus_sha256") != D003_SHA:
        raise AlphaContractError("L001 P0 D003 corpus SHA mismatch")
    if d003.get("source_d002_corpus_sha256") != D002_SHA:
        raise AlphaContractError("L001 P0 D003 upstream D002 source mismatch")
    if d003.get("document_count") != 1539:
        raise AlphaContractError("L001 P0 D003 document count mismatch")
    _require_closed(d003, "D003")
    rows = d003.get("documents")
    if not isinstance(rows, list) or len(rows) != 1539:
        raise AlphaContractError("L001 P0 requires full frozen D003 document manifest")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("L001 P0 D003 document row must be object")
        doc_id = row.get("document_id")
        if not isinstance(doc_id, str) or len(doc_id) != 64 or doc_id in result:
            raise AlphaContractError("L001 P0 D003 document identity mismatch")
        result[doc_id] = row
    return result


def _verified_segments(
    document: dict[str, Any],
    metadata: dict[str, Any],
    source: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    doc_id = source["document_id"]
    if (
        document.get("document_id") != doc_id
        or document.get("extraction_state") != "READY"
        or document.get("hash_reproduced") is not True
        or document.get("source_url") != metadata.get("source_url")
    ):
        raise AlphaContractError(f"L001 P0 {doc_id}: D003 text source identity invalid")
    if (
        document.get("segment_manifest_sha256") != source.get("segment_manifest_sha256")
        or metadata.get("segment_manifest_sha256") != source.get("segment_manifest_sha256")
    ):
        raise AlphaContractError(f"L001 P0 {doc_id}: segment manifest SHA mismatch")
    segments = document.get("segments")
    if not isinstance(segments, list) or not segments:
        raise AlphaContractError(f"L001 P0 {doc_id}: READY document lacks segments")
    ids = [item.get("segment_id") for item in segments if isinstance(item, dict)]
    if ids != source.get("segment_ids") or ids != metadata.get("segment_ids"):
        raise AlphaContractError(f"L001 P0 {doc_id}: segment IDs differ from Q002/D003")

    chars = 0
    for item in segments:
        if not isinstance(item, dict):
            raise TypeError("L001 P0 segment must be object")
        text = item.get("text")
        if not isinstance(text, str):
            raise AlphaContractError("L001 P0 segment text missing")
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if item.get("text_sha256") != sha:
            raise AlphaContractError("L001 P0 segment text SHA mismatch")
        chars += len(text)
    return segments, chars


def build_l001_p0_queue(
    *,
    q002: dict[str, Any],
    d003: dict[str, Any],
    read_document: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    documents = _validate_sources(q002, d003)
    packets = q002.get("packets")
    if not isinstance(packets, list) or len(packets) != 50:
        raise AlphaContractError("L001 P0 requires all 50 Q002 packets")

    selected: list[dict[str, Any]] = []
    states: Counter[str] = Counter()
    used_documents: set[str] = set()
    used_issuers: set[str] = set()

    for position, packet in enumerate(packets[:PILOT_ISSUER_COUNT], start=1):
        if not isinstance(packet, dict):
            raise TypeError("L001 P0 issuer packet must be object")
        symbol = packet.get("symbol")
        if (
            not isinstance(symbol, str)
            or not symbol
            or symbol in used_issuers
            or packet.get("review_queue_rank") != position
        ):
            raise AlphaContractError("L001 P0 first-12 issuer order/identity mismatch")
        used_issuers.add(symbol)
        events = packet.get("announcement_evidence")
        if not isinstance(events, list):
            raise AlphaContractError("L001 P0 issuer announcement evidence missing")
        skipped = []
        picked = None
        for event in events:
            if not isinstance(event, dict):
                raise TypeError("L001 P0 announcement event must be object")
            doc_id = event.get("document_id")
            if event.get("binding_state") != "TEXT_READY" or not isinstance(doc_id, str):
                skipped.append({"event_id": event.get("event_id"), "reason": "NOT_TEXT_READY"})
                continue
            metadata = documents.get(doc_id)
            if metadata is None:
                raise AlphaContractError("L001 P0 selected D003 document missing")
            if event.get("event_id") not in metadata.get("event_ids", []):
                raise AlphaContractError("L001 P0 event/D003 provenance mismatch")
            if symbol not in metadata.get("symbols", []):
                raise AlphaContractError("L001 P0 D003 issuer symbol mismatch")
            if doc_id in used_documents:
                skipped.append({"event_id": event.get("event_id"), "reason": "DOCUMENT_ALREADY_SELECTED"})
                continue
            if approved_attachment_url(metadata.get("source_url")) is None:
                raise AlphaContractError("L001 P0 D003 official source URL invalid")

            document = read_document(doc_id)
            if not isinstance(document, dict):
                raise TypeError("L001 P0 D003 document payload must be object")
            segments, char_count = _verified_segments(document, metadata, event)
            if len(segments) > MAX_SEGMENTS or char_count > MAX_TOTAL_CHARS:
                skipped.append(
                    {
                        "event_id": event.get("event_id"),
                        "reason": "COMPLETE_DOCUMENT_EXCEEDS_TRANSPORT_BOUNDS",
                        "segment_count": len(segments),
                        "char_count": char_count,
                    }
                )
                continue

            envelope = build_prompt_envelope(
                document_id=doc_id,
                source_url=str(metadata["source_url"]),
                event_ids=[str(value) for value in metadata.get("event_ids", [])],
                symbols=[str(value) for value in metadata.get("symbols", [])],
                category_hints=[str(value) for value in metadata.get("categories", [])],
                segments=segments,
                segment_manifest_sha256=str(metadata["segment_manifest_sha256"]),
            )
            picked = {
                "issuer_packet_rank": position,
                "symbol": symbol,
                "source_event_id": event["event_id"],
                "document_id": doc_id,
                "source_url": metadata["source_url"],
                "complete_segment_count": len(segments),
                "complete_char_count": char_count,
                "segment_manifest_sha256": metadata["segment_manifest_sha256"],
                "prompt_sha256": envelope["prompt_sha256"],
                "prompt_envelope": envelope,
                "ignored_prior_candidates": skipped,
                "model_inference_executed": False,
                "share_action_clearance_proven": False,
                "market_capitalization_calculated": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
            used_documents.add(doc_id)
            break

        if picked is None:
            states["SOURCE_OR_CONTEXT_LIMIT"] += 1
            selected.append(
                {
                    "issuer_packet_rank": position,
                    "symbol": symbol,
                    "selection_state": "SOURCE_OR_CONTEXT_LIMIT",
                    "ignored_prior_candidates": skipped,
                    "prompt_envelope": None,
                    "share_action_clearance_proven": False,
                    "market_capitalization_calculated": False,
                    "portfolio_eligibility_allowed": False,
                    "live_capital_allowed": False,
                }
            )
        else:
            states["SELECTED_COMPLETE_DOCUMENT"] += 1
            picked["selection_state"] = "SELECTED_COMPLETE_DOCUMENT"
            selected.append(picked)

    gates = {
        "exact_first_12_issuer_positions": len(selected) == PILOT_ISSUER_COUNT,
        "exact_12_complete_document_prompts": states["SELECTED_COMPLETE_DOCUMENT"] == PILOT_ISSUER_COUNT,
        "document_and_segment_hashes_bound": True,
        "no_segment_truncation": True,
        "no_llm_or_capitalization": True,
    }
    result = {
        "schema_version": 1,
        "queue_id": QUEUE_ID,
        "classification": "EVIDENCE_BOUND_ISSUER_RELEVANCE_LLM_QUEUE_NOT_SHARE_CLEARANCE",
        "source_q002_binding_sha256": Q002_SHA,
        "source_d003_corpus_sha256": D003_SHA,
        "issuer_count": PILOT_ISSUER_COUNT,
        "selected_document_count": states["SELECTED_COMPLETE_DOCUMENT"],
        "selection_state_counts": dict(sorted(states.items())),
        "max_segments": MAX_SEGMENTS,
        "max_total_chars": MAX_TOTAL_CHARS,
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "model_inference_executed": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
        "rows": selected,
    }
    result["queue_sha256"] = digest(result)
    return result
