from __future__ import annotations

import copy
import hashlib

from marketlab import hg006_p3_inference as p3
from marketlab.alpha import digest
from marketlab.hg006_inference_queue import MODEL_CONFIG, SYSTEM_PROMPT
from marketlab.hg006_stage_contract import extraction_template


def _segment(seed: str) -> dict:
    text = f"Board approved {seed}."
    return {
        "segment_id": f"seg-{seed}",
        "kind": "PDF_PAGE",
        "locator": {"page_number": 1},
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "phrase_hits": {},
        "source_order": 0,
    }


def _prior_prompt(
    *,
    chronology_id: str,
    document_id: str,
    manifest: str,
    symbol: str,
    family: str,
    event_id: str,
) -> dict:
    segment = _segment(document_id[:6])
    request_id = hashlib.sha256(
        f"HG006-L001-P1-v1|{chronology_id}|{document_id}".encode()
    ).hexdigest()
    request = {
        "queue_id": "HG006-L001-P1-v1",
        "request_id": request_id,
        "chronology_id": chronology_id,
        "document_id": document_id,
        "event_ids": [event_id],
        "symbol": symbol,
        "family": family,
        "chronology_timestamp_utc": "2024-01-01T10:00:00Z",
        "segment_manifest_sha256": manifest,
        "segments": [segment],
        "required_output_template": extraction_template(
            document_id=document_id,
            event_ids=[event_id],
            symbol=symbol,
            family=family,
        ),
    }
    envelope = {"system": SYSTEM_PROMPT, "request": request}
    return {
        "schema_version": 1,
        "queue_id": "HG006-L001-P1-v1",
        "request_id": request_id,
        "shard_id": 0,
        "chronology_id": chronology_id,
        "document_id": document_id,
        "symbol": symbol,
        "family": family,
        "event_ids": [event_id],
        "model_config": MODEL_CONFIG,
        "model_config_sha256": p3.EXPECTED_MODEL_CONFIG_SHA,
        "prompt_sha256": hashlib.sha256(
            p3._canonical_bytes(envelope)
        ).hexdigest(),
        "prompt_envelope": envelope,
    }


