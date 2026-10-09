from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.ss002_daily_documents import (
    build_daily_document_corpus,
    extract_official_attachment,
    prepare_document_requests,
)


def _load(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise TypeError("SS002 P003 source inbox must be a JSON object")
    return obj


def _retain_raw(directory: Path, raw: bytes, sha: str) -> str:
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError("SS002 P003 raw bytes differ from document ID")
    path = directory / "raw" / "sha256" / f"{sha}.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("SS002 P003 content-addressed collision")
    path.write_bytes(raw)
    return str(path.relative_to(directory))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p002-inbox", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.05)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = _load(args.p002_inbox)
    requests, _ = prepare_document_requests(source)
    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    documents: list[dict] = []
    extracted_cache: dict[str, dict] = {}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "documents").mkdir(parents=True, exist_ok=True)

    for index, request in enumerate(requests, start=1):
        fetched_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        raw = None
        failure = None
        try:
            raw = client.archive_bytes(str(request["source_url"]))
        except NSEAcquisitionError as exc:
            failure = f"{type(exc).__name__}: {exc}"

        raw_sha = hashlib.sha256(raw).hexdigest() if raw is not None else None
        evidence, extraction = extract_official_attachment(
            request,
            raw=raw,
            fetched_at_utc=fetched_at,
            error=failure,
            canonical_extraction=extracted_cache.get(raw_sha) if raw_sha else None,
        )

        if raw is not None and raw_sha is not None:
            evidence["raw_path"] = _retain_raw(args.out, raw, raw_sha)
        else:
            evidence["raw_path"] = None

        if extraction is not None:
            doc_id = str(extraction["document_id"])
            if doc_id not in extracted_cache:
                extracted_cache[doc_id] = extraction
                output_path = args.out / "documents" / f"{doc_id}.json"
                output_path.write_text(
                    json.dumps(
                        extraction,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                        allow_nan=False,
                    ) + "\n",
                    encoding="utf-8",
                )
            evidence["text_artifact_path"] = str(Path("documents") / f"{doc_id}.json")
        else:
            evidence["text_artifact_path"] = None

        documents.append(evidence)
        if index == 1 or index % 10 == 0 or index == len(requests):
            print(
                f"[p003] {index:03d}/{len(requests)} "
                f"{evidence['status']} {evidence['extraction_state']} "
                f"sha={str(evidence['document_id'] or '')[:12]}",
                flush=True,
            )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    corpus = build_daily_document_corpus(source, documents)
    (args.out / "ss002-p003-corpus.json").write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    summary = {
        key: value for key, value in corpus.items()
        if key not in {"documents", "event_states"}
    }
    (args.out / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
