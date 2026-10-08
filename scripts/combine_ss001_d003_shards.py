from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.ss001_size import SHARD_COUNT, build_company_size_panel


def _load(path: Path)->dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--d001-census",type=Path,required=True)
    p.add_argument("--shards-root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()

    files=sorted(args.shards_root.rglob("size-shard.json"))
    if len(files)!=SHARD_COUNT:
        raise ValueError(f"SS001 D003 requires {SHARD_COUNT} shard files, found {len(files)}")
    seen=set()
    rows=[]
    for path in files:
        payload=_load(path)
        shard_id=payload.get("shard_id")
        if (
            not isinstance(shard_id,int)
            or isinstance(shard_id,bool)
            or not 0<=shard_id<SHARD_COUNT
            or shard_id in seen
        ):
            raise ValueError("SS001 D003 invalid or duplicate shard")
        seen.add(shard_id)
        shard_rows=payload.get("rows")
        if not isinstance(shard_rows,list):
            raise TypeError("SS001 D003 shard rows must be a list")
        rows.extend(shard_rows)

    panel=build_company_size_panel(
        d001_census=_load(args.d001_census),
        acquired_rows=rows,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00","Z"),
    )
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"ss001-d003-size-panel.json").write_text(
        json.dumps(panel,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    summary={key:value for key,value in panel.items() if key!="rows"}
    (args.output/"summary.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(summary,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
