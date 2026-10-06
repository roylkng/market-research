from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg006_full_inference import combine_shard_bundles


def _load(path:Path)->dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--queue",type=Path,required=True)
    parser.add_argument("--p0-run",type=Path,required=True)
    parser.add_argument("--bundles-dir",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()

    bundles=[
        _load(args.bundles_dir/f"hg006-l001-p2-shard-{shard_id:02d}.json")
        for shard_id in range(16)
    ]
    output=combine_shard_bundles(_load(args.queue),_load(args.p0_run),bundles)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(
        json.dumps(output,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "ingestion_sha256":output["ingestion_sha256"],
        "status_counts":output["status_counts"],
        "validated_request_ratio":output["validated_request_ratio"],
        "validated_chronology_ratio":output["validated_chronology_ratio"],
        "full_ingestion_pass":output["full_ingestion_pass"],
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
