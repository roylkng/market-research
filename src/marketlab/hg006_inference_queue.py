from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg006_stage_contract import CONTRACT_ID, extraction_template, validate_extraction

QUEUE_ID = "HG006-L001-P1-v1"
EXPECTED_S002_ID = "HG006-S002-v1"
EXPECTED_S002_SHA = "e99f270bf48b76bb72f3e2734abddd34bcc580cb1583086cc73e50759e23766e"
EXPECTED_CHRONOLOGY_COUNT = 300
EXPECTED_EVIDENCE_READY = 298
EXPECTED_REQUEST_COUNT = 1448
SHARD_COUNT = 16

MODEL_CONFIG = {
    "provider_runtime": "CHATGPT_NATIVE_INTERACTIVE",
    "model_id": "GPT-5.6 Sol",
    "temperature": 0.0,
    "top_p": 1.0,
    "max_output_tokens": 4096,
    "contract_id": CONTRACT_ID,
    "transport": "NATIVE_CHAT_MODEL",
    "structured_output_mode": "JSON_OBJECT",
}

SYSTEM_PROMPT = (
    "Extract only explicit historical transaction stage, terminal-language and "
    "transaction anchor facts from the supplied official source segments. Use no "
    "outside knowledge, market prices, later company status, historical returns or "
    "current hidden-gem conclusions. Every explicit claim must cite supplied segment "
    "IDs. Preserve the frozen family; if document economics conflict, emit "
    "family_semantic_conflict with evidence. Do not group transaction episodes and do "
    "not estimate completion probability."
)


def _canonical_bytes(payload: Any) -> bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AlphaContractError("HG006 L001 queue payload must be finite JSON") from exc


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def request_id_for(chronology_id: str, document_id: str) -> str:
    if not chronology_id or len(document_id) != 64:
        raise AlphaContractError("HG006 L001 queue request identity is invalid")
    raw = f"{QUEUE_ID}|{chronology_id}|{document_id}".encode("utf-8")
    return _sha256_bytes(raw)


def shard_for_request_id(request_id: str) -> int:
    if len(request_id) != 64:
        raise AlphaContractError("HG006 L001 queue request_id must be SHA-256")
    try:
        return int(request_id[:8], 16) % SHARD_COUNT
    except ValueError as exc:
        raise AlphaContractError("HG006 L001 queue request_id must be hex") from exc


