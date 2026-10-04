from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.ss002_attachments import (
    attachment_evidence,
    build_attachment_corpus,
    build_attachment_requests,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def _retain(root: Path, raw: bytes, sha: str) -> str:
    path = root / "attachments" / "sha256" / f"{sha}.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"SS002 D002 content-addressed collision: {path}")
    path.write_bytes(raw)
    return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p2-census", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.01)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    census = _load(args.p2_census)
    requests, _ = build_attachment_requests(census)
    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    evidence = []

    for index, request in enumerate(requests, start=1):
        try:
            raw = client.archive_bytes(request.source_url)
            row = attachment_evidence(request, raw=raw, error=None)
            raw_path = _retain(args.raw_dir, raw, str(row["raw_sha256"]))
            row["raw_path"] = raw_path
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
                f"[attachments] {index:04d}/{len(requests)} "
                f"status={row['status']} family={row.get('document_family')}",
                flush=True,
            )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    corpus = build_attachment_corpus(
        census,
        evidence,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ss002-d002-corpus.json").write_text(
        json.dumps(corpus, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    summary = {
        key: value
        for key, value in corpus.items()
        if key not in {"documents", "event_states"}
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
