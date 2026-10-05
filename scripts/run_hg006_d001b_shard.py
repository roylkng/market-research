from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from marketlab.hg006_text import document_requests, extraction_index_row
from marketlab.ss002_text import extract_document_text, seal_extraction_row


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def _raw_path(root: Path, document_id: str) -> Path | None:
    matches = list(root.rglob(f"{document_id}.bin"))
    if len(matches) > 1:
        raise RuntimeError(f"duplicate HG006 D001B raw document: {document_id}")
    return matches[0] if matches else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d001a-corpus", type=Path, required=True)
    parser.add_argument("--shard-id", type=int, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    corpus = _load(args.d001a_corpus)
    requests = [
        row
        for row in document_requests(corpus)
        if row["owner_shard"] == args.shard_id
    ]

    documents_dir = args.output / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    index_rows = []

    for index, request in enumerate(requests, start=1):
        document_id = str(request["document_id"])
        path = _raw_path(args.raw_root, document_id)
        if path is None:
            extraction = seal_extraction_row(
                {
                    "document_id": document_id,
                    "source_url": request["source_urls"][0],
                    "d002_family": request["d002_family"],
                    "extraction_state": "HASH_REPRODUCTION_FAILED",
                    "details": {"error": "owner-shard raw document missing"},
                    "segments": [],
                    "hash_reproduced": False,
                }
            )
        else:
            raw = path.read_bytes()
            observed = hashlib.sha256(raw).hexdigest()
            if observed != document_id:
                extraction = seal_extraction_row(
                    {
                        "document_id": document_id,
                        "source_url": request["source_urls"][0],
                        "d002_family": request["d002_family"],
                        "extraction_state": "HASH_REPRODUCTION_FAILED",
                        "details": {
                            "error": "owner-shard raw SHA differs from document_id",
                            "observed_sha256": observed,
                        },
                        "segments": [],
                        "hash_reproduced": False,
                    }
                )
            else:
                extraction = extract_document_text(
                    document_id=document_id,
                    raw=raw,
                    d002_family=str(request["d002_family"]),
                    source_url=request["source_urls"][0],
                )
                extraction["hash_reproduced"] = True

        text_path = documents_dir / f"{document_id}.json"
        text_path.write_text(
            json.dumps(
                extraction,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        index_rows.append(
            extraction_index_row(
                extraction,
                request=request,
                text_artifact_path=str(
                    Path("documents") / f"{document_id}.json"
                ),
            )
        )

        if index == 1 or index % 50 == 0 or index == len(requests):
            print(
                f"[hg006-d001b shard={args.shard_id}] "
                f"{index:04d}/{len(requests)} "
                f"state={extraction['extraction_state']} "
                f"segments={len(extraction['segments'])}",
                flush=True,
            )

    payload = {
        "schema_version": 1,
        "shard_id": args.shard_id,
        "document_count": len(index_rows),
        "text_ready_count": sum(
            row["extraction_state"] == "READY" for row in index_rows
        ),
        "index_rows": index_rows,
    }
    (args.output / "shard-text-index.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
