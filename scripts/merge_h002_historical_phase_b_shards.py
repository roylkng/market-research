from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.h002_historical_outcomes_fast import phase_b_manifest_fast


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def run(args: argparse.Namespace) -> dict:
    root = Path(args.input_dir)
    files = sorted(root.rglob("shard-*.json"))
    if len(files) != args.shard_count:
        raise ValueError(f"expected {args.shard_count} shard files, found {len(files)}")

    all_records: list[dict] = []
    seen_shards: set[int] = set()
    seen_records: set[tuple[str, str]] = set()
    shard_evidence: list[dict] = []
    for path in files:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("phase") != "B_OUTCOME_RECONSTRUCTION_SHARD":
            raise ValueError(f"unexpected shard phase in {path}")
        if document.get("phase_a_manifest_sha256") != args.expected_phase_a_sha256:
            raise ValueError(f"shard {path} is not bound to the frozen Phase-A SHA")
        if int(document.get("shard_count", -1)) != args.shard_count:
            raise ValueError(f"shard-count mismatch in {path}")
        shard_index = int(document.get("shard_index", -1))
        if shard_index in seen_shards or not 0 <= shard_index < args.shard_count:
            raise ValueError(f"invalid/duplicate shard index {shard_index}")
        seen_shards.add(shard_index)
        records = document.get("records")
        if not isinstance(records, list):
            raise TypeError(f"shard {path} has no record list")
        if len(records) != int(document.get("eligible_record_count", -1)):
            raise ValueError(f"shard {path} record count changed")
        for record in records:
            key = (str(record.get("symbol")), str(record.get("quarter_id")))
            if key in seen_records:
                raise ValueError(f"duplicate Phase-B record across shards: {key}")
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

    if len(all_records) != args.expected_record_count:
        raise ValueError(
            f"expected {args.expected_record_count} Phase-B records, found {len(all_records)}"
        )
    all_records.sort(key=lambda item: (str(item.get("symbol")), str(item.get("quarter_id"))))
    manifest = phase_b_manifest_fast(
        phase_a_manifest_sha256=args.expected_phase_a_sha256,
        generated_at_utc=_iso(datetime.now(UTC)),
        records=all_records,
        evidence={
            "acquisition_mode": "4-way-company-sharded",
            "shard_count": args.shard_count,
            "bootstrap_implementation": "exact-vectorized-company-cluster-v1",
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
    parser = argparse.ArgumentParser(description="Merge frozen H002-HR001 Phase-B shards")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--expected-phase-a-sha256", required=True)
    parser.add_argument("--shard-count", type=int, default=4)
    parser.add_argument("--expected-record-count", type=int, default=178)
    parser.add_argument(
        "--output",
        default="research/historical/h002/H002-HR001/phase-b/fixed-u001-transport-outcomes.json",
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
