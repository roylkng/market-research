from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg006_inference_queue import MODEL_CONFIG, SYSTEM_PROMPT
from marketlab.hg006_stage_contract import extraction_template

QUEUE_ID = "HG006-L001-P3-v1"
EXPECTED_S003_ID = "HG006-S003-v1"
EXPECTED_S003_SHA = "ebd2943f9c41e4eb93fca9039cb73143150d2eb1c8d7b3d101e1fd0f9614dc03"
EXPECTED_PRIOR_QUEUE_ID = "HG006-L001-P1-v1"
EXPECTED_PRIOR_QUEUE_SHA = "6732f5741ec6d9a2e1926a94d234c642871d454f0354d60dfa87cec3807ce934"
EXPECTED_PRIOR_INGESTION_ID = "HG006-L001-P2-v1"
EXPECTED_PRIOR_INGESTION_SHA = "2188bf803f2088cd10f26892f92f1a82fc810543ad9679c4fc20534e2a3e59e6"
EXPECTED_MODEL_CONFIG_SHA = "043ec1f2d38aec7e72b24cfcbe864aebd83cda8b717d3c8c0fac2ecb3cafa51d"

EXPECTED_CHRONOLOGY_COUNT = 1043
EXPECTED_EVIDENCE_READY = 1032
EXPECTED_TEXT_UNAVAILABLE = 11
EXPECTED_REQUEST_COUNT = 4822
EXPECTED_REUSE_COUNT = 1443
EXPECTED_FRESH_COUNT = 3379
EXPECTED_PRIOR_REQUEST_COUNT = 1448
EXPECTED_CHANGED_PRIOR_COUNT = 5
SHARD_COUNT = 16


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
        raise AlphaContractError("HG006 P3 payload must be finite JSON") from exc


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fresh_request_id_for(
    chronology_id: str,
    document_id: str,
    segment_manifest_sha256: str,
) -> str:
    if (
        not chronology_id
        or len(document_id) != 64
        or len(segment_manifest_sha256) != 64
    ):
        raise AlphaContractError("HG006 P3 fresh request identity is invalid")
    raw = (
        f"{QUEUE_ID}|{chronology_id}|{document_id}|{segment_manifest_sha256}"
    ).encode()
    return _sha256(raw)


def shard_for_request_id(request_id: str) -> int:
    if len(request_id) != 64:
        raise AlphaContractError("HG006 P3 request_id must be SHA-256")
    try:
        return int(request_id[:8], 16) % SHARD_COUNT
    except ValueError as exc:
        raise AlphaContractError("HG006 P3 request_id must be hex") from exc


