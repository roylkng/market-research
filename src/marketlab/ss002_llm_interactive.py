from __future__ import annotations

import hashlib
import json
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_llm_contract import CONTRACT_ID, validate_extraction

RUN_ID = "SS002-L001-P1-GPT56SOL-INTERACTIVE-v1"
EXPECTED_SELECTION_SHA = "c040c519b8d28344a607838d2f025555b92fb9391582855e2dab7323aa805bc0"


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
        raise AlphaContractError("SS002 interactive response must be finite JSON") from exc


def interactive_model_config(registration: dict[str, Any]) -> dict[str, Any]:
    if registration.get("run_id") != RUN_ID:
        raise AlphaContractError("SS002 interactive run registration mismatch")
    if registration.get("selection_sha256") != EXPECTED_SELECTION_SHA:
        raise AlphaContractError("SS002 interactive selection SHA mismatch")
    if registration.get("contract_id") != CONTRACT_ID:
        raise AlphaContractError("SS002 interactive contract mismatch")
    if registration.get("return_outcomes_opened") is not False:
        raise AlphaContractError("SS002 interactive run must keep returns closed")
    return {
        "provider_runtime": registration.get("provider_runtime"),
        "model_id": registration.get("model_id"),
        "model_configuration": registration.get("model_configuration"),
        "contract_id": CONTRACT_ID,
        "selection_sha256": EXPECTED_SELECTION_SHA,
    }


def seal_interactive_response(
    *,
    raw_extraction: dict[str, Any],
    selection_row: dict[str, Any],
    registration: dict[str, Any],
) -> dict[str, Any]:
    prompt = selection_row.get("prompt_envelope")
    if not isinstance(prompt, dict):
        raise AlphaContractError("SS002 interactive selection prompt unavailable")
    request = prompt.get("request")
    if not isinstance(request, dict):
        raise AlphaContractError("SS002 interactive prompt request unavailable")

    if raw_extraction.get("provenance") not in (None, {}):
        raise AlphaContractError("SS002 interactive raw extraction must not prefill provenance")

    document_id = str(selection_row.get("document_id") or "")
    if document_id != str(request.get("document_id") or ""):
        raise AlphaContractError("SS002 interactive document identity mismatch")
    if selection_row.get("prompt_sha256") != prompt.get("prompt_sha256"):
        raise AlphaContractError("SS002 interactive prompt SHA mismatch")

    segments = request.get("segments")
    if not isinstance(segments, list):
        raise AlphaContractError("SS002 interactive prompt segments unavailable")
    segment_ids = {
        str(row.get("segment_id") or "")
        for row in segments
        if isinstance(row, dict)
    }
    if "" in segment_ids or len(segment_ids) != len(segments):
        raise AlphaContractError("SS002 interactive segment IDs invalid")

    raw_bytes = _canonical_bytes(raw_extraction)
    model_config = interactive_model_config(registration)
    model_config_sha = digest(model_config)

    extracted = dict(raw_extraction)
    extracted["provenance"] = {
        "provider_runtime": str(registration["provider_runtime"]),
        "model_id": str(registration["model_id"]),
        "model_config_sha256": model_config_sha,
        "prompt_contract_id": CONTRACT_ID,
        "prompt_sha256": str(prompt["prompt_sha256"]),
        "input_document_id": document_id,
        "input_segment_manifest_sha256": str(
            request["segment_manifest_sha256"]
        ),
        "raw_model_response_sha256": hashlib.sha256(raw_bytes).hexdigest(),
    }

    sealed = validate_extraction(
        extracted,
        input_document_id=document_id,
        allowed_event_ids={str(value) for value in request["event_ids"]},
        allowed_symbols={str(value) for value in request["symbols"]},
        allowed_segment_ids=segment_ids,
        expected_segment_manifest_sha256=str(request["segment_manifest_sha256"]),
    )
    return {
        "schema_version": 1,
        "run_id": RUN_ID,
        "pilot_family": selection_row.get("pilot_family"),
        "symbol": selection_row.get("symbol"),
        "announcement_id": selection_row.get("announcement_id"),
        "document_id": document_id,
        "selection_sha256": EXPECTED_SELECTION_SHA,
        "prompt_sha256": prompt["prompt_sha256"],
        "raw_model_response_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "model_config": model_config,
        "model_config_sha256": model_config_sha,
        "validated_extraction": sealed,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
