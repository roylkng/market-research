from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from marketlab.h003_candidates import (
    H003CandidateStore,
    extract_source,
    failed_fetch_record,
)
from marketlab.h022_expanded_candidates import load_expanded_sources
from marketlab.nse import NSEAcquisitionError, NSEClient


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _fetch_with_retry(client: NSEClient, url: str, attempts: int) -> bytes:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return client.archive_bytes(url)
        except NSEAcquisitionError as exc:
            last = exc
            if attempt < attempts:
                time.sleep(0.5 * (2 ** (attempt - 1)))
    assert last is not None
    raise last


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract one deterministic H022 expanded E002 shard")
    parser.add_argument("--source-bundle", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--records-out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--fetch-attempts", type=int, default=4)
    args = parser.parse_args()

    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        raise ValueError("invalid shard index/count")
    if args.fetch_attempts < 1:
        raise ValueError("fetch-attempts must be positive")

    all_sources = load_expanded_sources(args.source_bundle)
    selected = all_sources[args.shard_index :: args.shard_count]
    store = H003CandidateStore(args.store)
    client = NSEClient(timeout=25.0, attempts=1)
    records = []
    for index, item in enumerate(selected, start=1):
        source = item.source
        try:
            raw = _fetch_with_retry(client, source.attachment_url, args.fetch_attempts)
            record = extract_source(source, raw, store=store)
        except NSEAcquisitionError as exc:
            record = failed_fetch_record(source, reason=str(exc))
        records.append(record.to_dict())
        print(
            f"shard={args.shard_index}/{args.shard_count} "
            f"[{index}/{len(selected)}] {source.symbol} {record.status} "
            f"candidates={record.candidate_count}"
        )

    status_counts: dict[str, int] = {}
    for record in records:
        status = str(record["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    _write_json(args.records_out, records)
    summary = {
        "schema_version": 1,
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "selected_source_count": len(selected),
        "processed_source_count": len(records),
        "source_status_counts": dict(sorted(status_counts.items())),
        "candidate_count": sum(int(record["candidate_count"]) for record in records),
        "fetch_error_count": status_counts.get("FETCH_ERROR", 0),
        "parse_error_count": status_counts.get("PARSE_ERROR", 0),
        "no_text_count": status_counts.get("NO_TEXT", 0),
    }
    _write_json(args.summary_out, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
