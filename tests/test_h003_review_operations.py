from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from marketlab.h003_review import (
    BlindReviewPayload,
    H003ReviewError,
    build_review_decision,
)


def _module(path: str, name: str):
    target = Path(path)
    spec = importlib.util.spec_from_file_location(name, target)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _blind(candidate_id: str) -> BlindReviewPayload:
    provisional = BlindReviewPayload(
        schema_version=1,
        payload_sha256="",
        review_rule_id="H003-V001",
        review_rule_sha256="8b5f3d89b04b486ab2d1e6e9508f9b2ffb69bf51781fa13cbf1db9e81bdc2244",
        candidate_id=candidate_id,
        evidence_sha256="a" * 64,
        redacted_excerpt="We expect revenue growth of 15% next year.",
        redacted_page_context=("We expect revenue growth of 15% next year.",),
        page_number=1,
        line_start=1,
        line_end=1,
        future_markers=("we expect",),
        deadline_markers=("next year",),
        quantitative_tokens=("15%",),
        domain_markers=("revenue",),
    )
    chunk = _module("scripts/chunk_h003_review_queue.py", "chunk_h003_review_queue")
    unsigned = provisional.to_dict()
    unsigned.pop("payload_sha256", None)
    return BlindReviewPayload(
        **{**provisional.__dict__, "payload_sha256": chunk._canonical_hash(unsigned)}
    )


def test_semantic_chunk_partition_is_deterministic_and_exact():
    chunk = _module("scripts/chunk_h003_review_queue.py", "chunk_h003_review_queue")
    payloads = tuple(_blind(f"c{index:03d}") for index in range(93))
    first_manifest, first_chunks = chunk.build_chunks(payloads, chunk_size=40)
    second_manifest, second_chunks = chunk.build_chunks(payloads, chunk_size=40)
    assert first_manifest == second_manifest
    assert first_chunks == second_chunks
    assert [len(values) for values in first_chunks] == [40, 40, 13]
    flattened = [payload.candidate_id for values in first_chunks for payload in values]
    assert flattened == [payload.candidate_id for payload in payloads]
    assert len(set(flattened)) == 93
    assert first_manifest["candidate_count"] == 93
    assert first_manifest["chunk_count"] == 3
    assert len(first_manifest["manifest_sha256"]) == 64


def test_chunk_writer_removes_stale_chunk_files(tmp_path):
    chunk = _module("scripts/chunk_h003_review_queue.py", "chunk_h003_review_queue")
    payloads = tuple(_blind(f"c{index:03d}") for index in range(3))
    manifest, chunks = chunk.build_chunks(payloads, chunk_size=2)
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "chunk-9999.json").write_text("[]\n", encoding="utf-8")
    chunk.write_chunks(tmp_path, manifest, chunks)
    assert not (tmp_path / "chunk-9999.json").exists()
    assert (tmp_path / "chunk-0000.json").exists()
    assert (tmp_path / "chunk-0001.json").exists()
    assert json.loads((tmp_path / "manifest.json").read_text())["chunk_count"] == 2


def test_decision_loader_merges_mechanical_and_semantic_without_duplicates(tmp_path):
    freezer = _module("scripts/freeze_h003_review.py", "freeze_h003_review")
    first_payload = _blind("c1")
    second_payload = _blind("c2")
    first = build_review_decision(
        candidate_id="c1",
        blind_payload_sha256=first_payload.payload_sha256,
        disposition="REJECTED",
        reason_code="REJECT_QUESTION_OR_NON_MANAGEMENT_SPEAKER",
        reviewer_version="mechanical-v1",
        reviewed_at_utc="2026-09-07T00:00:00Z",
    )
    second = build_review_decision(
        candidate_id="c2",
        blind_payload_sha256=second_payload.payload_sha256,
        disposition="REJECTED",
        reason_code="REJECT_GENERIC_ASPIRATION",
        reviewer_version="semantic-v1",
        reviewed_at_utc="2026-09-07T00:00:00Z",
    )
    mechanical = tmp_path / "mechanical.json"
    semantic_dir = tmp_path / "semantic"
    semantic_dir.mkdir()
    mechanical.write_text(json.dumps([first.to_dict()]), encoding="utf-8")
    (semantic_dir / "chunk-0000-decisions.json").write_text(
        json.dumps([second.to_dict()]), encoding="utf-8"
    )
    decisions = freezer.load_decisions(mechanical, semantic_dir)
    assert {decision.candidate_id for decision in decisions} == {"c1", "c2"}


def test_decision_loader_rejects_duplicate_candidate_across_files(tmp_path):
    freezer = _module("scripts/freeze_h003_review.py", "freeze_h003_review")
    payload = _blind("c1")
    decision = build_review_decision(
        candidate_id="c1",
        blind_payload_sha256=payload.payload_sha256,
        disposition="REJECTED",
        reason_code="REJECT_GENERIC_ASPIRATION",
        reviewer_version="semantic-v1",
        reviewed_at_utc="2026-09-07T00:00:00Z",
    )
    mechanical = tmp_path / "mechanical.json"
    semantic_dir = tmp_path / "semantic"
    semantic_dir.mkdir()
    document = json.dumps([decision.to_dict()])
    mechanical.write_text(document, encoding="utf-8")
    (semantic_dir / "chunk-0000-decisions.json").write_text(document, encoding="utf-8")
    with pytest.raises(H003ReviewError, match="duplicate candidate decisions"):
        freezer.load_decisions(mechanical, semantic_dir)


def test_decision_loader_requires_semantic_decision_files(tmp_path):
    freezer = _module("scripts/freeze_h003_review.py", "freeze_h003_review")
    mechanical = tmp_path / "mechanical.json"
    mechanical.write_text("[]\n", encoding="utf-8")
    semantic_dir = tmp_path / "semantic"
    semantic_dir.mkdir()
    with pytest.raises(H003ReviewError, match="contains no decision files"):
        freezer.load_decisions(mechanical, semantic_dir)


def test_frozen_h003_source_denominator_is_100_cohort_97_source_bearing():
    from marketlab.h003_review import (
        EXPECTED_COHORT_COMPANY_COUNT,
        EXPECTED_SOURCE_BEARING_COMPANY_COUNT,
        FROZEN_ZERO_SOURCE_SYMBOLS,
    )

    source_path = Path(
        "research/prospective/h003/FY27-Q2-2026-09-06/source-coverage-v1.json"
    )
    document = json.loads(source_path.read_text(encoding="utf-8"))
    records = document["records"]
    source_bearing = [record for record in records if record["source_count"] > 0]
    zero_source = sorted(
        record["symbol"] for record in records if record["source_count"] == 0
    )
    assert len(records) == EXPECTED_COHORT_COMPANY_COUNT == 100
    assert len(source_bearing) == EXPECTED_SOURCE_BEARING_COMPANY_COUNT == 97
    assert zero_source == sorted(FROZEN_ZERO_SOURCE_SYMBOLS) == ["BHEL", "ITC", "TRENT"]
