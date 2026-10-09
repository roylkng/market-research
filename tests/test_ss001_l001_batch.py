from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss001_l001_batch import (
    SHARD_COUNT,
    SOURCE_MODEL_CONFIG_SHA,
    SOURCE_QUEUE_ID,
    TRANSPORT_ID,
    build_preflight,
    validate_and_seal_response,
    validate_config,
    validate_request,
)
from marketlab.ss002_llm_contract import build_prompt_envelope, extraction_template
from scripts.run_ss001_l001_batch import collect_verified, execute_shard


def _config() -> dict:
    return {
        "schema_version": 1,
        "provider_runtime": "OPENAI_COMPATIBLE_CHAT",
        "model_id": "test-local-model",
        "api_endpoint": "http://127.0.0.1:8080/v1/chat/completions",
        "temperature": 0.0,
        "top_p": 1.0,
        "max_completion_tokens": 4096,
        "timeout_seconds": 15,
        "auth_env": "MARKETLAB_LLM_API_KEY",
        "token_parameter": "max_tokens",
        "json_object_mode": True,
    }


def _row(index: int) -> dict:
    document_id = hashlib.sha256(f"doc-{index}".encode()).hexdigest()
    segment_id = f"{document_id}:pdf:page:0001"
    text = "Issuer TEST announces a buyback at INR 500 per equity share."
    segment = {
        "segment_id": segment_id,
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }
    manifest_sha = digest({
        "transport": "ONE_ORIGINAL_D003_SEGMENT",
        "source_document_manifest_sha256": "a" * 64,
        "segments": [
            {"segment_id": segment_id, "text_sha256": segment["text_sha256"]}
        ],
        "schema_version": 1,
    })
    prompt = build_prompt_envelope(
        document_id=document_id,
        source_url=f"https://nsearchives.nseindia.com/corporate/{index}.pdf",
        event_ids=[f"E-{index}"],
        symbols=["TEST"],
        category_hints=["BUYBACK"],
        segments=[segment],
        segment_manifest_sha256=manifest_sha,
    )
    basis = {
        "queue_id": SOURCE_QUEUE_ID,
        "issuer_packet_rank": 1,
        "symbol": "TEST",
        "document_id": document_id,
        "segment_id": segment_id,
        "source_document_manifest_sha256": "a" * 64,
        "request_segment_manifest_sha256": manifest_sha,
        "model_config_sha256": SOURCE_MODEL_CONFIG_SHA,
    }
    return {
        **basis,
        "request_id": digest(basis),
        "document_order": index,
        "segment_order": 1,
        "global_request_index": index,
        "shard_id": (index - 1) % SHARD_COUNT,
        "prompt_sha256": prompt["prompt_sha256"],
        "prompt_envelope": prompt,
    }


def _raw_response(row: dict) -> str:
    request = row["prompt_envelope"]["request"]
    output = extraction_template(
        document_id=row["document_id"],
        event_ids=list(request["event_ids"]),
        symbols=list(request["symbols"]),
    )
    output["economic_relevance"] = "DIRECT_LISTED_SECURITY"
    output["transaction_families"] = ["BUYBACK"]
    output["transaction_stage"] = "PUBLIC_ANNOUNCEMENT"
    output["facts"]["security_economics"]["offer_price_per_share"] = {
        "status": "EXPLICIT",
        "value": 500.0,
        "unit": "INR_PER_SHARE",
        "evidence_segment_ids": [row["segment_id"]],
    }
    return json.dumps(output, sort_keys=True)


def _queue(monkeypatch: pytest.MonkeyPatch) -> dict:
    rows = [_row(index) for index in range(1, 1241)]
    queue = {
        "queue_id": SOURCE_QUEUE_ID,
        "source_p1_run_sha256": (
            "1a3a2f73eaed8ba09c84ab7c8d60699fa895f39d25d5797bd16138b09fd620cb"
        ),
        "model_config_sha256": SOURCE_MODEL_CONFIG_SHA,
        "fresh_request_count": 1240,
        "shard_count": 16,
        "feasibility_pass": True,
        "model_inference_executed": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
        "requests": rows,
        "shard_request_counts": {
            shard: sum(row["shard_id"] == shard for row in rows)
            for shard in range(SHARD_COUNT)
        },
    }
    # Reproduce the frozen producer's integer-key SHA and the loaded
    # JSON artifact's string-key representation.
    sha = digest(queue)
    queue["queue_sha256"] = sha
    wire_queue = json.loads(json.dumps(queue))
    monkeypatch.setattr("marketlab.ss001_l001_batch.SOURCE_QUEUE_SHA", sha)
    monkeypatch.setattr("scripts.run_ss001_l001_batch.SOURCE_QUEUE_SHA", sha)
    return wire_queue


def test_response_is_bound_to_exact_page_and_separate_runtime() -> None:
    row = _row(1)
    validate_request(row)
    config = _config()
    sealed = validate_and_seal_response(row, config, _raw_response(row))
    assert sealed["transport_id"] == TRANSPORT_ID
    assert sealed["source_runtime_equivalence_claimed"] is False
    assert sealed["status"] == "VALIDATED_PENDING_SEMANTIC_AUDIT"
    assert sealed["semantic_audit_status"] == "PENDING"
    assert sealed["validated_extraction"]["facts"]["security_economics"][
        "offer_price_per_share"
    ]["value"] == 500.0
    assert sealed["runtime_model_config_sha256"] != SOURCE_MODEL_CONFIG_SHA
    assert sealed["portfolio_eligibility_allowed"] is False


