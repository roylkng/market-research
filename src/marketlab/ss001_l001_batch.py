from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_llm_contract import (
    CONTRACT_ID,
    extraction_template,
    validate_extraction,
)

TRANSPORT_ID = "SS001-D007-L001-R001-v1"
SOURCE_QUEUE_ID = "SS001-D007-L001-P2-v1"
SOURCE_QUEUE_SHA = "59929004bcc5a5eae4491cadc237aa1bb26b822102d56b5b50cf61fb6b667618"
SOURCE_MODEL_CONFIG_SHA = "133b5705036d1782f671d6a171fe5f24298939cf6d84314875c2e8452e7169dc"
SOURCE_REQUEST_COUNT = 1240
SHARD_COUNT = 16
REQUIRED_PROVIDER = "OPENAI_COMPATIBLE_CHAT"

CONFIG_KEYS = {
    "schema_version",
    "provider_runtime",
    "model_id",
    "api_endpoint",
    "temperature",
    "top_p",
    "max_completion_tokens",
    "timeout_seconds",
    "auth_env",
    "token_parameter",
    "json_object_mode",
}

RUN_PROHIBITIONS = (
    "share_action_clearance_proven",
    "market_capitalization_calculated",
    "return_outcomes_opened",
    "portfolio_eligibility_allowed",
    "live_capital_allowed",
)


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise AlphaContractError("R001 requires finite canonical JSON") from exc


def _sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_closed(payload: dict[str, Any], label: str) -> None:
    for field in RUN_PROHIBITIONS:
        if payload.get(field) is not False:
            raise AlphaContractError(f"R001 {label} must have {field}=false")


def validate_config(config: dict[str, Any]) -> str:
    if not isinstance(config, dict) or set(config) != CONFIG_KEYS:
        raise AlphaContractError("R001 API model configuration keys differ from contract")
    if config.get("schema_version") != 1:
        raise AlphaContractError("R001 configuration schema_version mismatch")
    if config.get("provider_runtime") != REQUIRED_PROVIDER:
        raise AlphaContractError("R001 requires explicit OPENAI_COMPATIBLE_CHAT runtime")
    model_id = config.get("model_id")
    if not isinstance(model_id, str) or not model_id.strip() or model_id == "CONFIGURE_MODEL":
        raise AlphaContractError("R001 requires a configured model identifier")
    endpoint = config.get("api_endpoint")
    if not isinstance(endpoint, str):
        raise AlphaContractError("R001 endpoint must be a string")
    parsed = urlparse(endpoint)
    loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        not parsed.hostname
        or parsed.scheme not in {"https", "http"}
        or (parsed.scheme == "http" and not loopback)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise AlphaContractError("R001 endpoint must be HTTPS or HTTP loopback without credentials")
    token_parameter = config.get("token_parameter")
    if token_parameter not in {"max_tokens", "max_completion_tokens"}:
        raise AlphaContractError("R001 token_parameter must be an approved name")
    if not isinstance(config.get("json_object_mode"), bool):
        raise AlphaContractError("R001 json_object_mode must be boolean")
    auth_env = config.get("auth_env")
    if not isinstance(auth_env, str) or not auth_env.isidentifier():
        raise AlphaContractError("R001 auth_env must be a valid environment variable name")
    for key in ("temperature", "top_p"):
        value = config.get(key)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise AlphaContractError(f"R001 {key} must be finite numeric or null")
    temp = config["temperature"]
    top_p = config["top_p"]
    if temp is not None and not 0 <= temp <= 2:
        raise AlphaContractError("R001 temperature is outside [0,2]")
    if top_p is not None and not 0 < top_p <= 1:
        raise AlphaContractError("R001 top_p is outside (0,1]")
    tokens = config.get("max_completion_tokens")
    if isinstance(tokens, bool) or not isinstance(tokens, int) or not 1 <= tokens <= 4096:
        raise AlphaContractError("R001 max_completion_tokens must be 1..4096")
    timeout = config.get("timeout_seconds")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 300:
        raise AlphaContractError("R001 timeout_seconds must be 1..300")
    return digest(config)


def _request_basis(row: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "queue_id",
        "issuer_packet_rank",
        "symbol",
        "document_id",
        "segment_id",
        "source_document_manifest_sha256",
        "request_segment_manifest_sha256",
        "model_config_sha256",
    )
    return {field: row.get(field) for field in fields}


