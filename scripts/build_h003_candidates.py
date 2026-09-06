from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.h003_candidates import (
    EXTRACTION_RULE_ID,
    EXTRACTION_RULE_SHA256,
    ClaimCandidate,
    H003CandidateError,
    H003CandidateStore,
    SourceExtractionRecord,
    _record_digest,
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


def _checkpoint_path(store_root: Path, source_id: str) -> Path:
    return store_root / "records" / f"{source_id}.json"


def _candidate_from_dict(payload: dict[str, Any]) -> ClaimCandidate:
    document = dict(payload)
    for key in (
        "future_markers",
        "deadline_markers",
        "quantitative_tokens",
        "domain_markers",
    ):
        value = document.get(key)
        if not isinstance(value, list):
            raise H003CandidateError(f"checkpoint candidate {key} must be a list")
        document[key] = tuple(str(item) for item in value)
    try:
        return ClaimCandidate(**document)
    except TypeError as exc:
        raise H003CandidateError(f"invalid candidate checkpoint: {exc}") from exc


def _load_checkpoint(
    path: Path,
    *,
    source_id: str,
    symbol: str,
    attachment_url: str,
) -> SourceExtractionRecord | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise H003CandidateError(f"could not read source checkpoint {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise H003CandidateError(f"source checkpoint root must be an object: {path}")
    document = dict(payload)
    candidates_payload = document.pop("candidates", None)
    if not isinstance(candidates_payload, list):
        raise H003CandidateError(f"source checkpoint candidates must be a list: {path}")
    candidates = tuple(_candidate_from_dict(item) for item in candidates_payload)
    try:
        record = SourceExtractionRecord(**document, candidates=candidates)
    except TypeError as exc:
        raise H003CandidateError(f"invalid source checkpoint {path}: {exc}") from exc
    if (
        record.rule_id != EXTRACTION_RULE_ID
        or record.rule_sha256 != EXTRACTION_RULE_SHA256
        or record.source_id != source_id
        or record.symbol != symbol
        or record.attachment_url != attachment_url
    ):
        raise H003CandidateError(f"source checkpoint identity mismatch: {path}")
    if record.candidate_count != len(record.candidates):
        raise H003CandidateError(f"source checkpoint candidate count mismatch: {path}")
    if record.record_id != _record_digest(record):
        raise H003CandidateError(f"source checkpoint hash mismatch: {path}")
    for candidate in record.candidates:
        if (
            candidate.rule_id != EXTRACTION_RULE_ID
            or candidate.rule_sha256 != EXTRACTION_RULE_SHA256
            or candidate.source_id != source_id
            or candidate.symbol != symbol
        ):
            raise H003CandidateError(f"candidate checkpoint identity mismatch: {path}")
    return None if record.status == "FETCH_ERROR" else record


def _write_checkpoint(path: Path, record: SourceExtractionRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (json.dumps(record.to_dict(), indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_suffix(".tmp")
    with temporary.open("wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


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
    records: list[SourceExtractionRecord] = []
    resumed_count = 0

    for index, source in enumerate(sources, start=1):
        checkpoint = _checkpoint_path(args.store, source.source_id)
        record = _load_checkpoint(
            checkpoint,
            source_id=source.source_id,
            symbol=source.symbol,
            attachment_url=source.attachment_url,
        )
        resumed = record is not None
        if record is None:
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
            _write_checkpoint(checkpoint, record)
        else:
            resumed_count += 1
        records.append(record)
        print(
            f"[{index}/{len(sources)}] {source.symbol} {source.source_id[:12]} "
            f"status={record.status} candidates={record.candidate_count} "
            f"resumed={str(resumed).lower()}",
            flush=True,
        )
        if args.sleep_seconds and not resumed:
            time.sleep(args.sleep_seconds)

    generated_at = datetime.now(UTC)
    report = build_report(records, generated_at=generated_at)
    write_report(args.report_out, report)
    status_counts = dict(sorted(Counter(record.status for record in records).items()))
    candidate_symbols = sorted(
        {record.symbol for record in records if record.candidate_count > 0}
    )
    summary = {
        "schema_version": 2,
        "rule_id": rule["id"],
        "rule_sha256": rule["sha256"],
        "source_bundle_sha256": report.source_bundle_sha256,
        "generated_at_utc": report.generated_at_utc,
        "sampled": args.sample_count is not None,
        "requested_sample_count": args.sample_count,
        "processed_source_count": report.processed_source_count,
        "processed_company_count": report.processed_company_count,
        "resumed_source_count": resumed_count,
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
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0 if all(record.status == "TEXT_READY" for record in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
