from __future__ import annotations

import copy

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg006_native_materializer import build_native_bundle


def _queue() -> dict:
    segment = {
        "segment_id": "doc:pdf:page:0001",
        "text": "Board approved allotment.",
        "text_sha256": "x",
    }
    template = {
        "schema_version": 1,
        "contract_id": "HG006-L001-v1",
        "document_id": "doc",
        "event_ids": ["e1"],
        "symbol": "AAA",
        "family": "PREFERENTIAL_WARRANT",
        "stage_observations": [],
        "explicit_terminal_language": "NO_EXPLICIT_TERMINAL_LANGUAGE",
        "terminal_evidence_segment_ids": [],
        "transaction_anchors": [],
        "family_semantic_conflict": None,
        "unresolved_questions": [],
        "contradictions_within_document": [],
        "extraction_caveats": [],
        "provenance": {},
    }
    return {
        "queue_id": "HG006-L001-P1-v1",
        "queue_sha256": (
            "6732f5741ec6d9a2e1926a94d234c642871d454f0354d60dfa87cec3807ce934"
        ),
        "model_config_sha256": (
            "043ec1f2d38aec7e72b24cfcbe864aebd83cda8b717d3c8c0fac2ecb3cafa51d"
        ),
        "requests": [{
            "request_id": "r1",
            "shard_id": 4,
            "prompt_envelope": {
                "request": {
                    "segments": [segment],
                    "required_output_template": template,
                }
            },
        }],
    }


def test_builds_generic_native_bundle_for_requested_shard() -> None:
    decisions = {
        "r1": {
            "s": [["BOARD_APPROVED", [1]]],
            "a": [["BOARD_APPROVAL_DATE", "2026-01-01", [1]]],
        }
    }
    bundle = build_native_bundle(
        _queue(),
        {"rows": []},
        decisions,
        shard_id=4,
    )
    assert bundle["shard_id"] == 4
    assert bundle["fresh_response_count"] == 1
    output = bundle["responses"][0]["model_output"]
    assert output["stage_observations"][0]["stage"] == "BOARD_APPROVED"
    assert output["stage_observations"][0]["evidence_segment_ids"] == [
        "doc:pdf:page:0001"
    ]


def test_fails_closed_on_missing_decision() -> None:
    with pytest.raises(AlphaContractError, match="decision accounting mismatch"):
        build_native_bundle(_queue(), {"rows": []}, {}, shard_id=4)


def test_does_not_mutate_queue_template() -> None:
    queue = _queue()
    before = copy.deepcopy(queue)
    build_native_bundle(
        queue,
        {"rows": []},
        {"r1": {"s": [["BOARD_APPROVED", [1]]]}},
        shard_id=4,
    )
    assert queue == before
