from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha import digest
from marketlab.hg006_full_inference import build_shard_template


def _load(path: Path) -> dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--queue",type=Path,required=True)
    parser.add_argument("--p0-run",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()

    queue=_load(args.queue)
    p0=_load(args.p0_run)
    args.output.mkdir(parents=True,exist_ok=True)
    manifests=[]
    total_pending=0
    total_reused=0
    for shard_id in range(16):
        template=build_shard_template(queue,p0,shard_id=shard_id)
        path=args.output/f"hg006-l001-p2-shard-{shard_id:02d}-template.json"
        path.write_text(
            json.dumps(template,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
            encoding="utf-8",
        )
        manifests.append({
            "shard_id":shard_id,
            "request_count":template["request_count"],
            "p0_reuse_count":template["p0_reuse_count"],
            "pending_native_count":template["pending_native_count"],
            "template_sha256":template["template_sha256"],
            "path":path.name,
        })
        total_pending+=template["pending_native_count"]
        total_reused+=template["p0_reuse_count"]

    index={
        "schema_version":1,
        "execution_id":"HG006-L001-P2-v1",
        "source_queue_sha256":queue["queue_sha256"],
        "p0_run_sha256":p0["run_sha256"],
        "model_config_sha256":queue["model_config_sha256"],
        "shard_count":16,
        "request_count":sum(row["request_count"] for row in manifests),
        "p0_reuse_count":total_reused,
        "pending_native_count":total_pending,
        "shards":manifests,
        "historical_terminal_labels_opened":False,
        "completion_probabilities_assigned":False,
        "return_outcomes_opened":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    index["index_sha256"]=digest(index)
    (args.output/"index.json").write_text(
        json.dumps(index,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(index,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
