import numpy as np
import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.po001 import optimize_portfolio
from marketlab.rm001 import FACTOR_NAMES


def _risk_state():
    rows = []
    exposures = [
        [1.0, -0.2, -0.5, -0.2, 0.1],
        [1.0, 0.0, 0.0, 0.0, 0.0],
        [1.0, 0.2, 0.5, 0.2, -0.1],
    ]
    for index, vector in enumerate(exposures):
        rows.append(
            {
                "symbol": f"S{index}",
                "isin": f"INE{index:09d}",
                "exposures": dict(
                    zip(FACTOR_NAMES, vector, strict=True)
                ),
                "idiosyncratic_variance_daily": 0.0001,
                "idiosyncratic_status": "OBSERVED",
            }
        )
    covariance = np.diag(
        [0.00005, 0.00002, 0.00002, 0.00001, 0.00001]
    ).tolist()
    state = {
        "schema_version": 1,
        "model_id": "RM001-v1-DEVELOPMENT",
        "as_of_session": "2026-09-25",
        "factor_names": list(FACTOR_NAMES),
        "factor_covariance_daily": covariance,
        "rows": rows,
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def _row(index, alpha, *, current=0.0, cost=0.0):
    return {
        "symbol": f"S{index}",
        "isin": f"INE{index:09d}",
        "expected_excess_return": alpha,
        "current_weight": current,
        "buy_cost_bps": cost,
        "sell_cost_bps": cost,
    }


def test_po001_prefers_higher_alpha_when_risk_and_cost_are_small():
    result = optimize_portfolio(
        decision_session="2026-09-25",
        horizon_sessions=5,
        alpha_rows=[
            _row(0, 0.01),
            _row(1, 0.02),
            _row(2, 0.04),
        ],
        risk_state=_risk_state(),
        risk_aversion=0.0,
        max_name_weight=0.50,
        max_invested_weight=1.0,
        max_traded_fraction_of_nav=1.0,
        terminal_liquidation=False,
    )
    weights = {
        row["symbol"]: row["target_weight"]
        for row in result["rows"]
    }
    assert weights["S2"] == pytest.approx(0.5, abs=1e-5)
    assert weights["S1"] == pytest.approx(0.5, abs=1e-5)
    assert weights["S0"] == pytest.approx(0.0, abs=1e-5)
    assert result["invested_weight"] == pytest.approx(1.0)


def test_po001_transaction_cost_can_prevent_marginal_rebalance():
    result = optimize_portfolio(
        decision_session="2026-09-25",
        horizon_sessions=5,
        alpha_rows=[
            _row(0, 0.0200, current=0.5, cost=0.0),
            _row(1, 0.0201, current=0.0, cost=100.0),
            _row(2, 0.0, current=0.0, cost=100.0),
        ],
        risk_state=_risk_state(),
        risk_aversion=0.0,
        max_name_weight=0.50,
        max_invested_weight=0.50,
        max_traded_fraction_of_nav=1.0,
        terminal_liquidation=False,
    )
    weights = {
        row["symbol"]: row["target_weight"]
        for row in result["rows"]
    }
    assert weights["S0"] > 0.49
    assert weights["S1"] < 0.01
    assert result["traded_fraction_of_nav"] < 0.02


def test_po001_honors_factor_exposure_bound():
    result = optimize_portfolio(
        decision_session="2026-09-25",
        horizon_sessions=5,
        alpha_rows=[
            _row(0, 0.01),
            _row(1, 0.02),
            _row(2, 0.05),
        ],
        risk_state=_risk_state(),
        risk_aversion=0.0,
        max_name_weight=0.60,
        max_invested_weight=1.0,
        max_traded_fraction_of_nav=1.0,
        factor_bounds={
            "MOMENTUM20": {"min": -0.05, "max": 0.05},
        },
        terminal_liquidation=False,
    )
    exposure = result["portfolio_factor_exposures"]["MOMENTUM20"]
    assert -0.050001 <= exposure <= 0.050001
    assert result["solver"]["success"] is True


def test_po001_risk_penalty_reduces_concentration():
    no_risk = optimize_portfolio(
        decision_session="2026-09-25",
        horizon_sessions=5,
        alpha_rows=[
            _row(0, 0.01),
            _row(1, 0.011),
            _row(2, 0.012),
        ],
        risk_state=_risk_state(),
        risk_aversion=0.0,
        max_name_weight=1.0,
        max_invested_weight=1.0,
        max_traded_fraction_of_nav=1.0,
        terminal_liquidation=False,
    )
    risk_aware = optimize_portfolio(
        decision_session="2026-09-25",
        horizon_sessions=5,
        alpha_rows=[
            _row(0, 0.01),
            _row(1, 0.011),
            _row(2, 0.012),
        ],
        risk_state=_risk_state(),
        risk_aversion=50.0,
        max_name_weight=1.0,
        max_invested_weight=1.0,
        max_traded_fraction_of_nav=1.0,
        terminal_liquidation=False,
    )
    max_no_risk = max(row["target_weight"] for row in no_risk["rows"])
    max_risk = max(row["target_weight"] for row in risk_aware["rows"])
    assert max_risk < max_no_risk


def test_po001_terminal_liquidation_uses_sell_cost_on_target_weight():
    result = optimize_portfolio(
        decision_session="2026-09-25",
        horizon_sessions=5,
        alpha_rows=[
            _row(0, 0.02, cost=20.0),
            _row(1, 0.0, cost=20.0),
            _row(2, 0.0, cost=20.0),
        ],
        risk_state=_risk_state(),
        risk_aversion=0.0,
        max_name_weight=0.5,
        max_invested_weight=0.5,
        max_traded_fraction_of_nav=0.5,
        terminal_liquidation=True,
    )
    assert result["terminal_liquidation_cost_fraction"] == pytest.approx(
        result["invested_weight"] * 20.0 / 10_000.0,
        abs=1e-8,
    )


def test_po001_refuses_risk_clock_mismatch():
    with pytest.raises(AlphaContractError, match="decision session differs"):
        optimize_portfolio(
            decision_session="2026-09-24",
            horizon_sessions=5,
            alpha_rows=[
                _row(0, 0.01),
                _row(1, 0.01),
                _row(2, 0.01),
            ],
            risk_state=_risk_state(),
            risk_aversion=1.0,
        )


def test_po001_refuses_infeasible_factor_bound():
    with pytest.raises(AlphaContractError, match="optimizer failed closed"):
        optimize_portfolio(
            decision_session="2026-09-25",
            horizon_sessions=5,
            alpha_rows=[
                _row(0, 0.01),
                _row(1, 0.02),
                _row(2, 0.03),
            ],
            risk_state=_risk_state(),
            risk_aversion=1.0,
            max_name_weight=0.5,
            factor_bounds={
                "MOMENTUM20": {"min": 2.0, "max": 3.0},
            },
        )
