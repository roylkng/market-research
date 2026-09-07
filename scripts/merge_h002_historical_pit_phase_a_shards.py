from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXPECTED_QUARTERS = (
    "FY25-Q4",
    "FY26-Q1",
    "FY26-Q2",
    "FY26-Q3",
    "FY26-Q4",
    "FY27-Q1",
)
EXPERIMENT_ID = "H002-HR003"


class PitMergeError(RuntimeError):
    pass


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.input_dir)
    files = sorted(root.rglob("*.json"))
    shards: dict[str, dict[str, Any]] = {}
    for path in files:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if document.get("experiment_id") != EXPERIMENT_ID:
            continue
        quarter_id = str(document.get("quarter_id") or "")
        if quarter_id in shards:
            raise PitMergeError(f"duplicate HR003 Phase-A shard for {quarter_id}")
        declared = str(document.get("manifest_sha256") or "")
        unsigned = dict(document)
        unsigned.pop("manifest_sha256", None)
        encoded = json.dumps(
            unsigned,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        actual = hashlib.sha256(encoded).hexdigest()
        if actual != declared:
            raise PitMergeError(
                f"shard {quarter_id} hash mismatch: declared={declared} actual={actual}"
            )
        if document.get("outcome_data_included") is not False:
            raise PitMergeError(f"shard {quarter_id} contains outcome data")
        if int(document.get("status_counts", {}).get("ERROR", 0)):
            raise PitMergeError(f"shard {quarter_id} contains ERROR observations")
        if int(document.get("observation_count", -1)) != int(
            document.get("member_count_requested", -2)
        ):
            raise PitMergeError(f"shard {quarter_id} observation/member count differs")
        shards[quarter_id] = document

    if set(shards) != set(EXPECTED_QUARTERS):
        raise PitMergeError(
            f"expected HR003 quarters {EXPECTED_QUARTERS}, found {sorted(shards)}"
        )

    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    membership_snapshots: list[dict[str, Any]] = []
    quarter_status_counts: dict[str, dict[str, int]] = {}
    total_requested = 0
    mechanics_ids = set()
    mechanics_hashes = set()
    source_signal_rules = set()
    compiler_revisions = set()
    for quarter_id in EXPECTED_QUARTERS:
        shard = shards[quarter_id]
        mechanics_ids.add(str(shard["mechanics_rule_id"]))
        mechanics_hashes.add(str(shard["mechanics_rule_sha256"]))
        source_signal_rules.add(str(shard["source_signal_rule_id"]))
        compiler_revisions.add(str(shard["compiler_revision"]))
        total_requested += int(shard["member_count_requested"])
        quarter_status_counts[quarter_id] = dict(shard["status_counts"])
        membership_snapshots.append(
            {
                "quarter_id": quarter_id,
                "membership_snapshot_path": shard["membership_snapshot_path"],
                "membership_snapshot_sha256": shard["membership_snapshot_sha256"],
                "member_count_requested": shard["member_count_requested"],
                "historical_freeze_at_utc": shard["historical_freeze_at_utc"],
                "shard_manifest_sha256": shard["manifest_sha256"],
            }
        )
        for record in shard["records"]:
            eligibility = record.get("point_in_time_eligibility")
            if not isinstance(eligibility, dict):
                raise PitMergeError(f"{quarter_id} record is missing point-in-time eligibility")
            key = (quarter_id, str(eligibility.get("symbol_at_freeze") or ""))
            if key in seen:
                raise PitMergeError(f"duplicate HR003 observation: {key}")
            seen.add(key)
            records.append(record)

    if len(mechanics_ids) != 1 or len(mechanics_hashes) != 1:
        raise PitMergeError("HR003 shards do not use one frozen historical mechanics rule")
    if len(source_signal_rules) != 1 or len(compiler_revisions) != 1:
        raise PitMergeError("HR003 shard signal/compiler identity differs")
    if len(records) != total_requested:
        raise PitMergeError(
            f"HR003 expected {total_requested} point-in-time observations, found {len(records)}"
        )

    status_counts = Counter(str(record.get("status")) for record in records)
    bucket_counts = Counter(
        str(record["signal"]["bucket"])
        for record in records
        if isinstance(record.get("signal"), dict)
    )
    body: dict[str, Any] = {
        "schema_version": 1,
        "phase": "A_SIGNAL_CAPTURE_ONLY",
        "experiment_id": EXPERIMENT_ID,
        "compiler_revision": next(iter(compiler_revisions)),
        "mechanics_rule_id": next(iter(mechanics_ids)),
        "mechanics_rule_sha256": next(iter(mechanics_hashes)),
        "source_signal_rule_id": next(iter(source_signal_rules)),
        "generated_at_utc": _iso(datetime.now(UTC)),
        "outcome_data_included": False,
        "live_capital_allowed": False,
        "cohort_bias_label": "POINT_IN_TIME_NIFTY200_MEMBERSHIP_NON_FINANCIAL",
        "membership_mode": "ALL_REGULAR_NON_FINANCIAL_NIFTY200_AT_EACH_HISTORICAL_FREEZE",
        "quarter_count": len(EXPECTED_QUARTERS),
        "member_observation_count_requested": total_requested,
        "observation_count": len(records),
        "status_counts": dict(sorted(status_counts.items())),
        "signal_bucket_counts": dict(sorted(bucket_counts.items())),
        "quarter_status_counts": quarter_status_counts,
        "membership_snapshots": membership_snapshots,
        "records": records,
    }
    encoded = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    document = {**body, "manifest_sha256": hashlib.sha256(encoded).hexdigest()}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "manifest_sha256": document["manifest_sha256"],
                "observation_count": document["observation_count"],
                "status_counts": document["status_counts"],
                "signal_bucket_counts": document["signal_bucket_counts"],
            },
            sort_keys=True,
        )
    )
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge six point-in-time H002-HR003 Phase-A shards")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument(
        "--output",
        default="research/historical/h002/H002-HR003/phase-a/point-in-time-nifty200-signals.json",
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
