#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from marketlab.h003_candidates import (
    H003CandidateStore,
    build_report,
    deterministic_sample,
    extract_source,
    failed_fetch_record,
    load_and_validate_extraction_rule,
    load_frozen_transcript_sources,
    write_report,
)
from marketlab.nse import NSEAcquisitionError, NSEClient


def _fetch_with_retries(
    client: NSEClient,
    url: str,
    *,
    attempts: int,
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return client.archive_bytes(url)
        except NSEAcquisitionError as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(min(8.0, 0.75 * (2 ** (attempt - 1))))
    assert last_error is not None
    raise NSEAcquisitionError(str(last_error)) from last_error


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic H003 claim candidates from the frozen transcript corpus."
    )
    parser.add_argument("--source-bundle", type=Path, required=True)
    parser.add_argument("--rule", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--sample-count", type=int)
    parser.add_argument("--fetch-attempts", type=int, default=3)
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    args = parser.parse_args()

    if args.fetch_attempts < 1:
        parser.error("--fetch-attempts must be at least 1")
    if args.sleep_seconds < 0:
        parser.error("--sleep-seconds cannot be negative")

    rule = load_and_validate_extraction_rule(args.rule)
    all_sources = load_frozen_transcript_sources(args.source_bundle)
    sources = (
        deterministic_sample(all_sources, args.sample_count)
        if args.sample_count is not None
        else all_sources
    )
    client = NSEClient(timeout=30.0, attempts=3)
    store = H003CandidateStore(args.store)
    records = []

    for index, source in enumerate(sources, start=1):
        try:
            raw = _fetch_with_retries(
                client,
                source.attachment_url,
                attempts=args.fetch_attempts,
            )
        except NSEAcquisitionError as exc:
            record = failed_fetch_record(source, reason=str(exc))
        else:
            record = extract_source(source, raw, store=store)
        records.append(record)
        print(
            f"[{index}/{len(sources)}] {source.symbol} {source.source_id[:12]} "
            f"status={record.status} candidates={record.candidate_count}"
        )
        if args.sleep_seconds:
            time.sleep(args.sleep_seconds)

    generated_at = datetime.now(UTC)
    report = build_report(records, generated_at=generated_at)
    write_report(args.report_out, report)
    status_counts = dict(sorted(Counter(record.status for record in records).items()))
    candidate_symbols = sorted(
        {record.symbol for record in records if record.candidate_count > 0}
    )
    summary = {
        "schema_version": 1,
        "rule_id": rule["id"],
        "rule_sha256": rule["sha256"],
        "source_bundle_sha256": report.source_bundle_sha256,
        "generated_at_utc": report.generated_at_utc,
        "sampled": args.sample_count is not None,
        "requested_sample_count": args.sample_count,
        "processed_source_count": report.processed_source_count,
        "processed_company_count": report.processed_company_count,
        "source_status_counts": status_counts,
        "candidate_count": report.candidate_count,
        "companies_with_candidates": report.companies_with_candidates,
        "candidate_symbols": candidate_symbols,
        "complete": report.complete,
        "freeze_blockers": list(report.freeze_blockers),
        "report_sha256": report.report_sha256,
    }
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if all(record.status == "TEXT_READY" for record in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
