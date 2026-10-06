from __future__ import annotations

import argparse
import json
from datetime import UTC,datetime
from pathlib import Path

from marketlab.hg006_text import SHARD_COUNT,build_selected_text_corpus


def _load(path:Path)->dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON payload must be object: {path}")
    return payload


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--selection",type=Path,required=True)
    p.add_argument("--source-corpus",type=Path,required=True)
    p.add_argument("--shards-root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()

    selection=_load(args.selection)
    source=_load(args.source_corpus)
    files=sorted(args.shards_root.rglob("shard-text.json"))
    if len(files)!=SHARD_COUNT:
        raise ValueError(f"HG006 D001B requires {SHARD_COUNT} shard files, found {len(files)}")
    seen=set()
    rows=[]
    for path in files:
        payload=_load(path)
        shard=payload.get("shard_id")
        if not isinstance(shard,int) or isinstance(shard,bool) or not 0<=shard<SHARD_COUNT:
            raise ValueError("HG006 D001B invalid shard id")
        if shard in seen:
            raise ValueError("HG006 D001B duplicate shard id")
        seen.add(shard)
        shard_rows=payload.get("rows")
        if not isinstance(shard_rows,list):
            raise TypeError("HG006 D001B shard rows must be list")
        rows.extend(shard_rows)

    corpus=build_selected_text_corpus(
        selection=selection,
        source_corpus=source,
        extraction_rows=rows,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00","Z"),
    )
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"hg006-d001b-text-corpus.json").write_text(
        json.dumps(corpus,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    summary={key:value for key,value in corpus.items() if key!="documents"}
    (args.output/"summary.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(summary,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
