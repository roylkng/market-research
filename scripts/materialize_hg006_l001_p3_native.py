from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg006_p3_execution import build_native_batch_bundle


def _load(path: Path) -> dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--queue",type=Path,required=True)
    p.add_argument("--decisions",type=Path,required=True)
    p.add_argument("--batch-id",type=int,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    bundle=build_native_batch_bundle(
        _load(args.queue),
        _load(args.decisions),
        batch_id=args.batch_id,
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
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
