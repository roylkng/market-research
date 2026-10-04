from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ha001_assets import build_asset_anomaly_panel


def _load(path:Path)->dict:
    p=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(p,dict): raise TypeError(f"JSON object required: {path}")
    return p


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--fa-panel",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    panel=build_asset_anomaly_panel(_load(args.fa_panel))
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"ha001-d001-panel.json").write_text(
        json.dumps(panel,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    summary={k:v for k,v in panel.items() if k!="rows"}
    (args.output/"summary.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(summary,sort_keys=True))
    return 0


if __name__=="__main__": raise SystemExit(main())