def _fixtures():
    doc1 = hashlib.sha256(b"doc1").hexdigest()
    doc2 = hashlib.sha256(b"doc2").hexdigest()
    m1 = "a" * 64
    m2_old = "b" * 64
    m2_new = "c" * 64
    prior1 = _prior_prompt(
        chronology_id="C1",
        document_id=doc1,
        manifest=m1,
        symbol="AAA",
        family="PREFERENTIAL_WARRANT",
        event_id="E1",
    )
    prior2 = _prior_prompt(
        chronology_id="C1",
        document_id=doc2,
        manifest=m2_old,
        symbol="AAA",
        family="PREFERENTIAL_WARRANT",
        event_id="E2",
    )
    prior_queue = {
        "queue_id": p3.EXPECTED_PRIOR_QUEUE_ID,
        "queue_sha256": p3.EXPECTED_PRIOR_QUEUE_SHA,
        "request_count": 2,
        "model_config_sha256": p3.EXPECTED_MODEL_CONFIG_SHA,
        "requests": [prior1, prior2],
    }
    ingestion_rows = []
    for row in [prior1, prior2]:
        sealed = {
            "request_id": row["request_id"],
            "validated_extraction": {"ok": True},
        }
        ingestion_rows.append(
            {
                "request_id": row["request_id"],
                "chronology_id": row["chronology_id"],
                "document_id": row["document_id"],
                "symbol": row["symbol"],
                "family": row["family"],
                "status": "VALIDATED",
                "validated_response": sealed,
            }
        )
    prior_ingestion = {
        "execution_id": p3.EXPECTED_PRIOR_INGESTION_ID,
        "ingestion_sha256": p3.EXPECTED_PRIOR_INGESTION_SHA,
        "request_count": 2,
        "validated_request_count": 2,
        "full_ingestion_pass": True,
        "rows": ingestion_rows,
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }

    seg1 = prior1["prompt_envelope"]["request"]["segments"]
    seg2 = prior2["prompt_envelope"]["request"]["segments"]
    pack = {
        "pack_id": p3.EXPECTED_S003_ID,
        "pack_sha256": p3.EXPECTED_S003_SHA,
        "chronology_count": 2,
        "state_counts": {"EVIDENCE_READY": 1, "TEXT_UNAVAILABLE": 1},
        "retained_document_count": 2,
        "chronologies": [
            {
                "chronology_id": "C1",
                "symbol": "AAA",
                "family": "PREFERENTIAL_WARRANT",
                "evidence_state": "EVIDENCE_READY",
                "retained_documents": [
                    {
                        "document_id": doc1,
                        "event_ids": ["E1"],
                        "chronology_timestamp_utc": "2024-01-01T10:00:00Z",
                        "segment_manifest_sha256": m1,
                        "selected_segments": copy.deepcopy(seg1),
                    },
                    {
                        "document_id": doc2,
                        "event_ids": ["E2"],
                        "chronology_timestamp_utc": "2024-01-01T10:00:00Z",
                        "segment_manifest_sha256": m2_new,
                        "selected_segments": copy.deepcopy(seg2),
                    },
                ],
            },
            {
                "chronology_id": "C2",
                "symbol": "BBB",
                "family": "SCHEME_REORGANISATION",
                "evidence_state": "TEXT_UNAVAILABLE",
                "retained_documents": [],
            },
        ],
        "expanded_population_terminal_labels_opened": False,
        "expanded_population_completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    return pack, prior_queue, prior_ingestion


def test_p3_reuses_only_exact_prior_prompt(monkeypatch) -> None:
    monkeypatch.setattr(p3, "EXPECTED_CHRONOLOGY_COUNT", 2)
    monkeypatch.setattr(p3, "EXPECTED_EVIDENCE_READY", 1)
    monkeypatch.setattr(p3, "EXPECTED_TEXT_UNAVAILABLE", 1)
    monkeypatch.setattr(p3, "EXPECTED_REQUEST_COUNT", 2)
    monkeypatch.setattr(p3, "EXPECTED_REUSE_COUNT", 1)
    monkeypatch.setattr(p3, "EXPECTED_FRESH_COUNT", 1)
    monkeypatch.setattr(p3, "EXPECTED_PRIOR_REQUEST_COUNT", 2)
    monkeypatch.setattr(p3, "EXPECTED_CHANGED_PRIOR_COUNT", 1)

    pack, prior_queue, prior_ingestion = _fixtures()
    queue = p3.build_p3_extension_queue(
        full_pack=pack,
        prior_queue=prior_queue,
        prior_ingestion=prior_ingestion,
    )
    assert queue["execution_state_counts"] == {
        "FRESH_MODEL_REQUIRED": 1,
        "P2_VALIDATED_REUSE": 1,
    }
    assert queue["changed_prior_prompt_count"] == 1
    reused = next(
        row for row in queue["requests"]
        if row["p3_execution_state"] == "P2_VALIDATED_REUSE"
    )
    fresh = next(
        row for row in queue["requests"]
        if row["p3_execution_state"] == "FRESH_MODEL_REQUIRED"
    )
    assert reused["queue_id"] == "HG006-L001-P1-v1"
    assert fresh["queue_id"] == p3.QUEUE_ID
    assert reused["p3_prior_validated_response_sha256"] == digest(
        prior_ingestion["rows"][0]["validated_response"]
    )


def test_fresh_request_identity_changes_with_manifest() -> None:
    document_id = hashlib.sha256(b"doc").hexdigest()
    one = p3.fresh_request_id_for("C1", document_id, "a" * 64)
    two = p3.fresh_request_id_for("C1", document_id, "b" * 64)
    assert one != two
    assert 0 <= p3.shard_for_request_id(one) < p3.SHARD_COUNT
