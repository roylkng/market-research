from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.tc001 import (
    TC001Config,
    equal_weight_replacement_cost_bps,
    round_trip_cost,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("T003 TC001 input must be a JSON object")
    return payload


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _bps(decimal_return: float) -> float:
    return float(decimal_return) * 10_000.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply TC001 to the sealed AE001 T003 5D diagnostics"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = _load(args.input)
    base = source["base"]
    augmented = source["augmented"]

    observable = round_trip_cost(
        buy_notional_inr=10_000_000,
        config=TC001Config(),
        include_execution_friction=False,
    )
    observable_rt = float(observable["equal_notional_round_trip_bps"])

    def portfolio_view(model: dict, round_trip_bps: float) -> dict:
        gross_bps = _bps(model["mean_top_decile_excess"])
        churn = float(model["average_top_decile_selection_churn"])
        drag = equal_weight_replacement_cost_bps(
            replacement_fraction=churn,
            round_trip_cost_bps=round_trip_bps,
        )
        return {
            "gross_top_decile_excess_bps": gross_bps,
            "selection_churn": churn,
            "replacement_cost_bps": drag,
            "net_excess_after_replacement_cost_bps": gross_bps - drag,
            "break_even_round_trip_cost_bps": gross_bps / churn,
        }

    observable_base = portfolio_view(base, observable_rt)
    observable_augmented = portfolio_view(augmented, observable_rt)

    scenarios = {}
    for name, scenario in source["illustrative_execution_scenarios"].items():
        participation = float(scenario["participation_rate"])
        adv = 100_000_000.0
        notional = adv * participation
        config = TC001Config(
            half_spread_buy_bps=float(
                scenario["half_spread_bps_each_side"]
            ),
            half_spread_sell_bps=float(
                scenario["half_spread_bps_each_side"]
            ),
            impact_coefficient=float(scenario["impact_coefficient"]),
        )
        report = round_trip_cost(
            buy_notional_inr=notional,
            adv20_inr=adv,
            daily_volatility_decimal=float(
                scenario["daily_volatility_decimal"]
            ),
            config=config,
            include_execution_friction=True,
        )
        round_trip_bps = float(report["equal_notional_round_trip_bps"])
        base_view = portfolio_view(base, round_trip_bps)
        augmented_view = portfolio_view(augmented, round_trip_bps)
        scenarios[name] = {
            **scenario,
            "round_trip_cost_bps": round_trip_bps,
            "impact_bps_each_side": report["buy"]["market_impact"]["bps"],
            "base": base_view,
            "augmented": augmented_view,
            "augmented_minus_base_net_excess_bps": (
                augmented_view["net_excess_after_replacement_cost_bps"]
                - base_view["net_excess_after_replacement_cost_bps"]
            ),
        }

    gross_delta_bps = (
        _bps(augmented["mean_top_decile_excess"])
        - _bps(base["mean_top_decile_excess"])
    )
    churn_delta = (
        float(augmented["average_top_decile_selection_churn"])
        - float(base["average_top_decile_selection_churn"])
    )
    relative_break_even_round_trip = (
        None if churn_delta <= 0 else gross_delta_bps / churn_delta
    )

    report = {
        "schema_version": 1,
        "analysis_id": source["analysis_id"],
        "source_run_id": source["source_run_id"],
        "source_report_sha256": source["source_report_sha256"],
        "evidence_class": source["evidence_class"],
        "horizon_sessions": source["horizon_sessions"],
        "observable_cost_floor": {
            "equal_notional_round_trip_bps": observable_rt,
            "base": observable_base,
            "augmented": observable_augmented,
            "augmented_minus_base_net_excess_bps": (
                observable_augmented[
                    "net_excess_after_replacement_cost_bps"
                ]
                - observable_base[
                    "net_excess_after_replacement_cost_bps"
                ]
            ),
        },
        "relative_break_even_round_trip_cost_bps": (
            relative_break_even_round_trip
        ),
        "illustrative_execution_scenarios": scenarios,
        "paired_augmented_minus_base": source[
            "paired_augmented_minus_base"
        ],
        "interpretation_limits": source["cost_interpretation"],
        "tc001_impact_model_calibrated_to_nse_execution": False,
        "tc001_does_not_establish_prospective_alpha": True,
        "live_capital_allowed": False,
    }
    _write(args.output, report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
