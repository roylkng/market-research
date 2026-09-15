from __future__ import annotations

import numpy as np
import pandas as pd

from marketlab.h020_timing_v1 import compute_snapshot as compute_snapshot_v1
from marketlab.h020_timing_v2 import compute_snapshot_v2


def _frame(values: np.ndarray) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-01", periods=len(values), tz="UTC")
    return pd.DataFrame(
        {"adj_close": values, "volume": np.full(len(values), 1_000_000)},
        index=index,
    )


def test_v2_blocks_extreme_down_day_that_v1_still_calls_eligible() -> None:
    sessions = 260
    x = np.arange(sessions)
    benchmark = _frame(100.0 + x * 0.03 + np.sin(x / 15) * 0.3)
    stock_values = 100.0 + x * 0.20 + np.sin(x / 8) * 0.10
    stock_values[-1] = stock_values[-2] * 0.99
    stock = _frame(stock_values)

    v1 = compute_snapshot_v1(stock, benchmark, symbol="SHOCK")
    assert v1["action"] == "PAPER_ENTRY_ELIGIBLE_TREND"

    v2 = compute_snapshot_v2(stock, benchmark, symbol="SHOCK")
    assert v2["v1_action"] == "PAPER_ENTRY_ELIGIBLE_TREND"
    assert v2["action"] == "WAIT_DOWNSIDE_SHOCK"
    assert v2["v2_override"] is True
    assert v2["v2_guard"]["downside_shock"] is True
    assert v2["v2_guard"]["downside_shock_z"] <= -2.0


def test_v2_never_upgrades_a_v1_wait_state() -> None:
    sessions = 260
    benchmark = _frame(np.linspace(100.0, 120.0, sessions))
    stock = _frame(np.linspace(180.0, 90.0, sessions))

    v1 = compute_snapshot_v1(stock, benchmark, symbol="FALLING")
    v2 = compute_snapshot_v2(stock, benchmark, symbol="FALLING")
    assert v1["action"] == "WAIT_FALLING"
    assert v2["action"] == v1["action"]
    assert v2["v2_override"] is False


def test_v2_preserves_blocked_data() -> None:
    benchmark = _frame(np.linspace(100.0, 110.0, 260))
    stock = _frame(np.linspace(100.0, 105.0, 100))
    v2 = compute_snapshot_v2(stock, benchmark, symbol="SHORT")
    assert v2["action"] == "BLOCKED_DATA"
    assert v2["v2_action"] == "BLOCKED_DATA"
    assert v2["v2_override"] is False
