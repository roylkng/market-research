from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.h022_expanded_candidates import (
    build_expanded_report,
    load_expanded_sources,
    validate_report,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate H022 expanded E002 shard records")
    parser.add_argument("--source-bundle", type=Path, required=True)
    parser.add_argument("--shards-root", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--expected-shards", type=int, default=16)
    args = parser.parse_args()

    record_files = sorted(args.shards_root.glob("**/records.json"))
    if len(record_files) != args.expected_shards:
        raise ValueError(
            f"expected {args.expected_shards} shard record files, found {len(record_files)}"
        )
    records: list[dict] = []
    for path in record_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise TypeError(f"shard records must be a list: {path}")
        for row in payload:
            if not isinstance(row, dict):
                raise TypeError(f"shard record must be an object: {path}")
            records.append(row)

    sources = load_expanded_sources(args.source_bundle)
    report = build_expanded_report(
        records,
        source_metadata=sources,
        generated_at=datetime.now(UTC),
    )
    validate_report(report)
    _write_json(args.report_out, report)
    summary = {
        "schema_version": 1,
        "report_sha256": report["report_sha256"],
        "source_bundle_sha256": report["source_bundle_sha256"],
        "candidate_rule_id": report["candidate_rule_id"],
        "candidate_rule_sha256": report["candidate_rule_sha256"],
        "processed_source_count": report["processed_source_count"],
        "processed_company_count": report["processed_company_count"],
        "source_status_counts": report["source_status_counts"],
        "candidate_count": report["candidate_count"],
        "signal_eligible_candidate_count": report["signal_eligible_candidate_count"],
        "context_only_candidate_count": report["context_only_candidate_count"],
        "companies_with_candidates": report["companies_with_candidates"],
        "signal_eligible_companies_with_candidates": report[
            "signal_eligible_companies_with_candidates"
        ],
        "complete": report["complete"],
        "freeze_blockers": report["freeze_blockers"],
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.summary_out, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
