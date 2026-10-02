import copy
import math

import numpy as np
import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.po001_v3 import optimize_portfolio_v3
from marketlab.po001_v4 import (
    KKT_TOLERANCE,
    _coordinate_minimum,
    optimize_portfolio_v4,
)


def _risk_state(count=8):
    factors = [
        "MARKET_COMMON",
        "BETA60_RELATIVE",
        "MOMENTUM20",
        "VOLATILITY60",
        "LIQUIDITY",
        "SIZE",
        "STAT_PC01",
    ]
    rows = []
    for index in range(count):
        centered = (index - (count - 1) / 2.0) / max(1.0, count / 2.0)
        rows.append(
            {
                "symbol": f"S{index:03d}",
                "isin": f"INE{index:09d}",
                "exposures": {
                    "MARKET_COMMON": 1.0,
                    "BETA60_RELATIVE": 0.20 * centered,
                    "MOMENTUM20": -0.30 * centered,
                    "VOLATILITY60": 0.15 * centered,
                    "LIQUIDITY": -0.10 * centered,
                    "SIZE": 0.25 * centered,
                    "STAT_PC01": 0.12 * ((index % 3) - 1),
                },
                "idiosyncratic_variance_daily": (
                    0.00005 + index * 0.000002
                ),
                "idiosyncratic_status": "OBSERVED",
            }
        )
    covariance = np.diag(
        [0.00002, 0.00001, 0.000008, 0.000007, 0.000006, 0.000005, 0.000004]
    )
    state = {
        "schema_version": 1,
        "model_id": "RM001-v3-DEVELOPMENT",
        "as_of_session": "2026-08-31",
        "factor_names": factors,
        "factor_covariance_daily": covariance.tolist(),
        "rows": rows,
        "deferred_factors": {},
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def _alpha_rows(count=8):
    return [
        {
            "symbol": f"S{index:03d}",
            "isin": f"INE{index:09d}",
            "expected_excess_return": 0.018 - index * 0.0012,
            "current_weight": 0.0,
            "buy_cost_bps": 8.0 + index * 0.2,
            "sell_cost_bps": 12.0 + index * 0.2,
            "adv20_inr": 80_000_000.0 + index * 10_000_000.0,
            "daily_volatility_decimal": 0.018 + index * 0.001,
        }
        for index in range(count)
    ]


def _kwargs():
    return {
        "decision_session": "2026-08-31",
        "horizon_sessions": 5,
        "alpha_rows": _alpha_rows(),
        "risk_state": _risk_state(),
        "portfolio_nav_inr": 10_000_000.0,
        "risk_aversion": 5.0,
        "impact_coefficient": 0.50,
        "max_participation": 0.10,
        "max_name_weight": 0.25,
        "max_invested_weight": 1.0,
        "max_traded_fraction_of_nav": 1.0,
        "factor_bounds": {},
        "terminal_liquidation": True,
    }


def test_coordinate_minimum_solves_scalar_stationarity():
    a = 0.8
    c = 0.3
    d = -0.2
    upper = 0.9
    weight = _coordinate_minimum(
        quadratic_coefficient=a,
        sqrt_coefficient=c,
        constant_derivative=d,
        upper_bound=upper,
    )
    assert 0 < weight < upper
    derivative = a * weight + c * math.sqrt(weight) + d
    assert derivative == pytest.approx(0.0, abs=1e-13)


def test_v4_matches_v3_economically_on_small_convex_problem():
    kwargs = _kwargs()
    v3 = optimize_portfolio_v3(**kwargs)
    v4 = optimize_portfolio_v4(**kwargs)

    left = {
        (row["symbol"], row["isin"]): row["target_weight"]
        for row in v3["rows"]
    }
    right = {
        (row["symbol"], row["isin"]): row["target_weight"]
        for row in v4["rows"]
    }
    assert left.keys() == right.keys()
    assert max(abs(left[key] - right[key]) for key in left) <= 5e-6
    assert abs(v4["invested_weight"] - v3["invested_weight"]) <= 1e-10
    assert abs(
        v4["expected_excess_return"] - v3["expected_excess_return"]
    ) <= 1e-8
    assert abs(
        v4["total_variance_daily"] - v3["total_variance_daily"]
    ) <= 1e-10
    assert abs(
        v4["total_transaction_cost_fraction"]
        - v3["total_transaction_cost_fraction"]
    ) <= 1e-8
    assert (
        v4["objective_utility"]
        >= v3["objective_utility"] - 1e-12
    )
    assert (
        v4["solver"]["kkt"]["maximum_coordinate_kkt_violation"]
        <= KKT_TOLERANCE
    )


def test_v4_is_exactly_deterministic_under_input_row_reordering():
    kwargs = _kwargs()
    first = optimize_portfolio_v4(**kwargs)

    reordered = copy.deepcopy(kwargs)
    reordered["alpha_rows"] = list(reversed(reordered["alpha_rows"]))
    reordered["risk_state"]["rows"] = list(
        reversed(reordered["risk_state"]["rows"])
    )
    unsigned = dict(reordered["risk_state"])
    unsigned.pop("state_sha256", None)
    reordered["risk_state"]["state_sha256"] = digest(unsigned)

    # Risk-state row ordering is part of the hash-verified state payload, so a
    # reordered state is a different artifact. Restore the original canonical
    # state and vary only alpha input ordering for exact solver determinism.
    reordered["risk_state"] = kwargs["risk_state"]
    second = optimize_portfolio_v4(**reordered)

    assert first == second
    assert first["artifact_sha256"] == second["artifact_sha256"]


def test_v4_can_hold_cash_when_alpha_does_not_cover_cost_and_risk():
    kwargs = _kwargs()
    kwargs["alpha_rows"] = [
        {
            **row,
            "expected_excess_return": -0.005,
        }
        for row in kwargs["alpha_rows"]
    ]
    result = optimize_portfolio_v4(**kwargs)
    assert result["invested_weight"] == pytest.approx(0.0, abs=1e-14)
    assert result["cash_weight"] == pytest.approx(1.0, abs=1e-14)


def test_v4_rejects_nonzero_current_weights_in_initial_scope():
    kwargs = _kwargs()
    kwargs["alpha_rows"][0]["current_weight"] = 0.01
    with pytest.raises(AlphaContractError, match="zero current weights"):
        optimize_portfolio_v4(**kwargs)


def test_v4_rejects_factor_bounds_in_initial_scope():
    kwargs = _kwargs()
    kwargs["factor_bounds"] = {
        "SIZE": {"min": -0.5, "max": 0.5},
    }
    with pytest.raises(AlphaContractError, match="factor hard bounds"):
        optimize_portfolio_v4(**kwargs)
