from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.ss002_text import (
    build_text_corpus,
    document_requests,
    extract_document_text,
    seal_extraction_row,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d002-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.01)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    d002 = _load(args.d002_manifest)
    requests = document_requests(d002)
    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)

    documents_dir = args.output / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    extraction_rows = []

    for index, request in enumerate(requests, start=1):
        document_id = str(request["document_id"])
        attempt_rows = []
        matched_raw = None
        used_url = None

        for url in request["source_urls"]:
            try:
                raw = client.archive_bytes(url)
                observed_sha = hashlib.sha256(raw).hexdigest()
                if observed_sha != document_id:
                    attempt_rows.append(
                        {
                            "source_url": url,
                            "status": "HASH_MISMATCH",
                            "observed_sha256": observed_sha,
                            "byte_count": len(raw),
                        }
                    )
                    continue
                attempt_rows.append(
                    {
                        "source_url": url,
                        "status": "HASH_REPRODUCED",
                        "observed_sha256": observed_sha,
                        "byte_count": len(raw),
                    }
                )
                matched_raw = raw
                used_url = url
                break
            except NSEAcquisitionError as exc:
                attempt_rows.append(
                    {
                        "source_url": url,
                        "status": "FETCH_FAILED",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

        if matched_raw is None or used_url is None:
            row = seal_extraction_row(
                {
                    "document_id": document_id,
                    "source_url": None,
                    "d002_family": request["d002_family"],
                    "extraction_state": "HASH_REPRODUCTION_FAILED",
                    "details": {
                        "error": "no frozen official URL reproduced D002 document_id"
                    },
                    "segments": [],
                    "hash_reproduced": False,
                    "attempts": attempt_rows,
                }
            )
        else:
            row = extract_document_text(
                document_id=document_id,
                raw=matched_raw,
                d002_family=str(request["d002_family"]),
                source_url=used_url,
            )
            row["hash_reproduced"] = True
            row["attempts"] = attempt_rows

        text_path = documents_dir / f"{document_id}.json"
        row["text_artifact_path"] = str(
            Path("documents") / f"{document_id}.json"
        )
        text_path.write_text(
            json.dumps(
                row,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        extraction_rows.append(row)

        if index == 1 or index % 50 == 0 or index == len(requests):
            print(
                f"[text] {index:04d}/{len(requests)} "
                f"state={row['extraction_state']} "
                f"segments={len(row['segments'])}",
                flush=True,
            )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    corpus = build_text_corpus(
        d002_corpus=d002,
        extraction_rows=extraction_rows,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ss002-d003-text-corpus.json").write_text(
        json.dumps(
            corpus,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in corpus.items() if key != "documents"}
    (args.output / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
