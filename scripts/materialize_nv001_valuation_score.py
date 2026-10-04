from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.normalized_valuation_score import build_normalized_valuation_score


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    score = build_normalized_valuation_score(_load_json(args.panel))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(score, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(
        f"score={score['score_id']} "
        f"scored={score['scored_count']} "
        f"top_quartile={score['top_valuation_quartile_count']}"
    )


if __name__ == "__main__":
    main()
