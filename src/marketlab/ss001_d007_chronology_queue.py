from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_llm_contract import build_prompt_envelope

QUEUE_ID = "SS001-D007-L001-P2-v1"
Q002_SHA = "c3c28d55b98a08c91e99b76d5ae2732f2ca24406fa12752be2f0e75fa0624f36"
D003_SHA = "92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce"
P1_RUN_ID = "SS001-D007-L001-P1-GPT56SOL-NATIVE-v1"
P1_RUN_SHA = "1a3a2f73eaed8ba09c84ab7c8d60699fa895f39d25d5797bd16138b09fd620cb"
MODEL_CONFIG_SHA = "133b5705036d1782f671d6a171fe5f24298939cf6d84314875c2e8452e7169dc"

ISSUERS = (
    "JAYKAY",
    "INDIAGLYCO",
    "HEGAM",
    "IITL",
    "ORBTEXP",
    "PVRINOX",
    "GANDHITUBE",
    "RATNAVEER",
    "TEAMLEASE",
    "TRIVENI",
    "DUCON",
    "INOXGREEN",
)
EXPECTED_ANNOUNCEMENT_REFERENCES = 95
EXPECTED_CORPORATE_ACTION_ROWS = 12
EXPECTED_DISTINCT_DOCUMENTS = 82
EXPECTED_P1_REUSE_DOCUMENTS = 12
EXPECTED_FRESH_DOCUMENTS = 70
EXPECTED_FRESH_REQUESTS = 1240
SHARD_COUNT = 16


def _canonical_sha(payload: Any) -> str:
    return digest(payload)


