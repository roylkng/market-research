from __future__ import annotations

import hashlib

from marketlab import hg006_p3_execution as ex
from marketlab.alpha import digest
from marketlab.hg006_stage_contract import extraction_template


def _segment() -> dict:
    text = "Board approved preferential allotment."
    return {
        "segment_id": "seg-1",
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def _fresh_row(request_id: str) -> dict:
    template = extraction_template(
        document_id="a" * 64,
        event_ids=["E1"],
        symbol="TEST",
        family="PREFERENTIAL_WARRANT",
    )
    request = {
        "queue_id": "HG006-L001-P3-v1",
        "request_id": request_id,
        "chronology_id": "C1",
        "document_id": "a" * 64,
        "event_ids": ["E1"],
        "symbol": "TEST",
        "family": "PREFERENTIAL_WARRANT",
        "chronology_timestamp_utc": "2026-01-01T00:00:00Z",
        "segment_manifest_sha256": "b" * 64,
        "segments": [_segment()],
        "required_output_template": template,
    }
    return {
        "request_id": request_id,
        "chronology_id": "C1",
        "document_id": "a" * 64,
        "event_ids": ["E1"],
        "symbol": "TEST",
        "family": "PREFERENTIAL_WARRANT",
        "shard_id": int(request_id[:8], 16) % 16,
        "prompt_sha256": "c" * 64,
        "model_config_sha256": ex.EXPECTED_MODEL_CONFIG_SHA,
        "prompt_envelope": {"system": "frozen", "request": request},
        "p3_execution_state": "FRESH_MODEL_REQUIRED",
    }


def _queue(row: dict) -> dict:
    return {
        "queue_id": "HG006-L001-P3-v1",
        "queue_sha256": ex.EXPECTED_QUEUE_SHA,
        "request_count": 1,
        "model_config_sha256": ex.EXPECTED_MODEL_CONFIG_SHA,
        "execution_state_counts": {
            "P2_VALIDATED_REUSE": 0,
            "FRESH_MODEL_REQUIRED": 1,
        },
        "requests": [row],
        "expanded_population_terminal_labels_opened": False,
        "expanded_population_completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_transport_batch_is_request_identity_only() -> None:
    request_id = "00000000" + "00000003" + "0" * 48
    assert ex.transport_batch_for_request_id(request_id) == 3


def test_batch_materialization_and_ingestion_validate_evidence(monkeypatch) -> None:
    request_id = "00000000" + "00000000" + "1" * 48
    row = _fresh_row(request_id)
    queue = _queue(row)
    monkeypatch.setattr(ex, "EXPECTED_REQUEST_COUNT", 1)
    monkeypatch.setattr(ex, "EXPECTED_REUSE_COUNT", 0)
    monkeypatch.setattr(ex, "EXPECTED_FRESH_COUNT", 1)
    monkeypatch.setattr(ex, "EXPECTED_BATCH_SIZES", {0: 1})

    decisions = {
        request_id: {
            "s": [["BOARD_APPROVED", ["seg-1"]]],
            "a": [["OTHER_EXPLICIT_TRANSACTION_REFERENCE", "preferential allotment", ["seg-1"]]],
        }
    }
    bundle = ex.build_native_batch_bundle(queue, decisions, batch_id=0)
    ingestion = ex.ingest_native_batch_bundle(queue, bundle, batch_id=0)

    assert bundle["request_count"] == 1
    assert ingestion["status_counts"] == {"VALIDATED": 1}
    sealed = ingestion["rows"][0]["validated_response"]
    assert sealed["stage_observations"][0]["stage"] == "BOARD_APPROVED"
    assert sealed["completion_probability_assigned"] is False


def test_invalid_evidence_becomes_validation_failure(monkeypatch) -> None:
    request_id = "00000000" + "00000000" + "2" * 48
    row = _fresh_row(request_id)
    queue = _queue(row)
    monkeypatch.setattr(ex, "EXPECTED_REQUEST_COUNT", 1)
    monkeypatch.setattr(ex, "EXPECTED_REUSE_COUNT", 0)
    monkeypatch.setattr(ex, "EXPECTED_FRESH_COUNT", 1)
    monkeypatch.setattr(ex, "EXPECTED_BATCH_SIZES", {0: 1})

    decisions = {
        request_id: {
            "s": [["BOARD_APPROVED", ["invented-segment"]]],
        }
    }
    bundle = ex.build_native_batch_bundle(queue, decisions, batch_id=0)
    ingestion = ex.ingest_native_batch_bundle(queue, bundle, batch_id=0)
    assert ingestion["status_counts"] == {"VALIDATION_FAILURE": 1}


def test_final_combine_preserves_exact_reuse(monkeypatch) -> None:
    fresh_id = "00000000" + "00000000" + "3" * 48
    fresh = _fresh_row(fresh_id)
    reuse_id = "f" * 64
    prior_validated = {"sealed": "prior"}
    reuse = {
        "request_id": reuse_id,
        "chronology_id": "C2",
        "document_id": "d" * 64,
        "symbol": "OLD",
        "family": "SCHEME_REORGANISATION",
        "p3_execution_state": "P2_VALIDATED_REUSE",
        "p3_prior_validated_response_sha256": digest(prior_validated),
    }
    queue = {
        "queue_id": "HG006-L001-P3-v1",
        "queue_sha256": ex.EXPECTED_QUEUE_SHA,
        "request_count": 2,
        "model_config_sha256": ex.EXPECTED_MODEL_CONFIG_SHA,
        "execution_state_counts": {
            "P2_VALIDATED_REUSE": 1,
            "FRESH_MODEL_REQUIRED": 1,
        },
        "requests": [fresh, reuse],
        "expanded_population_terminal_labels_opened": False,
        "expanded_population_completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    monkeypatch.setattr(ex, "EXPECTED_REQUEST_COUNT", 2)
    monkeypatch.setattr(ex, "EXPECTED_REUSE_COUNT", 1)
    monkeypatch.setattr(ex, "EXPECTED_FRESH_COUNT", 1)
    monkeypatch.setattr(ex, "EXPECTED_EVIDENCE_READY", 2)
    monkeypatch.setattr(ex, "BATCH_COUNT", 1)

    prior = {
        "execution_id": "HG006-L001-P2-v1",
        "ingestion_sha256": ex.EXPECTED_PRIOR_INGESTION_SHA,
        "rows": [
            {
                "request_id": reuse_id,
                "status": "VALIDATED",
                "validated_response": prior_validated,
            }
        ],
    }
    batch = {
        "execution_id": ex.EXECUTION_ID,
        "source_queue_sha256": ex.EXPECTED_QUEUE_SHA,
        "batch_id": 0,
        "ingestion_sha256": "e" * 64,
        "rows": [
            {
                "request_id": fresh_id,
                "chronology_id": "C1",
                "document_id": fresh["document_id"],
                "symbol": "TEST",
                "family": "PREFERENTIAL_WARRANT",
                "status": "VALIDATED",
                "validated_response": {"sealed": "fresh"},
                "error": None,
            }
        ],
    }
    result = ex.combine_p3_ingestion(queue, prior, [batch])
    assert result["reuse_count"] == 1
    assert result["fresh_validated_count"] == 1
    assert result["full_ingestion_pass"] is True
