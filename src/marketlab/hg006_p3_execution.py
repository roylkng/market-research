from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg006_native_materializer import materialize_native_output
from marketlab.hg006_p3_inference import (
    EXPECTED_EVIDENCE_READY,
    EXPECTED_FRESH_COUNT,
    EXPECTED_MODEL_CONFIG_SHA,
    EXPECTED_PRIOR_INGESTION_SHA,
    EXPECTED_REQUEST_COUNT,
    EXPECTED_REUSE_COUNT,
    QUEUE_ID,
)
from marketlab.hg006_stage_contract import validate_extraction

EXECUTION_ID = "HG006-L001-P3-T1-v1"
EXPECTED_QUEUE_SHA = "0b93d72fa063c05568cb508b4c4249ad14dff48fa2900209750059a5ca954429"
BATCH_COUNT = 64
EXPECTED_BATCH_SIZES = {
    0: 41, 1: 49, 2: 56, 3: 37,
    4: 63, 5: 46, 6: 64, 7: 42,
    8: 52, 9: 53, 10: 58, 11: 68,
    12: 44, 13: 52, 14: 55, 15: 47,
    16: 57, 17: 64, 18: 59, 19: 56,
    20: 55, 21: 52, 22: 53, 23: 60,
    24: 61, 25: 58, 26: 49, 27: 61,
    28: 55, 29: 52, 30: 45, 31: 59,
    32: 47, 33: 59, 34: 44, 35: 52,
    36: 52, 37: 42, 38: 62, 39: 54,
    40: 55, 41: 65, 42: 46, 43: 53,
    44: 46, 45: 52, 46: 52, 47: 63,
    48: 42, 49: 36, 50: 65, 51: 43,
    52: 59, 53: 56, 54: 53, 55: 57,
    56: 48, 57: 55, 58: 43, 59: 57,
    60: 56, 61: 41, 62: 54, 63: 47,
}


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
        raise AlphaContractError("HG006 P3 execution payload must be finite JSON") from exc


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def transport_batch_for_request_id(request_id: str) -> int:
    if len(request_id) != 64:
        raise AlphaContractError("HG006 P3 request_id must be SHA-256")
    try:
        primary = int(request_id[:8], 16) % 16
        sub_batch = int(request_id[8:16], 16) % 4
    except ValueError as exc:
        raise AlphaContractError("HG006 P3 request_id must be hex") from exc
    return primary * 4 + sub_batch