def test_source_segment_tamper_fails_closed() -> None:
    row = _row(1)
    row["prompt_envelope"]["request"]["segments"][0]["text"] = "tampered"
    with pytest.raises(AlphaContractError, match="prompt SHA mismatch"):
        validate_request(row)


def test_model_invented_evidence_fails_closed() -> None:
    row = _row(1)
    output = json.loads(_raw_response(row))
    output["facts"]["security_economics"]["offer_price_per_share"][
        "evidence_segment_ids"
    ] = ["invented-segment"]
    with pytest.raises(AlphaContractError, match="unknown evidence"):
        validate_and_seal_response(row, _config(), json.dumps(output))


def test_model_cannot_add_expected_return() -> None:
    row = _row(1)
    output = json.loads(_raw_response(row))
    output["expected_return"] = 50
    with pytest.raises(AlphaContractError, match="substantive schema"):
        validate_and_seal_response(row, _config(), json.dumps(output))


def test_non_https_external_endpoint_rejected() -> None:
    config = _config()
    config["api_endpoint"] = "http://example.com/v1/chat/completions"
    with pytest.raises(AlphaContractError, match="HTTPS or HTTP loopback"):
        validate_config(config)


def test_resumable_single_request_and_full_queue_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = _queue(monkeypatch)
    config = _config()
    preflight = build_preflight(queue, config)
    assert preflight["request_count"] == 1240
    assert preflight["status"] == "PREFLIGHT_PASS_NO_INFERENCE"

    called = []
    def fake_transport(row: dict, _: dict) -> str:
        called.append(row["request_id"])
        return _raw_response(row)

    first = execute_shard(
        queue=queue, config=config, output_dir=tmp_path,
        shard_id=0, max_requests=1, transport=fake_transport,
    )
    assert first["new_validated"] == 1
    assert len(called) == 1

    second = execute_shard(
        queue=queue, config=config, output_dir=tmp_path,
        shard_id=0, max_requests=1, transport=fake_transport,
    )
    assert second["existing_validated_skipped"] == 1
    assert second["new_validated"] == 1
    assert len(called) == 2

    collection = collect_verified(queue, config, tmp_path)
    assert collection["status"] == "PARTIAL_VALIDATED_EXTRACTIONS"
    assert collection["validated_request_count"] == 2
    assert collection["remaining_request_count"] == 1238
    assert collection["share_action_clearance_proven"] is False


def test_invalid_output_retained_and_only_explicitly_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = _queue(monkeypatch)
    config = _config()

    failed = execute_shard(
        queue=queue, config=config, output_dir=tmp_path,
        shard_id=1, max_requests=1, transport=lambda _r, _c: "{bad json",
    )
    assert failed["new_failures"] == 1

    skipped = execute_shard(
        queue=queue, config=config, output_dir=tmp_path,
        shard_id=1, max_requests=1, transport=lambda row, _c: _raw_response(row),
    )
    assert skipped["failed_requests_skipped"] == 1
    assert skipped["new_attempts"] == 1

    retried = execute_shard(
        queue=queue, config=config, output_dir=tmp_path,
        shard_id=1, max_requests=1, retry_failed=True,
        transport=lambda row, _c: _raw_response(row),
    )
    assert retried["new_validated"] == 1
    path = tmp_path / "requests" / "shard-01" / queue["requests"][1]["request_id"]
    assert sorted(p.name for p in path.glob("attempt-*.json")) == [
        "attempt-001.json", "attempt-002.json"
    ]


def test_collection_rejects_mutated_sealed_fact() -> None:
    row = _row(1)
    record = validate_and_seal_response(row, _config(), _raw_response(row))
    changed = copy.deepcopy(record)
    changed["validated_extraction"]["facts"]["security_economics"][
        "offer_price_per_share"
    ]["value"] = 99999
    # Demonstrate a recomputation of the sealed response rejects a mutated claim.
    original = validate_and_seal_response(row, _config(), changed["raw_model_response_text"])
    assert original != changed

def test_mutated_cached_success_is_rejected_before_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = _queue(monkeypatch)
    config = _config()
    execute_shard(
        queue=queue, config=config, output_dir=tmp_path,
        shard_id=0, max_requests=1,
        transport=lambda row, _c: _raw_response(row),
    )
    path = (
        tmp_path / "requests" / "shard-00"
        / queue["requests"][0]["request_id"] / "attempt-001.json"
    )
    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt["sealed"]["validated_extraction"]["facts"]["security_economics"][
        "offer_price_per_share"
    ]["value"] = 900
    path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(AlphaContractError, match="previous receipt SHA mismatch"):
        execute_shard(
            queue=queue, config=config, output_dir=tmp_path,
            shard_id=0, max_requests=1,
            transport=lambda row, _c: _raw_response(row),
        )
