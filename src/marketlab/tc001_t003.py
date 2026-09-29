from __future__ import annotations

from typing import Any

from marketlab.alpha import AlphaContractError
from marketlab.tc001 import (
    TC001Config,
    equal_weight_replacement_cost_bps,
    round_trip_cost,
)


def _bps(decimal_return: float) -> float:
    return float(decimal_return) * 10_000.0


def _cohort_view(model: dict[str, Any], round_trip_bps: float) -> dict[str, float]:
    """Cost one independently held 5D cohort on the same 5D return clock."""

    gross_bps = _bps(float(model["mean_top_decile_excess"]))
    return {
        "gross_5d_top_decile_excess_bps": gross_bps,
        "full_cohort_round_trip_cost_bps": float(round_trip_bps),
        "net_5d_excess_after_full_round_trip_bps": (
            gross_bps - float(round_trip_bps)
        ),
        "cohort_break_even_round_trip_cost_bps": gross_bps,
    }


def _turnover_pressure(
    model: dict[str, Any],
    round_trip_bps: float,
) -> dict[str, float]:
    """Report daily selection-replacement pressure without netting it into 5D labels."""

    churn = float(model["average_top_decile_selection_churn"])
    drag = equal_weight_replacement_cost_bps(
        replacement_fraction=churn,
        round_trip_cost_bps=float(round_trip_bps),
    )
    return {
        "daily_selection_churn": churn,
        "daily_replacement_cost_proxy_bps": drag,
    }


def build_t003_tc001_report(source: dict[str, Any]) -> dict[str, Any]:
    if int(source.get("horizon_sessions") or 0) != 5:
        raise AlphaContractError("T003 TC001 overlay requires the frozen 5D horizon")

    base = source["base"]
    augmented = source["augmented"]

    observable = round_trip_cost(
        buy_notional_inr=10_000_000,
        config=TC001Config(),
        include_execution_friction=False,
    )
    observable_rt = float(observable["equal_notional_round_trip_bps"])

    def surface(round_trip_bps: float) -> dict[str, Any]:
        base_cohort = _cohort_view(base, round_trip_bps)
        augmented_cohort = _cohort_view(augmented, round_trip_bps)
        base_turnover = _turnover_pressure(base, round_trip_bps)
        augmented_turnover = _turnover_pressure(augmented, round_trip_bps)
        return {
            "round_trip_cost_bps": float(round_trip_bps),
            "cohort_5d": {
                "base": base_cohort,
                "augmented": augmented_cohort,
                "augmented_minus_base_net_5d_excess_bps": (
                    augmented_cohort[
                        "net_5d_excess_after_full_round_trip_bps"
                    ]
                    - base_cohort[
                        "net_5d_excess_after_full_round_trip_bps"
                    ]
                ),
                "equal_cost_assumption_causes_common_cost_to_cancel_in_delta": True,
            },
            "daily_selection_turnover_pressure": {
                "base": base_turnover,
                "augmented": augmented_turnover,
                "augmented_minus_base_daily_replacement_cost_proxy_bps": (
                    augmented_turnover["daily_replacement_cost_proxy_bps"]
                    - base_turnover["daily_replacement_cost_proxy_bps"]
                ),
                "may_be_subtracted_from_5d_forward_label": False,
            },
        }

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
        cost = round_trip_cost(
            buy_notional_inr=notional,
            adv20_inr=adv,
            daily_volatility_decimal=float(
                scenario["daily_volatility_decimal"]
            ),
            config=config,
            include_execution_friction=True,
        )
        round_trip_bps = float(cost["equal_notional_round_trip_bps"])
        scenarios[name] = {
            **scenario,
            "impact_bps_each_side": cost["buy"]["market_impact"]["bps"],
            **surface(round_trip_bps),
        }

    gross_delta_bps = (
        _bps(float(augmented["mean_top_decile_excess"]))
        - _bps(float(base["mean_top_decile_excess"]))
    )

    report = {
        "schema_version": 2,
        "analysis_id": source["analysis_id"],
        "source_run_id": source["source_run_id"],
        "source_report_sha256": source["source_report_sha256"],
        "evidence_class": source["evidence_class"],
        "horizon_sessions": 5,
        "gross_augmented_minus_base_top_decile_excess_bps": gross_delta_bps,
        "observable_cost_floor": {
            "equal_notional_round_trip_bps": observable_rt,
            **surface(observable_rt),
        },
        "illustrative_execution_scenarios": scenarios,
        "paired_augmented_minus_base": source["paired_augmented_minus_base"],
        "interpretation_limits": {
            **source["cost_interpretation"],
            "forward_return_clock": "FIVE_SESSION_COHORT",
            "selection_churn_clock": "CONSECUTIVE_DAILY_DECISIONS",
            "mixed_clock_netting_prohibited": True,
            "rolling_portfolio_path_constructed": False,
            "cohort_cost_method": (
                "SUBTRACT_ONE_FULL_ROUND_TRIP_FROM_EACH_5D_COHORT_RETURN"
            ),
            "daily_churn_cost_method": (
                "REPORT_REPLACEMENT_COST_PRESSURE_SEPARATELY_ONLY"
            ),
            "net_rolling_portfolio_pnl_estimated": False,
        },
        "tc001_impact_model_calibrated_to_nse_execution": False,
        "tc001_does_not_establish_prospective_alpha": True,
        "live_capital_allowed": False,
    }
    return report
