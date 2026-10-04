from __future__ import annotations

import argparse
import json
from datetime import UTC,datetime
from pathlib import Path

from marketlab.ei001_full_market import build_full_comparative_panel
from marketlab.fa001_facts import SHARD_COUNT


def _load(path:Path)->dict:
    p=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(p,dict): raise TypeError(f"JSON object required: {path}")
    return p


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--fa-panel",type=Path,required=True)
    p.add_argument("--shards-root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    fa=_load(args.fa_panel)
    rows=[]; seen=set(); shards=set()
    for path in sorted(args.shards_root.rglob("ei001-d002-shard-*.json")):
        x=_load(path); idx=x.get("shard_index")
        if idx in shards: raise ValueError(f"duplicate shard {idx}")
        shards.add(idx)
        if x.get("shard_count")!=SHARD_COUNT: raise ValueError("wrong shard_count")
        rr=x.get("rows")
        if not isinstance(rr,list): raise TypeError("shard rows unavailable")
        for row in rr:
            sym=str(row.get("symbol") or "").upper()
            if not sym or sym in seen: raise ValueError(f"duplicate/empty symbol {sym}")
            seen.add(sym); rows.append(row)
    if shards!=set(range(SHARD_COUNT)): raise ValueError("missing EI001 shards")
    if len(rows)!=2319: raise ValueError(f"expected 2319 rows, got {len(rows)}")
    panel=build_full_comparative_panel(fa_panel=fa,acquired_rows=rows,captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00","Z"))
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"ei001-d002-panel.json").write_text(json.dumps(panel,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
    summary={k:v for k,v in panel.items() if k!="rows"}
    (args.output/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(summary,sort_keys=True))
    return 0


if __name__=="__main__": raise SystemExit(main())
