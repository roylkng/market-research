from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.tc001 import (
    IMPACT_COEFFICIENTS,
    TC001Config,
    equal_weight_replacement_cost_bps,
    max_order_notional_for_alpha,
    round_trip_cost,
)


def _write(path: Path | None, payload: object) -> None:
    text = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    if path is None:
        print(text, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report TC001 NSE delivery-equity transaction-cost sensitivity"
    )
    parser.add_argument("--order-notional-inr", type=float, required=True)
    parser.add_argument("--adv20-inr", type=float, required=True)
    parser.add_argument("--daily-volatility", type=float, required=True)
    parser.add_argument("--half-spread-bps", type=float, default=0.0)
    parser.add_argument("--brokerage-bps", type=float, default=0.0)
    parser.add_argument("--dp-sell-charge-inr", type=float, default=0.0)
    parser.add_argument("--gst-on-dp", action="store_true")
    parser.add_argument("--replacement-fraction", type=float)
    parser.add_argument("--gross-alpha-bps", type=float)
    parser.add_argument("--required-net-alpha-bps", type=float, default=0.0)
    parser.add_argument("--maximum-participation", type=float, default=0.10)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_config = TC001Config(
        brokerage_buy_bps=args.brokerage_bps,
        brokerage_sell_bps=args.brokerage_bps,
        dp_sell_charge_inr=args.dp_sell_charge_inr,
        gst_on_dp_sell_charge=args.gst_on_dp,
        half_spread_buy_bps=args.half_spread_bps,
        half_spread_sell_bps=args.half_spread_bps,
        impact_coefficient=IMPACT_COEFFICIENTS["BASE"],
    )
    observable = round_trip_cost(
        buy_notional_inr=args.order_notional_inr,
        config=base_config,
        include_execution_friction=False,
    )
    observable_round_trip = observable["equal_notional_round_trip_bps"]
    assert observable_round_trip is not None

    scenarios = {}
    for name, coefficient in IMPACT_COEFFICIENTS.items():
        config = TC001Config(
            brokerage_buy_bps=args.brokerage_bps,
            brokerage_sell_bps=args.brokerage_bps,
            dp_sell_charge_inr=args.dp_sell_charge_inr,
            gst_on_dp_sell_charge=args.gst_on_dp,
            half_spread_buy_bps=args.half_spread_bps,
            half_spread_sell_bps=args.half_spread_bps,
            impact_coefficient=coefficient,
        )
        report = round_trip_cost(
            buy_notional_inr=args.order_notional_inr,
            adv20_inr=args.adv20_inr,
            daily_volatility_decimal=args.daily_volatility,
            config=config,
            include_execution_friction=True,
        )
        round_trip_bps = report["equal_notional_round_trip_bps"]
        assert round_trip_bps is not None
        scenario = {
            "impact_coefficient": coefficient,
            "round_trip_bps": round_trip_bps,
            "buy_total_bps": report["buy"]["total_bps"],
            "sell_total_bps": report["sell"]["total_bps"],
            "participation_rate": report["buy"]["participation_rate"],
            "market_impact_bps_each_side": report["buy"]["market_impact"]["bps"],
        }
        if args.replacement_fraction is not None:
            rebalance_cost = equal_weight_replacement_cost_bps(
                replacement_fraction=args.replacement_fraction,
                round_trip_cost_bps=round_trip_bps,
            )
            scenario["equal_weight_replacement_cost_bps"] = rebalance_cost
            if args.gross_alpha_bps is not None:
                scenario["gross_alpha_bps"] = args.gross_alpha_bps
                scenario["net_alpha_after_replacement_cost_bps"] = (
                    args.gross_alpha_bps - rebalance_cost
                )

        if args.gross_alpha_bps is not None:
            nonimpact = round_trip_bps - (
                2.0 * report["buy"]["market_impact"]["bps"]
            )
            scenario["capacity"] = max_order_notional_for_alpha(
                adv20_inr=args.adv20_inr,
                gross_alpha_bps=args.gross_alpha_bps,
                required_net_alpha_bps=args.required_net_alpha_bps,
                nonimpact_round_trip_cost_bps=nonimpact,
                daily_volatility_decimal=args.daily_volatility,
                impact_coefficient=coefficient,
                maximum_participation=args.maximum_participation,
            )
        scenarios[name] = scenario

    payload = {
        "schema_version": 1,
        "model_id": "TC001-v1-DEVELOPMENT",
        "inputs": {
            "order_notional_inr": args.order_notional_inr,
            "adv20_inr": args.adv20_inr,
            "daily_volatility_decimal": args.daily_volatility,
            "half_spread_bps_each_side": args.half_spread_bps,
            "brokerage_bps_each_side": args.brokerage_bps,
            "dp_sell_charge_inr": args.dp_sell_charge_inr,
            "gst_on_dp_sell_charge": args.gst_on_dp,
            "replacement_fraction": args.replacement_fraction,
            "gross_alpha_bps": args.gross_alpha_bps,
            "required_net_alpha_bps": args.required_net_alpha_bps,
            "maximum_participation": args.maximum_participation,
        },
        "observable_round_trip_bps": observable_round_trip,
        "impact_model_calibrated_to_nse_execution": False,
        "scenarios": scenarios,
        "live_capital_allowed": False,
    }
    _write(args.output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
