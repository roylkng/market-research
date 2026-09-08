from __future__ import annotations

import json
from copy import deepcopy

import pytest

from marketlab.h003_review_batches import (
    BATCH_SIZE,
    OUTCOME_RULE_ID,
    OUTCOME_RULE_SHA256,
    H003ReviewBatchError,
    canonical_hash,
    shard_blind_packets,
    validate_source_document,
)


def packet(index: int) -> dict[str, object]:
    provisional: dict[str, object] = {
        "schema_version": 1,
        "payload_sha256": "",
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "packet_id": f"H003O-{index:024x}",
        "source_date": "2025-01-01",
        "normalized_claim": f"Deliver target {index} during FY26.",
        "claim_type": "GUIDANCE",
        "metric": "target",
        "unit": "%",
        "target_min": float(index),
        "target_max": None,
        "target_deadline": None,
        "target_horizon": "FY26",
        "evidence": [],
    }
    unsigned = dict(provisional)
    unsigned.pop("payload_sha256")
    provisional["payload_sha256"] = canonical_hash(unsigned)
    return provisional


def source_documents(count: int = 41) -> tuple[dict[str, object], dict[str, object]]:
    packets = [packet(index) for index in reversed(range(count))]
    source_unsigned: dict[str, object] = {
        "schema_version": 1,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "review_ledger_sha256": "a" * 64,
        "claim_audit_sha256": "b" * 64,
        "source_bundle_sha256": "c" * 64,
        "source_cutoff_utc": "2026-09-06T12:21:06.431463Z",
        "packet_count": count,
        "packets": packets,
        "market_outcomes_included": False,
        "live_capital_allowed": False,
    }
    source = {**source_unsigned, "package_sha256": canonical_hash(source_unsigned)}
    manifest_unsigned: dict[str, object] = {
        "schema_version": 1,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "blind_package_sha256": source["package_sha256"],
        "packet_count": count,
        "outcome_data_accessed": False,
        "market_outcomes_included": False,
        "live_capital_allowed": False,
    }
    manifest = {**manifest_unsigned, "manifest_sha256": canonical_hash(manifest_unsigned)}
    return source, manifest


def write_json(path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_validate_source_sorts_and_verifies_every_packet() -> None:
    source, manifest = source_documents()
    packets = validate_source_document(source, manifest, expected_packet_count=41)
    ids = [item["packet_id"] for item in packets]
    assert ids == sorted(ids)
    assert len(ids) == 41


def test_corrupted_packet_hash_fails_closed() -> None:
    source, manifest = source_documents()
    source = deepcopy(source)
    source["packets"][0]["normalized_claim"] = "tampered"
    source_unsigned = dict(source)
    source_unsigned.pop("package_sha256")
    source["package_sha256"] = canonical_hash(source_unsigned)
    manifest["blind_package_sha256"] = source["package_sha256"]
    manifest_unsigned = dict(manifest)
    manifest_unsigned.pop("manifest_sha256")
    manifest["manifest_sha256"] = canonical_hash(manifest_unsigned)
    with pytest.raises(H003ReviewBatchError, match="payload hash mismatch"):
        validate_source_document(source, manifest, expected_packet_count=41)


def test_private_binding_key_fails_closed() -> None:
    source, manifest = source_documents()
    source = deepcopy(source)
    source["packets"][0]["symbol"] = "SECRET"
    unsigned_packet = dict(source["packets"][0])
    unsigned_packet.pop("payload_sha256")
    source["packets"][0]["payload_sha256"] = canonical_hash(unsigned_packet)
    source_unsigned = dict(source)
    source_unsigned.pop("package_sha256")
    source["package_sha256"] = canonical_hash(source_unsigned)
    manifest["blind_package_sha256"] = source["package_sha256"]
    manifest_unsigned = dict(manifest)
    manifest_unsigned.pop("manifest_sha256")
    manifest["manifest_sha256"] = canonical_hash(manifest_unsigned)
    with pytest.raises(H003ReviewBatchError, match="private binding key leaked"):
        validate_source_document(source, manifest, expected_packet_count=41)


def test_sharding_is_deterministic_and_exact(tmp_path) -> None:
    source, manifest = source_documents()
    source_path = tmp_path / "blind.json"
    manifest_path = tmp_path / "public.json"
    write_json(source_path, source)
    write_json(manifest_path, manifest)

    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    first = shard_blind_packets(
        blind_packet_path=source_path,
        public_manifest_path=manifest_path,
        output_dir=out_a,
        expected_packet_count=41,
    )
    second = shard_blind_packets(
        blind_packet_path=source_path,
        public_manifest_path=manifest_path,
        output_dir=out_b,
        expected_packet_count=41,
    )

    assert first == second
    assert first["packet_count"] == 41
    assert first["batch_size"] == BATCH_SIZE
    assert first["batch_count"] == 3
    assert [entry["packet_count"] for entry in first["batches"]] == [20, 20, 1]
    assert first["private_binding_accessed"] is False
    assert first["market_outcomes_included"] is False
    assert first["live_capital_allowed"] is False
    for filename in (
        "batch-0001.json",
        "batch-0002.json",
        "batch-0003.json",
        "manifest.json",
    ):
        assert (out_a / filename).read_bytes() == (out_b / filename).read_bytes()


def test_nonfrozen_batch_size_is_rejected(tmp_path) -> None:
    source, manifest = source_documents()
    source_path = tmp_path / "blind.json"
    manifest_path = tmp_path / "public.json"
    write_json(source_path, source)
    write_json(manifest_path, manifest)
    with pytest.raises(H003ReviewBatchError, match="batch size is frozen"):
        shard_blind_packets(
            blind_packet_path=source_path,
            public_manifest_path=manifest_path,
            output_dir=tmp_path / "out",
            expected_packet_count=41,
            batch_size=10,
        )
