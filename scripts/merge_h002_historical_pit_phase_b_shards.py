from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.h002_historical_pit_outcomes import phase_b_manifest_pit

EXPERIMENT_ID = "H002-HR003"


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _record_key(record: dict) -> tuple[str, str]:
    eligibility = record.get("point_in_time_eligibility")
    if not isinstance(eligibility, dict):
        raise ValueError("HR003 Phase-B record lacks point-in-time eligibility")
    quarter = str(record.get("quarter_id") or "")
    freeze_symbol = str(eligibility.get("symbol_at_freeze") or "").strip().upper()
    if not quarter or not freeze_symbol:
        raise ValueError("HR003 Phase-B record has incomplete observation identity")
    return quarter, freeze_symbol


def run(args: argparse.Namespace) -> dict:
    root = Path(args.input_dir)
    files = sorted(root.rglob("shard-*.json"))
    if len(files) != args.shard_count:
        raise ValueError(f"expected {args.shard_count} shard files, found {len(files)}")

    all_records: list[dict] = []
    seen_shards: set[int] = set()
    seen_records: set[tuple[str, str]] = set()
    shard_evidence: list[dict] = []
    resolver_versions: set[str] = set()
    for path in files:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise TypeError(f"HR003 shard root must be an object: {path}")
        if document.get("phase") != "B_OUTCOME_RECONSTRUCTION_SHARD":
            raise ValueError(f"unexpected shard phase in {path}")
        if document.get("replay_rule_id") != EXPERIMENT_ID:
            raise ValueError(f"unexpected replay rule in {path}")
        if document.get("phase_a_manifest_sha256") != args.expected_phase_a_sha256:
            raise ValueError(f"shard {path} is not bound to the frozen HR003 Phase-A SHA")
        if int(document.get("shard_count", -1)) != args.shard_count:
            raise ValueError(f"shard-count mismatch in {path}")
        shard_index = int(document.get("shard_index", -1))
        if shard_index in seen_shards or not 0 <= shard_index < args.shard_count:
            raise ValueError(f"invalid/duplicate shard index {shard_index}")
        seen_shards.add(shard_index)
        resolver_versions.add(str(document.get("resolver_version") or ""))
        records = document.get("records")
        if not isinstance(records, list):
            raise TypeError(f"shard {path} has no record list")
        if len(records) != int(document.get("eligible_record_count", -1)):
            raise ValueError(f"shard {path} record count changed")
        for record in records:
            key = _record_key(record)
            if key in seen_records:
                raise ValueError(f"duplicate HR003 Phase-B record across shards: {key}")
            seen_records.add(key)
            all_records.append(record)
        shard_evidence.append(
            {
                "shard_index": shard_index,
                "source_path": str(path),
                "record_count": len(records),
                "evidence": document.get("evidence"),
            }
        )

    if len(resolver_versions) != 1 or not next(iter(resolver_versions), ""):
        raise ValueError(f"HR003 shard resolver identity differs: {sorted(resolver_versions)}")
    if len(all_records) != args.expected_record_count:
        raise ValueError(
            f"expected {args.expected_record_count} HR003 Phase-B records, found {len(all_records)}"
        )
    all_records.sort(key=lambda item: _record_key(item))
    manifest = phase_b_manifest_pit(
        phase_a_manifest_sha256=args.expected_phase_a_sha256,
        generated_at_utc=_iso(datetime.now(UTC)),
        records=all_records,
        evidence={
            "acquisition_mode": f"{args.shard_count}-way-identity-cluster-sharded",
            "shard_count": args.shard_count,
            "resolver_version": next(iter(resolver_versions)),
            "bootstrap_implementation": "exact-vectorized-company-cluster-v1",
            "company_cluster_identity": "registered_identity_preserving_ticker_alias_group",
            "shards": sorted(shard_evidence, key=lambda item: item["shard_index"]),
        },
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "manifest_sha256": manifest["manifest_sha256"],
                "completed_count": manifest["summary"]["completed_count"],
                "status_counts": manifest["summary"]["status_counts"],
            },
            sort_keys=True,
        )
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge survivorship-clean H002-HR003 outcome shards")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--expected-phase-a-sha256", required=True)
    parser.add_argument("--shard-count", type=int, default=8)
    parser.add_argument("--expected-record-count", type=int, required=True)
    parser.add_argument(
        "--output",
        default="research/historical/h002/H002-HR003/phase-b/point-in-time-nifty200-outcomes.json",
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
