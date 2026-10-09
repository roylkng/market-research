from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss001_d007_a001 import assess_a001_readiness


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Check frozen SS001-D007-A001 readiness")
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--l002", type=Path, required=True)
    parser.add_argument("--collection", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    output = assess_a001_readiness(
        _load(args.queue), _load(args.l002),
        _load(args.collection) if args.collection else None,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": output["status"],
        "pending_l002_page_count": output["pending_l002_page_count"],
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
