from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss001_share_action_review import build_share_action_review


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"D006 input must be JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d005-panel", type=Path, required=True)
    parser.add_argument("--d001-census", type=Path, required=True)
    parser.add_argument("--p2-census", type=Path, required=True)
    parser.add_argument("--d001-actions-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    d005 = _load(args.d005_panel)
    d001 = _load(args.d001_census)
    p2 = _load(args.p2_census)
    raw_chunks = {}
    for chunk in d001["source_metadata"]["corporate_action_window"]["chunks"]:
        sha = str(chunk["raw_sha256"])
        path = args.d001_actions_root / f"{sha}.bin"
        raw_chunks[sha] = path.read_bytes()

    output = build_share_action_review(
        d005_panel=d005,
        d001_census=d001,
        p2_census=p2,
        raw_action_chunks=raw_chunks,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ss001-d006-review.json").write_text(
        json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in output.items() if key != "rows"}
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
