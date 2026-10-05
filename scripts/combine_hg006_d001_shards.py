from __future__ import annotations

import argparse
import json
from datetime import UTC,datetime
from pathlib import Path

from marketlab.events import sha256_bytes
from marketlab.hg006_historical_events import (
    SOURCE_END,
    SOURCE_START,
    build_historical_event_census,
)


def parse_args()->argparse.Namespace:
    parser=argparse.ArgumentParser()
    parser.add_argument("--shards-root",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    return parser.parse_args()


def main()->int:
    args=parse_args()
    manifests=sorted(args.shards_root.rglob("shard-manifest.json"))
    if len(manifests)!=4:
        raise ValueError(f"HG006 combine requires 4 shard manifests, found {len(manifests)}")

    payloads={}
    hashes={}
    shard_summary=[]
    for manifest_path in manifests:
        manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        days=manifest.get("days")
        if not isinstance(days,list):
            raise TypeError("HG006 shard days must be list")
        for row in days:
            day=str(row["date"])
            if day in payloads:
                raise ValueError(f"HG006 duplicate shard day: {day}")
            raw_path=manifest_path.parent/str(row["relative_path"])
            raw=raw_path.read_bytes()
            sha=sha256_bytes(raw)
            if sha!=row["raw_sha256"]:
                raise ValueError(f"HG006 shard SHA mismatch: {day}")
            payloads[day]=json.loads(raw.decode("utf-8"))
            hashes[day]=sha
        shard_summary.append({
            "shard_id":manifest["shard_id"],
            "start_date":manifest["start_date"],
            "end_date":manifest["end_date"],
            "calendar_day_count":manifest["calendar_day_count"],
        })

    expected=[
        datetime.fromordinal(SOURCE_START.toordinal()+offset).date().isoformat()
        for offset in range((SOURCE_END-SOURCE_START).days+1)
    ]
    if sorted(payloads)!=expected:
        missing=sorted(set(expected)-set(payloads))
        extra=sorted(set(payloads)-set(expected))
        raise ValueError(
            f"HG006 combined coverage mismatch missing={missing[:10]} extra={extra[:10]}"
        )

    census=build_historical_event_census(
        daily_payloads=payloads,
        daily_raw_sha256=hashes,
        generated_at_utc=datetime.now(UTC).isoformat().replace("+00:00","Z"),
    )
    census["acquisition_topology"]="P1_FOUR_PARALLEL_CALENDAR_SHARDS"
    census["acquisition_shards"]=sorted(shard_summary,key=lambda row:row["shard_id"])

    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"hg006-d001-census.json").write_text(
        json.dumps(census,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    summary={
        key:value
        for key,value in census.items()
        if key not in {
            "events",
            "chronologies",
            "daily_raw_sha256",
            "daily_source_row_counts",
            "daily_retained_event_counts",
        }
    }
    (args.output/"summary.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(summary,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
