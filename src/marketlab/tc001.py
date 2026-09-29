from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from marketlab.alpha import AlphaContractError, digest

CRORE_INR = 10_000_000.0
BPS_PER_UNIT = 10_000.0

STT_BUY_BPS = 10.0
STT_SELL_BPS = 10.0
STAMP_BUY_BPS = 1.5
STAMP_SELL_BPS = 0.0
NSE_TRANSACTION_CHARGE_INR_PER_CRORE = 306.99
NSE_IPFT_INR_PER_CRORE = 0.01
SEBI_TURNOVER_FEE_INR_PER_CRORE = 10.0
GST_RATE = 0.18

IMPACT_COEFFICIENTS = {
    "LOW": 0.25,
    "BASE": 0.50,
    "HIGH": 1.00,
}


@dataclass(frozen=True)
class TC001Config:
    brokerage_buy_bps: float = 0.0
    brokerage_sell_bps: float = 0.0
    dp_sell_charge_inr: float = 0.0
    gst_on_dp_sell_charge: bool = False
    half_spread_buy_bps: float = 0.0
    half_spread_sell_bps: float = 0.0
    impact_coefficient: float = IMPACT_COEFFICIENTS["BASE"]

    def validate(self) -> None:
        numeric = {
            "brokerage_buy_bps": self.brokerage_buy_bps,
            "brokerage_sell_bps": self.brokerage_sell_bps,
            "dp_sell_charge_inr": self.dp_sell_charge_inr,
            "half_spread_buy_bps": self.half_spread_buy_bps,
            "half_spread_sell_bps": self.half_spread_sell_bps,
            "impact_coefficient": self.impact_coefficient,
        }
        for name, value in numeric.items():
            if isinstance(value, bool) or not math.isfinite(float(value)):
                raise AlphaContractError(f"TC001 {name} must be finite")
            if float(value) < 0:
                raise AlphaContractError(f"TC001 {name} cannot be negative")


