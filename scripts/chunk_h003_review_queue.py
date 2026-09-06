from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from marketlab.h003_review import (
    REVIEW_RULE_ID,
    REVIEW_RULE_SHA256,
    BlindReviewPayload,
    H003ReviewError,
)


def _canonical_hash(payload: Any) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _payload_from_dict(document: dict[str, Any]) -> BlindReviewPayload:
    payload = dict(document)
    for field in (
        "redacted_page_context",
        "future_markers",
        "deadline_markers",
        "quantitative_tokens",
        "domain_markers",
    ):
        value = payload.get(field)
        if not isinstance(value, list):
            raise H003ReviewError(f"blind payload {field} must be a list")
        payload[field] = tuple(str(item) for item in value)
    try:
        result = BlindReviewPayload(**payload)
    except TypeError as exc:
        raise H003ReviewError(f"invalid blind payload: {exc}") from exc
    unsigned = result.to_dict()
    declared = unsigned.pop("payload_sha256", None)
    if (
        result.schema_version != 1
        or result.review_rule_id != REVIEW_RULE_ID
        or result.review_rule_sha256 != REVIEW_RULE_SHA256
        or declared != _canonical_hash(unsigned)
    ):
        raise H003ReviewError(f"blind payload identity/hash mismatch: {result.candidate_id}")
    return result


def load_semantic_queue(path: Path) -> tuple[BlindReviewPayload, ...]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise H003ReviewError(f"could not read semantic review queue {path}: {exc}") from exc
    if not isinstance(document, list):
        raise H003ReviewError("semantic review queue root must be a list")
    payloads = tuple(_payload_from_dict(item) for item in document if isinstance(item, dict))
    if len(payloads) != len(document):
        raise H003ReviewError("semantic review queue contains a non-object item")
    candidate_ids = [payload.candidate_id for payload in payloads]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise H003ReviewError("semantic review queue contains duplicate candidate ids")
    return payloads


def build_chunks(
    payloads: tuple[BlindReviewPayload, ...],
    *,
    chunk_size: int,
) -> tuple[dict[str, Any], tuple[tuple[BlindReviewPayload, ...], ...]]:
    if chunk_size < 1:
        raise H003ReviewError("chunk_size must be positive")
    chunks = tuple(
        tuple(payloads[start : start + chunk_size])
        for start in range(0, len(payloads), chunk_size)
    )
    chunk_entries = []
    for index, chunk in enumerate(chunks):
        documents = [payload.to_dict() for payload in chunk]
        chunk_entries.append(
            {
                "chunk_index": index,
                "file": f"chunk-{index:04d}.json",
                "candidate_count": len(chunk),
                "first_candidate_id": None if not chunk else chunk[0].candidate_id,
                "last_candidate_id": None if not chunk else chunk[-1].candidate_id,
                "chunk_sha256": _canonical_hash(documents),
            }
        )
    unsigned = {
        "schema_version": 1,
        "review_rule_id": REVIEW_RULE_ID,
        "review_rule_sha256": REVIEW_RULE_SHA256,
        "chunk_size": chunk_size,
        "candidate_count": len(payloads),
        "chunk_count": len(chunks),
        "queue_sha256": _canonical_hash([payload.to_dict() for payload in payloads]),
        "chunks": chunk_entries,
    }
    return {**unsigned, "manifest_sha256": _canonical_hash(unsigned)}, chunks


def write_chunks(
    out_dir: Path,
    manifest: dict[str, Any],
    chunks: tuple[tuple[BlindReviewPayload, ...], ...],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    expected_files = set()
    for index, chunk in enumerate(chunks):
        filename = f"chunk-{index:04d}.json"
        expected_files.add(filename)
        (out_dir / filename).write_text(
            json.dumps([payload.to_dict() for payload in chunk], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    for existing in out_dir.glob("chunk-*.json"):
        if existing.name not in expected_files:
            existing.unlink()
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Split a blind H003 semantic review queue into deterministic chunks."
    )
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--chunk-size", type=int, default=40)
    args = parser.parse_args()
    payloads = load_semantic_queue(args.queue)
    manifest, chunks = build_chunks(payloads, chunk_size=args.chunk_size)
    write_chunks(args.out_dir, manifest, chunks)
    print(json.dumps(manifest, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
