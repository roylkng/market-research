from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.hg006_full_priority import (
    SHARD_COUNT,
    build_full_text_corpus,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-corpus", type=Path, required=True)
    parser.add_argument("--shards-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    files = sorted(args.shards_root.rglob("shard-text.json"))
    if len(files) != SHARD_COUNT:
        raise ValueError(
            f"HG006 P2 requires {SHARD_COUNT} shard files, found {len(files)}"
        )
    seen = set()
    rows = []
    for path in files:
        payload = _load(path)
        shard_id = payload.get("shard_id")
        if (
            not isinstance(shard_id, int)
            or isinstance(shard_id, bool)
            or not 0 <= shard_id < SHARD_COUNT
            or shard_id in seen
        ):
            raise ValueError("HG006 P2 invalid or duplicate shard")
        seen.add(shard_id)
        shard_rows = payload.get("rows")
        if not isinstance(shard_rows, list):
            raise TypeError("HG006 P2 shard rows must be list")
        rows.extend(shard_rows)

    corpus = build_full_text_corpus(
        source_corpus=_load(args.source_corpus),
        extraction_rows=rows,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "hg006-d001b-p2-corpus.json").write_text(
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
    summary = {
        key: value
        for key, value in corpus.items()
        if key not in {"documents", "chronologies"}
    }
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
