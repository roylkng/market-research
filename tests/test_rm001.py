import math

import numpy as np
import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001 import (
    FACTOR_NAMES,
    _fit_factor_return,
    build_rm001_risk_state,
    portfolio_risk,
    trailing_beta60,
)


def test_trailing_beta60_recovers_known_linear_beta():
    benchmark_returns = np.asarray(
        [0.001 * ((index % 7) - 3) for index in range(60)],
        dtype=float,
    )
    stock_returns = 1.5 * benchmark_returns + 0.0002
    benchmark = [100.0]
    stock = [80.0]
    for benchmark_return, stock_return in zip(
        benchmark_returns,
        stock_returns,
        strict=True,
    ):
        benchmark.append(benchmark[-1] * (1.0 + benchmark_return))
        stock.append(stock[-1] * (1.0 + stock_return))

    assert trailing_beta60(stock, benchmark) == pytest.approx(1.5)


def test_factor_regression_recovers_known_coefficients():
    true = np.asarray([0.001, 0.002, -0.0015, 0.0008, 0.0012])
    rows = []
    realized = {}
    for index in range(120):
        exposures = np.asarray(
            [
                1.0,
                (index - 60) / 60.0,
                ((index * 7) % 101) / 50.0 - 1.0,
                ((index * 11) % 103) / 51.0 - 1.0,
                ((index * 13) % 107) / 53.0 - 1.0,
            ],
            dtype=float,
        )
        symbol = f"S{index:03d}"
        isin = f"INE{index:09d}"
        rows.append(
            {
                "symbol": symbol,
                "isin": isin,
                "exposures": dict(
                    zip(FACTOR_NAMES, exposures.tolist(), strict=True)
                ),
            }
        )
        realized[(symbol, isin)] = float(exposures @ true)

    factors, residuals = _fit_factor_return(rows, realized)
    assert len(residuals) == 120
    for idx, factor in enumerate(FACTOR_NAMES):
        assert factors[factor] == pytest.approx(true[idx], abs=1e-12)
    assert max(abs(row["residual_return"]) for row in residuals) < 1e-12


