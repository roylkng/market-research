from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss002_l001_pilot import select_pilot


def _load(path: Path) -> dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--p2-census",type=Path,required=True)
    p.add_argument("--d3-corpus",type=Path,required=True)
    p.add_argument("--documents-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()

    records=[]
    for path in sorted(args.documents_dir.glob("*.json")):
        payload=_load(path)
        records.append(payload)

    selection=select_pilot(
        _load(args.p2_census),
        _load(args.d3_corpus),
        records,
    )
    args.output.mkdir(parents=True,exist_ok=True)
    full=args.output/"ss002-l001-p1-selection.json"
    full.write_text(
        json.dumps(selection,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    summary={k:v for k,v in selection.items() if k!="rows"}
    summary["selected_rows"]=[
        {
            "pilot_family":row["pilot_family"],
            "exchange_published_at_utc":row["exchange_published_at_utc"],
            "announcement_id":row["announcement_id"],
            "symbol":row["symbol"],
            "document_id":row["document_id"],
            "segment_count":row["segment_count"],
            "prompt_sha256":row["prompt_sha256"],
        }
        for row in selection["rows"]
    ]
    (args.output/"summary.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(summary,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
