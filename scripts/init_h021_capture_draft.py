from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h021_capture_draft import build_capture_draft


def _load_object(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write_new_or_identical(path: Path, content: str) -> str:
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"capture draft already exists with different content: {path}")
        return "UNCHANGED"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "CREATED"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-date", required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--batches", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--correction-reason")
    args = parser.parse_args()

    universe = _load_object(args.universe)
    batches = _load_object(args.batches)
    draft = build_capture_draft(
        args.capture_date,
        universe,
        batches,
        version=args.version,
        correction_reason=args.correction_reason,
    )
    content = json.dumps(draft, indent=2, sort_keys=True) + "\n"
    state = _write_new_or_identical(args.out, content)
    print(
        f"draft={draft['logical_capture_id']} observations={len(draft['observations'])} "
        f"state={state} out={args.out}"
    )


if __name__ == "__main__":
    main()
