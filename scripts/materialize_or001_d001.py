from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.or001_router import build_opportunity_router


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ss001", type=Path, required=True)
    parser.add_argument("--ei001", type=Path, required=True)
    parser.add_argument("--ha001", type=Path, required=True)
    parser.add_argument("--gf001", type=Path, required=True)
    parser.add_argument("--ss002", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = build_opportunity_router(
        ss001=_load(args.ss001),
        ei001=_load(args.ei001),
        ha001=_load(args.ha001),
        gf001=_load(args.gf001),
        ss002=_load(args.ss002),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "or001-d001-router.json").write_text(
        json.dumps(
            output,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in output.items() if key not in {"rows", "multi_evidence_queue"}}
    summary["multi_evidence_queue"] = [
        {
            "symbol": row["symbol"],
            "company_name": row["company_name"],
            "in_existing_u001": row["in_existing_u001"],
            "independent_route_count": row["independent_route_count"],
            "research_priority": row["research_priority"],
            "opportunity_routes": row["opportunity_routes"],
            "earnings_inflection_flags": row["earnings_inflection_flags"],
            "asset_anomaly_flags": row["asset_anomaly_flags"],
            "special_situation_categories": row["special_situation_categories"],
            "governance_caution_flags": row["governance_caution_flags"],
            "liquidity_band": row["liquidity_band"],
            "median_daily_turnover_inr": row["median_daily_turnover_inr"],
        }
        for row in output["multi_evidence_queue"]
    ]
    (args.output / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "router_sha256": output["router_sha256"],
                "priority_counts": output["priority_counts"],
                "route_combination_counts": output["route_combination_counts"],
                "multi_evidence_count": output["multi_evidence_count"],
                "outside_u001_multi_evidence_count": output[
                    "outside_u001_multi_evidence_count"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