def _exposure_panel():
    rows = []
    for index in range(2):
        rows.append(
            {
                "session_date": "2026-09-25",
                "symbol": f"S{index}",
                "isin": f"INE{index:09d}",
                "exposures": {
                    "MARKET_COMMON": 1.0,
                    "BETA60_RELATIVE": 0.2 * index,
                    "MOMENTUM20": 0.1 * (index + 1),
                    "VOLATILITY60": -0.1 * index,
                    "LIQUIDITY": 0.3 - 0.2 * index,
                },
            }
        )
    panel = {
        "schema_version": 1,
        "model_id": "RM001-v1-DEVELOPMENT",
        "factor_names": list(FACTOR_NAMES),
        "input_feature_panel_sha256": "a" * 64,
        "input_ranked_feature_panel_sha256": "b" * 64,
        "input_market_panel_sha256": "c" * 64,
        "corporate_action_ledger_sha256": "d" * 64,
        "exposure_count": len(rows),
        "exclusions": {},
        "rows": rows,
        "deferred_factors": {
            "SIZE": "POINT_IN_TIME_MARKET_CAP_SOURCE_NOT_FROZEN",
            "SECTOR": "POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN",
        },
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _factor_history(exposure_panel):
    factor_returns = []
    residuals = []
    start = np.datetime64("2026-06-01")
    for index in range(60):
        day = str(start + np.timedelta64(index, "D"))
        factor_returns.append(
            {
                "exposure_session": day,
                "realized_session": day,
                "factor_returns": {
                    "MARKET_COMMON": 0.001 + index * 1e-6,
                    "BETA60_RELATIVE": 0.0002 * ((index % 3) - 1),
                    "MOMENTUM20": 0.0003 * ((index % 5) - 2),
                    "VOLATILITY60": -0.0001 * ((index % 7) - 3),
                    "LIQUIDITY": 0.00015 * ((index % 4) - 1.5),
                },
                "observation_count": 200,
            }
        )
        for stock_index in range(2):
            residuals.append(
                {
                    "exposure_session": day,
                    "realized_session": day,
                    "symbol": f"S{stock_index}",
                    "isin": f"INE{stock_index:09d}",
                    "residual_return": (
                        (stock_index + 1) * 0.0002 * ((index % 5) - 2)
                    ),
                }
            )
    history = {
        "schema_version": 1,
        "model_id": "RM001-v1-DEVELOPMENT",
        "factor_names": list(FACTOR_NAMES),
        "exposure_panel_sha256": exposure_panel["panel_sha256"],
        "market_panel_sha256": "c" * 64,
        "corporate_action_ledger_sha256": "d" * 64,
        "factor_return_count": len(factor_returns),
        "residual_count": len(residuals),
        "factor_returns": factor_returns,
        "residuals": residuals,
        "exclusions": {},
        "live_capital_allowed": False,
    }
    history["history_sha256"] = digest(history)
    return history


def test_risk_state_uses_only_realized_history_and_observed_idio_variance():
    exposure_panel = _exposure_panel()
    history = _factor_history(exposure_panel)
    state = build_rm001_risk_state(
        exposure_panel=exposure_panel,
        factor_history=history,
        as_of_session="2026-09-25",
    )
    assert state["security_count"] == 2
    assert state["factor_covariance_window"] == 60
    assert len(state["factor_covariance_daily"]) == len(FACTOR_NAMES)
    assert all(
        row["idiosyncratic_status"] == "OBSERVED"
        for row in state["rows"]
    )
    assert len(state["state_sha256"]) == 64


def test_portfolio_risk_matches_direct_matrix_algebra():
    exposure_panel = _exposure_panel()
    history = _factor_history(exposure_panel)
    state = build_rm001_risk_state(
        exposure_panel=exposure_panel,
        factor_history=history,
        as_of_session="2026-09-25",
    )
    positions = [
        {"symbol": "S0", "isin": "INE000000000", "weight": 0.4},
        {"symbol": "S1", "isin": "INE000000001", "weight": 0.5},
    ]
    report = portfolio_risk(state, positions=positions)

    weights = np.asarray([0.4, 0.5])
    exposure_matrix = np.asarray(
        [
            [state["rows"][0]["exposures"][factor] for factor in FACTOR_NAMES],
            [state["rows"][1]["exposures"][factor] for factor in FACTOR_NAMES],
        ]
    )
    factor_vector = weights @ exposure_matrix
    covariance = np.asarray(state["factor_covariance_daily"])
    expected_factor = float(factor_vector @ covariance @ factor_vector)
    idio = np.asarray(
        [row["idiosyncratic_variance_daily"] for row in state["rows"]]
    )
    expected_idio = float(np.sum((weights**2) * idio))

    assert report["factor_variance_daily"] == pytest.approx(expected_factor)
    assert report["idiosyncratic_variance_daily"] == pytest.approx(
        expected_idio
    )
    assert report["total_variance_daily"] == pytest.approx(
        expected_factor + expected_idio
    )
    assert report["annualized_volatility"] == pytest.approx(
        math.sqrt((expected_factor + expected_idio) * 252)
    )
    assert report["cash_weight"] == pytest.approx(0.1)


def test_portfolio_risk_refuses_leverage_in_v1():
    exposure_panel = _exposure_panel()
    history = _factor_history(exposure_panel)
    state = build_rm001_risk_state(
        exposure_panel=exposure_panel,
        factor_history=history,
        as_of_session="2026-09-25",
    )
    with pytest.raises(AlphaContractError, match="cannot exceed 1"):
        portfolio_risk(
            state,
            positions=[
                {"symbol": "S0", "isin": "INE000000000", "weight": 0.6},
                {"symbol": "S1", "isin": "INE000000001", "weight": 0.6},
            ],
        )
