from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

from marketlab.events import sha256_bytes
from marketlab.hg006_historical_events import SOURCE_END, SOURCE_START
from marketlab.nse import NSEClient

SHARDS={
    "H2023":("2023-01-01","2023-12-31"),
    "H2024":("2024-01-01","2024-12-31"),
    "H2025":("2025-01-01","2025-12-31"),
    "H2026":("2026-01-01","2026-09-30"),
}


def _nse_date(day:date)->str:
    return day.strftime("%d-%m-%Y")


def parse_args()->argparse.Namespace:
    parser=argparse.ArgumentParser()
    parser.add_argument("--shard-id",choices=sorted(SHARDS),required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--attempts",type=int,default=4)
    parser.add_argument("--timeout-seconds",type=float,default=25.0)
    parser.add_argument("--pause-seconds",type=float,default=0.03)
    return parser.parse_args()


def main()->int:
    args=parse_args()
    start_text,end_text=SHARDS[args.shard_id]
    start=date.fromisoformat(start_text)
    end=date.fromisoformat(end_text)
    if start<SOURCE_START or end>SOURCE_END:
        raise ValueError("HG006 shard lies outside frozen source window")

    client=NSEClient(timeout=args.timeout_seconds,attempts=args.attempts)
    daily_dir=args.output/"daily"
    daily_dir.mkdir(parents=True,exist_ok=True)
    rows=[]
    total=(end-start).days+1

    for offset in range(total):
        day=date.fromordinal(start.toordinal()+offset)
        payload,raw=client.corporate_announcements_with_raw(
            None,
            from_date=_nse_date(day),
            to_date=_nse_date(day),
        )
        sha=sha256_bytes(raw)
        path=daily_dir/f"{day.isoformat()}.json"
        path.write_bytes(raw)
        if sha256_bytes(path.read_bytes())!=sha:
            raise RuntimeError("HG006 shard retained raw SHA mismatch")
        count=len(payload) if isinstance(payload,list) else len(payload.get("data",[]))
        rows.append({
            "date":day.isoformat(),
            "raw_sha256":sha,
            "relative_path":f"daily/{day.isoformat()}.json",
            "row_count":count,
        })
        if offset==0 or (offset+1)%50==0 or offset+1==total:
            print(
                f"[{args.shard_id}] {offset+1:03d}/{total} "
                f"{day.isoformat()} rows={count} sha={sha[:12]}",
                flush=True,
            )
        if args.pause_seconds>0:
            time.sleep(args.pause_seconds)

    manifest={
        "schema_version":1,
        "shard_id":args.shard_id,
        "start_date":start.isoformat(),
        "end_date":end.isoformat(),
        "calendar_day_count":total,
        "days":rows,
    }
    (args.output/"shard-manifest.json").write_text(
        json.dumps(manifest,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    return 0


if __name__=="__main__":
    raise SystemExit(main())
