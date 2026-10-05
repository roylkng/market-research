from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from marketlab.alpha import digest
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.hg006_evidence import seal_shard_manifest, shard_requests
from marketlab.ss002_attachments import detect_document_family
from marketlab.ss002_text import extract_document_text


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def _segment_content_sha(row: dict) -> str:
    segments = row.get("segments")
    if not isinstance(segments, list):
        raise TypeError("HG006 S001 extraction segments must be a list")
    return digest(
        [
            {
                "segment_id": segment.get("segment_id"),
                "kind": segment.get("kind"),
                "locator": segment.get("locator"),
                "text_sha256": segment.get("text_sha256"),
                "utf8_byte_count": segment.get("utf8_byte_count"),
                "character_count": segment.get("character_count"),
            }
            for segment in segments
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d001-census", type=Path, required=True)
    parser.add_argument("--shard-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.01)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    census = _load(args.d001_census)
    requests = shard_requests(census, args.shard_id)
    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)

    documents_dir = args.output / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    full_rows = []
    manifest_rows = []

    for index, request in enumerate(requests, start=1):
        url = str(request["source_url"])
        url_sha = hashlib.sha256(url.encode("utf-8")).hexdigest()
        try:
            raw = client.archive_bytes(url)
            raw_sha = hashlib.sha256(raw).hexdigest()
            family = detect_document_family(raw, url)
            extraction = extract_document_text(
                document_id=raw_sha,
                raw=raw,
                d002_family=family,
                source_url=url,
            )
            row = {
                **extraction,
                "source_url": url,
                "fetch_state": "READY",
                "raw_sha256": raw_sha,
                "raw_byte_count": len(raw),
                "document_family": family,
                "event_ids": request["event_ids"],
                "chronology_ids": request["chronology_ids"],
                "symbols": request["symbols"],
                "families": request["families"],
                "segment_count": len(extraction["segments"]),
                "segment_content_sha256": _segment_content_sha(extraction),
                "fetch_error": None,
                "text_artifact_path": f"documents/{url_sha}.json",
            }
        except NSEAcquisitionError as exc:
            row = {
                "source_url": url,
                "fetch_state": "FETCH_FAILED",
                "raw_sha256": None,
                "raw_byte_count": None,
                "document_id": None,
                "document_family": None,
                "extraction_state": None,
                "segment_manifest_sha256": None,
                "segment_content_sha256": None,
                "segment_count": 0,
                "segments": [],
                "event_ids": request["event_ids"],
                "chronology_ids": request["chronology_ids"],
                "symbols": request["symbols"],
                "families": request["families"],
                "fetch_error": f"{type(exc).__name__}: {exc}",
                "text_artifact_path": f"documents/{url_sha}.json",
            }

        path = documents_dir / f"{url_sha}.json"
        path.write_text(
            json.dumps(row, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            + "\n",
            encoding="utf-8",
        )
        full_rows.append(row)
        manifest_rows.append(
            {
                key: value
                for key, value in row.items()
                if key != "segments"
            }
        )

        if index == 1 or index % 100 == 0 or index == len(requests):
            print(
                f"[{args.shard_id}] {index:04d}/{len(requests)} "
                f"fetch={row['fetch_state']} extract={row.get('extraction_state')}",
                flush=True,
            )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    manifest = seal_shard_manifest(
        census=census,
        shard_id=args.shard_id,
        evidence_rows=manifest_rows,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "shard-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "shard_id": args.shard_id,
                "expected_url_count": manifest["expected_url_count"],
                "ready_url_count": manifest["ready_url_count"],
                "text_ready_url_count": manifest["text_ready_url_count"],
                "shard_sha256": manifest["shard_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