def inr_per_crore_to_bps(value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise AlphaContractError("INR-per-crore charge must be finite and non-negative")
    return value / CRORE_INR * BPS_PER_UNIT


def bps_to_inr(notional_inr: float, bps: float) -> float:
    _validate_notional(notional_inr)
    if not math.isfinite(bps) or bps < 0:
        raise AlphaContractError("bps must be finite and non-negative")
    return notional_inr * bps / BPS_PER_UNIT


def _validate_notional(notional_inr: float) -> None:
    if (
        isinstance(notional_inr, bool)
        or not math.isfinite(float(notional_inr))
        or float(notional_inr) <= 0
    ):
        raise AlphaContractError("TC001 notional must be finite and positive")


def _validate_market_inputs(
    *,
    order_notional_inr: float,
    adv20_inr: float,
    daily_volatility_decimal: float,
) -> float:
    _validate_notional(order_notional_inr)
    _validate_notional(adv20_inr)
    if (
        isinstance(daily_volatility_decimal, bool)
        or not math.isfinite(float(daily_volatility_decimal))
        or float(daily_volatility_decimal) < 0
    ):
        raise AlphaContractError(
            "TC001 daily volatility must be finite and non-negative"
        )
    participation = float(order_notional_inr) / float(adv20_inr)
    if participation > 1.0:
        raise AlphaContractError(
            "TC001 square-root impact model does not support participation above 100%"
        )
    return participation


def market_impact_bps(
    *,
    order_notional_inr: float,
    adv20_inr: float,
    daily_volatility_decimal: float,
    impact_coefficient: float,
) -> float:
    participation = _validate_market_inputs(
        order_notional_inr=order_notional_inr,
        adv20_inr=adv20_inr,
        daily_volatility_decimal=daily_volatility_decimal,
    )
    if (
        isinstance(impact_coefficient, bool)
        or not math.isfinite(float(impact_coefficient))
        or float(impact_coefficient) < 0
    ):
        raise AlphaContractError(
            "TC001 impact coefficient must be finite and non-negative"
        )
    return (
        float(impact_coefficient)
        * float(daily_volatility_decimal)
        * BPS_PER_UNIT
        * math.sqrt(participation)
    )


def _line_item(notional_inr: float, bps: float) -> dict[str, float]:
    return {
        "bps": float(bps),
        "inr": bps_to_inr(notional_inr, float(bps)),
    }


def observable_side_cost(
    *,
    side: str,
    notional_inr: float,
    config: TC001Config | None = None,
) -> dict[str, Any]:
    """Return delivery-equity cash charges excluding spread and market impact."""

    cfg = config or TC001Config()
    cfg.validate()
    _validate_notional(notional_inr)
    normalized_side = side.strip().upper()
    if normalized_side not in {"BUY", "SELL"}:
        raise AlphaContractError("TC001 side must be BUY or SELL")

    stt_bps = STT_BUY_BPS if normalized_side == "BUY" else STT_SELL_BPS
    stamp_bps = STAMP_BUY_BPS if normalized_side == "BUY" else STAMP_SELL_BPS
    brokerage_bps = (
        cfg.brokerage_buy_bps
        if normalized_side == "BUY"
        else cfg.brokerage_sell_bps
    )
    exchange_bps = inr_per_crore_to_bps(
        NSE_TRANSACTION_CHARGE_INR_PER_CRORE
    )
    ipft_bps = inr_per_crore_to_bps(NSE_IPFT_INR_PER_CRORE)
    sebi_bps = inr_per_crore_to_bps(SEBI_TURNOVER_FEE_INR_PER_CRORE)

    line_items: dict[str, dict[str, float]] = {
        "stt": _line_item(notional_inr, stt_bps),
        "stamp_duty": _line_item(notional_inr, stamp_bps),
        "nse_transaction_charge": _line_item(notional_inr, exchange_bps),
        "nse_ipft": _line_item(notional_inr, ipft_bps),
        "sebi_turnover_fee": _line_item(notional_inr, sebi_bps),
        "brokerage": _line_item(notional_inr, brokerage_bps),
    }

    gst_variable_base_inr = sum(
        line_items[name]["inr"]
        for name in (
            "nse_transaction_charge",
            "nse_ipft",
            "sebi_turnover_fee",
            "brokerage",
        )
    )
    dp_charge_inr = (
        float(cfg.dp_sell_charge_inr)
        if normalized_side == "SELL"
        else 0.0
    )
    dp_charge_bps = dp_charge_inr / notional_inr * BPS_PER_UNIT
    line_items["dp_charge"] = {
        "inr": dp_charge_inr,
        "bps": dp_charge_bps,
    }

    gst_base_inr = gst_variable_base_inr
    if cfg.gst_on_dp_sell_charge and normalized_side == "SELL":
        gst_base_inr += dp_charge_inr
    gst_inr = gst_base_inr * GST_RATE
    gst_bps = gst_inr / notional_inr * BPS_PER_UNIT
    line_items["gst"] = {
        "inr": gst_inr,
        "bps": gst_bps,
    }

    total_inr = sum(item["inr"] for item in line_items.values())
    total_bps = total_inr / notional_inr * BPS_PER_UNIT
    return {
        "schema_version": 1,
        "side": normalized_side,
        "notional_inr": float(notional_inr),
        "line_items": line_items,
        "gst_variable_base_convention": (
            "BROKERAGE_PLUS_NSE_TRANSACTION_PLUS_NSE_IPFT_PLUS_SEBI"
        ),
        "gst_on_dp_sell_charge": cfg.gst_on_dp_sell_charge,
        "total_inr": total_inr,
        "total_bps": total_bps,
        "live_capital_allowed": False,
    }


def all_in_side_cost(
    *,
    side: str,
    notional_inr: float,
    adv20_inr: float,
    daily_volatility_decimal: float,
    config: TC001Config | None = None,
) -> dict[str, Any]:
    cfg = config or TC001Config()
    observable = observable_side_cost(
        side=side,
        notional_inr=notional_inr,
        config=cfg,
    )
    normalized_side = side.strip().upper()
    half_spread_bps = (
        cfg.half_spread_buy_bps
        if normalized_side == "BUY"
        else cfg.half_spread_sell_bps
    )
    impact_bps = market_impact_bps(
        order_notional_inr=notional_inr,
        adv20_inr=adv20_inr,
        daily_volatility_decimal=daily_volatility_decimal,
        impact_coefficient=cfg.impact_coefficient,
    )
    half_spread_inr = bps_to_inr(notional_inr, half_spread_bps)
    impact_inr = bps_to_inr(notional_inr, impact_bps)

    total_inr = observable["total_inr"] + half_spread_inr + impact_inr
    total_bps = total_inr / notional_inr * BPS_PER_UNIT
    return {
        **observable,
        "adv20_inr": float(adv20_inr),
        "daily_volatility_decimal": float(daily_volatility_decimal),
        "participation_rate": float(notional_inr) / float(adv20_inr),
        "impact_coefficient": cfg.impact_coefficient,
        "half_spread": {
            "inr": half_spread_inr,
            "bps": float(half_spread_bps),
        },
        "market_impact": {
            "inr": impact_inr,
            "bps": impact_bps,
            "model": "SQUARE_ROOT_PARTICIPATION_SCENARIO_V1",
            "calibrated_to_nse_execution": False,
        },
        "observable_total_inr": observable["total_inr"],
        "observable_total_bps": observable["total_bps"],
        "total_inr": total_inr,
        "total_bps": total_bps,
    }


def round_trip_cost(
    *,
    buy_notional_inr: float,
    sell_notional_inr: float | None = None,
    adv20_inr: float | None = None,
    daily_volatility_decimal: float | None = None,
    config: TC001Config | None = None,
    include_execution_friction: bool = True,
) -> dict[str, Any]:
    cfg = config or TC001Config()
    sell_notional = (
        float(buy_notional_inr)
        if sell_notional_inr is None
        else float(sell_notional_inr)
    )
    if include_execution_friction:
        if adv20_inr is None or daily_volatility_decimal is None:
            raise AlphaContractError(
                "TC001 frictional round trip requires ADV20 and daily volatility"
            )
        buy = all_in_side_cost(
            side="BUY",
            notional_inr=buy_notional_inr,
            adv20_inr=adv20_inr,
            daily_volatility_decimal=daily_volatility_decimal,
            config=cfg,
        )
        sell = all_in_side_cost(
            side="SELL",
            notional_inr=sell_notional,
            adv20_inr=adv20_inr,
            daily_volatility_decimal=daily_volatility_decimal,
            config=cfg,
        )
    else:
        buy = observable_side_cost(
            side="BUY",
            notional_inr=buy_notional_inr,
            config=cfg,
        )
        sell = observable_side_cost(
            side="SELL",
            notional_inr=sell_notional,
            config=cfg,
        )

    reference_notional = (float(buy_notional_inr) + sell_notional) / 2.0
    total_inr = buy["total_inr"] + sell["total_inr"]
    equal_notional_bps = (
        None
        if not math.isclose(float(buy_notional_inr), sell_notional)
        else buy["total_bps"] + sell["total_bps"]
    )
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "model_id": "TC001-v1-DEVELOPMENT",
        "buy": buy,
        "sell": sell,
        "buy_notional_inr": float(buy_notional_inr),
        "sell_notional_inr": sell_notional,
        "total_inr": total_inr,
        "total_bps_on_average_side_notional": (
            total_inr / reference_notional * BPS_PER_UNIT
        ),
        "equal_notional_round_trip_bps": equal_notional_bps,
        "include_execution_friction": include_execution_friction,
        "config": asdict(cfg),
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def portfolio_rebalance_cost_bps(
    *,
    buy_fraction_of_nav: float,
    sell_fraction_of_nav: float,
    buy_cost_bps: float,
    sell_cost_bps: float,
) -> float:
    for name, value in {
        "buy_fraction_of_nav": buy_fraction_of_nav,
        "sell_fraction_of_nav": sell_fraction_of_nav,
    }.items():
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise AlphaContractError(f"TC001 {name} must be in [0, 1]")
    for name, value in {
        "buy_cost_bps": buy_cost_bps,
        "sell_cost_bps": sell_cost_bps,
    }.items():
        if not math.isfinite(value) or value < 0:
            raise AlphaContractError(f"TC001 {name} must be non-negative")
    return (
        float(buy_fraction_of_nav) * float(buy_cost_bps)
        + float(sell_fraction_of_nav) * float(sell_cost_bps)
    )


def equal_weight_replacement_cost_bps(
    *,
    replacement_fraction: float,
    round_trip_cost_bps: float,
) -> float:
    if (
        not math.isfinite(replacement_fraction)
        or not 0.0 <= replacement_fraction <= 1.0
    ):
        raise AlphaContractError(
            "TC001 replacement fraction must be in [0, 1]"
        )
    if not math.isfinite(round_trip_cost_bps) or round_trip_cost_bps < 0:
        raise AlphaContractError(
            "TC001 round-trip cost must be finite and non-negative"
        )
    return float(replacement_fraction) * float(round_trip_cost_bps)


def max_participation_for_alpha(
    *,
    gross_alpha_bps: float,
    required_net_alpha_bps: float,
    nonimpact_round_trip_cost_bps: float,
    daily_volatility_decimal: float,
    impact_coefficient: float,
    maximum_participation: float = 1.0,
) -> float:
    values = {
        "gross_alpha_bps": gross_alpha_bps,
        "required_net_alpha_bps": required_net_alpha_bps,
        "nonimpact_round_trip_cost_bps": nonimpact_round_trip_cost_bps,
        "daily_volatility_decimal": daily_volatility_decimal,
        "impact_coefficient": impact_coefficient,
        "maximum_participation": maximum_participation,
    }
    for name, value in values.items():
        if not math.isfinite(value):
            raise AlphaContractError(f"TC001 {name} must be finite")
    if (
        required_net_alpha_bps < 0
        or nonimpact_round_trip_cost_bps < 0
        or daily_volatility_decimal < 0
        or impact_coefficient < 0
        or not 0 < maximum_participation <= 1
    ):
        raise AlphaContractError("TC001 capacity inputs are outside valid bounds")

    impact_budget_bps = (
        float(gross_alpha_bps)
        - float(required_net_alpha_bps)
        - float(nonimpact_round_trip_cost_bps)
    )
    if impact_budget_bps <= 0:
        return 0.0
    denominator = (
        2.0
        * float(impact_coefficient)
        * float(daily_volatility_decimal)
        * BPS_PER_UNIT
    )
    if denominator == 0:
        return float(maximum_participation)
    participation = (impact_budget_bps / denominator) ** 2
    return min(float(maximum_participation), participation)


def max_order_notional_for_alpha(
    *,
    adv20_inr: float,
    gross_alpha_bps: float,
    required_net_alpha_bps: float,
    nonimpact_round_trip_cost_bps: float,
    daily_volatility_decimal: float,
    impact_coefficient: float,
    maximum_participation: float = 1.0,
) -> dict[str, float]:
    _validate_notional(adv20_inr)
    participation = max_participation_for_alpha(
        gross_alpha_bps=gross_alpha_bps,
        required_net_alpha_bps=required_net_alpha_bps,
        nonimpact_round_trip_cost_bps=nonimpact_round_trip_cost_bps,
        daily_volatility_decimal=daily_volatility_decimal,
        impact_coefficient=impact_coefficient,
        maximum_participation=maximum_participation,
    )
    return {
        "max_participation": participation,
        "max_order_notional_inr": float(adv20_inr) * participation,
    }