def _validate_pack(pack: dict[str, Any]) -> list[dict[str, Any]]:
    if pack.get("pack_id") != EXPECTED_S002_ID:
        raise AlphaContractError("HG006 L001 queue requires frozen S002 pack")
    if pack.get("pack_sha256") != EXPECTED_S002_SHA:
        raise AlphaContractError("HG006 L001 queue S002 pack SHA mismatch")
    if pack.get("chronology_count") != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 L001 queue chronology count mismatch")
    state_counts = pack.get("state_counts")
    if (
        not isinstance(state_counts, dict)
        or state_counts.get("EVIDENCE_READY") != EXPECTED_EVIDENCE_READY
        or state_counts.get("TEXT_UNAVAILABLE") != 2
    ):
        raise AlphaContractError("HG006 L001 queue S002 evidence-state counts mismatch")
    if pack.get("retained_document_count") != EXPECTED_REQUEST_COUNT:
        raise AlphaContractError("HG006 L001 queue retained document count mismatch")
    for field in (
        "historical_terminal_labels_opened",
        "completion_probabilities_assigned",
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if pack.get(field) is not False:
            raise AlphaContractError(f"HG006 L001 queue requires S002 {field}=false")
    rows = pack.get("chronologies")
    if not isinstance(rows, list) or len(rows) != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 L001 queue S002 chronology rows unavailable")
    return rows


def _validate_segment(segment: dict[str, Any]) -> None:
    segment_id = str(segment.get("segment_id") or "")
    text = segment.get("text")
    text_sha = str(segment.get("text_sha256") or "")
    if not segment_id or not isinstance(text, str) or len(text_sha) != 64:
        raise AlphaContractError("HG006 L001 queue segment is incomplete")
    if _sha256_bytes(text.encode("utf-8")) != text_sha:
        raise AlphaContractError("HG006 L001 queue segment text SHA mismatch")


def build_inference_queue(pack: dict[str, Any]) -> dict[str, Any]:
    chronologies = _validate_pack(pack)
    model_config_sha = digest(MODEL_CONFIG)
    requests: list[dict[str, Any]] = []
    seen_request_ids: set[str] = set()
    seen_chronologies: set[str] = set()
    unavailable_ids: list[str] = []
    shard_counts: Counter[int] = Counter()
    family_counts: Counter[str] = Counter()

    for chronology in chronologies:
        if not isinstance(chronology, dict):
            raise TypeError("HG006 L001 queue chronology must be object")
        chronology_id = str(chronology.get("chronology_id") or "")
        symbol = str(chronology.get("symbol") or "")
        family = str(chronology.get("family") or "")
        state = str(chronology.get("evidence_state") or "")
        if not chronology_id or not symbol or not family:
            raise AlphaContractError("HG006 L001 queue chronology identity incomplete")
        if chronology_id in seen_chronologies:
            raise AlphaContractError("HG006 L001 queue duplicate chronology")
        seen_chronologies.add(chronology_id)

        if state == "TEXT_UNAVAILABLE":
            unavailable_ids.append(chronology_id)
            if chronology.get("retained_documents"):
                raise AlphaContractError(
                    "HG006 L001 queue TEXT_UNAVAILABLE chronology carries documents"
                )
            continue
        if state != "EVIDENCE_READY":
            raise AlphaContractError("HG006 L001 queue unknown evidence state")

        docs = chronology.get("retained_documents")
        if not isinstance(docs, list) or not docs:
            raise AlphaContractError("HG006 L001 queue ready chronology lacks documents")
        for doc in docs:
            if not isinstance(doc, dict):
                raise TypeError("HG006 L001 queue retained document must be object")
            document_id = str(doc.get("document_id") or "")
            event_ids = [str(value) for value in doc.get("event_ids", [])]
            segments = doc.get("selected_segments")
            segment_manifest_sha = str(doc.get("segment_manifest_sha256") or "")
            timestamp = str(doc.get("chronology_timestamp_utc") or "")
            if (
                len(document_id) != 64
                or not event_ids
                or len(event_ids) != len(set(event_ids))
                or not isinstance(segments, list)
                or not segments
                or len(segment_manifest_sha) != 64
                or not timestamp
            ):
                raise AlphaContractError("HG006 L001 queue retained document incomplete")
            for segment in segments:
                if not isinstance(segment, dict):
                    raise TypeError("HG006 L001 queue segment must be object")
                _validate_segment(segment)
            segment_ids = [str(segment["segment_id"]) for segment in segments]
            if len(segment_ids) != len(set(segment_ids)):
                raise AlphaContractError("HG006 L001 queue duplicate segment ID in request")

            request_id = request_id_for(chronology_id, document_id)
            if request_id in seen_request_ids:
                raise AlphaContractError("HG006 L001 queue duplicate request_id")
            seen_request_ids.add(request_id)
            shard_id = shard_for_request_id(request_id)

            request_payload = {
                "queue_id": QUEUE_ID,
                "request_id": request_id,
                "chronology_id": chronology_id,
                "document_id": document_id,
                "event_ids": sorted(event_ids),
                "symbol": symbol,
                "family": family,
                "chronology_timestamp_utc": timestamp,
                "segment_manifest_sha256": segment_manifest_sha,
                "segments": segments,
                "required_output_template": extraction_template(
                    document_id=document_id,
                    event_ids=event_ids,
                    symbol=symbol,
                    family=family,
                ),
            }
            prompt_envelope = {
                "system": SYSTEM_PROMPT,
                "request": request_payload,
            }
            prompt_sha = _sha256_bytes(_canonical_bytes(prompt_envelope))
            row = {
                "schema_version": 1,
                "queue_id": QUEUE_ID,
                "request_id": request_id,
                "shard_id": shard_id,
                "chronology_id": chronology_id,
                "document_id": document_id,
                "symbol": symbol,
                "family": family,
                "event_ids": sorted(event_ids),
                "model_config": MODEL_CONFIG,
                "model_config_sha256": model_config_sha,
                "prompt_sha256": prompt_sha,
                "prompt_envelope": prompt_envelope,
                "historical_terminal_labels_opened": False,
                "completion_probability_assigned": False,
                "return_outcomes_opened": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
            requests.append(row)
            shard_counts[shard_id] += 1
            family_counts[family] += 1

    if len(requests) != EXPECTED_REQUEST_COUNT:
        raise AlphaContractError(
            f"HG006 L001 queue expected {EXPECTED_REQUEST_COUNT} requests, got {len(requests)}"
        )
    if len(unavailable_ids) != 2:
        raise AlphaContractError("HG006 L001 queue expected two TEXT_UNAVAILABLE chronologies")

    output = {
        "schema_version": 1,
        "queue_id": QUEUE_ID,
        "classification": "FROZEN_HISTORICAL_LLM_INFERENCE_QUEUE_NOT_LABELS",
        "source_s002_pack_sha256": EXPECTED_S002_SHA,
        "model_config": MODEL_CONFIG,
        "model_config_sha256": model_config_sha,
        "request_count": len(requests),
        "chronology_count": EXPECTED_CHRONOLOGY_COUNT,
        "evidence_ready_chronology_count": EXPECTED_EVIDENCE_READY,
        "text_unavailable_chronology_ids": sorted(unavailable_ids),
        "request_counts_by_shard": {
            str(key): value for key, value in sorted(shard_counts.items())
        },
        "request_counts_by_family": dict(sorted(family_counts.items())),
        "requests": sorted(requests, key=lambda row: row["request_id"]),
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["queue_sha256"] = digest(output)
    return output


def validate_and_seal_response(
    *,
    queue_row: dict[str, Any],
    model_output: dict[str, Any],
    raw_model_response_bytes: bytes,
) -> dict[str, Any]:
    request = queue_row.get("prompt_envelope", {}).get("request")
    if not isinstance(request, dict):
        raise AlphaContractError("HG006 L001 response queue request unavailable")
    segment_ids = {
        str(row.get("segment_id") or "")
        for row in request.get("segments", [])
        if isinstance(row, dict)
    }
    if "" in segment_ids:
        raise AlphaContractError("HG006 L001 response queue segment ID unavailable")

    output = json.loads(json.dumps(model_output))
    provenance = output.get("provenance")
    if not isinstance(provenance, dict):
        raise AlphaContractError("HG006 L001 response provenance unavailable")
    expected_raw_sha = _sha256_bytes(raw_model_response_bytes)
    if provenance.get("raw_model_response_sha256") != expected_raw_sha:
        raise AlphaContractError("HG006 L001 raw model response SHA mismatch")
    if provenance.get("provider_runtime") != MODEL_CONFIG["provider_runtime"]:
        raise AlphaContractError("HG006 L001 provider/runtime mismatch")
    if provenance.get("model_id") != MODEL_CONFIG["model_id"]:
        raise AlphaContractError("HG006 L001 model ID mismatch")
    if provenance.get("model_config_sha256") != queue_row.get("model_config_sha256"):
        raise AlphaContractError("HG006 L001 model config SHA mismatch")
    if provenance.get("prompt_sha256") != queue_row.get("prompt_sha256"):
        raise AlphaContractError("HG006 L001 prompt SHA mismatch")

    sealed = validate_extraction(
        output,
        document_id=str(queue_row["document_id"]),
        event_ids={str(value) for value in queue_row["event_ids"]},
        symbol=str(queue_row["symbol"]),
        family=str(queue_row["family"]),
        allowed_segment_ids=segment_ids,
        segment_manifest_sha256=str(request["segment_manifest_sha256"]),
    )
    return {
        "schema_version": 1,
        "queue_id": QUEUE_ID,
        "request_id": queue_row["request_id"],
        "shard_id": queue_row["shard_id"],
        "chronology_id": queue_row["chronology_id"],
        "document_id": queue_row["document_id"],
        "status": "VALIDATED",
        "prompt_sha256": queue_row["prompt_sha256"],
        "model_config_sha256": queue_row["model_config_sha256"],
        "raw_model_response_sha256": expected_raw_sha,
        "validated_extraction": sealed,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
