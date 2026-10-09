from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss001_d007_a002 import (
    build_a002_review_packet,
    build_a002_selection,
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize frozen source-only SS001 D007 A002 audit sample"
    )
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=("selection", "packet"), default="selection")
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--receipts", type=Path)
    args = parser.parse_args()

    queue = _load(args.queue)
    if args.mode == "selection":
        output = build_a002_selection(queue)
    else:
        if args.selection is None or args.config is None or args.receipts is None:
            parser.error("packet mode requires --selection --config --receipts")
        receipts = json.loads(args.receipts.read_text(encoding="utf-8"))
        if not isinstance(receipts, list):
            raise TypeError("receipts must be a list of validated R001 records")
        output = build_a002_review_packet(
            queue,
            _load(args.selection),
            _load(args.config),
            receipts,
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "audit_id": output["audit_id"],
        "mode": args.mode,
        "selected_page_count": output["selected_page_count"],
        "independent_semantic_audit_complete": False,
        "share_action_clearance_proven": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
