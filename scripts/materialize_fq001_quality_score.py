from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.fundamental_quality_score import build_quality_score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    panel = json.loads(args.panel.read_text(encoding="utf-8"))
    if not isinstance(panel, dict):
        raise TypeError("FQ001 S001 source panel must be a JSON object")

    output = build_quality_score(panel)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    print(
        f"score={output['score_id']} "
        f"scored={output['scored_count']} "
        f"prerequisite_failed={output['quality_prerequisite_failed_count']} "
        f"source_unavailable={output['source_unavailable_count']} "
        f"sha={output['score_sha256']}"
    )


if __name__ == "__main__":
    main()
