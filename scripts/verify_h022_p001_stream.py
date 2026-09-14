from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h022_p001_acquisition import validate_operational_context
from marketlab.h022_p001_stream import (
    scan_complete,
    unresolved_source_records,
    validate_e002_ledger,
    validate_scan_manifest,
    validate_source_ledger,
    validate_stream_consistency,
)
from marketlab.h022_prospective import validate_signal_ledger


def _load_object(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify H022-P001 prospective stream state")
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--context-dir", type=Path, required=True)
    parser.add_argument("--source-ledger", type=Path, required=True)
    parser.add_argument("--e002-ledger", type=Path, required=True)
    parser.add_argument("--signal-ledger", type=Path, required=True)
    parser.add_argument("--scan-manifest", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    universe = _load_object(args.universe)
    discovery_manifest = _load_object(args.context_dir / "discovery-manifest.json")
    core_gate = _load_object(args.context_dir / "context-gate.json")
    prior_index = _load_object(args.context_dir / "static-prior-index.json")
    operational_context = _load_object(args.context_dir / "operational-context.json")
    validate_operational_context(
        operational_context=operational_context,
        core_gate=core_gate,
        prior_index=prior_index,
        discovery_manifest=discovery_manifest,
        universe_snapshot=universe,
    )

    source_ledger = _load_object(args.source_ledger)
    e002_ledger = _load_object(args.e002_ledger)
    signal_ledger = _load_object(args.signal_ledger)
    scan_manifest = _load_object(args.scan_manifest)
    summary = _load_object(args.summary)

    validate_source_ledger(source_ledger)
    validate_e002_ledger(e002_ledger)
    validate_signal_ledger(signal_ledger)
    validate_stream_consistency(
        source_ledger=source_ledger,
        e002_ledger=e002_ledger,
        signal_ledger=signal_ledger,
    )
    validate_scan_manifest(scan_manifest, universe)
    if not scan_complete(scan_manifest):
        raise ValueError("canonical P001 scan manifest is not complete")

    source_ids = {str(row["source"]["source_id"]) for row in source_ledger["records"]}
    scan_ids = set(scan_manifest["source_ids"])
    if not scan_ids.issubset(source_ids):
        raise ValueError(
            f"scan contains sources absent from ledger: {sorted(scan_ids - source_ids)}"
        )
    unresolved = unresolved_source_records(source_ledger, e002_ledger)
    unresolved_ids = [str(row["source"]["source_id"]) for row in unresolved]

    if summary.get("status") != "COMPLETE_SCAN":
        raise ValueError("P001 stream summary is not COMPLETE_SCAN")
    expected = {
        "scan_sha256": scan_manifest["scan_sha256"],
        "source_ledger_sha256": source_ledger["ledger_sha256"],
        "e002_ledger_sha256": e002_ledger["ledger_sha256"],
        "signal_ledger_sha256": signal_ledger["ledger_sha256"],
        "discovered_source_count": source_ledger["record_count"],
        "text_ready_source_count": e002_ledger["record_count"],
        "signal_record_count": signal_ledger["record_count"],
        "unresolved_source_count": len(unresolved_ids),
        "unresolved_source_ids": unresolved_ids,
    }
    for field, value in expected.items():
        if summary.get(field) != value:
            raise ValueError(f"P001 stream summary {field} mismatch")
    if summary.get("outcome_data_attached") is not False:
        raise ValueError("P001 stream summary contains outcome attachment")
    if summary.get("live_capital_allowed") is not False:
        raise ValueError("P001 stream summary enabled live capital")

    print(
        "H022-P001 stream verified: "
        f"scan={scan_manifest['scan_sha256']} sources={source_ledger['record_count']} "
        f"text_ready={e002_ledger['record_count']} signals={signal_ledger['record_count']} "
        f"unresolved={len(unresolved_ids)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
