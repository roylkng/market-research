from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h003_outcome_review import compile_judgment_batch, decision_status_counts


def load_json(path: Path) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read JSON {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-batch", type=Path, required=True)
    parser.add_argument("--judgments", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    compiled = compile_judgment_batch(
        load_json(args.source_batch),
        load_json(args.judgments),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(compiled, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "decision_count": compiled["decision_count"],
                "decision_batch_sha256": compiled["decision_batch_sha256"],
                "status_counts": decision_status_counts(compiled),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