def _validate_queue(queue: dict[str, Any]) -> list[dict[str, Any]]:
    if queue.get("queue_id") != QUEUE_ID:
        raise AlphaContractError("HG006 P3 execution requires frozen queue")
    if queue.get("queue_sha256") != EXPECTED_QUEUE_SHA:
        raise AlphaContractError("HG006 P3 execution queue SHA mismatch")
    if queue.get("request_count") != EXPECTED_REQUEST_COUNT:
        raise AlphaContractError("HG006 P3 execution request count mismatch")
    if queue.get("model_config_sha256") != EXPECTED_MODEL_CONFIG_SHA:
        raise AlphaContractError("HG006 P3 execution model config mismatch")
    states = queue.get("execution_state_counts")
    if not isinstance(states, dict):
        raise AlphaContractError("HG006 P3 execution state counts unavailable")
    if (
        states.get("P2_VALIDATED_REUSE") != EXPECTED_REUSE_COUNT
        or states.get("FRESH_MODEL_REQUIRED") != EXPECTED_FRESH_COUNT
    ):
        raise AlphaContractError("HG006 P3 execution state counts mismatch")
    for field in (
        "expanded_population_terminal_labels_opened",
        "expanded_population_completion_probabilities_assigned",
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if queue.get(field) is not False:
            raise AlphaContractError(f"HG006 P3 execution requires queue {field}=false")
    rows = queue.get("requests")
    if not isinstance(rows, list) or len(rows) != EXPECTED_REQUEST_COUNT:
        raise AlphaContractError("HG006 P3 execution rows unavailable")
    return rows


def fresh_rows_for_batch(
    queue: dict[str, Any],
    *,
    batch_id: int,
) -> list[dict[str, Any]]:
    if (
        not isinstance(batch_id, int)
        or isinstance(batch_id, bool)
        or not 0 <= batch_id < BATCH_COUNT
    ):
        raise AlphaContractError("HG006 P3 transport batch must be 0..63")
    rows = _validate_queue(queue)
    selected = [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("p3_execution_state") == "FRESH_MODEL_REQUIRED"
        and transport_batch_for_request_id(str(row.get("request_id") or "")) == batch_id
    ]
    selected.sort(key=lambda row: str(row["request_id"]))
    expected = EXPECTED_BATCH_SIZES[batch_id]
    if len(selected) != expected:
        raise AlphaContractError(
            f"HG006 P3 batch {batch_id:02d} expected {expected} rows, got {len(selected)}"
        )
    return selected


def build_batch_template(
    queue: dict[str, Any],
    *,
    batch_id: int,
) -> dict[str, Any]:
    rows = fresh_rows_for_batch(queue, batch_id=batch_id)
    output = {
        "schema_version": 1,
        "execution_id": EXECUTION_ID,
        "template_id": f"HG006-L001-P3-T1-BATCH-{batch_id:02d}-TEMPLATE-v1",
        "classification": "FROZEN_NATIVE_P3_TRANSPORT_BATCH_TEMPLATE_NOT_OUTPUT",
        "source_queue_sha256": EXPECTED_QUEUE_SHA,
        "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
        "batch_id": batch_id,
        "request_count": len(rows),
        "rows": [
            {
                "request_id": row["request_id"],
                "chronology_id": row["chronology_id"],
                "document_id": row["document_id"],
                "symbol": row["symbol"],
                "family": row["family"],
                "primary_shard_id": row["shard_id"],
                "prompt_sha256": row["prompt_sha256"],
                "prompt_envelope": row["prompt_envelope"],
            }
            for row in rows
        ],
        "expanded_population_terminal_labels_opened": False,
        "expanded_population_completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["template_sha256"] = digest(output)
    return output


def _inject_provenance(
    queue_row: dict[str, Any],
    raw_payload: dict[str, Any],
) -> tuple[dict[str, Any], bytes]:
    payload = copy.deepcopy(raw_payload)
    raw_bytes = _canonical_bytes(payload)
    raw_sha = _sha256(raw_bytes)
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        raise AlphaContractError("HG006 P3 payload provenance unavailable")
    provenance.update(
        {
            "provider_runtime": "CHATGPT_NATIVE_INTERACTIVE",
            "model_id": "GPT-5.6 Sol",
            "model_config_sha256": str(queue_row["model_config_sha256"]),
            "prompt_contract_id": "HG006-L001-v1",
            "prompt_sha256": str(queue_row["prompt_sha256"]),
            "input_document_id": str(queue_row["document_id"]),
            "input_segment_manifest_sha256": str(
                queue_row["prompt_envelope"]["request"]["segment_manifest_sha256"]
            ),
            "raw_model_response_sha256": raw_sha,
        }
    )
    return payload, raw_bytes


def _validate_one_output(
    queue_row: dict[str, Any],
    raw_payload: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    model_output, raw_bytes = _inject_provenance(queue_row, raw_payload)
    request = queue_row["prompt_envelope"]["request"]
    segment_ids = {
        str(segment["segment_id"])
        for segment in request["segments"]
        if isinstance(segment, dict)
    }
    sealed = validate_extraction(
        model_output,
        document_id=str(queue_row["document_id"]),
        event_ids={str(value) for value in queue_row["event_ids"]},
        symbol=str(queue_row["symbol"]),
        family=str(queue_row["family"]),
        allowed_segment_ids=segment_ids,
        segment_manifest_sha256=str(request["segment_manifest_sha256"]),
    )
    return sealed, _sha256(raw_bytes)


def build_native_batch_bundle(
    queue: dict[str, Any],
    decisions: dict[str, Any],
    *,
    batch_id: int,
) -> dict[str, Any]:
    rows = fresh_rows_for_batch(queue, batch_id=batch_id)
    by_id = {str(row["request_id"]): row for row in rows}
    if not isinstance(decisions, dict):
        raise TypeError("HG006 P3 native decisions must be object")
    if set(decisions) != set(by_id):
        missing = sorted(set(by_id) - set(decisions))
        extra = sorted(set(decisions) - set(by_id))
        raise AlphaContractError(
            f"HG006 P3 batch {batch_id:02d} decision accounting mismatch "
            f"missing={missing} extra={extra}"
        )

    responses = []
    for request_id in sorted(by_id):
        decision = decisions[request_id]
        if not isinstance(decision, dict):
            raise TypeError("HG006 P3 decision must be object")
        if decision.get("status") == "MODEL_FAILURE":
            error = str(decision.get("error") or "").strip()
            if not error:
                raise AlphaContractError("HG006 P3 MODEL_FAILURE requires error")
            responses.append(
                {
                    "request_id": request_id,
                    "status": "MODEL_FAILURE",
                    "model_output": None,
                    "error": error,
                }
            )
            continue
        if decision.get("status") not in (None, "MODEL_OUTPUT"):
            raise AlphaContractError("HG006 P3 decision status invalid")
        compact = decision.get("decision", decision)
        model_output = materialize_native_output(by_id[request_id], compact)
        responses.append(
            {
                "request_id": request_id,
                "status": "MODEL_OUTPUT",
                "model_output": model_output,
                "error": None,
            }
        )

    output = {
        "schema_version": 1,
        "execution_id": EXECUTION_ID,
        "bundle_id": f"HG006-L001-P3-T1-BATCH-{batch_id:02d}-v1",
        "classification": "NATIVE_P3_TRANSPORT_BATCH_MODEL_OUTPUT_NOT_LABELS",
        "source_queue_sha256": EXPECTED_QUEUE_SHA,
        "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
        "batch_id": batch_id,
        "request_count": len(responses),
        "responses": responses,
        "expanded_population_terminal_labels_opened": False,
        "expanded_population_completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["bundle_sha256"] = digest(output)
    return output


def ingest_native_batch_bundle(
    queue: dict[str, Any],
    bundle: dict[str, Any],
    *,
    batch_id: int,
) -> dict[str, Any]:
    rows = fresh_rows_for_batch(queue, batch_id=batch_id)
    by_id = {str(row["request_id"]): row for row in rows}
    if bundle.get("execution_id") != EXECUTION_ID:
        raise AlphaContractError("HG006 P3 bundle execution ID mismatch")
    if bundle.get("batch_id") != batch_id:
        raise AlphaContractError("HG006 P3 bundle batch mismatch")
    if bundle.get("source_queue_sha256") != EXPECTED_QUEUE_SHA:
        raise AlphaContractError("HG006 P3 bundle queue SHA mismatch")
    if bundle.get("model_config_sha256") != EXPECTED_MODEL_CONFIG_SHA:
        raise AlphaContractError("HG006 P3 bundle model config mismatch")

    responses = bundle.get("responses")
    if not isinstance(responses, list):
        raise TypeError("HG006 P3 bundle responses must be list")
    response_by_id: dict[str, dict[str, Any]] = {}
    for response in responses:
        if not isinstance(response, dict):
            raise TypeError("HG006 P3 response row must be object")
        request_id = str(response.get("request_id") or "")
        if not request_id or request_id in response_by_id:
            raise AlphaContractError("HG006 P3 response IDs invalid")
        response_by_id[request_id] = response
    if set(response_by_id) != set(by_id):
        raise AlphaContractError("HG006 P3 response request set mismatch")

    ingested = []
    for request_id in sorted(by_id):
        response = response_by_id[request_id]
        queue_row = by_id[request_id]
        status = str(response.get("status") or "")
        if status == "MODEL_FAILURE":
            error = str(response.get("error") or "").strip()
            if not error or response.get("model_output") is not None:
                raise AlphaContractError("HG006 P3 invalid MODEL_FAILURE row")
            ingested.append(
                {
                    "request_id": request_id,
                    "batch_id": batch_id,
                    "chronology_id": queue_row["chronology_id"],
                    "document_id": queue_row["document_id"],
                    "symbol": queue_row["symbol"],
                    "family": queue_row["family"],
                    "status": "MODEL_FAILURE",
                    "raw_model_response_sha256": None,
                    "validated_response": None,
                    "error": error,
                }
            )
            continue
        if status != "MODEL_OUTPUT":
            raise AlphaContractError("HG006 P3 response status invalid")
        raw_payload = response.get("model_output")
        if not isinstance(raw_payload, dict):
            raise TypeError("HG006 P3 MODEL_OUTPUT requires object")
        try:
            sealed, raw_sha = _validate_one_output(queue_row, raw_payload)
            final_status = "VALIDATED"
            error = None
        except (AlphaContractError, TypeError, ValueError) as exc:
            raw_sha = _sha256(_canonical_bytes(raw_payload))
            sealed = None
            final_status = "VALIDATION_FAILURE"
            error = f"{type(exc).__name__}: {exc}"
        ingested.append(
            {
                "request_id": request_id,
                "batch_id": batch_id,
                "chronology_id": queue_row["chronology_id"],
                "document_id": queue_row["document_id"],
                "symbol": queue_row["symbol"],
                "family": queue_row["family"],
                "status": final_status,
                "raw_model_response_sha256": raw_sha,
                "validated_response": sealed,
                "error": error,
            }
        )

    counts = Counter(str(row["status"]) for row in ingested)
    output = {
        "schema_version": 1,
        "execution_id": EXECUTION_ID,
        "ingestion_id": f"HG006-L001-P3-T1-BATCH-{batch_id:02d}-INGESTION-v1",
        "classification": "VALIDATED_P3_TRANSPORT_BATCH_NOT_TERMINAL_LABELS",
        "source_queue_sha256": EXPECTED_QUEUE_SHA,
        "source_bundle_sha256": bundle.get("bundle_sha256"),
        "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
        "batch_id": batch_id,
        "request_count": len(ingested),
        "status_counts": dict(sorted(counts.items())),
        "rows": ingested,
        "expanded_population_terminal_labels_opened": False,
        "expanded_population_completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["ingestion_sha256"] = digest(output)
    return output


def combine_p3_ingestion(
    queue: dict[str, Any],
    prior_ingestion: dict[str, Any],
    batch_ingestions: list[dict[str, Any]],
) -> dict[str, Any]:
    queue_rows = _validate_queue(queue)
    if prior_ingestion.get("execution_id") != "HG006-L001-P2-v1":
        raise AlphaContractError("HG006 P3 prior ingestion ID mismatch")
    if prior_ingestion.get("ingestion_sha256") != EXPECTED_PRIOR_INGESTION_SHA:
        raise AlphaContractError("HG006 P3 prior ingestion SHA mismatch")
    prior_rows = prior_ingestion.get("rows")
    if not isinstance(prior_rows, list):
        raise TypeError("HG006 P3 prior ingestion rows unavailable")
    prior_by_id = {
        str(row["request_id"]): row
        for row in prior_rows
        if isinstance(row, dict) and row.get("status") == "VALIDATED"
    }

    if len(batch_ingestions) != BATCH_COUNT:
        raise AlphaContractError("HG006 P3 requires exactly 64 batch ingestions")
    by_batch: dict[int, dict[str, Any]] = {}
    fresh_rows: list[dict[str, Any]] = []
    for ingestion in batch_ingestions:
        if not isinstance(ingestion, dict):
            raise TypeError("HG006 P3 batch ingestion must be object")
        batch_id = ingestion.get("batch_id")
        if (
            not isinstance(batch_id, int)
            or isinstance(batch_id, bool)
            or not 0 <= batch_id < BATCH_COUNT
            or batch_id in by_batch
        ):
            raise AlphaContractError("HG006 P3 batch ingestion IDs invalid")
        if ingestion.get("execution_id") != EXECUTION_ID:
            raise AlphaContractError("HG006 P3 batch execution ID mismatch")
        if ingestion.get("source_queue_sha256") != EXPECTED_QUEUE_SHA:
            raise AlphaContractError("HG006 P3 batch queue SHA mismatch")
        rows = ingestion.get("rows")
        if not isinstance(rows, list):
            raise TypeError("HG006 P3 batch rows unavailable")
        by_batch[batch_id] = ingestion
        fresh_rows.extend(rows)
    if set(by_batch) != set(range(BATCH_COUNT)):
        raise AlphaContractError("HG006 P3 batch set incomplete")
    if len(fresh_rows) != EXPECTED_FRESH_COUNT:
        raise AlphaContractError("HG006 P3 fresh ingestion count mismatch")

    final_rows = []
    fresh_by_id = {str(row.get("request_id") or ""): row for row in fresh_rows}
    if len(fresh_by_id) != EXPECTED_FRESH_COUNT or "" in fresh_by_id:
        raise AlphaContractError("HG006 P3 fresh request IDs invalid")

    reuse_count = 0
    for queue_row in queue_rows:
        request_id = str(queue_row["request_id"])
        state = str(queue_row["p3_execution_state"])
        if state == "P2_VALIDATED_REUSE":
            source = prior_by_id.get(request_id)
            if source is None:
                raise AlphaContractError("HG006 P3 reused response unavailable")
            expected_response_sha = str(
                queue_row.get("p3_prior_validated_response_sha256") or ""
            )
            if digest(source["validated_response"]) != expected_response_sha:
                raise AlphaContractError("HG006 P3 reused response SHA mismatch")
            final_rows.append(
                {
                    "request_id": request_id,
                    "chronology_id": queue_row["chronology_id"],
                    "document_id": queue_row["document_id"],
                    "symbol": queue_row["symbol"],
                    "family": queue_row["family"],
                    "status": "VALIDATED",
                    "source": "P2_VALIDATED_REUSE",
                    "validated_response": source["validated_response"],
                    "error": None,
                }
            )
            reuse_count += 1
        elif state == "FRESH_MODEL_REQUIRED":
            fresh = fresh_by_id.get(request_id)
            if fresh is None:
                raise AlphaContractError("HG006 P3 fresh response unavailable")
            final_rows.append(
                {
                    **fresh,
                    "source": "P3_FRESH_NATIVE_OUTPUT",
                }
            )
        else:
            raise AlphaContractError("HG006 P3 unknown queue execution state")

    if reuse_count != EXPECTED_REUSE_COUNT:
        raise AlphaContractError("HG006 P3 reuse accounting mismatch")
    if len(final_rows) != EXPECTED_REQUEST_COUNT:
        raise AlphaContractError("HG006 P3 final request accounting mismatch")

    fresh_validated = sum(
        row.get("status") == "VALIDATED" for row in fresh_rows
    )
    fresh_validation_ratio = fresh_validated / EXPECTED_FRESH_COUNT
    validated_chronologies = {
        str(row["chronology_id"])
        for row in final_rows
        if row.get("status") == "VALIDATED"
    }
    chronology_ratio = len(validated_chronologies) / EXPECTED_EVIDENCE_READY
    status_counts = Counter(str(row.get("status") or "") for row in final_rows)

    gates = {
        "complete_4822_request_accounting": len(final_rows) == EXPECTED_REQUEST_COUNT,
        "exact_1443_reuse_accounting": reuse_count == EXPECTED_REUSE_COUNT,
        "complete_64_batch_accounting": len(by_batch) == BATCH_COUNT,
        "minimum_95pct_fresh_validation": fresh_validation_ratio >= 0.95,
        "minimum_95pct_chronology_validation_coverage": chronology_ratio >= 0.95,
    }

    output = {
        "schema_version": 1,
        "execution_id": EXECUTION_ID,
        "classification": "FULL_PRIORITY_HISTORICAL_LLM_INGESTION_NOT_TERMINAL_LABELS",
        "source_queue_sha256": EXPECTED_QUEUE_SHA,
        "source_prior_ingestion_sha256": EXPECTED_PRIOR_INGESTION_SHA,
        "request_count": EXPECTED_REQUEST_COUNT,
        "reuse_count": reuse_count,
        "fresh_request_count": EXPECTED_FRESH_COUNT,
        "fresh_validated_count": fresh_validated,
        "fresh_validation_ratio": fresh_validation_ratio,
        "validated_chronology_count": len(validated_chronologies),
        "validated_chronology_ratio": chronology_ratio,
        "status_counts": dict(sorted(status_counts.items())),
        "batch_ingestion_sha256": {
            str(batch_id): by_batch[batch_id]["ingestion_sha256"]
            for batch_id in sorted(by_batch)
        },
        "threshold_passes": gates,
        "full_ingestion_pass": all(gates.values()),
        "promotion_allowed_to_expanded_threading": all(gates.values()),
        "rows": sorted(final_rows, key=lambda row: str(row["request_id"])),
        "expanded_population_terminal_labels_opened": False,
        "expanded_population_completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["ingestion_sha256"] = digest(output)
    return output