def validate_request(row: dict[str, Any]) -> None:
    if not isinstance(row, dict):
        raise TypeError("R001 request must be an object")
    if row.get("queue_id") != SOURCE_QUEUE_ID:
        raise AlphaContractError("R001 request queue ID mismatch")
    if row.get("model_config_sha256") != SOURCE_MODEL_CONFIG_SHA:
        raise AlphaContractError("R001 request source model config mismatch")
    if row.get("request_id") != digest(_request_basis(row)):
        raise AlphaContractError("R001 request ID mismatch")
    prompt = row.get("prompt_envelope")
    if not isinstance(prompt, dict) or not isinstance(prompt.get("request"), dict):
        raise AlphaContractError("R001 request prompt envelope unavailable")
    request = prompt["request"]
    original_prompt = {key: value for key, value in prompt.items() if key != "prompt_sha256"}
    if prompt.get("prompt_sha256") != digest(original_prompt):
        raise AlphaContractError("R001 recomputed prompt SHA mismatch")
    if row.get("prompt_sha256") != prompt["prompt_sha256"]:
        raise AlphaContractError("R001 row prompt SHA mismatch")
    if row.get("request_segment_manifest_sha256") != request.get("segment_manifest_sha256"):
        raise AlphaContractError("R001 page manifest SHA mismatch")
    if request.get("document_id") != row.get("document_id"):
        raise AlphaContractError("R001 page document ID mismatch")
    if row.get("symbol") not in request.get("symbols", []):
        raise AlphaContractError("R001 page issuer symbol mismatch")
    segments = request.get("segments")
    if not isinstance(segments, list) or len(segments) != 1:
        raise AlphaContractError("R001 requires exactly one original page segment")
    segment = segments[0]
    if not isinstance(segment, dict) or segment.get("segment_id") != row.get("segment_id"):
        raise AlphaContractError("R001 segment identity mismatch")
    segment_text = segment.get("text")
    if not isinstance(segment_text, str):
        raise AlphaContractError("R001 segment text missing")
    if segment.get("text_sha256") != _sha_bytes(segment_text.encode("utf-8")):
        raise AlphaContractError("R001 segment text SHA mismatch")
    template = request.get("required_output_template")
    if not isinstance(template, dict) or template.get("document_id") != row.get("document_id"):
        raise AlphaContractError("R001 required model output template mismatch")
    if template.get("contract_id") != CONTRACT_ID:
        raise AlphaContractError("R001 prompt contract mismatch")


def validate_queue(queue: dict[str, Any]) -> list[dict[str, Any]]:
    if queue.get("queue_id") != SOURCE_QUEUE_ID:
        raise AlphaContractError("R001 frozen queue ID mismatch")
    if queue.get("queue_sha256") != SOURCE_QUEUE_SHA:
        raise AlphaContractError("R001 frozen queue SHA mismatch")
    if digest({key: value for key, value in queue.items() if key != "queue_sha256"}) != SOURCE_QUEUE_SHA:
        raise AlphaContractError("R001 queue contents do not reproduce frozen SHA")
    if queue.get("source_p1_run_sha256") != (
        "1a3a2f73eaed8ba09c84ab7c8d60699fa895f39d25d5797bd16138b09fd620cb"
    ):
        raise AlphaContractError("R001 P1 source run mismatch")
    if queue.get("model_config_sha256") != SOURCE_MODEL_CONFIG_SHA:
        raise AlphaContractError("R001 frozen queue model config mismatch")
    if queue.get("fresh_request_count") != SOURCE_REQUEST_COUNT or queue.get("shard_count") != SHARD_COUNT:
        raise AlphaContractError("R001 queue size or shard count mismatch")
    if queue.get("feasibility_pass") is not True or queue.get("model_inference_executed") is not False:
        raise AlphaContractError("R001 requires frozen pre-inference source queue")
    _require_closed(queue, "source queue")
    rows = queue.get("requests")
    if not isinstance(rows, list) or len(rows) != SOURCE_REQUEST_COUNT:
        raise AlphaContractError("R001 frozen queue requests unavailable")
    ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        validate_request(row)
        if row.get("global_request_index") != index:
            raise AlphaContractError("R001 global request order changed")
        if row.get("shard_id") != (index - 1) % SHARD_COUNT:
            raise AlphaContractError("R001 frozen shard assignment changed")
        request_id = row["request_id"]
        if request_id in ids:
            raise AlphaContractError("R001 duplicate request ID")
        ids.add(request_id)
    return rows


