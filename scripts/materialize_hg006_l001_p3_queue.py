from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg006_p3_inference import SHARD_COUNT, build_p3_extension_queue


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--s003-pack", type=Path, required=True)
    parser.add_argument("--prior-queue", type=Path, required=True)
    parser.add_argument("--prior-ingestion", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    queue = build_p3_extension_queue(
        full_pack=_load(args.s003_pack),
        prior_queue=_load(args.prior_queue),
        prior_ingestion=_load(args.prior_ingestion),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "hg006-l001-p3-queue.json").write_text(
        json.dumps(queue, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )

    fresh = [
        row
        for row in queue["requests"]
        if row["p3_execution_state"] == "FRESH_MODEL_REQUIRED"
    ]
    for shard_id in range(SHARD_COUNT):
        rows = [row for row in fresh if int(row["shard_id"]) == shard_id]
        path = args.output / f"fresh-shard-{shard_id:02d}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
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

    summary = {key: value for key, value in queue.items() if key != "requests"}
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
