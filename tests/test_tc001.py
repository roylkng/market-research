import pytest

from marketlab.alpha import AlphaContractError
from marketlab.tc001 import (
    TC001Config,
    all_in_side_cost,
    equal_weight_replacement_cost_bps,
    inr_per_crore_to_bps,
    market_impact_bps,
    max_order_notional_for_alpha,
    max_participation_for_alpha,
    observable_side_cost,
    portfolio_rebalance_cost_bps,
    round_trip_cost,
)


def test_inr_per_crore_conversion_is_exact():
    assert inr_per_crore_to_bps(306.99) == pytest.approx(0.30699)
    assert inr_per_crore_to_bps(0.01) == pytest.approx(0.00001)
    assert inr_per_crore_to_bps(10.0) == pytest.approx(0.01)


def test_zero_brokerage_observable_delivery_round_trip_is_frozen_baseline():
    report = round_trip_cost(
        buy_notional_inr=10_000_000,
        include_execution_friction=False,
        config=TC001Config(),
    )
    assert report["buy"]["total_bps"] == pytest.approx(11.87406)
    assert report["sell"]["total_bps"] == pytest.approx(10.37406)
    assert report["equal_notional_round_trip_bps"] == pytest.approx(
        22.24812
    )
    assert report["buy"]["line_items"]["stamp_duty"]["bps"] == pytest.approx(
        1.5
    )
    assert report["sell"]["line_items"]["stamp_duty"]["bps"] == pytest.approx(
        0.0
    )
    assert report["buy"]["line_items"]["stt"]["bps"] == pytest.approx(10.0)
    assert report["sell"]["line_items"]["stt"]["bps"] == pytest.approx(10.0)


def test_gst_base_includes_brokerage_and_variable_regulatory_charges():
    report = observable_side_cost(
        side="BUY",
        notional_inr=1_000_000,
        config=TC001Config(brokerage_buy_bps=5.0),
    )
    # 5.0 brokerage + 0.30699 exchange + 0.00001 IPFT + 0.01 SEBI.
    expected_gst_bps = (5.0 + 0.30699 + 0.00001 + 0.01) * 0.18
    assert report["line_items"]["gst"]["bps"] == pytest.approx(
        expected_gst_bps
    )


def test_fixed_dp_charge_has_notional_dependent_effective_bps():
    config = TC001Config(
        dp_sell_charge_inr=20.0,
        gst_on_dp_sell_charge=True,
    )
    small = observable_side_cost(
        side="SELL",
        notional_inr=100_000,
        config=config,
    )
    large = observable_side_cost(
        side="SELL",
        notional_inr=1_000_000,
        config=config,
    )
    assert small["line_items"]["dp_charge"]["bps"] == pytest.approx(2.0)
    assert large["line_items"]["dp_charge"]["bps"] == pytest.approx(0.2)
    assert small["line_items"]["gst"]["inr"] > large["line_items"]["gst"]["inr"] - 1e-12


def test_square_root_impact_matches_frozen_sensitivity_formula():
    impact = market_impact_bps(
        order_notional_inr=1_000_000,
        adv20_inr=100_000_000,
        daily_volatility_decimal=0.02,
        impact_coefficient=0.50,
    )
    # 50% coefficient * 2% daily vol * 10,000 * sqrt(1% participation).
    assert impact == pytest.approx(10.0)


def test_all_in_cost_adds_spread_and_impact_without_hiding_observable_cost():
    report = all_in_side_cost(
        side="BUY",
        notional_inr=1_000_000,
        adv20_inr=100_000_000,
        daily_volatility_decimal=0.02,
        config=TC001Config(
            half_spread_buy_bps=3.0,
            impact_coefficient=0.50,
        ),
    )
    assert report["market_impact"]["bps"] == pytest.approx(10.0)
    assert report["half_spread"]["bps"] == pytest.approx(3.0)
    assert report["total_bps"] == pytest.approx(
        report["observable_total_bps"] + 13.0
    )
    assert report["market_impact"]["calibrated_to_nse_execution"] is False


def test_equal_weight_replacement_churn_maps_to_round_trip_cost_only_under_contract():
    cost = equal_weight_replacement_cost_bps(
        replacement_fraction=0.3713,
        round_trip_cost_bps=22.24812,
    )
    assert cost == pytest.approx(8.260326956)


def test_buy_sell_turnover_are_modeled_separately():
    cost = portfolio_rebalance_cost_bps(
        buy_fraction_of_nav=0.30,
        sell_fraction_of_nav=0.20,
        buy_cost_bps=12.0,
        sell_cost_bps=10.0,
    )
    assert cost == pytest.approx(5.6)


def test_capacity_inverts_square_root_impact_budget():
    participation = max_participation_for_alpha(
        gross_alpha_bps=60.0,
        required_net_alpha_bps=10.0,
        nonimpact_round_trip_cost_bps=30.0,
        daily_volatility_decimal=0.02,
        impact_coefficient=0.50,
    )
    # 20 bps impact budget = 2 * .5 * .02 * 10000 * sqrt(p)
    # => sqrt(p)=0.1 => p=1%.
    assert participation == pytest.approx(0.01)

    capacity = max_order_notional_for_alpha(
        adv20_inr=200_000_000,
        gross_alpha_bps=60.0,
        required_net_alpha_bps=10.0,
        nonimpact_round_trip_cost_bps=30.0,
        daily_volatility_decimal=0.02,
        impact_coefficient=0.50,
    )
    assert capacity["max_participation"] == pytest.approx(0.01)
    assert capacity["max_order_notional_inr"] == pytest.approx(2_000_000)


def test_no_alpha_budget_means_zero_capacity():
    assert (
        max_participation_for_alpha(
            gross_alpha_bps=20.0,
            required_net_alpha_bps=5.0,
            nonimpact_round_trip_cost_bps=22.0,
            daily_volatility_decimal=0.02,
            impact_coefficient=0.50,
        )
        == 0.0
    )


def test_impact_model_fails_closed_above_100_percent_participation():
    with pytest.raises(AlphaContractError, match="above 100%"):
        market_impact_bps(
            order_notional_inr=101_000_000,
            adv20_inr=100_000_000,
            daily_volatility_decimal=0.02,
            impact_coefficient=0.50,
        )
