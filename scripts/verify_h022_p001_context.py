from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h022_p001_acquisition import (
    discovery_complete,
    validate_discovery_manifest,
    validate_operational_context,
)
from marketlab.h022_prospective import source_disposition, validate_e002_record


def _load_object(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _load_list(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        raise TypeError(f"expected JSON object list: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify sealed H022-P001 context artifacts")
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--context-dir", type=Path, required=True)
    args = parser.parse_args()

    universe = _load_object(args.universe)
    manifest = _load_object(args.context_dir / "discovery-manifest.json")
    gate = _load_object(args.context_dir / "context-gate.json")
    prior_index = _load_object(args.context_dir / "static-prior-index.json")
    operational = _load_object(args.context_dir / "operational-context.json")
    catchup_records = _load_list(args.context_dir / "catchup-records.json")
    summary = _load_object(args.context_dir / "summary.json")

    validate_discovery_manifest(manifest, universe)
    if not discovery_complete(manifest):
        raise ValueError("sealed P001 discovery manifest is not complete")
    validate_operational_context(
        operational_context=operational,
        core_gate=gate,
        prior_index=prior_index,
        discovery_manifest=manifest,
        universe_snapshot=universe,
    )

    expected_source_ids = set(manifest["catchup_source_ids"])
    actual_source_ids: set[str] = set()
    for record in catchup_records:
        validate_e002_record(record)
        source_id = str(record["source_id"])
        if source_id in actual_source_ids:
            raise ValueError(f"duplicate sealed catch-up source id: {source_id}")
        actual_source_ids.add(source_id)
        if source_disposition(record) != "CONTEXT_ONLY_PRE_START":
            raise ValueError(f"{source_id}: sealed catch-up record disposition changed")
    if actual_source_ids != expected_source_ids:
        raise ValueError(
            "sealed catch-up extraction set differs from discovery manifest: "
            f"missing={sorted(expected_source_ids - actual_source_ids)} "
            f"extra={sorted(actual_source_ids - expected_source_ids)}"
        )
    if prior_index.get("catchup_source_ids") != sorted(expected_source_ids):
        raise ValueError("static prior index catch-up source set differs from discovery")
    if summary.get("status") != "COMPLETE":
        raise ValueError("sealed P001 context summary is not COMPLETE")
    expected_hashes = {
        "discovery_manifest_sha256": manifest["manifest_sha256"],
        "context_gate_sha256": gate["context_gate_sha256"],
        "prior_index_sha256": prior_index["prior_index_sha256"],
        "operational_context_sha256": operational["operational_context_sha256"],
    }
    for field, expected in expected_hashes.items():
        if summary.get(field) != expected:
            raise ValueError(f"sealed P001 summary {field} mismatch")
    if summary.get("catchup_source_count") != len(expected_source_ids):
        raise ValueError("sealed P001 summary catch-up count mismatch")
    if summary.get("outcome_data_attached") is not False:
        raise ValueError("sealed P001 context summary contains outcome attachment")
    if summary.get("live_capital_allowed") is not False:
        raise ValueError("sealed P001 context summary enabled live capital")

    print(
        "H022-P001 context verified: "
        f"members={manifest['member_count']} catchup_sources={len(expected_source_ids)} "
        f"operational_context_sha256={operational['operational_context_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
