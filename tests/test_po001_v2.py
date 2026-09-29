import math

import numpy as np
import pytest

from marketlab.alpha import digest
from marketlab.po001_v2 import (
    impact_cost_fraction,
    optimize_portfolio_v2,
)
from marketlab.rm001 import FACTOR_NAMES


def _risk_state():
    rows = []
    for index in range(3):
        rows.append(
            {
                "symbol": f"S{index}",
                "isin": f"INE{index:09d}",
                "exposures": {
                    "MARKET_COMMON": 1.0,
                    "BETA60_RELATIVE": 0.0,
                    "MOMENTUM20": 0.0,
                    "VOLATILITY60": 0.0,
                    "LIQUIDITY": 0.0,
                },
                "idiosyncratic_variance_daily": 0.00001,
                "idiosyncratic_status": "OBSERVED",
            }
        )
    state = {
        "schema_version": 1,
        "model_id": "RM001-v1-DEVELOPMENT",
        "as_of_session": "2026-08-31",
        "factor_names": list(FACTOR_NAMES),
        "factor_covariance_daily": np.diag(
            [0.00001, 0.00001, 0.00001, 0.00001, 0.00001]
        ).tolist(),
        "rows": rows,
        "deferred_factors": {
            "SIZE": "POINT_IN_TIME_MARKET_CAP_SOURCE_NOT_FROZEN",
            "SECTOR": "POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN",
        },
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def _row(index, *, alpha=0.02, adv=100_000_000.0, vol=0.02):
    return {
        "symbol": f"S{index}",
        "isin": f"INE{index:09d}",
        "expected_excess_return": alpha,
        "current_weight": 0.0,
        "buy_cost_bps": 0.0,
        "sell_cost_bps": 0.0,
        "adv20_inr": adv,
        "daily_volatility_decimal": vol,
    }


def test_impact_cost_fraction_matches_tc001_square_root_formula():
    observed = impact_cost_fraction(
        order_fraction_of_nav=0.05,
        portfolio_nav_inr=10_000_000.0,
        adv20_inr=20_000_000.0,
        daily_volatility_decimal=0.02,
        impact_coefficient=0.50,
    )
    participation = 0.05 * 10_000_000.0 / 20_000_000.0
    expected_bps = 0.50 * 0.02 * 10_000.0 * math.sqrt(participation)
    expected_fraction = 0.05 * expected_bps / 10_000.0
    assert observed == pytest.approx(expected_fraction)


def test_v2_prefers_more_liquid_name_when_alpha_and_risk_match():
    result = optimize_portfolio_v2(
        decision_session="2026-08-31",
        horizon_sessions=5,
        alpha_rows=[
            _row(0, adv=500_000_000.0),
            _row(1, adv=50_000_000.0),
            _row(2, adv=20_000_000.0),
        ],
        risk_state=_risk_state(),
        portfolio_nav_inr=10_000_000.0,
        risk_aversion=0.0,
        impact_coefficient=0.50,
        max_participation=0.10,
        max_name_weight=0.60,
        max_invested_weight=1.0,
        max_traded_fraction_of_nav=1.0,
        terminal_liquidation=True,
    )
    weights = {
        row["symbol"]: row["target_weight"]
        for row in result["rows"]
    }
    assert weights["S0"] > weights["S1"] > weights["S2"]
    assert result["immediate_impact_cost_fraction"] > 0
    assert result["terminal_impact_cost_fraction"] > 0
    assert result["maximum_observed_participation"] <= 0.1000001


def test_v2_participation_cap_can_force_cash():
    result = optimize_portfolio_v2(
        decision_session="2026-08-31",
        horizon_sessions=5,
        alpha_rows=[
            _row(0, alpha=0.10, adv=1_000_000.0),
            _row(1, alpha=0.09, adv=1_000_000.0),
            _row(2, alpha=0.08, adv=1_000_000.0),
        ],
        risk_state=_risk_state(),
        portfolio_nav_inr=100_000_000.0,
        risk_aversion=0.0,
        impact_coefficient=0.50,
        max_participation=0.10,
        max_name_weight=1.0,
        max_invested_weight=1.0,
        max_traded_fraction_of_nav=1.0,
        terminal_liquidation=True,
    )
    # Each name can carry at most 0.1 * 1m / 100m = 0.1%.
    assert result["invested_weight"] <= pytest.approx(0.003, abs=1e-6)
    assert result["cash_weight"] >= 0.9969


def test_v2_zero_impact_reduces_to_linear_observable_cost_surface():
    result = optimize_portfolio_v2(
        decision_session="2026-08-31",
        horizon_sessions=5,
        alpha_rows=[
            _row(0, alpha=0.03, adv=1_000_000_000.0, vol=0.0),
            _row(1, alpha=0.02, adv=1_000_000_000.0, vol=0.0),
            _row(2, alpha=0.01, adv=1_000_000_000.0, vol=0.0),
        ],
        risk_state=_risk_state(),
        portfolio_nav_inr=1_000_000.0,
        risk_aversion=0.0,
        impact_coefficient=0.50,
        max_participation=0.10,
        max_name_weight=0.5,
        max_invested_weight=1.0,
        max_traded_fraction_of_nav=1.0,
        terminal_liquidation=True,
    )
    assert result["immediate_impact_cost_fraction"] == pytest.approx(0.0)
    assert result["terminal_impact_cost_fraction"] == pytest.approx(0.0)
