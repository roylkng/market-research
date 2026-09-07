from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from marketlab.h003_review import REVIEW_RULE_ID, REVIEW_RULE_SHA256


def _module():
    path = Path("scripts/compile_h003_review_judgments.py")
    spec = importlib.util.spec_from_file_location("compile_h003_review_judgments", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _blind_payload(module, candidate_id: str = "cand-1"):
    unsigned = {
        "schema_version": 1,
        "review_rule_id": REVIEW_RULE_ID,
        "review_rule_sha256": REVIEW_RULE_SHA256,
        "candidate_id": candidate_id,
        "evidence_sha256": "e" * 64,
        "redacted_excerpt": "We expect revenue growth of 15% next year.",
        "redacted_page_context": ["We expect revenue growth of 15% next year."],
        "page_number": 1,
        "line_start": 1,
        "line_end": 1,
        "future_markers": ["we expect"],
        "deadline_markers": ["next year"],
        "quantitative_tokens": ["15%"],
        "domain_markers": ["revenue", "growth"],
    }
    return {**unsigned, "payload_sha256": module._canonical_hash(unsigned)}


def _source_batch(module, payload):
    return [
        {
            "candidate_id": payload["candidate_id"],
            "payload_sha256": payload["payload_sha256"],
            "excerpt": payload["redacted_excerpt"],
            "before": "",
            "after": "",
            "future": ["we expect"],
            "deadline": ["next year"],
            "quant": ["15%"],
            "domain": ["revenue", "growth"],
        }
    ]


def _accepted_judgment(candidate_id: str = "cand-1"):
    return {
        "candidate_id": candidate_id,
        "disposition": "ACCEPTED",
        "reason_code": "ACCEPT_MEASURABLE_MANAGEMENT_COMMITMENT",
        "note": None,
        "duplicate_of_candidate_id": None,
        "normalized_claim": {
            "claim_type": "GROWTH_GUIDANCE",
            "metric": "revenue_growth",
            "unit": "percent",
            "target_min": 15.0,
            "target_max": 15.0,
            "target_deadline": None,
            "target_horizon": "next year",
            "normalized_claim": "Deliver 15% revenue growth next year.",
        },
    }


def test_compile_batch_binds_frozen_payload_and_supplied_review_time():
    module = _module()
    payload = _blind_payload(module)
    source_batch = _source_batch(module, payload)
    batch_sha = module._canonical_hash(source_batch)
    document = {
        "schema_version": 1,
        "batch_file": "batch-0000.json",
        "batch_sha256": batch_sha,
        "reviewer_version": "blind-review-r4-v1",
        "reviewed_at_utc": "2099-01-01T00:00:00Z",
        "judgments": [_accepted_judgment()],
    }
    decisions = module.compile_batch(
        judgment_document=document,
        source_batch=source_batch,
        expected_batch_file="batch-0000.json",
        expected_batch_sha256=batch_sha,
        blind_payload_sha_by_candidate={"cand-1": payload["payload_sha256"]},
        reviewed_at_utc="2026-09-07T05:00:00Z",
    )
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision["candidate_id"] == "cand-1"
    assert decision["blind_payload_sha256"] == payload["payload_sha256"]
    assert decision["reviewed_at_utc"] == "2026-09-07T05:00:00Z"
    assert decision["decision_id"]
    assert decision["normalized_claim"]["target_min"] == 15.0


def test_compile_batch_rejects_changed_batch_hash():
    module = _module()
    payload = _blind_payload(module)
    source_batch = _source_batch(module, payload)
    document = {
        "schema_version": 1,
        "batch_file": "batch-0000.json",
        "batch_sha256": "0" * 64,
        "reviewer_version": "blind-review-r4-v1",
        "judgments": [_accepted_judgment()],
    }
    with pytest.raises(module.JudgmentCompileError, match="batch_sha256"):
        module.compile_batch(
            judgment_document=document,
            source_batch=source_batch,
            expected_batch_file="batch-0000.json",
            expected_batch_sha256=module._canonical_hash(source_batch),
            blind_payload_sha_by_candidate={"cand-1": payload["payload_sha256"]},
            reviewed_at_utc="2026-09-07T05:00:00Z",
        )


def test_compile_batch_rejects_candidate_order_or_coverage_change():
    module = _module()
    first = _blind_payload(module, "cand-1")
    second = _blind_payload(module, "cand-2")
    source_batch = _source_batch(module, first) + _source_batch(module, second)
    batch_sha = module._canonical_hash(source_batch)
    document = {
        "schema_version": 1,
        "batch_file": "batch-0000.json",
        "batch_sha256": batch_sha,
        "reviewer_version": "blind-review-r4-v1",
        "judgments": [_accepted_judgment("cand-2"), _accepted_judgment("cand-1")],
    }
    with pytest.raises(module.JudgmentCompileError, match="order/coverage"):
        module.compile_batch(
            judgment_document=document,
            source_batch=source_batch,
            expected_batch_file="batch-0000.json",
            expected_batch_sha256=batch_sha,
            blind_payload_sha_by_candidate={
                "cand-1": first["payload_sha256"],
                "cand-2": second["payload_sha256"],
            },
            reviewed_at_utc="2026-09-07T05:00:00Z",
        )


def test_compile_batch_rejects_payload_binding_mismatch():
    module = _module()
    payload = _blind_payload(module)
    source_batch = _source_batch(module, payload)
    batch_sha = module._canonical_hash(source_batch)
    document = {
        "schema_version": 1,
        "batch_file": "batch-0000.json",
        "batch_sha256": batch_sha,
        "reviewer_version": "blind-review-r4-v1",
        "judgments": [_accepted_judgment()],
    }
    with pytest.raises(module.JudgmentCompileError, match="payload binding"):
        module.compile_batch(
            judgment_document=document,
            source_batch=source_batch,
            expected_batch_file="batch-0000.json",
            expected_batch_sha256=batch_sha,
            blind_payload_sha_by_candidate={"cand-1": "f" * 64},
            reviewed_at_utc="2026-09-07T05:00:00Z",
        )


def test_validate_blind_payloads_recomputes_payload_hash():
    module = _module()
    payload = _blind_payload(module)
    assert module._validate_blind_payloads([payload]) == {
        "cand-1": payload["payload_sha256"]
    }
    changed = json.loads(json.dumps(payload))
    changed["redacted_excerpt"] = "changed"
    with pytest.raises(module.JudgmentCompileError, match="identity/hash"):
        module._validate_blind_payloads([changed])


def test_validate_batch_manifest_recomputes_manifest_hash():
    module = _module()
    unsigned = {
        "schema_version": 4,
        "source_semantic_queue_sha256": "q" * 64,
        "candidate_count": 1,
        "batch_size": 20,
        "batch_count": 1,
        "candidate_ids_sha256": "i" * 64,
        "batches": [
            {
                "batch_index": 0,
                "file": "batch-0000.json",
                "candidate_count": 1,
                "batch_sha256": "b" * 64,
                "first_candidate_id": "cand-1",
                "last_candidate_id": "cand-1",
            }
        ],
    }
    document = {**unsigned, "manifest_sha256": module._canonical_hash(unsigned)}
    assert "batch-0000.json" in module._validate_batch_manifest(document)
    document["candidate_count"] = 2
    with pytest.raises(module.JudgmentCompileError, match="manifest hash"):
        module._validate_batch_manifest(document)
