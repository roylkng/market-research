from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg004_terms import select_hg004_detailed_terms


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hg003-l002", type=Path, required=True)
    parser.add_argument("--p2-census", type=Path, required=True)
    parser.add_argument("--d3-corpus", type=Path, required=True)
    parser.add_argument("--documents-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    records = [_load(path) for path in sorted(args.documents_dir.glob("*.json"))]
    selection = select_hg004_detailed_terms(
        _load(args.hg003_l002),
        _load(args.p2_census),
        _load(args.d3_corpus),
        records,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "hg004-d001-selection.json").write_text(
        json.dumps(
            selection,
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
        for key, value in selection.items()
        if key not in {"event_links", "prompts"}
    }
    summary["prompt_rows"] = [
        {
            "document_id": row["document_id"],
            "symbols": row["symbols"],
            "event_ids": row["event_ids"],
            "semantic_clusters": row["semantic_clusters"],
            "segment_count": row["segment_count"],
            "prompt_sha256": row["prompt_sha256"],
        }
        for row in selection["prompts"]
    ]
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
