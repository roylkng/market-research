from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg006_full_priority import (
    SHARD_COUNT,
    build_full_stage_evidence_pack,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d001-census", type=Path, required=True)
    parser.add_argument("--text-summary", type=Path, required=True)
    parser.add_argument("--shards-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    files = sorted(args.shards_root.rglob("shard-text.json"))
    if len(files) != SHARD_COUNT:
        raise ValueError(
            f"HG006 S003 requires {SHARD_COUNT} shard files, found {len(files)}"
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
            raise ValueError("HG006 S003 invalid or duplicate shard")
        seen.add(shard_id)
        shard_rows = payload.get("rows")
        if not isinstance(shard_rows, list):
            raise TypeError("HG006 S003 shard rows must be list")
        rows.extend(shard_rows)

    output = build_full_stage_evidence_pack(
        d001=_load(args.d001_census),
        text_summary=_load(args.text_summary),
        text_rows=rows,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            output,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "pack_sha256": output["pack_sha256"],
                "chronology_count": output["chronology_count"],
                "state_counts": output["state_counts"],
                "retained_document_count": output["retained_document_count"],
                "retained_segment_count": output["retained_segment_count"],
                "feasibility_pass": output["feasibility_pass"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
