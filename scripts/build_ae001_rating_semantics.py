from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.alpha_history import canonical_gzip_json
from marketlab.alpha_rating_semantics import (
    build_rating_semantic_record,
    validate_rating_source_list,
)
from marketlab.events import sha256_bytes
from marketlab.nse import NSEAcquisitionError, NSEClient


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AlphaContractError(f"T008 expected JSON object: {path}")
    return payload


def _checkpoint_path(root: Path, announcement_id: str) -> Path:
    return root / "checkpoints" / f"{announcement_id}.json"


def _raw_path(root: Path, raw_sha256: str) -> Path:
    return root / "raw" / "sha256" / f"{raw_sha256}.pdf"


def _write_atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    temporary = path.with_suffix(".tmp")
    with temporary.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _retain_raw(root: Path, raw: bytes) -> str:
    raw_sha = sha256_bytes(raw)
    path = _raw_path(root, raw_sha)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise AlphaContractError(
                f"T008 content-addressed PDF collision: {path}"
            )
    else:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    return raw_sha


def _validate_checkpoint(
    payload: dict,
    *,
    source: dict,
) -> None:
    unsigned = dict(payload)
    stored = str(unsigned.pop("record_sha256", ""))
    from marketlab.alpha import digest

    if stored != digest(unsigned):
        raise AlphaContractError("T008 checkpoint record hash mismatch")
    for field in (
        "announcement_id",
        "symbol",
        "seq_id",
        "exchange_published_at_utc",
        "description",
        "attachment_url",
    ):
        expected = (
            str(source[field]).upper()
            if field == "symbol"
            else str(source[field])
        )
        if str(payload.get(field) or "") != expected:
            raise AlphaContractError(
                f"T008 checkpoint/source mismatch: {field}"
            )


def _fetch(
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build resumable T008 credit-rating semantic records"
    )
    parser.add_argument("--source-list", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--fetch-attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--pause-seconds", type=float, default=0.02)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_list = _load_json(args.source_list)
    validate_rating_source_list(source_list)
    if args.shard_count < 1:
        raise AlphaContractError("T008 shard count must be positive")
    if not 0 <= args.shard_index < args.shard_count:
        raise AlphaContractError("T008 shard index is outside shard count")
    if args.fetch_attempts < 1:
        raise AlphaContractError("T008 fetch attempts must be positive")
    if args.pause_seconds < 0:
        raise AlphaContractError("T008 pause seconds cannot be negative")

    sources = source_list["records"][args.shard_index :: args.shard_count]
    client = NSEClient(
        timeout=args.timeout_seconds,
        attempts=1,
    )
    records = []
    resumed = 0

    for index, source in enumerate(sources, start=1):
        checkpoint = _checkpoint_path(
            args.store,
            str(source["announcement_id"]),
        )
        record = None
        if checkpoint.exists():
            candidate = _load_json(checkpoint)
            _validate_checkpoint(candidate, source=source)
            if candidate.get("status") != "FETCH_ERROR":
                record = candidate
                resumed += 1

        if record is None:
            try:
                raw = _fetch(
                    client,
                    str(source["attachment_url"]),
                    attempts=args.fetch_attempts,
                )
            except NSEAcquisitionError as exc:
                record = build_rating_semantic_record(
                    source,
                    raw_pdf=None,
                    fetch_error=str(exc),
                )
            else:
                raw_sha = _retain_raw(args.store, raw)
                record = build_rating_semantic_record(
                    source,
                    raw_pdf=raw,
                )
                if record.get("raw_sha256") != raw_sha:
                    raise AlphaContractError(
                        "T008 retained PDF hash differs from semantic record"
                    )
            _write_atomic_json(checkpoint, record)

        records.append(record)
        print(
            f"[{index}/{len(sources)}] "
            f"{source['symbol']} {str(source['announcement_id'])[:12]} "
            f"status={record['status']} resumed={str(checkpoint.exists()).lower()}",
            flush=True,
        )
        if args.pause_seconds and record.get("status") != "FETCH_ERROR":
            time.sleep(args.pause_seconds)

    status_counts = dict(
        sorted(Counter(str(record["status"]) for record in records).items())
    )
    shard = {
        "schema_version": 1,
        "artifact_id": "AE001-T008-RATING-SEMANTIC-SHARD-v1",
        "source_list_sha256": source_list["source_list_sha256"],
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "shard_count": args.shard_count,
        "shard_index": args.shard_index,
        "selected_source_count": len(sources),
        "resumed_source_count": resumed,
        "status_counts": status_counts,
        "records": records,
        "market_return_outcomes_attached": False,
        "live_capital_allowed": False,
    }
    from marketlab.alpha import digest

    shard["artifact_sha256"] = digest(shard)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_gzip_json(shard))
    print(
        json.dumps(
            {
                "artifact_sha256": shard["artifact_sha256"],
                "shard_count": args.shard_count,
                "shard_index": args.shard_index,
                "selected_source_count": len(sources),
                "resumed_source_count": resumed,
                "status_counts": status_counts,
                "unresolved_fetch_error_count": status_counts.get(
                    "FETCH_ERROR",
                    0,
                ),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 2 if status_counts.get("FETCH_ERROR", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
