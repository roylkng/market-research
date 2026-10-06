from __future__ import annotations

import copy

from marketlab.hg006_full_inference import (
    EXPECTED_MODEL_CONFIG_SHA,
    EXPECTED_P0_RUN_SHA,
    EXPECTED_QUEUE_SHA,
    build_shard_template,
    combine_shard_bundles,
    ingest_shard_responses,
)
from marketlab.hg006_stage_contract import extraction_template


def _queue() -> dict:
    rows = []
    for index in range(1448):
        request_id = f"{index:064x}"
        shard_id = index % 16
        chronology_id = f"C{index % 298:03d}"
        document_id = f"{index + 5000:064x}"
        symbol = f"S{index:04d}"
        family = (
            "PREFERENTIAL_WARRANT"
            if index < 738
            else "SCHEME_REORGANISATION"
        )
        segment_id = f"{document_id}:pdf:page:0001"
        rows.append(
            {
                "schema_version": 1,
                "queue_id": "HG006-L001-P1-v1",
                "request_id": request_id,
                "shard_id": shard_id,
                "chronology_id": chronology_id,
                "document_id": document_id,
                "symbol": symbol,
                "family": family,
                "event_ids": [f"E{index:04d}"],
                "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
                "prompt_sha256": f"{index + 10000:064x}",
                "prompt_envelope": {
                    "system": "frozen",
                    "request": {
                        "request_id": request_id,
                        "chronology_id": chronology_id,
                        "document_id": document_id,
                        "event_ids": [f"E{index:04d}"],
                        "symbol": symbol,
                        "family": family,
                        "segment_manifest_sha256": f"{index + 20000:064x}",
                        "segments": [
                            {
                                "segment_id": segment_id,
                                "text": "No material stage stated.",
                                "text_sha256": (
                                    "e" * 64
                                ),
                            }
                        ],
                        "required_output_template": extraction_template(
                            document_id=document_id,
                            event_ids=[f"E{index:04d}"],
                            symbol=symbol,
                            family=family,
                        ),
                    },
                },
            }
        )
    return {
        "queue_id": "HG006-L001-P1-v1",
        "queue_sha256": EXPECTED_QUEUE_SHA,
        "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
        "request_count": 1448,
        "chronology_count": 300,
        "requests": rows,
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _p0(queue: dict) -> dict:
    rows = []
    for queue_row in queue["requests"][:20]:
        extraction = extraction_template(
            document_id=queue_row["document_id"],
            event_ids=queue_row["event_ids"],
            symbol=queue_row["symbol"],
            family=queue_row["family"],
        )
        extraction["validated_structured_output_sha256"] = "a" * 64
        sealed = {
            "request_id": queue_row["request_id"],
            "document_id": queue_row["document_id"],
            "status": "VALIDATED",
            "prompt_sha256": queue_row["prompt_sha256"],
            "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
            "raw_model_response_sha256": "b" * 64,
            "validated_extraction": extraction,
        }
        rows.append(
            {
                "request_id": queue_row["request_id"],
                "raw_model_response_sha256": "b" * 64,
                "sealed_response": sealed,
            }
        )
    return {
        "run_id": "HG006-L001-P0-GPT56SOL-NATIVE-v1",
        "run_sha256": EXPECTED_P0_RUN_SHA,
        "selected_request_count": 20,
        "validated_response_count": 20,
        "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
        "rows": rows,
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_shard_template_separates_p0_reuse_and_pending() -> None:
    queue = _queue()
    p0 = _p0(queue)
    template = build_shard_template(queue, p0, shard_id=0)

    assert template["shard_id"] == 0
    assert template["request_count"] > 0
    assert template["p0_reuse_count"] > 0
    assert (
        template["p0_reuse_count"] + template["pending_native_count"]
        == template["request_count"]
    )
    assert all(
        row["prompt_envelope"] is None
        for row in template["rows"]
        if row["execution_state"] == "P0_VALIDATED_REUSE"
    )
    assert all(
        isinstance(row["prompt_envelope"], dict)
        for row in template["rows"]
        if row["execution_state"] == "PENDING_NATIVE_OUTPUT"
    )


def test_ingest_shard_validates_fresh_empty_evidence_outputs() -> None:
    queue = _queue()
    p0 = _p0(queue)
    template = build_shard_template(queue, p0, shard_id=0)
    queue_by_id = {row["request_id"]: row for row in queue["requests"]}
    responses = []
    for row in template["rows"]:
        if row["execution_state"] != "PENDING_NATIVE_OUTPUT":
            continue
        queue_row = queue_by_id[row["request_id"]]
        responses.append(
            {
                "request_id": row["request_id"],
                "status": "MODEL_OUTPUT",
                "model_output": extraction_template(
                    document_id=queue_row["document_id"],
                    event_ids=queue_row["event_ids"],
                    symbol=queue_row["symbol"],
                    family=queue_row["family"],
                ),
            }
        )

    bundle = ingest_shard_responses(
        queue,
        p0,
        shard_id=0,
        native_bundle={
            "execution_id": "HG006-L001-P2-v1",
            "shard_id": 0,
            "source_queue_sha256": EXPECTED_QUEUE_SHA,
            "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
            "responses": responses,
        },
    )

    assert bundle["request_count"] == template["request_count"]
    assert bundle["status_counts"] == {"VALIDATED": template["request_count"]}
    assert all(row["status"] == "VALIDATED" for row in bundle["rows"])


def test_combine_requires_all_shards_and_passes_full_validated_fixture() -> None:
    queue = _queue()
    p0 = _p0(queue)
    p0_ids = {row["request_id"] for row in p0["rows"]}
    bundles = []
    for shard_id in range(16):
        rows = []
        for queue_row in queue["requests"]:
            if queue_row["shard_id"] != shard_id:
                continue
            request_id = queue_row["request_id"]
            rows.append(
                {
                    "request_id": request_id,
                    "shard_id": shard_id,
                    "chronology_id": queue_row["chronology_id"],
                    "document_id": queue_row["document_id"],
                    "symbol": queue_row["symbol"],
                    "family": queue_row["family"],
                    "status": "VALIDATED",
                    "source": (
                        "P0_VALIDATED_REUSE"
                        if request_id in p0_ids
                        else "FRESH_NATIVE_OUTPUT"
                    ),
                }
            )
        bundle = {
            "execution_id": "HG006-L001-P2-v1",
            "source_queue_sha256": EXPECTED_QUEUE_SHA,
            "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
            "shard_id": shard_id,
            "rows": rows,
            "bundle_sha256": f"{shard_id + 1:064x}",
        }
        bundles.append(bundle)

    combined = combine_shard_bundles(queue, p0, bundles)

    assert combined["request_count"] == 1448
    assert combined["validated_request_count"] == 1448
    assert combined["validated_chronology_count"] == 298
    assert combined["full_ingestion_pass"] is True
    assert combined["promotion_allowed_to_d003_threading"] is True


def test_model_failure_remains_explicit() -> None:
    queue = _queue()
    p0 = _p0(queue)
    template = build_shard_template(queue, p0, shard_id=1)
    responses = []
    failed_once = False
    for row in template["rows"]:
        if row["execution_state"] != "PENDING_NATIVE_OUTPUT":
            continue
        if not failed_once:
            responses.append(
                {
                    "request_id": row["request_id"],
                    "status": "MODEL_FAILURE",
                    "model_output": None,
                    "error": "transport failure",
                }
            )
            failed_once = True
        else:
            queue_row = next(
                item
                for item in queue["requests"]
                if item["request_id"] == row["request_id"]
            )
            responses.append(
                {
                    "request_id": row["request_id"],
                    "status": "MODEL_OUTPUT",
                    "model_output": copy.deepcopy(
                        queue_row["prompt_envelope"]["request"][
                            "required_output_template"
                        ]
                    ),
                }
            )

    bundle = ingest_shard_responses(
        queue,
        p0,
        shard_id=1,
        native_bundle={
            "execution_id": "HG006-L001-P2-v1",
            "shard_id": 1,
            "source_queue_sha256": EXPECTED_QUEUE_SHA,
            "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
            "responses": responses,
        },
    )

    assert bundle["status_counts"]["MODEL_FAILURE"] == 1
