from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from marketlab.hg006_text import (
    SHARD_COUNT,
    extract_verified_document,
    selected_document_requests,
)
from marketlab.nse import NSEAcquisitionError, NSEClient


def _load(path:Path)->dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON payload must be object: {path}")
    return payload


def parse_args()->argparse.Namespace:
    p=argparse.ArgumentParser()
    p.add_argument("--selection",type=Path,required=True)
    p.add_argument("--source-corpus",type=Path,required=True)
    p.add_argument("--shard-id",type=int,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--attempts",type=int,default=4)
    p.add_argument("--timeout-seconds",type=float,default=30.0)
    p.add_argument("--pause-seconds",type=float,default=0.01)
    return p.parse_args()


def main()->int:
    args=parse_args()
    if not 0<=args.shard_id<SHARD_COUNT:
        raise ValueError(f"HG006 D001B shard must be 0..{SHARD_COUNT-1}")
    selection=_load(args.selection)
    source=_load(args.source_corpus)
    requests=[
        row for row in selected_document_requests(selection,source)
        if row["shard_id"]==args.shard_id
    ]
    client=NSEClient(timeout=args.timeout_seconds,attempts=args.attempts)
    rows=[]
    for index,request in enumerate(requests,start=1):
        matched_raw=None
        matched_url=None
        attempts=[]
        for url in request["source_urls"]:
            try:
                raw=client.archive_bytes(url)
                sha=hashlib.sha256(raw).hexdigest()
                if sha==request["document_id"]:
                    attempts.append({
                        "source_url":url,
                        "status":"HASH_MATCH",
                        "observed_sha256":sha,
                    })
                    matched_raw=raw
                    matched_url=url
                    break
                attempts.append({
                    "source_url":url,
                    "status":"HASH_MISMATCH",
                    "observed_sha256":sha,
                })
            except NSEAcquisitionError as exc:
                attempts.append({
                    "source_url":url,
                    "status":"FETCH_FAILED",
                    "error":f"{type(exc).__name__}: {exc}",
                })
        row=extract_verified_document(
            request,
            raw=matched_raw,
            source_url=matched_url,
            attempts=attempts,
        )
        rows.append(row)
        if index==1 or index%25==0 or index==len(requests):
            print(
                f"[hg006-d001b shard={args.shard_id}] {index:04d}/{len(requests)} "
                f"hash={row['hash_reproduced']} state={row['extraction_state']}",
                flush=True,
            )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    args.output.mkdir(parents=True,exist_ok=True)
    payload={
        "schema_version":1,
        "shard_id":args.shard_id,
        "shard_count":SHARD_COUNT,
        "request_count":len(requests),
        "hash_reproduced_count":sum(row["hash_reproduced"] is True for row in rows),
        "text_ready_count":sum(row["extraction_state"]=="READY" for row in rows),
        "rows":rows,
    }
    (args.output/"shard-text.json").write_text(
        json.dumps(payload,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    return 0


if __name__=="__main__":
    raise SystemExit(main())
