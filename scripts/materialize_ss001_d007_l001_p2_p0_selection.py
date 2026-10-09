from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss001_d007_page_pilot import select_page_pilot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    selection = select_page_pilot(queue)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(selection, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "selection_id": selection["selection_id"],
        "selection_sha256": selection["selection_sha256"],
        "selected_request_count": selection["selected_request_count"],
        "issuer_counts": selection["issuer_counts"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
