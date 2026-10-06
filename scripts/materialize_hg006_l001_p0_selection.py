from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg006_native_pilot import select_native_pilot


def _load(path: Path) -> dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON payload must be object: {path}")
    return payload


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--queue",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    selection=select_native_pilot(_load(args.queue))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(
        json.dumps(selection,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "selection_sha256":selection["selection_sha256"],
        "selected_request_count":selection["selected_request_count"],
        "selected_counts_by_family":selection["selected_counts_by_family"],
        "request_ids":[row["request_id"] for row in selection["rows"]],
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