def _text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require_closed(payload: dict[str, Any], label: str) -> None:
    for field in (
        "return_outcomes_opened",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if payload.get(field) is not False:
            raise AlphaContractError(f"P2 queue requires {label} {field}=false")


def _validate_sources(
    q002: dict[str, Any],
    d003: dict[str, Any],
    p1_run: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if q002.get("binding_id") != "SS001-D007-Q002-v1":
        raise AlphaContractError("P2 queue Q002 binding id mismatch")
    if q002.get("binding_sha256") != Q002_SHA:
        raise AlphaContractError("P2 queue Q002 binding SHA mismatch")
    if q002.get("pilot_packet_count") != 50:
        raise AlphaContractError("P2 queue requires frozen 50 Q002 packets")
    if q002.get("source_d003_corpus_sha256") != D003_SHA:
        raise AlphaContractError("P2 queue Q002 D003 source mismatch")
    if q002.get("feasibility_pass") is not True:
        raise AlphaContractError("P2 queue Q002 did not pass")
    _require_closed(q002, "Q002")

    if d003.get("corpus_id") != "SS002-D003-v1":
        raise AlphaContractError("P2 queue D003 corpus id mismatch")
    if d003.get("corpus_sha256") != D003_SHA:
        raise AlphaContractError("P2 queue D003 corpus SHA mismatch")
    if d003.get("document_count") != 1539:
        raise AlphaContractError("P2 queue D003 document count mismatch")
    _require_closed(d003, "D003")
    if d003.get("llm_inference_executed") is not False:
        raise AlphaContractError("P2 queue D003 unexpectedly claims LLM inference")

    if p1_run.get("run_id") != P1_RUN_ID:
        raise AlphaContractError("P2 queue P1 run id mismatch")
    if p1_run.get("run_sha256") != P1_RUN_SHA:
        raise AlphaContractError("P2 queue P1 run SHA mismatch")
    if p1_run.get("model_config_sha256") != MODEL_CONFIG_SHA:
        raise AlphaContractError("P2 queue P1 model config SHA mismatch")
    if p1_run.get("selected_request_count") != EXPECTED_P1_REUSE_DOCUMENTS:
        raise AlphaContractError("P2 queue P1 response count mismatch")
    if p1_run.get("validated_response_count") != EXPECTED_P1_REUSE_DOCUMENTS:
        raise AlphaContractError("P2 queue P1 validation count mismatch")
    if p1_run.get("share_action_clearance_proven") is not False:
        raise AlphaContractError("P2 queue refuses P1 share clearance")
    if p1_run.get("market_capitalization_calculated") is not False:
        raise AlphaContractError("P2 queue refuses P1 capitalization")
    _require_closed(p1_run, "P1")

    packets = q002.get("packets")
    if not isinstance(packets, list) or len(packets) != 50:
        raise AlphaContractError("P2 queue Q002 packet list unavailable")

    manifest_rows = d003.get("documents")
    if not isinstance(manifest_rows, list) or len(manifest_rows) != 1539:
        raise AlphaContractError("P2 queue D003 manifest unavailable")
    docs: dict[str, dict[str, Any]] = {}
    for row in manifest_rows:
        if not isinstance(row, dict):
            raise TypeError("P2 queue D003 document row must be object")
        document_id = row.get("document_id")
        if not isinstance(document_id, str) or len(document_id) != 64 or document_id in docs:
            raise AlphaContractError("P2 queue D003 document identity mismatch")
        docs[document_id] = row

    p1_rows = p1_run.get("rows")
    if not isinstance(p1_rows, list) or len(p1_rows) != EXPECTED_P1_REUSE_DOCUMENTS:
        raise AlphaContractError("P2 queue P1 rows unavailable")
    p1_by_document: dict[str, dict[str, Any]] = {}
    for row in p1_rows:
        if not isinstance(row, dict):
            raise TypeError("P2 queue P1 row must be object")
        document_id = row.get("document_id")
        if not isinstance(document_id, str) or document_id in p1_by_document:
            raise AlphaContractError("P2 queue P1 document identity mismatch")
        validated = row.get("validated_extraction")
        if not isinstance(validated, dict):
            raise AlphaContractError("P2 queue P1 validated extraction unavailable")
        if validated.get("document_id") != document_id:
            raise AlphaContractError("P2 queue P1 validated document mismatch")
        p1_by_document[document_id] = row
    return packets, docs, p1_by_document


def _verified_document(
    *,
    document_id: str,
    manifest: dict[str, Any],
    read_document: Callable[[str], dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if manifest.get("extraction_state") != "READY" or manifest.get("hash_reproduced") is not True:
        raise AlphaContractError(f"P2 queue {document_id}: D003 document not READY")
    payload = read_document(document_id)
    if not isinstance(payload, dict):
        raise TypeError("P2 queue D003 document payload must be object")
    if (
        payload.get("document_id") != document_id
        or payload.get("extraction_state") != "READY"
        or payload.get("hash_reproduced") is not True
        or payload.get("source_url") != manifest.get("source_url")
        or payload.get("segment_manifest_sha256") != manifest.get("segment_manifest_sha256")
    ):
        raise AlphaContractError(f"P2 queue {document_id}: D003 document identity mismatch")
    segments = payload.get("segments")
    if not isinstance(segments, list) or not segments:
        raise AlphaContractError(f"P2 queue {document_id}: D003 segments unavailable")
    manifest_ids = manifest.get("segment_ids")
    segment_ids = [row.get("segment_id") for row in segments if isinstance(row, dict)]
    if not isinstance(manifest_ids, list) or segment_ids != manifest_ids:
        raise AlphaContractError(f"P2 queue {document_id}: segment order mismatch")
    for row in segments:
        if not isinstance(row, dict):
            raise TypeError("P2 queue segment must be object")
        text = row.get("text")
        if not isinstance(text, str):
            raise AlphaContractError("P2 queue segment text unavailable")
        if row.get("text_sha256") != _text_sha(text):
            raise AlphaContractError("P2 queue segment text SHA mismatch")
    return payload, segments


def _page_manifest_sha(
    *,
    source_document_manifest_sha256: str,
    segment: dict[str, Any],
) -> str:
    return _canonical_sha(
        {
            "schema_version": 1,
            "transport": "ONE_ORIGINAL_D003_SEGMENT",
            "source_document_manifest_sha256": source_document_manifest_sha256,
            "segments": [
                {
                    "segment_id": segment["segment_id"],
                    "text_sha256": segment["text_sha256"],
                }
            ],
        }
    )


def build_p2_queue(
    *,
    q002: dict[str, Any],
    d003: dict[str, Any],
    p1_run: dict[str, Any],
    read_document: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    packets, manifest_by_document, p1_by_document = _validate_sources(q002, d003, p1_run)

    first12 = packets[: len(ISSUERS)]
    if tuple(str(row.get("symbol") or "") for row in first12) != ISSUERS:
        raise AlphaContractError("P2 queue first-12 issuer order mismatch")
    if tuple(row.get("review_queue_rank") for row in first12) != tuple(range(1, 13)):
        raise AlphaContractError("P2 queue first-12 ranks mismatch")

    announcement_reference_count = 0
    corporate_action_rows = []
    document_owner: dict[str, str] = {}
    ordered_documents: list[dict[str, Any]] = []

    for rank, packet in enumerate(first12, start=1):
        symbol = ISSUERS[rank - 1]
        events = packet.get("announcement_evidence")
        actions = packet.get("corporate_action_evidence")
        if not isinstance(events, list) or not isinstance(actions, list):
            raise AlphaContractError("P2 queue Q002 evidence blocks unavailable")
        announcement_reference_count += len(events)
        if len(actions) != 1:
            raise AlphaContractError(f"P2 queue {symbol}: expected one corporate action row")
        corporate_action_rows.append(
            {
                "issuer_packet_rank": rank,
                "symbol": symbol,
                **actions[0],
            }
        )
        seen_issuer_docs: set[str] = set()
        for event_order, event in enumerate(events, start=1):
            if not isinstance(event, dict):
                raise TypeError("P2 queue Q002 event must be object")
            if event.get("binding_state") != "TEXT_READY":
                raise AlphaContractError(f"P2 queue {symbol}: first-12 event is not TEXT_READY")
            document_id = event.get("document_id")
            if not isinstance(document_id, str):
                raise AlphaContractError("P2 queue Q002 document id unavailable")
            if document_id in seen_issuer_docs:
                continue
            seen_issuer_docs.add(document_id)
            previous_owner = document_owner.get(document_id)
            if previous_owner is not None and previous_owner != symbol:
                raise AlphaContractError("P2 queue document is shared across pilot issuers")
            document_owner[document_id] = symbol
            ordered_documents.append(
                {
                    "issuer_packet_rank": rank,
                    "symbol": symbol,
                    "document_first_event_order": event_order,
                    "document_id": document_id,
                    "q002_event_ids": [
                        str(row.get("event_id"))
                        for row in events
                        if isinstance(row, dict) and row.get("document_id") == document_id
                    ],
                    "q002_source_urls": sorted(
                        {
                            str(row.get("source_url"))
                            for row in events
                            if isinstance(row, dict)
                            and row.get("document_id") == document_id
                            and row.get("source_url")
                        }
                    ),
                }
            )

    if announcement_reference_count != EXPECTED_ANNOUNCEMENT_REFERENCES:
        raise AlphaContractError(
            f"P2 queue expected {EXPECTED_ANNOUNCEMENT_REFERENCES} announcement refs, "
            f"observed {announcement_reference_count}"
        )
    if len(corporate_action_rows) != EXPECTED_CORPORATE_ACTION_ROWS:
        raise AlphaContractError("P2 queue corporate-action count mismatch")
    if len(ordered_documents) != EXPECTED_DISTINCT_DOCUMENTS:
        raise AlphaContractError(
            f"P2 queue expected {EXPECTED_DISTINCT_DOCUMENTS} documents, "
            f"observed {len(ordered_documents)}"
        )

    reused_documents = []
    fresh_documents = []
    fresh_candidates = []

    for document_order, doc_ref in enumerate(ordered_documents, start=1):
        document_id = doc_ref["document_id"]
        manifest = manifest_by_document.get(document_id)
        if manifest is None:
            raise AlphaContractError("P2 queue selected document missing from D003 manifest")
        _payload, segments = _verified_document(
            document_id=document_id,
            manifest=manifest,
            read_document=read_document,
        )
        symbol = doc_ref["symbol"]
        if symbol not in [str(value) for value in manifest.get("symbols", [])]:
            raise AlphaContractError("P2 queue D003 symbol mismatch")
        q002_event_ids = set(doc_ref["q002_event_ids"])
        manifest_event_ids = {str(value) for value in manifest.get("event_ids", [])}
        if not q002_event_ids.issubset(manifest_event_ids):
            raise AlphaContractError("P2 queue Q002/D003 event provenance mismatch")

        source_meta = {
            **doc_ref,
            "document_order": document_order,
            "source_url": manifest.get("source_url"),
            "d003_segment_manifest_sha256": manifest.get("segment_manifest_sha256"),
            "d003_segment_count": len(segments),
            "d003_categories": [str(value) for value in manifest.get("categories", [])],
            "d003_event_ids": sorted(manifest_event_ids),
        }

        p1 = p1_by_document.get(document_id)
        if p1 is not None:
            if p1.get("symbol") != symbol:
                raise AlphaContractError("P2 queue P1 reuse symbol mismatch")
            if p1.get("issuer_packet_rank") != doc_ref["issuer_packet_rank"]:
                raise AlphaContractError("P2 queue P1 reuse rank mismatch")
            if p1.get("segment_manifest_sha256") != manifest.get("segment_manifest_sha256"):
                raise AlphaContractError("P2 queue P1 reuse segment manifest mismatch")
            validated = p1["validated_extraction"]
            if set(validated.get("event_ids", [])) != manifest_event_ids:
                raise AlphaContractError("P2 queue P1 reuse event IDs mismatch")
            reused_documents.append(
                {
                    **source_meta,
                    "execution_state": "P1_REUSE",
                    "p1_prompt_sha256": p1.get("prompt_sha256"),
                    "p1_model_config_sha256": p1.get("model_config_sha256"),
                    "p1_raw_model_response_sha256": p1.get("raw_model_response_sha256"),
                    "p1_validated_structured_output_sha256": validated.get(
                        "validated_structured_output_sha256"
                    ),
                }
            )
            continue

        fresh_documents.append(
            {
                **source_meta,
                "execution_state": "FRESH_PAGE_REQUESTS",
            }
        )
        for segment_order, segment in enumerate(segments, start=1):
            page_manifest_sha = _page_manifest_sha(
                source_document_manifest_sha256=str(manifest["segment_manifest_sha256"]),
                segment=segment,
            )
            prompt = build_prompt_envelope(
                document_id=document_id,
                source_url=str(manifest["source_url"]),
                event_ids=[str(value) for value in manifest.get("event_ids", [])],
                symbols=[str(value) for value in manifest.get("symbols", [])],
                category_hints=[str(value) for value in manifest.get("categories", [])],
                segments=[segment],
                segment_manifest_sha256=page_manifest_sha,
            )
            request_basis = {
                "queue_id": QUEUE_ID,
                "issuer_packet_rank": doc_ref["issuer_packet_rank"],
                "symbol": symbol,
                "document_id": document_id,
                "segment_id": segment["segment_id"],
                "source_document_manifest_sha256": manifest["segment_manifest_sha256"],
                "request_segment_manifest_sha256": page_manifest_sha,
                "model_config_sha256": MODEL_CONFIG_SHA,
            }
            fresh_candidates.append(
                {
                    **request_basis,
                    "request_id": digest(request_basis),
                    "document_order": document_order,
                    "segment_order": segment_order,
                    "prompt_sha256": prompt["prompt_sha256"],
                    "prompt_envelope": prompt,
                }
            )

    if len(reused_documents) != EXPECTED_P1_REUSE_DOCUMENTS:
        raise AlphaContractError("P2 queue P1 reuse document count mismatch")
    if len(fresh_documents) != EXPECTED_FRESH_DOCUMENTS:
        raise AlphaContractError("P2 queue fresh document count mismatch")
    if len(fresh_candidates) != EXPECTED_FRESH_REQUESTS:
        raise AlphaContractError(
            f"P2 queue expected {EXPECTED_FRESH_REQUESTS} fresh requests, "
            f"observed {len(fresh_candidates)}"
        )

    fresh_candidates.sort(
        key=lambda row: (
            row["issuer_packet_rank"],
            row["document_order"],
            row["segment_order"],
            row["request_id"],
        )
    )
    requests = []
    for index, row in enumerate(fresh_candidates, start=1):
        requests.append(
            {
                **row,
                "global_request_index": index,
                "shard_id": (index - 1) % SHARD_COUNT,
            }
        )

    if {row["shard_id"] for row in requests} != set(range(SHARD_COUNT)):
        raise AlphaContractError("P2 queue all shard IDs must be present")

    segment_ids = [row["segment_id"] for row in requests]
    if len(segment_ids) != len(set(segment_ids)):
        raise AlphaContractError("P2 queue fresh segment accounting is not unique")

    gates = {
        "exact_first_12_issuer_packets": True,
        "exact_95_announcement_references": announcement_reference_count
        == EXPECTED_ANNOUNCEMENT_REFERENCES,
        "exact_12_corporate_action_rows": len(corporate_action_rows)
        == EXPECTED_CORPORATE_ACTION_ROWS,
        "exact_82_distinct_documents": len(ordered_documents)
        == EXPECTED_DISTINCT_DOCUMENTS,
        "exact_12_p1_reuse_documents": len(reused_documents)
        == EXPECTED_P1_REUSE_DOCUMENTS,
        "exact_70_fresh_documents": len(fresh_documents) == EXPECTED_FRESH_DOCUMENTS,
        "exact_1240_fresh_requests": len(requests) == EXPECTED_FRESH_REQUESTS,
        "all_fresh_d003_segments_accounted_once": len(segment_ids)
        == len(set(segment_ids))
        == EXPECTED_FRESH_REQUESTS,
        "all_16_shards_present": {row["shard_id"] for row in requests}
        == set(range(SHARD_COUNT)),
        "no_inference_or_capitalization": True,
    }

    output = {
        "schema_version": 1,
        "queue_id": QUEUE_ID,
        "classification": "FULL_ISSUER_CHRONOLOGY_LLM_EXTRACTION_QUEUE_NOT_SHARE_CLEARANCE",
        "source_q002_binding_sha256": Q002_SHA,
        "source_d003_corpus_sha256": D003_SHA,
        "source_p1_run_sha256": P1_RUN_SHA,
        "model_config_sha256": MODEL_CONFIG_SHA,
        "issuer_count": len(ISSUERS),
        "issuer_symbols": list(ISSUERS),
        "announcement_reference_count": announcement_reference_count,
        "corporate_action_row_count": len(corporate_action_rows),
        "distinct_document_count": len(ordered_documents),
        "p1_reuse_document_count": len(reused_documents),
        "fresh_document_count": len(fresh_documents),
        "fresh_request_count": len(requests),
        "shard_count": SHARD_COUNT,
        "shard_request_counts": dict(
            sorted(Counter(row["shard_id"] for row in requests).items())
        ),
        "corporate_action_evidence": corporate_action_rows,
        "reused_documents": reused_documents,
        "fresh_documents": fresh_documents,
        "requests": requests,
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "model_inference_executed": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["queue_sha256"] = digest(output)
    return output
