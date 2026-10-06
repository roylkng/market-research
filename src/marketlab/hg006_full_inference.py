from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg006_inference_queue import validate_and_seal_response

EXECUTION_ID = "HG006-L001-P2-v1"
EXPECTED_QUEUE_ID = "HG006-L001-P1-v1"
EXPECTED_QUEUE_SHA = "6732f5741ec6d9a2e1926a94d234c642871d454f0354d60dfa87cec3807ce934"
EXPECTED_MODEL_CONFIG_SHA = "043ec1f2d38aec7e72b24cfcbe864aebd83cda8b717d3c8c0fac2ecb3cafa51d"
EXPECTED_REQUEST_COUNT = 1448
EXPECTED_CHRONOLOGY_COUNT = 300
EXPECTED_EVIDENCE_READY_CHRONOLOGY_COUNT = 298
SHARD_COUNT = 16
EXPECTED_P0_RUN_ID = "HG006-L001-P0-GPT56SOL-NATIVE-v1"
EXPECTED_P0_RUN_SHA = "0b606aa4b3c27545d150dd046d3c0f2c5fb68d3380f310095be82754bfca1a79"
EXPECTED_P0_COUNT = 20


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
        raise AlphaContractError("HG006 P2 payload must be finite JSON") from exc


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _validate_queue(queue: dict[str, Any]) -> list[dict[str, Any]]:
    if queue.get("queue_id") != EXPECTED_QUEUE_ID:
        raise AlphaContractError("HG006 P2 requires frozen L001-P1 queue")
    if queue.get("queue_sha256") != EXPECTED_QUEUE_SHA:
        raise AlphaContractError("HG006 P2 queue SHA mismatch")
    if queue.get("model_config_sha256") != EXPECTED_MODEL_CONFIG_SHA:
        raise AlphaContractError("HG006 P2 model config SHA mismatch")
    if queue.get("request_count") != EXPECTED_REQUEST_COUNT:
        raise AlphaContractError("HG006 P2 request count mismatch")
    if queue.get("chronology_count") != EXPECTED_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 P2 chronology count mismatch")
    for field in (
        "historical_terminal_labels_opened",
        "completion_probabilities_assigned",
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if queue.get(field) is not False:
            raise AlphaContractError(f"HG006 P2 requires queue {field}=false")
    rows = queue.get("requests")
    if not isinstance(rows, list) or len(rows) != EXPECTED_REQUEST_COUNT:
        raise AlphaContractError("HG006 P2 queue rows unavailable")
    ids = [str(row.get("request_id") or "") for row in rows if isinstance(row, dict)]
    if len(ids) != EXPECTED_REQUEST_COUNT or len(ids) != len(set(ids)) or "" in ids:
        raise AlphaContractError("HG006 P2 queue request IDs are invalid")
    return rows


def _validate_p0(p0_run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if p0_run.get("run_id") != EXPECTED_P0_RUN_ID:
        raise AlphaContractError("HG006 P2 P0 run identity mismatch")
    if p0_run.get("run_sha256") != EXPECTED_P0_RUN_SHA:
        raise AlphaContractError("HG006 P2 P0 run SHA mismatch")
    if p0_run.get("selected_request_count") != EXPECTED_P0_COUNT:
        raise AlphaContractError("HG006 P2 P0 request count mismatch")
    if p0_run.get("validated_response_count") != EXPECTED_P0_COUNT:
        raise AlphaContractError("HG006 P2 P0 validation count mismatch")
    if p0_run.get("model_config_sha256") != EXPECTED_MODEL_CONFIG_SHA:
        raise AlphaContractError("HG006 P2 P0 model config SHA mismatch")
    for field in (
        "historical_terminal_labels_opened",
        "completion_probabilities_assigned",
        "return_outcomes_opened",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if p0_run.get(field) is not False:
            raise AlphaContractError(f"HG006 P2 requires P0 {field}=false")
    rows = p0_run.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_P0_COUNT:
        raise AlphaContractError("HG006 P2 P0 rows unavailable")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 P2 P0 row must be object")
        request_id = str(row.get("request_id") or "")
        sealed = row.get("sealed_response")
        if not request_id or request_id in result or not isinstance(sealed, dict):
            raise AlphaContractError("HG006 P2 P0 response identity invalid")
        if sealed.get("status") != "VALIDATED" or sealed.get("request_id") != request_id:
            raise AlphaContractError("HG006 P2 P0 sealed response invalid")
        if sealed.get("model_config_sha256") != EXPECTED_MODEL_CONFIG_SHA:
            raise AlphaContractError("HG006 P2 P0 sealed model config mismatch")
        result[request_id] = row
    return result


def _queue_index(queue_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["request_id"]): row for row in queue_rows}


def _validate_p0_against_queue(
    queue_by_id: dict[str, dict[str, Any]],
    p0_by_id: dict[str, dict[str, Any]],
) -> None:
    for request_id, p0_row in p0_by_id.items():
        queue_row = queue_by_id.get(request_id)
        if queue_row is None:
            raise AlphaContractError("HG006 P2 P0 request absent from full queue")
        sealed = p0_row["sealed_response"]
        checks = {
            "document_id": queue_row.get("document_id"),
            "prompt_sha256": queue_row.get("prompt_sha256"),
            "model_config_sha256": queue_row.get("model_config_sha256"),
        }
        for field, expected in checks.items():
            if sealed.get(field) != expected:
                raise AlphaContractError(
                    f"HG006 P2 P0/queue {field} mismatch for {request_id}"
                )
        if p0_row.get("raw_model_response_sha256") != sealed.get(
            "raw_model_response_sha256"
        ):
            raise AlphaContractError("HG006 P2 P0 raw response SHA mismatch")


def build_shard_template(
    queue: dict[str, Any],
    p0_run: dict[str, Any],
    *,
    shard_id: int,
) -> dict[str, Any]:
    if shard_id < 0 or shard_id >= SHARD_COUNT:
        raise AlphaContractError("HG006 P2 shard_id out of range")
    queue_rows = _validate_queue(queue)
    p0_by_id = _validate_p0(p0_run)
    queue_by_id = _queue_index(queue_rows)
    _validate_p0_against_queue(queue_by_id, p0_by_id)

    shard_rows = [
        row for row in queue_rows if int(row.get("shard_id", -1)) == shard_id
    ]
    if not shard_rows:
        raise AlphaContractError("HG006 P2 frozen shard is empty")
    output_rows = []
    for row in sorted(shard_rows, key=lambda item: str(item["request_id"])):
        request_id = str(row["request_id"])
        if request_id in p0_by_id:
            p0_row = p0_by_id[request_id]
            sealed = p0_row["sealed_response"]
            output_rows.append(
                {
                    "request_id": request_id,
                    "execution_state": "P0_VALIDATED_REUSE",
                    "chronology_id": row["chronology_id"],
                    "document_id": row["document_id"],
                    "symbol": row["symbol"],
                    "family": row["family"],
                    "prompt_sha256": row["prompt_sha256"],
                    "model_config_sha256": row["model_config_sha256"],
                    "raw_model_response_sha256": sealed[
                        "raw_model_response_sha256"
                    ],
                    "validated_structured_output_sha256": sealed[
                        "validated_extraction"
                    ]["validated_structured_output_sha256"],
                    "prompt_envelope": None,
                }
            )
        else:
            output_rows.append(
                {
                    "request_id": request_id,
                    "execution_state": "PENDING_NATIVE_OUTPUT",
                    "chronology_id": row["chronology_id"],
                    "document_id": row["document_id"],
                    "symbol": row["symbol"],
                    "family": row["family"],
                    "prompt_sha256": row["prompt_sha256"],
                    "model_config_sha256": row["model_config_sha256"],
                    "raw_model_response_sha256": None,
                    "validated_structured_output_sha256": None,
                    "prompt_envelope": row["prompt_envelope"],
                }
            )

    output = {
        "schema_version": 1,
        "execution_id": EXECUTION_ID,
        "template_id": f"HG006-L001-P2-SHARD-{shard_id:02d}-TEMPLATE-v1",
        "classification": "FROZEN_NATIVE_HISTORICAL_SHARD_PROMPT_TEMPLATE_NOT_OUTPUT",
        "source_queue_sha256": EXPECTED_QUEUE_SHA,
        "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
        "p0_run_sha256": EXPECTED_P0_RUN_SHA,
        "shard_id": shard_id,
        "request_count": len(output_rows),
        "p0_reuse_count": sum(
            row["execution_state"] == "P0_VALIDATED_REUSE" for row in output_rows
        ),
        "pending_native_count": sum(
            row["execution_state"] == "PENDING_NATIVE_OUTPUT" for row in output_rows
        ),
        "rows": output_rows,
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
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
        raise AlphaContractError("HG006 P2 native payload provenance unavailable")
    provenance.update(
        {
            "provider_runtime": "CHATGPT_NATIVE_INTERACTIVE",
            "model_id": "GPT-5.6 Sol",
            "model_config_sha256": str(queue_row["model_config_sha256"]),
            "prompt_contract_id": "HG006-L001-v1",
            "prompt_sha256": str(queue_row["prompt_sha256"]),
            "input_document_id": str(queue_row["document_id"]),
            "input_segment_manifest_sha256": str(
                queue_row["prompt_envelope"]["request"][
                    "segment_manifest_sha256"
                ]
            ),
            "raw_model_response_sha256": raw_sha,
        }
    )
    return payload, raw_bytes


def ingest_shard_responses(
    queue: dict[str, Any],
    p0_run: dict[str, Any],
    *,
    shard_id: int,
    native_bundle: dict[str, Any],
) -> dict[str, Any]:
    queue_rows = _validate_queue(queue)
    p0_by_id = _validate_p0(p0_run)
    queue_by_id = _queue_index(queue_rows)
    _validate_p0_against_queue(queue_by_id, p0_by_id)
    template = build_shard_template(queue, p0_run, shard_id=shard_id)

    if native_bundle.get("execution_id") != EXECUTION_ID:
        raise AlphaContractError("HG006 P2 native bundle execution ID mismatch")
    if native_bundle.get("shard_id") != shard_id:
        raise AlphaContractError("HG006 P2 native bundle shard mismatch")
    if native_bundle.get("source_queue_sha256") != EXPECTED_QUEUE_SHA:
        raise AlphaContractError("HG006 P2 native bundle queue SHA mismatch")
    if native_bundle.get("model_config_sha256") != EXPECTED_MODEL_CONFIG_SHA:
        raise AlphaContractError("HG006 P2 native bundle model config mismatch")

    native_rows = native_bundle.get("responses")
    if not isinstance(native_rows, list):
        raise TypeError("HG006 P2 native responses must be a list")
    native_by_id: dict[str, dict[str, Any]] = {}
    for row in native_rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 P2 native response row must be object")
        request_id = str(row.get("request_id") or "")
        if not request_id or request_id in native_by_id:
            raise AlphaContractError("HG006 P2 native request IDs invalid")
        native_by_id[request_id] = row

    pending_ids = {
        str(row["request_id"])
        for row in template["rows"]
        if row["execution_state"] == "PENDING_NATIVE_OUTPUT"
    }
    if set(native_by_id) != pending_ids:
        raise AlphaContractError("HG006 P2 native response accounting mismatch")

    ingested = []
    for template_row in template["rows"]:
        request_id = str(template_row["request_id"])
        queue_row = queue_by_id[request_id]
        if request_id in p0_by_id:
            sealed = p0_by_id[request_id]["sealed_response"]
            ingested.append(
                {
                    "request_id": request_id,
                    "shard_id": shard_id,
                    "chronology_id": queue_row["chronology_id"],
                    "document_id": queue_row["document_id"],
                    "symbol": queue_row["symbol"],
                    "family": queue_row["family"],
                    "status": "VALIDATED",
                    "source": "P0_VALIDATED_REUSE",
                    "raw_model_response_sha256": sealed[
                        "raw_model_response_sha256"
                    ],
                    "validated_response": sealed,
                    "error": None,
                }
            )
            continue

        native = native_by_id[request_id]
        state = str(native.get("status") or "")
        if state == "MODEL_FAILURE":
            error = str(native.get("error") or "").strip()
            if not error or native.get("model_output") is not None:
                raise AlphaContractError(
                    "HG006 P2 MODEL_FAILURE requires error and no model output"
                )
            ingested.append(
                {
                    "request_id": request_id,
                    "shard_id": shard_id,
                    "chronology_id": queue_row["chronology_id"],
                    "document_id": queue_row["document_id"],
                    "symbol": queue_row["symbol"],
                    "family": queue_row["family"],
                    "status": "MODEL_FAILURE",
                    "source": "FRESH_NATIVE_OUTPUT",
                    "raw_model_response_sha256": None,
                    "validated_response": None,
                    "error": error,
                }
            )
            continue
        if state != "MODEL_OUTPUT":
            raise AlphaContractError("HG006 P2 native status is invalid")
        raw_payload = native.get("model_output")
        if not isinstance(raw_payload, dict):
            raise TypeError("HG006 P2 MODEL_OUTPUT requires object payload")
        model_output, raw_bytes = _inject_provenance(queue_row, raw_payload)
        raw_sha = _sha256(raw_bytes)
        try:
            sealed = validate_and_seal_response(
                queue_row=queue_row,
                model_output=model_output,
                raw_model_response_bytes=raw_bytes,
            )
        except (AlphaContractError, TypeError, ValueError) as exc:
            ingested.append(
                {
                    "request_id": request_id,
                    "shard_id": shard_id,
                    "chronology_id": queue_row["chronology_id"],
                    "document_id": queue_row["document_id"],
                    "symbol": queue_row["symbol"],
                    "family": queue_row["family"],
                    "status": "VALIDATION_FAILURE",
                    "source": "FRESH_NATIVE_OUTPUT",
                    "raw_model_response_sha256": raw_sha,
                    "validated_response": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        ingested.append(
            {
                "request_id": request_id,
                "shard_id": shard_id,
                "chronology_id": queue_row["chronology_id"],
                "document_id": queue_row["document_id"],
                "symbol": queue_row["symbol"],
                "family": queue_row["family"],
                "status": "VALIDATED",
                "source": "FRESH_NATIVE_OUTPUT",
                "raw_model_response_sha256": raw_sha,
                "validated_response": sealed,
                "error": None,
            }
        )

    counts = Counter(row["status"] for row in ingested)
    output = {
        "schema_version": 1,
        "execution_id": EXECUTION_ID,
        "bundle_id": f"HG006-L001-P2-SHARD-{shard_id:02d}-v1",
        "classification": "NATIVE_HISTORICAL_SHARD_RESPONSE_INGESTION_NOT_LABELS",
        "source_queue_sha256": EXPECTED_QUEUE_SHA,
        "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
        "p0_run_sha256": EXPECTED_P0_RUN_SHA,
        "shard_id": shard_id,
        "request_count": len(ingested),
        "status_counts": dict(sorted(counts.items())),
        "rows": ingested,
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["bundle_sha256"] = digest(output)
    return output


def combine_shard_bundles(
    queue: dict[str, Any],
    p0_run: dict[str, Any],
    shard_bundles: list[dict[str, Any]],
) -> dict[str, Any]:
    queue_rows = _validate_queue(queue)
    _validate_p0(p0_run)
    if len(shard_bundles) != SHARD_COUNT:
        raise AlphaContractError("HG006 P2 requires exactly 16 shard bundles")
    by_shard: dict[int, dict[str, Any]] = {}
    all_rows: list[dict[str, Any]] = []
    for bundle in shard_bundles:
        if not isinstance(bundle, dict):
            raise TypeError("HG006 P2 shard bundle must be object")
        shard_id = bundle.get("shard_id")
        if (
            not isinstance(shard_id, int)
            or isinstance(shard_id, bool)
            or shard_id < 0
            or shard_id >= SHARD_COUNT
            or shard_id in by_shard
        ):
            raise AlphaContractError("HG006 P2 shard IDs invalid")
        if bundle.get("execution_id") != EXECUTION_ID:
            raise AlphaContractError("HG006 P2 bundle execution ID mismatch")
        if bundle.get("source_queue_sha256") != EXPECTED_QUEUE_SHA:
            raise AlphaContractError("HG006 P2 bundle queue SHA mismatch")
        if bundle.get("model_config_sha256") != EXPECTED_MODEL_CONFIG_SHA:
            raise AlphaContractError("HG006 P2 bundle model config mismatch")
        rows = bundle.get("rows")
        if not isinstance(rows, list):
            raise TypeError("HG006 P2 bundle rows unavailable")
        by_shard[shard_id] = bundle
        all_rows.extend(rows)

    if set(by_shard) != set(range(SHARD_COUNT)):
        raise AlphaContractError("HG006 P2 shard set incomplete")
    if len(all_rows) != EXPECTED_REQUEST_COUNT:
        raise AlphaContractError("HG006 P2 full response count mismatch")
    ids = [str(row.get("request_id") or "") for row in all_rows]
    if len(ids) != len(set(ids)) or "" in ids:
        raise AlphaContractError("HG006 P2 full response request IDs invalid")
    queue_ids = {str(row["request_id"]) for row in queue_rows}
    if set(ids) != queue_ids:
        raise AlphaContractError("HG006 P2 full response request set mismatch")

    status_counts = Counter(str(row.get("status") or "") for row in all_rows)
    validated_count = status_counts["VALIDATED"]
    validation_ratio = validated_count / EXPECTED_REQUEST_COUNT

    evidence_ready_chronologies = {
        str(row["chronology_id"]) for row in queue_rows
    }
    if len(evidence_ready_chronologies) != EXPECTED_EVIDENCE_READY_CHRONOLOGY_COUNT:
        raise AlphaContractError("HG006 P2 evidence-ready chronology count mismatch")
    validated_chronologies = {
        str(row["chronology_id"])
        for row in all_rows
        if row.get("status") == "VALIDATED"
    }
    chronology_ratio = len(validated_chronologies) / len(evidence_ready_chronologies)

    threshold_passes = {
        "complete_1448_request_accounting": len(all_rows) == EXPECTED_REQUEST_COUNT,
        "complete_16_shard_accounting": len(by_shard) == SHARD_COUNT,
        "minimum_95pct_request_validation": validation_ratio >= 0.95,
        "minimum_95pct_chronology_validation_coverage": chronology_ratio >= 0.95,
        "p0_audit_sample_preserved": all(
            row.get("source") == "P0_VALIDATED_REUSE"
            for row in all_rows
            if str(row.get("request_id") or "")
            in {
                str(p0_row["request_id"])
                for p0_row in p0_run["rows"]
            }
        ),
    }
    output = {
        "schema_version": 1,
        "execution_id": EXECUTION_ID,
        "classification": "FULL_NATIVE_HISTORICAL_LLM_RESPONSE_INGESTION_NOT_LABELS",
        "source_queue_sha256": EXPECTED_QUEUE_SHA,
        "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
        "p0_run_sha256": EXPECTED_P0_RUN_SHA,
        "request_count": EXPECTED_REQUEST_COUNT,
        "status_counts": dict(sorted(status_counts.items())),
        "validated_request_count": validated_count,
        "validated_request_ratio": validation_ratio,
        "evidence_ready_chronology_count": len(evidence_ready_chronologies),
        "validated_chronology_count": len(validated_chronologies),
        "validated_chronology_ratio": chronology_ratio,
        "shard_bundle_sha256": {
            str(shard_id): by_shard[shard_id]["bundle_sha256"]
            for shard_id in sorted(by_shard)
        },
        "threshold_passes": threshold_passes,
        "full_ingestion_pass": all(threshold_passes.values()),
        "promotion_allowed_to_d003_threading": all(threshold_passes.values()),
        "rows": sorted(all_rows, key=lambda row: str(row["request_id"])),
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["ingestion_sha256"] = digest(output)
    return output
