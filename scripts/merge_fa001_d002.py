from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.fa001_facts import build_full_fact_panel


def _load(path: Path)->dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def parse_args()->argparse.Namespace:
    parser=argparse.ArgumentParser()
    parser.add_argument("--d001-census",type=Path,required=True)
    parser.add_argument("--shards-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    return parser.parse_args()


def main()->int:
    args=parse_args()
    census=_load(args.d001_census)
    paths=sorted(args.shards_dir.rglob("fa001-d002-shard-*.json"))
    shards=[_load(path) for path in paths]
    panel=build_full_fact_panel(
        d001_census=census,
        shard_payloads=shards,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00","Z"),
    )
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"fa001-d002-panel.json").write_text(
        json.dumps(panel,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    summary={key:value for key,value in panel.items() if key!="rows"}
    (args.output/"summary.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(summary,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
