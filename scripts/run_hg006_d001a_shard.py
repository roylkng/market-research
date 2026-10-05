from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from marketlab.hg006_documents import (
    SHARD_COUNT,
    attachment_evidence,
    build_attachment_requests,
    shard_for_url,
)
from marketlab.nse import NSEAcquisitionError, NSEClient


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def _retain(root: Path, raw: bytes, sha: str) -> str:
    path = root / "documents" / "sha256" / f"{sha}.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"HG006 D001A content-addressed collision: {path}")
    path.write_bytes(raw)
    return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--census", type=Path, required=True)
    parser.add_argument("--shard-id", type=int, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--pause-seconds", type=float, default=0.01)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 0 <= args.shard_id < SHARD_COUNT:
        raise ValueError(f"HG006 D001A shard must be 0..{SHARD_COUNT - 1}")

    census = _load(args.census)
    requests, _ = build_attachment_requests(census)
    requests = [
        request
        for request in requests
        if shard_for_url(request.source_url) == args.shard_id
    ]

    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    evidence = []
    for index, request in enumerate(requests, start=1):
        try:
            raw = client.archive_bytes(request.source_url)
            row = attachment_evidence(request, raw=raw, error=None)
            row["raw_path"] = _retain(
                args.raw_dir,
                raw,
                str(row["raw_sha256"]),
            )
        except NSEAcquisitionError as exc:
            row = attachment_evidence(
                request,
                raw=None,
                error=f"{type(exc).__name__}: {exc}",
            )
            row["raw_path"] = None
        evidence.append(row)
        if index == 1 or index % 50 == 0 or index == len(requests):
            print(
                f"[hg006-d001a shard={args.shard_id}] "
                f"{index:04d}/{len(requests)} "
                f"status={row['status']} family={row.get('document_family')}",
                flush=True,
            )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    args.output.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "shard_id": args.shard_id,
        "shard_count": SHARD_COUNT,
        "request_count": len(requests),
        "ready_count": sum(row["status"] == "READY" for row in evidence),
        "failed_count": sum(row["status"] != "READY" for row in evidence),
        "evidence": evidence,
    }
    (args.output / "shard-evidence.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
