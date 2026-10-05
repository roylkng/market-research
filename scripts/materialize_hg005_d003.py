from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg005_d003 import build_payoff_frameworks


def load(path: Path) -> dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--market-context",type=Path,required=True)
    parser.add_argument("--d002b-synthesis",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()

    output=build_payoff_frameworks(
        market_context=load(args.market_context),
        d002b_synthesis=load(args.d002b_synthesis),
    )
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(
        json.dumps(output,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "framework_id":output["framework_id"],
        "framework_sha256":output["framework_sha256"],
        "companies":output["companies"],
        "expected_returns_calculated":output["expected_returns_calculated"],
    },sort_keys=True))


if __name__=="__main__":
    main()
