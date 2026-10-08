from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg006_p3_execution import BATCH_COUNT, combine_p3_ingestion


def _load(path: Path) -> dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--queue",type=Path,required=True)
    p.add_argument("--prior-ingestion",type=Path,required=True)
    p.add_argument("--batches-root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    ingestions=[]
    seen=set()
    for path in sorted(args.batches_root.rglob("ingestion.json")):
        payload=_load(path)
        batch_id=payload.get("batch_id")
        if not isinstance(batch_id,int) or isinstance(batch_id,bool) or batch_id in seen:
            raise ValueError("HG006 P3 invalid or duplicate batch ingestion")
        seen.add(batch_id)
        ingestions.append(payload)
    if seen!=set(range(BATCH_COUNT)):
        raise ValueError(
            f"HG006 P3 requires batches 0..{BATCH_COUNT-1}, observed {sorted(seen)}"
        )
    output=combine_p3_ingestion(
        _load(args.queue),
        _load(args.prior_ingestion),
        ingestions,
    )
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(
        json.dumps(output,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "ingestion_sha256":output["ingestion_sha256"],
        "status_counts":output["status_counts"],
        "full_ingestion_pass":output["full_ingestion_pass"],
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
