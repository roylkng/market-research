from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.hg006_documents import SHARD_COUNT, build_historical_document_corpus


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--census", type=Path, required=True)
    parser.add_argument("--shards-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    census = _load(args.census)
    shard_files = sorted(args.shards_root.rglob("shard-evidence.json"))
    if len(shard_files) != SHARD_COUNT:
        raise ValueError(
            f"HG006 D001A requires {SHARD_COUNT} shard evidence files, "
            f"found {len(shard_files)}"
        )

    seen_shards = set()
    evidence = []
    for path in shard_files:
        payload = _load(path)
        shard_id = payload.get("shard_id")
        if (
            not isinstance(shard_id, int)
            or isinstance(shard_id, bool)
            or not 0 <= shard_id < SHARD_COUNT
            or shard_id in seen_shards
        ):
            raise ValueError("HG006 D001A shard identity invalid or duplicated")
        seen_shards.add(shard_id)
        rows = payload.get("evidence")
        if not isinstance(rows, list):
            raise TypeError("HG006 D001A shard evidence must be a list")
        evidence.extend(rows)

    corpus = build_historical_document_corpus(
        census,
        evidence,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "hg006-d001a-corpus.json").write_text(
        json.dumps(corpus, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    summary = {
        key: value
        for key, value in corpus.items()
        if key not in {"documents", "event_states", "chronologies"}
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
