from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg006_full_inference import ingest_shard_responses


def _load(path: Path)->dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--queue",type=Path,required=True)
    parser.add_argument("--p0-run",type=Path,required=True)
    parser.add_argument("--native-bundle",type=Path,required=True)
    parser.add_argument("--shard-id",type=int,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()

    bundle=ingest_shard_responses(
        _load(args.queue),
        _load(args.p0_run),
        shard_id=args.shard_id,
        native_bundle=_load(args.native_bundle),
    )
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(
        json.dumps(bundle,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "bundle_id":bundle["bundle_id"],
        "bundle_sha256":bundle["bundle_sha256"],
        "request_count":bundle["request_count"],
        "status_counts":bundle["status_counts"],
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