def build_preflight(queue: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    config_sha = validate_config(config)
    rows = validate_queue(queue)
    counts = Counter(row["shard_id"] for row in rows)
    output = {
        "schema_version": 1,
        "transport_id": TRANSPORT_ID,
        "source_queue_id": SOURCE_QUEUE_ID,
        "source_queue_sha256": SOURCE_QUEUE_SHA,
        "source_p2_model_config_sha256": SOURCE_MODEL_CONFIG_SHA,
        "runtime_model_config_sha256": config_sha,
        "runtime_model_id": config["model_id"],
        "runtime_provider": config["provider_runtime"],
        "source_runtime_equivalence_claimed": False,
        "request_count": len(rows),
        "shard_count": SHARD_COUNT,
        "shard_request_counts": {str(key): counts[key] for key in sorted(counts)},
        "status": "PREFLIGHT_PASS_NO_INFERENCE",
        "model_inference_executed": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["preflight_sha256"] = digest(output)
    return output


def validate_and_seal_response(
    row: dict[str, Any],
    config: dict[str, Any],
    raw_content: str,
) -> dict[str, Any]:
    validate_request(row)
    config_sha = validate_config(config)
    if not isinstance(raw_content, str) or not raw_content:
        raise AlphaContractError("R001 model returned no text")
    try:
        result = json.loads(raw_content, parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"invalid JSON constant: {value}")
        ))
    except (json.JSONDecodeError, ValueError) as exc:
        raise AlphaContractError("R001 model output is not strict JSON") from exc
    if not isinstance(result, dict):
        raise AlphaContractError("R001 model output must be a JSON object")
    request = row["prompt_envelope"]["request"]
    template = extraction_template(
        document_id=str(row["document_id"]),
        event_ids=[str(v) for v in request["event_ids"]],
        symbols=[str(v) for v in request["symbols"]],
    )
    expected_substantive = set(template) - {"provenance"}
    supplied_substantive = set(result) - {"provenance"}
    if supplied_substantive != expected_substantive:
        raise AlphaContractError("R001 output fields differ from frozen substantive schema")

    output = copy.deepcopy(result)
    output["provenance"] = {
        "provider_runtime": config["provider_runtime"],
        "model_id": config["model_id"],
        "model_config_sha256": config_sha,
        "prompt_contract_id": CONTRACT_ID,
        "prompt_sha256": row["prompt_sha256"],
        "input_document_id": row["document_id"],
        "input_segment_manifest_sha256": request["segment_manifest_sha256"],
        "raw_model_response_sha256": _sha_bytes(raw_content.encode("utf-8")),
    }
    sealed = validate_extraction(
        output,
        input_document_id=str(row["document_id"]),
        allowed_event_ids={str(v) for v in request["event_ids"]},
        allowed_symbols={str(v) for v in request["symbols"]},
        allowed_segment_ids={str(s["segment_id"]) for s in request["segments"]},
        expected_segment_manifest_sha256=str(request["segment_manifest_sha256"]),
    )
    return {
        "schema_version": 1,
        "transport_id": TRANSPORT_ID,
        "request_id": row["request_id"],
        "global_request_index": row["global_request_index"],
        "shard_id": row["shard_id"],
        "symbol": row["symbol"],
        "document_id": row["document_id"],
        "segment_id": row["segment_id"],
        "source_queue_sha256": SOURCE_QUEUE_SHA,
        "source_p2_model_config_sha256": SOURCE_MODEL_CONFIG_SHA,
        "runtime_model_config_sha256": config_sha,
        "source_runtime_equivalence_claimed": False,
        "prompt_sha256": row["prompt_sha256"],
        "raw_model_response_sha256": _sha_bytes(raw_content.encode("utf-8")),
        "raw_model_response_text": raw_content,
        "validated_extraction": sealed,
        "status": "VALIDATED_PENDING_SEMANTIC_AUDIT",
        "semantic_audit_status": "PENDING",
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def build_collection_status(
    queue: dict[str, Any],
    config: dict[str, Any],
    validated_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    requests = validate_queue(queue)
    config_sha = validate_config(config)
    index = {row["request_id"]: row for row in requests}
    seen: set[str] = set()
    for record in validated_rows:
        request_id = record.get("request_id")
        if request_id in seen or request_id not in index:
            raise AlphaContractError("R001 invalid or duplicate collected request ID")
        seen.add(request_id)
        source = index[request_id]
        if record.get("status") != "VALIDATED_PENDING_SEMANTIC_AUDIT":
            raise AlphaContractError("R001 collection includes unvalidated output")
        if record.get("runtime_model_config_sha256") != config_sha:
            raise AlphaContractError("R001 mixed model/runtime configuration")
        if (
            record.get("document_id") != source["document_id"]
            or record.get("prompt_sha256") != source["prompt_sha256"]
            or record.get("shard_id") != source["shard_id"]
        ):
            raise AlphaContractError("R001 collected response source mismatch")
        _require_closed(record, "collected response")
        if record.get("semantic_audit_status") != "PENDING":
            raise AlphaContractError("R001 transport cannot claim completed semantic audit")
        extraction = record.get("validated_extraction")
        if not isinstance(extraction, dict) or extraction.get("document_id") != source["document_id"]:
            raise AlphaContractError("R001 validated response is not bound to source")
        raw_content = record.get("raw_model_response_text")
        if not isinstance(raw_content, str):
            raise AlphaContractError("R001 collected response lacks raw model text")
        reconstructed = validate_and_seal_response(source, config, raw_content)
        if record != reconstructed:
            raise AlphaContractError("R001 collected response does not reproduce sealed record")
    count = len(validated_rows)
    status = (
        "COMPLETE_VALIDATED_PENDING_SEMANTIC_AUDIT"
        if count == SOURCE_REQUEST_COUNT
        else "PARTIAL_VALIDATED_EXTRACTIONS"
    )
    output = {
        "schema_version": 1,
        "transport_id": TRANSPORT_ID,
        "source_queue_sha256": SOURCE_QUEUE_SHA,
        "runtime_model_config_sha256": config_sha,
        "validated_request_count": count,
        "remaining_request_count": SOURCE_REQUEST_COUNT - count,
        "status": status,
        "model_inference_executed": count > 0,
        "semantic_audit_complete": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["collection_sha256"] = digest(output)
    return output
