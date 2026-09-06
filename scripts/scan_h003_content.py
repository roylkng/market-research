from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.h003_content import (
    TranscriptContentStore,
    build_content_bundle,
    load_frozen_sources,
    write_content_bundle,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify all frozen H003 transcript PDF content")
    parser.add_argument("--source-bundle", required=True)
    parser.add_argument("--store", default=".marketlab")
    parser.add_argument("--out", required=True)
    parser.add_argument("--pause-seconds", type=float, default=0.05)
    parser.add_argument("--attempts", type=int, default=3)
    return parser.parse_args()


def fetch_pdf(
    session: requests.Session,
    url: str,
    *,
    attempts: int,
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=35)
            response.raise_for_status()
            if not response.content:
                raise requests.RequestException("empty response body")
            return response.content
        except requests.RequestException as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(0.5 * attempt)
    raise requests.RequestException(f"transcript fetch failed after {attempts} attempts: {last_error}")


def main() -> int:
    args = parse_args()
    if args.attempts < 1:
        raise SystemExit("--attempts must be >= 1")
    sources = load_frozen_sources(args.source_bundle)
    store = TranscriptContentStore(args.store)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "Chrome/151.0 Safari/537.36"
            ),
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        }
    )

    records = []
    total = len(sources)
    for index, source in enumerate(sources, start=1):
        fetched_at = datetime.now(UTC)
        try:
            raw = fetch_pdf(session, source.attachment_url, attempts=args.attempts)
        except requests.RequestException as exc:
            record = store.record_failure(
                source,
                fetched_at=fetched_at,
                status="FETCH_FAILED",
                error=str(exc),
            )
        else:
            record = store.record_success(source, raw, fetched_at=fetched_at)
        records.append(record)
        print(
            f"[{index:03d}/{total:03d}] {source.symbol} {source.seq_id}: "
            f"{record.status} pages={record.page_count} chars={record.extracted_char_count}"
            + (f" error={record.error}" if record.error else "")
        )
        if args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

    bundle = build_content_bundle(records, generated_at=datetime.now(UTC))
    write_content_bundle(args.out, bundle)
    summary = {
        "source_count": bundle.source_count,
        "status_counts": bundle.status_counts,
        "company_count_with_content_ready": bundle.company_count_with_content_ready,
        "company_count_with_3plus_content_ready": bundle.company_count_with_3plus_content_ready,
        "company_count_with_6plus_content_ready": bundle.company_count_with_6plus_content_ready,
        "bundle_sha256": bundle.bundle_sha256,
        "status_counter_check": dict(sorted(Counter(record.status for record in records).items())),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
