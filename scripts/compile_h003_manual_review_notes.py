from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h003_review_notes import compile_review_notes


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-batch", type=Path, required=True)
    parser.add_argument("--workset", type=Path, required=True)
    parser.add_argument("--notes", type=Path, required=True)
    parser.add_argument("--judgments-out", type=Path, required=True)
    parser.add_argument("--decisions-out", type=Path, required=True)
    args = parser.parse_args()

    judgments, decisions = compile_review_notes(
        load_json(args.source_batch),
        load_json(args.workset),
        load_json(args.notes),
    )
    write_json(args.judgments_out, judgments)
    write_json(args.decisions_out, decisions)
    print(
        json.dumps(
            {
                "source_batch_number": decisions["source_batch_number"],
                "decision_count": decisions["decision_count"],
                "decision_batch_sha256": decisions["decision_batch_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
