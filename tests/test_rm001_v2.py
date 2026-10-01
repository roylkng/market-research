from datetime import date, timedelta

import numpy as np
import pytest

from marketlab.alpha import digest
from marketlab.rm001_v2 import (
    FACTOR_NAMES_V2,
    _fit_factor_return_v2,
    build_rm001_v2_exposure_panel,
    build_rm001_v2_risk_state,
    portfolio_risk_v2,
)


def _action_ledger(start, end):
    ledger = {
        "schema_version": 1,
        "ledger_id": "AE001-CORPORATE-ACTIONS-v1",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "coverage_start_date": start,
        "coverage_end_date": end,
        "source_chunks": [],
        "record_count": 0,
        "records": [],
        "no_record_means_no_share_changing_action_in_covered_source": True,
        "historical_source_retrieved_prospectively": False,
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = digest(ledger)
    return ledger


def _market_and_features():
    start = date(2026, 7, 27)
    symbols = [
        ("SMALL", "INE000000001", 1_000_000.0),
        ("MID", "INE000000002", 2_000_000.0),
        ("LARGE", "INE000000003", 4_000_000.0),
    ]
    closes = {symbol: 100.0 for symbol, _, _ in symbols}
    benchmark_close = 20_000.0
    sessions = []
    for index in range(61):
        day = (start + timedelta(days=index)).isoformat()
        benchmark_return = 0.001 * ((index % 7) - 3)
        benchmark_prior = benchmark_close
        benchmark_close *= 1.0 + benchmark_return
        equities = []
        for symbol, isin, _ in symbols:
            prior = closes[symbol]
            closes[symbol] *= 1.0 + benchmark_return + 0.0001
            close = closes[symbol]
            equities.append(
                {
                    "session_date": day,
                    "symbol": symbol,
                    "isin": isin,
                    "open_price": prior,
                    "high_price": max(prior, close) * 1.01,
                    "low_price": min(prior, close) * 0.99,
                    "close_price": close,
                    "previous_close": prior,
                    "volume": 100_000.0,
                    "turnover_inr": 30_000_000.0,
                    "trade_count": 1_000.0,
                }
            )
        sessions.append(
            {
                "session_date": day,
                "equities": equities,
                "benchmark": {
                    "benchmark_id": "nifty_500",
                    "index_name": "Nifty 500",
                    "session_date": day,
                    "open_price": benchmark_prior,
                    "close_price": benchmark_close,
                },
            }
        )
    market = {
        "schema_version": 1,
        "panel_id": "TEST-MARKET",
        "sessions": sessions,
        "live_capital_allowed": False,
    }
    market["panel_sha256"] = digest(market)
    actions = _action_ledger(
        sessions[0]["session_date"],
        sessions[-1]["session_date"],
    )
    final = sessions[-1]["session_date"]
    features = {
        "schema_version": 1,
        "panel_id": "RANKED",
        "corporate_action_ledger_sha256": actions["ledger_sha256"],
        "transform": "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1",
        "rows": [
            {
                "feature_session": final,
                "symbol": symbol,
                "isin": isin,
                "values": {
                    "momentum_20": percentile,
                    "realized_vol_60": 0.5,
                    "turnover_inr": 0.5,
                },
            }
            for (symbol, isin, _), percentile in zip(
                symbols,
                (0.0, 0.5, 1.0),
                strict=True,
            )
        ],
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    features["panel_sha256"] = digest(features)
    final_market = {
        (row["symbol"], row["isin"]): row["close_price"]
        for row in sessions[-1]["equities"]
    }
    size_rows = [
        {
            "symbol": symbol,
            "isin": isin,
            "issued_size": issued,
            "official_close": final_market[(symbol, isin)],
            "total_market_cap_inr": final_market[(symbol, isin)] * issued,
        }
        for symbol, isin, issued in symbols
    ]
    size_session = {
        "session_date": final,
        "source_url": "https://nsearchives.nseindia.com/x",
        "raw_sha256": "a" * 64,
        "market_eq_identity_count": 3,
        "exact_joined_identity_count": 3,
        "exact_join_coverage": 1.0,
        "positive_issued_size_coverage": 1.0,
        "positive_market_cap_coverage": 1.0,
        "rows": size_rows,
    }
    size_session["session_sha256"] = digest(size_session)
    size_panel = {
        "schema_version": 1,
        "panel_id": "RM001-v2-SIZE-PANEL-v1",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "market_panel_sha256": market["panel_sha256"],
        "d007_result_sha256": (
            "4151612cb85c88d605344fd018fab85118c295e71a90fabbe6c2223d15f27c14"
        ),
        "size_formula": "TOTAL_MARKET_CAP_INR = OFFICIAL_CLOSE * ISSD_CPTL",
        "session_count": 1,
        "row_count": 3,
        "minimum_exact_join_coverage": 1.0,
        "sessions": [size_session],
        "prospective_source_timing_verified": False,
        "live_capital_allowed": False,
    }
    size_panel["panel_sha256"] = digest(size_panel)
    return market, features, actions, size_panel


def test_v2_exposure_panel_adds_centered_total_size_rank():
    market, features, actions, size_panel = _market_and_features()
    panel = build_rm001_v2_exposure_panel(
        feature_panel=features,
        market_panel=market,
        action_ledger=actions,
        size_panel=size_panel,
    )
    assert panel["exposure_count"] == 3
    by_symbol = {
        row["symbol"]: row["exposures"]
        for row in panel["rows"]
    }
    assert by_symbol["SMALL"]["SIZE"] == pytest.approx(-1.0)
    assert by_symbol["MID"]["SIZE"] == pytest.approx(0.0)
    assert by_symbol["LARGE"]["SIZE"] == pytest.approx(1.0)
    assert panel["factor_names"] == list(FACTOR_NAMES_V2)
    assert panel["deferred_factors"]["FREE_FLOAT_SIZE"] == "SOURCE_NOT_POPULATED"


def test_v2_factor_regression_recovers_six_known_coefficients():
    true = np.asarray([0.001, 0.002, -0.0015, 0.0008, 0.0012, -0.0007])
    rows = []
    realized = {}
    for index in range(150):
        vector = np.asarray(
            [
                1.0,
                (index - 75) / 75.0,
                ((index * 7) % 101) / 50.0 - 1.0,
                ((index * 11) % 103) / 51.0 - 1.0,
                ((index * 13) % 107) / 53.0 - 1.0,
                ((index * 17) % 109) / 54.0 - 1.0,
            ]
        )
        symbol = f"S{index:03d}"
        isin = f"INE{index:09d}"
        rows.append(
            {
                "symbol": symbol,
                "isin": isin,
                "exposures": dict(
                    zip(FACTOR_NAMES_V2, vector.tolist(), strict=True)
                ),
            }
        )
        realized[(symbol, isin)] = float(vector @ true)
    factors, residuals = _fit_factor_return_v2(rows, realized)
    assert len(residuals) == 150
    for index, factor in enumerate(FACTOR_NAMES_V2):
        assert factors[factor] == pytest.approx(true[index], abs=1e-12)


def _risk_inputs():
    exposure_rows = []
    for index in range(2):
        exposure_rows.append(
            {
                "session_date": "2026-09-25",
                "symbol": f"S{index}",
                "isin": f"INE{index:09d}",
                "exposures": {
                    factor: (
                        1.0
                        if factor == "MARKET_COMMON"
                        else 0.1 * (index + 1)
                    )
                    for factor in FACTOR_NAMES_V2
                },
            }
        )
    exposure = {
        "schema_version": 1,
        "model_id": "RM001-v2-DEVELOPMENT",
        "factor_names": list(FACTOR_NAMES_V2),
        "rows": exposure_rows,
        "size_contract": {},
        "deferred_factors": {},
        "live_capital_allowed": False,
    }
    exposure["panel_sha256"] = digest(exposure)

    factor_returns = []
    residuals = []
    start = date(2026, 6, 1)
    for index in range(60):
        day = (start + timedelta(days=index)).isoformat()
        factor_returns.append(
            {
                "exposure_session": day,
                "realized_session": day,
                "factor_returns": {
                    factor: 0.0001 * (factor_index + 1) * ((index % 5) - 2)
                    for factor_index, factor in enumerate(FACTOR_NAMES_V2)
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
                        0.0002 * (stock_index + 1) * ((index % 5) - 2)
                    ),
                }
            )
    history = {
        "schema_version": 1,
        "model_id": "RM001-v2-DEVELOPMENT",
        "factor_names": list(FACTOR_NAMES_V2),
        "exposure_panel_sha256": exposure["panel_sha256"],
        "factor_return_count": 60,
        "residual_count": len(residuals),
        "factor_returns": factor_returns,
        "residuals": residuals,
        "live_capital_allowed": False,
    }
    history["history_sha256"] = digest(history)
    return exposure, history


def test_v2_risk_state_has_six_factor_covariance_and_portfolio_size_exposure():
    exposure, history = _risk_inputs()
    state = build_rm001_v2_risk_state(
        exposure_panel=exposure,
        factor_history=history,
        as_of_session="2026-09-25",
    )
    assert state["security_count"] == 2
    assert len(state["factor_covariance_daily"]) == 6
    assert all(len(row) == 6 for row in state["factor_covariance_daily"])

    report = portfolio_risk_v2(
        state,
        positions=[
            {"symbol": "S0", "isin": "INE000000000", "weight": 0.4},
            {"symbol": "S1", "isin": "INE000000001", "weight": 0.5},
        ],
    )
    assert "SIZE" in report["portfolio_factor_exposures"]
    assert report["portfolio_factor_exposures"]["SIZE"] == pytest.approx(0.14)
    assert report["annualized_volatility"] >= 0
