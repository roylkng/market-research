from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg006_evidence_pack import build_stage_evidence_pack


def _load(path:Path)->dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON payload must be object: {path}")
    return payload


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--selection",type=Path,required=True)
    p.add_argument("--d001-census",type=Path,required=True)
    p.add_argument("--d001b-summary",type=Path,required=True)
    p.add_argument("--shards-root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()

    text_files=sorted(args.shards_root.rglob("shard-text.json"))
    if len(text_files)!=8:
        raise ValueError(f"HG006 S002 requires 8 D001B shard-text files, found {len(text_files)}")
    seen=set()
    rows=[]
    for path in text_files:
        payload=_load(path)
        shard=payload.get("shard_id")
        if not isinstance(shard,int) or isinstance(shard,bool) or not 0<=shard<8:
            raise ValueError("HG006 S002 invalid shard ID")
        if shard in seen:
            raise ValueError("HG006 S002 duplicate shard ID")
        seen.add(shard)
        shard_rows=payload.get("rows")
        if not isinstance(shard_rows,list):
            raise TypeError("HG006 S002 shard rows must be list")
        rows.extend(shard_rows)

    result=build_stage_evidence_pack(
        selection=_load(args.selection),
        d001=_load(args.d001_census),
        d001b_summary=_load(args.d001b_summary),
        text_rows=rows,
    )
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(
        json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "pack_sha256":result["pack_sha256"],
        "chronology_count":result["chronology_count"],
        "state_counts":result["state_counts"],
        "retained_document_count":result["retained_document_count"],
        "retained_segment_count":result["retained_segment_count"],
        "feasibility_pass":result["feasibility_pass"],
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
