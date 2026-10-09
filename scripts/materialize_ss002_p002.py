from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss002_daily_research_inbox import (
    SOURCE_CAPTURE_SHAS,
    build_daily_research_inbox,
)


def _read(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize frozen SS002-P002 daily source research inbox"
    )
    parser.add_argument("--daily-capture-dir", type=Path, required=True)
    parser.add_argument("--hg001-router", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    captures = {
        day: _read(args.daily_capture_dir / f"{day}-v1.json")
        for day in SOURCE_CAPTURE_SHAS
    }
    result = build_daily_research_inbox(captures, _read(args.hg001_router))

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "ss002-p002-inbox.json").write_text(
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    summary = {
        key: value
        for key, value in result.items()
        if key not in {"events", "thread_index"}
    }
    (args.out / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