def _validate_pack(pack: dict[str, Any]) -> list[dict[str, Any]]:
    if pack.get("pack_id") != EXPECTED_S003_ID:
        raise AlphaContractError("HG006 P3 requires frozen S003 pack")
    if pack.get("pack_sha256") != EXPECTED_S003_SHA:
        raise AlphaContractError("HG006 P3 S003 pack SHA mismatch")
    if pack.get("chronology_count") != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 P3 chronology count mismatch")
    states = pack.get("state_counts")
    if not isinstance(states, dict):
        raise AlphaContractError("HG006 P3 S003 state counts unavailable")
    if (
        states.get("EVIDENCE_READY") != EXPECTED_EVIDENCE_READY
        or states.get("TEXT_UNAVAILABLE") != EXPECTED_TEXT_UNAVAILABLE
    ):
        raise AlphaContractError("HG006 P3 S003 evidence state mismatch")
    if pack.get("retained_document_count") != EXPECTED_REQUEST_COUNT:
        raise AlphaContractError("HG006 P3 retained document count mismatch")
    for field in (
        "expanded_population_terminal_labels_opened",
        "expanded_population_completion_probabilities_assigned",
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if pack.get(field) is not False:
            raise AlphaContractError(f"HG006 P3 requires S003 {field}=false")
    rows = pack.get("chronologies")
    if not isinstance(rows, list) or len(rows) != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 P3 S003 chronology rows unavailable")
    return rows


def _validate_prior_queue(queue: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    if queue.get("queue_id") != EXPECTED_PRIOR_QUEUE_ID:
        raise AlphaContractError("HG006 P3 prior queue ID mismatch")
    if queue.get("queue_sha256") != EXPECTED_PRIOR_QUEUE_SHA:
        raise AlphaContractError("HG006 P3 prior queue SHA mismatch")
    if queue.get("request_count") != EXPECTED_PRIOR_REQUEST_COUNT:
        raise AlphaContractError("HG006 P3 prior queue count mismatch")
    if queue.get("model_config_sha256") != EXPECTED_MODEL_CONFIG_SHA:
        raise AlphaContractError("HG006 P3 prior model config mismatch")
    rows = queue.get("requests")
    if not isinstance(rows, list) or len(rows) != EXPECTED_PRIOR_REQUEST_COUNT:
        raise AlphaContractError("HG006 P3 prior queue rows unavailable")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    request_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 P3 prior queue row must be object")
        key = (
            str(row.get("chronology_id") or ""),
            str(row.get("document_id") or ""),
        )
        request_id = str(row.get("request_id") or "")
        if (
            not key[0]
            or len(key[1]) != 64
            or not request_id
            or key in result
            or request_id in request_ids
        ):
            raise AlphaContractError("HG006 P3 prior queue identity invalid")
        result[key] = row
        request_ids.add(request_id)
    return result


def _validate_prior_ingestion(
    ingestion: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if ingestion.get("execution_id") != EXPECTED_PRIOR_INGESTION_ID:
        raise AlphaContractError("HG006 P3 prior ingestion ID mismatch")
    if ingestion.get("ingestion_sha256") != EXPECTED_PRIOR_INGESTION_SHA:
        raise AlphaContractError("HG006 P3 prior ingestion SHA mismatch")
    if ingestion.get("request_count") != EXPECTED_PRIOR_REQUEST_COUNT:
        raise AlphaContractError("HG006 P3 prior ingestion count mismatch")
    if ingestion.get("full_ingestion_pass") is not True:
        raise AlphaContractError("HG006 P3 prior ingestion did not pass")
    if ingestion.get("validated_request_count") != EXPECTED_PRIOR_REQUEST_COUNT:
        raise AlphaContractError("HG006 P3 prior ingestion not fully validated")
    for field in (
        "historical_terminal_labels_opened",
        "completion_probabilities_assigned",
        "return_outcomes_opened",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if ingestion.get(field) is not False:
            raise AlphaContractError(
                f"HG006 P3 requires prior ingestion {field}=false"
            )
    rows = ingestion.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_PRIOR_REQUEST_COUNT:
        raise AlphaContractError("HG006 P3 prior ingestion rows unavailable")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 P3 prior ingestion row must be object")
        request_id = str(row.get("request_id") or "")
        if (
            not request_id
            or request_id in result
            or row.get("status") != "VALIDATED"
            or not isinstance(row.get("validated_response"), dict)
        ):
            raise AlphaContractError("HG006 P3 prior validated row invalid")
        result[request_id] = row
    return result


def _validate_segment(segment: dict[str, Any]) -> None:
    segment_id = str(segment.get("segment_id") or "")
    text = segment.get("text")
    text_sha = str(segment.get("text_sha256") or "")
    if not segment_id or not isinstance(text, str) or len(text_sha) != 64:
        raise AlphaContractError("HG006 P3 segment incomplete")
    if _sha256(text.encode("utf-8")) != text_sha:
        raise AlphaContractError("HG006 P3 segment text SHA mismatch")


def _fresh_prompt_row(
    *,
    chronology_id: str,
    symbol: str,
    family: str,
    document: dict[str, Any],
) -> dict[str, Any]:
    document_id = str(document.get("document_id") or "")
    event_ids = sorted(str(value) for value in document.get("event_ids", []))
    segments = document.get("selected_segments")
    segment_manifest_sha = str(document.get("segment_manifest_sha256") or "")
    timestamp = str(document.get("chronology_timestamp_utc") or "")
    if (
        len(document_id) != 64
        or not event_ids
        or len(event_ids) != len(set(event_ids))
        or not isinstance(segments, list)
        or not segments
        or len(segment_manifest_sha) != 64
        or not timestamp
    ):
        raise AlphaContractError("HG006 P3 retained document incomplete")
    for segment in segments:
        if not isinstance(segment, dict):
            raise TypeError("HG006 P3 segment must be object")
        _validate_segment(segment)
    segment_ids = [str(segment["segment_id"]) for segment in segments]
    if len(segment_ids) != len(set(segment_ids)):
        raise AlphaContractError("HG006 P3 duplicate segment ID in request")

    request_id = fresh_request_id_for(
        chronology_id,
        document_id,
        segment_manifest_sha,
    )
    request_payload = {
        "queue_id": QUEUE_ID,
        "request_id": request_id,
        "chronology_id": chronology_id,
        "document_id": document_id,
        "event_ids": event_ids,
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
    prompt_sha = _sha256(_canonical_bytes(prompt_envelope))
    return {
        "schema_version": 1,
        "queue_id": QUEUE_ID,
        "request_id": request_id,
        "shard_id": shard_for_request_id(request_id),
        "chronology_id": chronology_id,
        "document_id": document_id,
        "symbol": symbol,
        "family": family,
        "event_ids": event_ids,
        "model_config": MODEL_CONFIG,
        "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
        "prompt_sha256": prompt_sha,
        "prompt_envelope": prompt_envelope,
    }


def _is_exact_reuse(
    prior_row: dict[str, Any],
    *,
    chronology_id: str,
    symbol: str,
    family: str,
    document: dict[str, Any],
) -> bool:
    request = prior_row.get("prompt_envelope", {}).get("request")
    envelope = prior_row.get("prompt_envelope")
    if not isinstance(request, dict) or not isinstance(envelope, dict):
        return False
    expected_template = extraction_template(
        document_id=str(document.get("document_id") or ""),
        event_ids=sorted(str(value) for value in document.get("event_ids", [])),
        symbol=symbol,
        family=family,
    )
    return (
        prior_row.get("chronology_id") == chronology_id
        and prior_row.get("symbol") == symbol
        and prior_row.get("family") == family
        and prior_row.get("model_config_sha256") == EXPECTED_MODEL_CONFIG_SHA
        and envelope.get("system") == SYSTEM_PROMPT
        and request.get("chronology_id") == chronology_id
        and request.get("document_id") == document.get("document_id")
        and request.get("event_ids")
        == sorted(str(value) for value in document.get("event_ids", []))
        and request.get("symbol") == symbol
        and request.get("family") == family
        and request.get("chronology_timestamp_utc")
        == document.get("chronology_timestamp_utc")
        and request.get("segment_manifest_sha256")
        == document.get("segment_manifest_sha256")
        and request.get("segments") == document.get("selected_segments")
        and request.get("required_output_template") == expected_template
    )


def build_p3_extension_queue(
    *,
    full_pack: dict[str, Any],
    prior_queue: dict[str, Any],
    prior_ingestion: dict[str, Any],
) -> dict[str, Any]:
    chronologies = _validate_pack(full_pack)
    prior_by_key = _validate_prior_queue(prior_queue)
    prior_ingestion_by_id = _validate_prior_ingestion(prior_ingestion)

    requests: list[dict[str, Any]] = []
    seen_request_ids: set[str] = set()
    chronology_ids: set[str] = set()
    unavailable_ids: list[str] = []
    state_counts: Counter[str] = Counter()
    fresh_shard_counts: Counter[int] = Counter()
    family_counts: Counter[str] = Counter()
    prior_pair_count = 0
    changed_prior_count = 0

    for chronology in chronologies:
        if not isinstance(chronology, dict):
            raise TypeError("HG006 P3 chronology must be object")
        chronology_id = str(chronology.get("chronology_id") or "")
        symbol = str(chronology.get("symbol") or "")
        family = str(chronology.get("family") or "")
        state = str(chronology.get("evidence_state") or "")
        if not chronology_id or not symbol or not family:
            raise AlphaContractError("HG006 P3 chronology identity incomplete")
        if chronology_id in chronology_ids:
            raise AlphaContractError("HG006 P3 duplicate chronology")
        chronology_ids.add(chronology_id)

        if state == "TEXT_UNAVAILABLE":
            unavailable_ids.append(chronology_id)
            if chronology.get("retained_documents"):
                raise AlphaContractError(
                    "HG006 P3 TEXT_UNAVAILABLE chronology carries documents"
                )
            continue
        if state != "EVIDENCE_READY":
            raise AlphaContractError("HG006 P3 unknown evidence state")

        documents = chronology.get("retained_documents")
        if not isinstance(documents, list) or not documents:
            raise AlphaContractError("HG006 P3 ready chronology lacks documents")
        for document in documents:
            if not isinstance(document, dict):
                raise TypeError("HG006 P3 retained document must be object")
            key = (chronology_id, str(document.get("document_id") or ""))
            prior = prior_by_key.get(key)
            if prior is not None:
                prior_pair_count += 1

            if prior is not None and _is_exact_reuse(
                prior,
                chronology_id=chronology_id,
                symbol=symbol,
                family=family,
                document=document,
            ):
                prior_request_id = str(prior["request_id"])
                ingested = prior_ingestion_by_id.get(prior_request_id)
                if ingested is None:
                    raise AlphaContractError(
                        "HG006 P3 reusable prior response missing ingestion row"
                    )
                if (
                    ingested.get("chronology_id") != chronology_id
                    or ingested.get("document_id") != document.get("document_id")
                    or ingested.get("symbol") != symbol
                    or ingested.get("family") != family
                ):
                    raise AlphaContractError(
                        "HG006 P3 reusable ingestion identity mismatch"
                    )
                request_id = prior_request_id
                row = {
                    **prior,
                    "p3_execution_state": "P2_VALIDATED_REUSE",
                    "p3_source_ingestion_sha256": EXPECTED_PRIOR_INGESTION_SHA,
                    "p3_prior_validated_response_sha256": digest(
                        ingested["validated_response"]
                    ),
                }
            else:
                if prior is not None:
                    changed_prior_count += 1
                row = _fresh_prompt_row(
                    chronology_id=chronology_id,
                    symbol=symbol,
                    family=family,
                    document=document,
                )
                request_id = str(row["request_id"])
                row["p3_execution_state"] = "FRESH_MODEL_REQUIRED"
                row["p3_source_ingestion_sha256"] = None
                row["p3_prior_validated_response_sha256"] = None
                fresh_shard_counts[int(row["shard_id"])] += 1

            if request_id in seen_request_ids:
                raise AlphaContractError("HG006 P3 duplicate request ID")
            seen_request_ids.add(request_id)
            requests.append(row)
            state_counts[str(row["p3_execution_state"])] += 1
            family_counts[family] += 1

    if len(requests) != EXPECTED_REQUEST_COUNT:
        raise AlphaContractError(
            f"HG006 P3 expected {EXPECTED_REQUEST_COUNT} requests, got {len(requests)}"
        )
    if len(unavailable_ids) != EXPECTED_TEXT_UNAVAILABLE:
        raise AlphaContractError("HG006 P3 TEXT_UNAVAILABLE count mismatch")
    if prior_pair_count != EXPECTED_PRIOR_REQUEST_COUNT:
        raise AlphaContractError("HG006 P3 prior pair overlap count mismatch")
    if changed_prior_count != EXPECTED_CHANGED_PRIOR_COUNT:
        raise AlphaContractError("HG006 P3 changed prior prompt count mismatch")
    if state_counts["P2_VALIDATED_REUSE"] != EXPECTED_REUSE_COUNT:
        raise AlphaContractError("HG006 P3 exact reuse count mismatch")
    if state_counts["FRESH_MODEL_REQUIRED"] != EXPECTED_FRESH_COUNT:
        raise AlphaContractError("HG006 P3 fresh request count mismatch")

    output = {
        "schema_version": 1,
        "queue_id": QUEUE_ID,
        "classification": "FULL_PRIORITY_HISTORICAL_LLM_EXTENSION_QUEUE_NOT_LABELS",
        "source_s003_pack_sha256": EXPECTED_S003_SHA,
        "source_prior_queue_sha256": EXPECTED_PRIOR_QUEUE_SHA,
        "source_prior_ingestion_sha256": EXPECTED_PRIOR_INGESTION_SHA,
        "model_config": MODEL_CONFIG,
        "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
        "chronology_count": EXPECTED_CHRONOLOGY_COUNT,
        "evidence_ready_chronology_count": EXPECTED_EVIDENCE_READY,
        "text_unavailable_chronology_ids": sorted(unavailable_ids),
        "request_count": len(requests),
        "execution_state_counts": dict(sorted(state_counts.items())),
        "prior_pair_overlap_count": prior_pair_count,
        "changed_prior_prompt_count": changed_prior_count,
        "fresh_request_counts_by_shard": {
            str(key): value for key, value in sorted(fresh_shard_counts.items())
        },
        "request_counts_by_family": dict(sorted(family_counts.items())),
        "requests": sorted(
            requests,
            key=lambda row: (
                str(row["p3_execution_state"]),
                str(row["request_id"]),
            ),
        ),
        "expanded_population_terminal_labels_opened": False,
        "expanded_population_completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["queue_sha256"] = digest(output)
    return output
