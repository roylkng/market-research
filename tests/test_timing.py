from __future__ import annotations

import numpy as np
import pandas as pd

from marketlab.timing import compute_snapshot


def _frame(values: np.ndarray) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-01", periods=len(values), tz="UTC")
    return pd.DataFrame({"adj_close": values, "volume": np.full(len(values), 1_000_000)}, index=index)


def test_falling_series_is_not_entry_eligible() -> None:
    sessions = 260
    benchmark = _frame(np.linspace(100.0, 120.0, sessions))
    stock = _frame(np.linspace(180.0, 90.0, sessions))
    result = compute_snapshot(stock, benchmark, symbol="FALLING")
    assert result["action"] == "WAIT_FALLING"
    assert result["flags"]["falling"] is True
    assert result["policies"]["D_multivariate_v1"] is False


def test_missing_history_fails_closed() -> None:
    benchmark = _frame(np.linspace(100.0, 110.0, 260))
    stock = _frame(np.linspace(100.0, 105.0, 100))
    result = compute_snapshot(stock, benchmark, symbol="SHORT")
    assert result["action"] == "BLOCKED_DATA"
    assert "insufficient" in result["reason"]


def test_future_rows_do_not_change_asof_snapshot_when_excluded() -> None:
    sessions = 260
    benchmark = _frame(100.0 + np.arange(sessions) * 0.04 + np.sin(np.arange(sessions) / 7))
    stock = _frame(100.0 + np.arange(sessions) * 0.06 + 3 * np.sin(np.arange(sessions) / 8))
    base = compute_snapshot(stock, benchmark, symbol="POINTINTIME")

    future_index = pd.bdate_range(stock.index[-1] + pd.Timedelta(days=1), periods=20, tz="UTC")
    future_stock = pd.DataFrame({"adj_close": np.linspace(200.0, 50.0, 20), "volume": 9_000_000}, index=future_index)
    future_benchmark = pd.DataFrame({"adj_close": np.linspace(130.0, 90.0, 20), "volume": 9_000_000}, index=future_index)

    cutoff = stock.index[-1]
    combined_stock = pd.concat([stock, future_stock]).loc[:cutoff]
    combined_benchmark = pd.concat([benchmark, future_benchmark]).loc[:cutoff]
    replay = compute_snapshot(combined_stock, combined_benchmark, symbol="POINTINTIME")

    assert replay["action"] == base["action"]
    assert replay["timing_score_0_100_not_probability"] == base["timing_score_0_100_not_probability"]
    assert replay["close_adjusted"] == base["close_adjusted"]
