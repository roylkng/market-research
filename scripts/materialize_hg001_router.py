from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ei001_inflection import build_inflection_router
from marketlab.hg001_router import build_hidden_gem_router


def _load(path: Path) -> dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON payload must be object: {path}")
    return payload


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(
        json.dumps(payload,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--ei-panel",type=Path,required=True)
    parser.add_argument("--ha-panel",type=Path,required=True)
    parser.add_argument("--gf-panel",type=Path,required=True)
    parser.add_argument("--investability",type=Path,required=True)
    parser.add_argument("--special",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()

    ei=build_inflection_router(_load(args.ei_panel))
    hg=build_hidden_gem_router(
        ei=ei,
        ha=_load(args.ha_panel),
        gf=_load(args.gf_panel),
        investability=_load(args.investability),
        special=_load(args.special),
    )
    _write(args.output/"ei001-s001-router.json",ei)
    _write(args.output/"hg001-d001-router.json",hg)

    print(json.dumps({
        "ei_router_sha256":ei["router_sha256"],
        "ei_active_inflection_count":ei["active_inflection_count"],
        "ei_state_counts":ei["state_counts"],
        "hg_router_sha256":hg["router_sha256"],
        "hg_active_research_candidate_count":hg["active_research_candidate_count"],
        "hg_research_route_counts":hg["research_route_counts"],
        "hg_lane_count_distribution":hg["lane_count_distribution"],
        "hg_convergent_outside_u001_count":hg["convergent_outside_u001_count"],
        "top_convergent":[
            {
                "symbol":row["symbol"],
                "lanes":row["active_opportunity_lanes"],
                "earnings_state":row["earnings_inflection_state"],
                "asset_flags":row["asset_opportunity_flags"],
                "governance_cautions":row["governance_caution_flags"],
                "liquidity_band":row["liquidity_band"],
                "special_categories":row["special_situation_categories"],
                "in_existing_u001":row["in_existing_u001"],
            }
            for row in hg["research_queue"]
            if row["research_route"]=="CONVERGENT_DEEP_DIVE"
        ][:60],
    },indent=2,sort_keys=True))


if __name__=="__main__":
    main()
