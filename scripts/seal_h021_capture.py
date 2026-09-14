from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h021_capture import (
    build_capture_artifacts,
    canonical_json_bytes,
    verify_artifact_bytes,
)


def _load_object(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write_immutable(path: Path, payload: bytes) -> str:
    if path.exists():
        existing = path.read_bytes()
        if existing != payload:
            raise FileExistsError(
                f"immutable H021 capture path already exists with different bytes: {path}"
            )
        return "UNCHANGED"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return "CREATED"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--batches", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    snapshot = _load_object(args.draft)
    universe = _load_object(args.universe)
    batches = _load_object(args.batches)
    artifacts = build_capture_artifacts(snapshot, universe, batches)

    capture_id = artifacts.logical_capture_id
    payload_path = args.out_dir / f"{capture_id}.json.gz"
    manifest_path = args.out_dir / f"{capture_id}.manifest.json"
    report_path = args.out_dir / f"{capture_id}.md"

    manifest_bytes = canonical_json_bytes(artifacts.manifest)
    report_bytes = artifacts.report_markdown.encode("utf-8")
    states = {
        "payload": _write_immutable(payload_path, artifacts.payload_gzip),
        "manifest": _write_immutable(manifest_path, manifest_bytes),
        "report": _write_immutable(report_path, report_bytes),
    }

    sealed_snapshot = verify_artifact_bytes(payload_path.read_bytes(), artifacts.manifest)
    if sealed_snapshot != snapshot:
        raise RuntimeError("sealed H021 payload does not round-trip to the validated draft")

    print(
        f"capture={capture_id} observations={len(snapshot['observations'])} "
        f"payload_sha256={artifacts.manifest['payload_uncompressed_sha256']} states={states}"
    )


if __name__ == "__main__":
    main()
