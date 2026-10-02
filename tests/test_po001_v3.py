import numpy as np
import pytest

from marketlab.alpha import digest
from marketlab.po001_v2 import optimize_portfolio_v2
from marketlab.po001_v3 import optimize_portfolio_v3
from marketlab.rm001 import FACTOR_NAMES


def _risk_state_v1():
    rows = []
    for index in range(4):
        rows.append(
            {
                "symbol": f"S{index}",
                "isin": f"INE{index:09d}",
                "exposures": {
                    "MARKET_COMMON": 1.0,
                    "BETA60_RELATIVE": 0.1 * index,
                    "MOMENTUM20": -0.2 + 0.1 * index,
                    "VOLATILITY60": 0.15 - 0.05 * index,
                    "LIQUIDITY": -0.1 + 0.08 * index,
                },
                "idiosyncratic_variance_daily": (
                    0.00001 + index * 0.000002
                ),
                "idiosyncratic_status": "OBSERVED",
            }
        )
    state = {
        "schema_version": 1,
        "model_id": "RM001-v1-DEVELOPMENT",
        "as_of_session": "2026-08-31",
        "factor_names": list(FACTOR_NAMES),
        "factor_covariance_daily": np.diag(
            [0.00001, 0.000008, 0.000007, 0.000006, 0.000005]
        ).tolist(),
        "rows": rows,
        "deferred_factors": {},
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def _alpha_rows():
    return [
        {
            "symbol": f"S{index}",
            "isin": f"INE{index:09d}",
            "expected_excess_return": 0.03 - index * 0.004,
            "current_weight": 0.0,
            "buy_cost_bps": 10.0 + index,
            "sell_cost_bps": 12.0 + index,
            "adv20_inr": 100_000_000.0 - index * 10_000_000.0,
            "daily_volatility_decimal": 0.02 + index * 0.002,
        }
        for index in range(4)
    ]


def test_po001_v3_is_economically_equivalent_to_v2_on_v1_risk():
    kwargs = {
        "decision_session": "2026-08-31",
        "horizon_sessions": 5,
        "alpha_rows": _alpha_rows(),
        "risk_state": _risk_state_v1(),
        "portfolio_nav_inr": 10_000_000.0,
        "risk_aversion": 5.0,
        "impact_coefficient": 0.50,
        "max_participation": 0.10,
        "max_name_weight": 0.40,
        "max_invested_weight": 1.0,
        "max_traded_fraction_of_nav": 1.0,
        "factor_bounds": {},
        "terminal_liquidation": True,
    }
    control = optimize_portfolio_v2(**kwargs)
    challenger = optimize_portfolio_v3(**kwargs)

    control_weights = {
        (row["symbol"], row["isin"]): row["target_weight"]
        for row in control["rows"]
    }
    challenger_weights = {
        (row["symbol"], row["isin"]): row["target_weight"]
        for row in challenger["rows"]
    }
    assert control_weights.keys() == challenger_weights.keys()
    assert max(
        abs(control_weights[key] - challenger_weights[key])
        for key in control_weights
    ) <= 1e-10

    for field in (
        "expected_excess_return",
        "factor_variance_daily",
        "idiosyncratic_variance_daily",
        "total_variance_daily",
        "immediate_observable_cost_fraction",
        "immediate_impact_cost_fraction",
        "terminal_observable_cost_fraction",
        "terminal_impact_cost_fraction",
        "total_transaction_cost_fraction",
        "objective_utility",
    ):
        assert challenger[field] == pytest.approx(
            control[field],
            abs=1e-12,
        )


def _risk_state_v3():
    factors = [
        "MARKET_COMMON",
        "BETA60_RELATIVE",
        "MOMENTUM20",
        "VOLATILITY60",
        "LIQUIDITY",
        "SIZE",
        "STAT_PC01",
        "STAT_PC02",
        "STAT_PC03",
        "STAT_PC04",
        "STAT_PC05",
    ]
    rows = []
    for index in range(4):
        exposures = {
            factor: (
                1.0
                if factor == "MARKET_COMMON"
                else 0.03 * (index + 1) * (factor_index + 1)
            )
            for factor_index, factor in enumerate(factors)
        }
        rows.append(
            {
                "symbol": f"S{index}",
                "isin": f"INE{index:09d}",
                "exposures": exposures,
                "idiosyncratic_variance_daily": (
                    0.00001 + index * 0.000002
                ),
                "idiosyncratic_status": "OBSERVED",
                "statistical_status": "COMPLETE_STAT_HISTORY",
            }
        )
    covariance = np.diag(
        [0.00001 + index * 0.000001 for index in range(len(factors))]
    )
    state = {
        "schema_version": 1,
        "model_id": "RM001-v3-DEVELOPMENT",
        "as_of_session": "2026-08-31",
        "factor_names": factors,
        "factor_covariance_daily": covariance.tolist(),
        "rows": rows,
        "deferred_factors": {
            "SECTOR": "POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN"
        },
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def test_po001_v3_accepts_full_rm001_v3_factor_set_and_bounds():
    result = optimize_portfolio_v3(
        decision_session="2026-08-31",
        horizon_sessions=5,
        alpha_rows=_alpha_rows(),
        risk_state=_risk_state_v3(),
        portfolio_nav_inr=10_000_000.0,
        risk_aversion=5.0,
        impact_coefficient=0.50,
        max_participation=0.10,
        max_name_weight=0.40,
        max_invested_weight=1.0,
        max_traded_fraction_of_nav=1.0,
        factor_bounds={
            "STAT_PC01": {"min": -1.0, "max": 1.0},
            "SIZE": {"min": -1.0, "max": 1.0},
        },
        terminal_liquidation=True,
    )
    assert result["optimizer_id"] == "PO001-v3-DEVELOPMENT"
    assert set(result["portfolio_factor_exposures"]) == set(
        _risk_state_v3()["factor_names"]
    )
    assert set(result["factor_bounds"]) == {"SIZE", "STAT_PC01"}
    assert result["solver"]["success"] is True


def test_po001_v3_rejects_exposure_factor_mismatch():
    state = _risk_state_v3()
    state["rows"][0]["exposures"].pop("STAT_PC05")
    unsigned = dict(state)
    unsigned.pop("state_sha256", None)
    state["state_sha256"] = digest(unsigned)

    with pytest.raises(Exception, match="exposure factor set mismatch"):
        optimize_portfolio_v3(
            decision_session="2026-08-31",
            horizon_sessions=5,
            alpha_rows=_alpha_rows(),
            risk_state=state,
            portfolio_nav_inr=10_000_000.0,
            risk_aversion=5.0,
            impact_coefficient=0.50,
            max_participation=0.10,
            max_name_weight=0.40,
            max_invested_weight=1.0,
            max_traded_fraction_of_nav=1.0,
            factor_bounds={},
            terminal_liquidation=True,
        )
