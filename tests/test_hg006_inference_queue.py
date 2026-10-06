from __future__ import annotations

import copy
import hashlib
import json

from marketlab.alpha import digest
from marketlab.hg006_inference_queue import (
    MODEL_CONFIG,
    build_inference_queue,
    request_id_for,
    shard_for_request_id,
    validate_and_seal_response,
)
from marketlab.hg006_stage_contract import extraction_template


def _segment(seed: str) -> dict:
    text = f"Board approved transaction {seed}."
    return {
        "segment_id": f"seg-{seed}",
        "kind": "PDF_PAGE",
        "locator": {"page_number": 1},
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "phrase_hits": {},
        "source_order": 0,
    }


def _pack() -> dict:
    chronologies = []
    remaining_extra = 1150
    for index in range(300):
        chronology_id = f"C{index:03d}"
        family = (
            "PREFERENTIAL_WARRANT"
            if index < 150
            else "SCHEME_REORGANISATION"
        )
        if index >= 298:
            docs = []
            state = "TEXT_UNAVAILABLE"
        else:
            count = 1
            if index == 0:
                count += remaining_extra
            docs = []
            for doc_index in range(count):
                document_id = hashlib.sha256(
                    f"{chronology_id}-{doc_index}".encode()
                ).hexdigest()
                docs.append(
                    {
                        "document_id": document_id,
                        "chronology_timestamp_utc": "2024-01-01T10:00:00Z",
                        "event_ids": [f"E{index:03d}-{doc_index}"],
                        "segment_manifest_sha256": "a" * 64,
                        "source_segment_count": 1,
                        "hit_summary": {},
                        "selected_segments": [
                            _segment(f"{index}-{doc_index}")
                        ],
                    }
                )
            state = "EVIDENCE_READY"
        chronologies.append(
            {
                "chronology_id": chronology_id,
                "symbol": f"S{index:03d}",
                "family": family,
                "evidence_state": state,
                "retained_documents": docs,
            }
        )
    return {
        "pack_id": "HG006-S002-v1",
        "pack_sha256": (
            "e99f270bf48b76bb72f3e2734abddd34bcc580cb1583086cc73e50759e23766e"
        ),
        "chronology_count": 300,
        "state_counts": {
            "EVIDENCE_READY": 298,
            "TEXT_UNAVAILABLE": 2,
        },
        "retained_document_count": 1448,
        "chronologies": chronologies,
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_queue_has_exact_frozen_request_count_and_shards() -> None:
    queue = build_inference_queue(_pack())
    assert queue["request_count"] == 1448
    assert sum(queue["request_counts_by_shard"].values()) == 1448
    assert len(queue["request_counts_by_shard"]) == 16
    assert queue["evidence_ready_chronology_count"] == 298
    assert len(queue["text_unavailable_chronology_ids"]) == 2
    assert queue["completion_probabilities_assigned"] is False


def test_request_identity_and_sharding_are_deterministic() -> None:
    request_id = request_id_for("C001", "f" * 64)
    assert request_id == request_id_for("C001", "f" * 64)
    assert 0 <= shard_for_request_id(request_id) < 16


def test_response_sealing_validates_provenance_and_evidence() -> None:
    queue = build_inference_queue(_pack())
    row = queue["requests"][0]
    request = row["prompt_envelope"]["request"]

    output = extraction_template(
        document_id=row["document_id"],
        event_ids=row["event_ids"],
        symbol=row["symbol"],
        family=row["family"],
    )
    segment_id = request["segments"][0]["segment_id"]
    output["stage_observations"] = [
        {
            "stage": "BOARD_APPROVED",
            "evidence_segment_ids": [segment_id],
        }
    ]
    raw_model_payload = copy.deepcopy(output)
    raw_bytes = json.dumps(
        raw_model_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    output["provenance"] = {
        "provider_runtime": MODEL_CONFIG["provider_runtime"],
        "model_id": MODEL_CONFIG["model_id"],
        "model_config_sha256": row["model_config_sha256"],
        "prompt_contract_id": "HG006-L001-v1",
        "prompt_sha256": row["prompt_sha256"],
        "input_document_id": row["document_id"],
        "input_segment_manifest_sha256": request[
            "segment_manifest_sha256"
        ],
        "raw_model_response_sha256": hashlib.sha256(raw_bytes).hexdigest(),
    }

    sealed = validate_and_seal_response(
        queue_row=row,
        model_output=output,
        raw_model_response_bytes=raw_bytes,
    )
    assert sealed["status"] == "VALIDATED"
    assert sealed["validated_extraction"]["completion_probability_assigned"] is False
    assert sealed["live_capital_allowed"] is False


def test_model_config_hash_is_frozen() -> None:
    queue = build_inference_queue(_pack())
    assert queue["model_config_sha256"] == digest(MODEL_CONFIG)
    assert all(
        row["model_config_sha256"] == queue["model_config_sha256"]
        for row in queue["requests"]
    )
