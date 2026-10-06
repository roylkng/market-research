from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg006_inference_queue import SHARD_COUNT, build_inference_queue


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--s002-pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    queue = build_inference_queue(_load(args.s002_pack))
    args.output.mkdir(parents=True, exist_ok=True)

    (args.output / "hg006-l001-p1-queue.json").write_text(
        json.dumps(queue, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )

    requests = queue["requests"]
    for shard_id in range(SHARD_COUNT):
        shard_rows = [
            row for row in requests if int(row["shard_id"]) == shard_id
        ]
        path = args.output / f"shard-{shard_id:02d}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for row in shard_rows:
                handle.write(
                    json.dumps(
                        row,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                        allow_nan=False,
                    )
                    + "\n"
                )

    summary = {
        key: value
        for key, value in queue.items()
        if key not in {"requests"}
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "queue_sha256": queue["queue_sha256"],
                "request_count": queue["request_count"],
                "request_counts_by_shard": queue["request_counts_by_shard"],
                "request_counts_by_family": queue["request_counts_by_family"],
                "text_unavailable_chronology_ids": queue[
                    "text_unavailable_chronology_ids"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
