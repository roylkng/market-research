from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import requests

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_llm_contract import CONTRACT_ID, validate_extraction


class SS002LLMRuntimeError(RuntimeError):
    """Raised when an L001 model request cannot be executed or decoded safely."""


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    provider_runtime: str
    base_url: str
    model_id: str
    temperature: float = 0.0
    top_p: float = 1.0
    max_output_tokens: int = 4096
    timeout_seconds: float = 120.0

    def public_payload(self) -> dict[str, Any]:
        return {
            "provider_runtime": self.provider_runtime,
            "base_url": self.base_url.rstrip("/"),
            "model_id": self.model_id,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_output_tokens": self.max_output_tokens,
            "timeout_seconds": self.timeout_seconds,
            "contract_id": CONTRACT_ID,
            "transport": "OPENAI_COMPATIBLE_CHAT_COMPLETIONS",
            "structured_output_mode": "JSON_OBJECT",
        }

    def sha256(self) -> str:
        return digest(self.public_payload())


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
        raise AlphaContractError("SS002 L001 runtime payload must be finite JSON") from exc


def _response_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise SS002LLMRuntimeError("LLM response must be a JSON object")
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise SS002LLMRuntimeError("LLM response must contain exactly one choice")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise SS002LLMRuntimeError("LLM choice must be an object")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise SS002LLMRuntimeError("LLM choice.message must be an object")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise SS002LLMRuntimeError("LLM message content must be non-empty text")
    return content


def build_chat_request(
    *,
    prompt_envelope: dict[str, Any],
    config: OpenAICompatibleConfig,
) -> dict[str, Any]:
    system = prompt_envelope.get("system")
    request = prompt_envelope.get("request")
    prompt_sha = prompt_envelope.get("prompt_sha256")
    if not isinstance(system, str) or not isinstance(request, dict):
        raise AlphaContractError("SS002 L001 prompt envelope is incomplete")
    if not isinstance(prompt_sha, str) or len(prompt_sha) != 64:
        raise AlphaContractError("SS002 L001 prompt SHA is unavailable")
    return {
        "model": config.model_id,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    request,
                    sort_keys=True,
                    ensure_ascii=False,
                    allow_nan=False,
                ),
            },
        ],
        "temperature": config.temperature,
        "top_p": config.top_p,
        "max_tokens": config.max_output_tokens,
        "response_format": {"type": "json_object"},
        "stream": False,
    }


def execute_l001_request(
    *,
    prompt_envelope: dict[str, Any],
    config: OpenAICompatibleConfig,
    api_key: str | None,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    request = prompt_envelope.get("request")
    if not isinstance(request, dict):
        raise AlphaContractError("SS002 L001 prompt request is unavailable")
    document_id = str(request.get("document_id") or "")
    event_ids = request.get("event_ids")
    symbols = request.get("symbols")
    segments = request.get("segments")
    manifest_sha = str(request.get("segment_manifest_sha256") or "")
    if (
        not document_id
        or not isinstance(event_ids, list)
        or not isinstance(symbols, list)
        or not isinstance(segments, list)
        or not manifest_sha
    ):
        raise AlphaContractError("SS002 L001 prompt request identity is incomplete")

    allowed_segment_ids = {
        str(row.get("segment_id") or "")
        for row in segments
        if isinstance(row, dict)
    }
    if "" in allowed_segment_ids or len(allowed_segment_ids) != len(segments):
        raise AlphaContractError("SS002 L001 prompt segment IDs are invalid")

    body = build_chat_request(prompt_envelope=prompt_envelope, config=config)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    client = session or requests.Session()
    endpoint = f"{config.base_url.rstrip('/')}/v1/chat/completions"
    try:
        response = client.post(
            endpoint,
            headers=headers,
            json=body,
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SS002LLMRuntimeError(f"LLM_REQUEST_FAILED: {exc}") from exc

    raw_response = response.content
    if not raw_response:
        raise SS002LLMRuntimeError("LLM response bytes are empty")
    raw_response_sha = hashlib.sha256(raw_response).hexdigest()
    try:
        payload = response.json()
    except ValueError as exc:
        raise SS002LLMRuntimeError("LLM transport response is not JSON") from exc

    content = _response_content(payload)
    try:
        extracted = json.loads(content)
    except json.JSONDecodeError as exc:
        raise SS002LLMRuntimeError(
            "LLM message content is not valid JSON"
        ) from exc
    if not isinstance(extracted, dict):
        raise SS002LLMRuntimeError("LLM structured content must be an object")

    extracted["provenance"] = {
        "provider_runtime": config.provider_runtime,
        "model_id": config.model_id,
        "model_config_sha256": config.sha256(),
        "prompt_contract_id": CONTRACT_ID,
        "prompt_sha256": str(prompt_envelope["prompt_sha256"]),
        "input_document_id": document_id,
        "input_segment_manifest_sha256": manifest_sha,
        "raw_model_response_sha256": raw_response_sha,
    }

    sealed = validate_extraction(
        extracted,
        input_document_id=document_id,
        allowed_event_ids={str(value) for value in event_ids},
        allowed_symbols={str(value) for value in symbols},
        allowed_segment_ids=allowed_segment_ids,
        expected_segment_manifest_sha256=manifest_sha,
    )
    return {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "document_id": document_id,
        "model_config": config.public_payload(),
        "model_config_sha256": config.sha256(),
        "prompt_sha256": prompt_envelope["prompt_sha256"],
        "request_body_sha256": hashlib.sha256(_canonical_bytes(body)).hexdigest(),
        "raw_transport_response_sha256": raw_response_sha,
        "validated_extraction": sealed,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
