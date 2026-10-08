from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss001_share_document_binding import build_q002_document_binding


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Q002 input must be a JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bind the frozen SS001 D007 first-50 review packets to D002/D003 evidence"
    )
    parser.add_argument("--q001-queue", type=Path, required=True)
    parser.add_argument("--q001-pilot", type=Path, required=True)
    parser.add_argument("--d002-manifest", type=Path, required=True)
    parser.add_argument("--d003-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = build_q002_document_binding(
        queue=_load(args.q001_queue),
        pilot=_load(args.q001_pilot),
        d002=_load(args.d002_manifest),
        d003=_load(args.d003_manifest),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ss001-d007-q002-bound-pilot.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in result.items() if key != "packets"}
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
