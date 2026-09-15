from __future__ import annotations

import numpy as np
import pandas as pd

from marketlab.timing import compute_snapshot
from marketlab.timing_v2 import compute_snapshot_v2


def _frame(values: np.ndarray) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-01", periods=len(values), tz="UTC")
    return pd.DataFrame(
        {"adj_close": values, "volume": np.full(len(values), 1_000_000)},
        index=index,
    )


def _strong_trend(*, final_stock: float, final_benchmark: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    stock_history = np.concatenate(
        [
            np.linspace(80.0, 100.0, 239),
            np.linspace(100.5, 116.0, 20),
            np.array([final_stock]),
        ]
    )
    benchmark_history = np.concatenate(
        [
            np.linspace(100.0, 104.0, 259),
            np.array([final_benchmark]),
        ]
    )
    return _frame(stock_history), _frame(benchmark_history)


def test_adverse_relative_shock_defers_an_otherwise_valid_entry() -> None:
    stock, benchmark = _strong_trend(final_stock=112.0, final_benchmark=102.96)
    v1 = compute_snapshot(stock, benchmark, symbol="SHOCK")
    assert v1["action"].startswith("PAPER_ENTRY_ELIGIBLE")

    v2 = compute_snapshot_v2(stock, benchmark, symbol="SHOCK")
    assert v2["v1_action_before_shock_guard"] == v1["action"]
    assert v2["flags"]["adverse_relative_shock_v2"] is True
    assert v2["action"] == "WAIT_SHOCK_CONFIRMATION"
    assert v2["policies"]["D_multivariate_v2"] is False


def test_small_relative_dip_does_not_override_v1_entry() -> None:
    stock, benchmark = _strong_trend(final_stock=114.5, final_benchmark=102.96)
    v1 = compute_snapshot(stock, benchmark, symbol="NORMAL")
    assert v1["action"].startswith("PAPER_ENTRY_ELIGIBLE")

    v2 = compute_snapshot_v2(stock, benchmark, symbol="NORMAL")
    assert v2["flags"]["adverse_relative_shock_v2"] is False
    assert v2["action"] == v1["action"]
    assert v2["policies"]["D_multivariate_v2"] is True


def test_challenger_never_upgrades_a_non_entry_v1_action() -> None:
    sessions = 260
    benchmark = _frame(np.linspace(100.0, 120.0, sessions))
    stock = _frame(np.linspace(180.0, 90.0, sessions))
    v1 = compute_snapshot(stock, benchmark, symbol="FALLING")
    v2 = compute_snapshot_v2(stock, benchmark, symbol="FALLING")
    assert not v1["action"].startswith("PAPER_ENTRY_ELIGIBLE")
    assert v2["action"] == v1["action"]
    assert v2["policies"]["D_multivariate_v2"] is False
