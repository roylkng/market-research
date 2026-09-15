from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from marketlab.h020_timing_v1 import MIN_SESSIONS
from marketlab.h020_timing_v1 import compute_snapshot as compute_snapshot_v1

DOWNSIDE_SHOCK_Z_THRESHOLD = -2.0
BREAKDOWN_LOOKBACK_SESSIONS = 10


def _safe_float(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def compute_snapshot_v2(
    stock: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    symbol: str,
    design_influenced: bool = False,
) -> dict[str, Any]:
    """Apply the frozen H020-v2 downside guard on top of untouched H020-v1.

    V2 is monotonic with respect to new-entry eligibility: it may convert a v1
    PAPER_ENTRY_ELIGIBLE state into a wait state, but it never upgrades a v1
    wait/block state. The rule was specified after observing the 2026-09-15
    selloff and is therefore prospective only from the 2026-09-16 boundary.
    """

    v1 = compute_snapshot_v1(
        stock,
        benchmark,
        symbol=symbol,
        design_influenced=design_influenced,
    )
    if v1.get("action") == "BLOCKED_DATA":
        return {
            **v1,
            "v1_action": v1["action"],
            "v2_action": v1["action"],
            "v2_override": False,
            "v2_guard": {"status": "BLOCKED_DATA"},
        }

    required = {"adj_close", "volume"}
    if not required.issubset(stock.columns) or not required.issubset(benchmark.columns):
        raise ValueError("v1/v2 required-column contract drift")

    stock = stock.dropna(subset=["adj_close"]).copy()
    benchmark = benchmark.dropna(subset=["adj_close"]).copy()
    common = stock.index.intersection(benchmark.index)
    stock = stock.loc[common]
    benchmark = benchmark.loc[common]
    if len(stock) < MIN_SESSIONS:
        raise ValueError("v1/v2 minimum-session contract drift")

    close = stock["adj_close"].astype(float)
    bench = benchmark["adj_close"].astype(float)
    stock_returns = close.pct_change().dropna()
    benchmark_returns = bench.pct_change().dropna()

    latest_return = float(stock_returns.iloc[-1])
    latest_benchmark_return = float(benchmark_returns.iloc[-1])
    latest_relative_return = latest_return - latest_benchmark_return

    prior20_returns = stock_returns.iloc[-21:-1]
    prior20_mean = float(prior20_returns.mean())
    prior20_sigma = float(prior20_returns.std(ddof=1))
    downside_shock_z = (
        (latest_return - prior20_mean) / prior20_sigma
        if prior20_sigma > 0.0
        else float("nan")
    )
    downside_shock = bool(
        np.isfinite(downside_shock_z)
        and downside_shock_z <= DOWNSIDE_SHOCK_Z_THRESHOLD
        and latest_relative_return < 0.0
    )

    prior10_low = float(close.iloc[-(BREAKDOWN_LOOKBACK_SESSIONS + 1) : -1].min())
    closing_breakdown = bool(
        float(close.iloc[-1]) < prior10_low and latest_relative_return < 0.0
    )

    v1_action = str(v1["action"])
    v2_action = v1_action
    v2_reason = str(v1["reason"])
    override_reason: str | None = None
    if v1_action.startswith("PAPER_ENTRY_ELIGIBLE"):
        if downside_shock:
            v2_action = "WAIT_DOWNSIDE_SHOCK"
            override_reason = (
                "v1 entry blocked: latest stock return is a <= -2 sigma downside "
                "shock versus its prior 20 sessions and underperformed Nifty that session"
            )
        elif closing_breakdown:
            v2_action = "WAIT_BREAKDOWN"
            override_reason = (
                "v1 entry blocked: latest close is below the prior 10-session closing low "
                "and underperformed Nifty that session"
            )
        if override_reason is not None:
            v2_reason = override_reason

    result = dict(v1)
    result.update(
        {
            "action": v2_action,
            "reason": v2_reason,
            "v1_action": v1_action,
            "v1_reason": v1["reason"],
            "v2_action": v2_action,
            "v2_override": v2_action != v1_action,
            "v2_guard": {
                "rule_id": "H020-V2-DOWNSIDE-GUARD-20260915",
                "prospective_start_ist": "2026-09-16T00:00:00+05:30",
                "return_1d_pct": 100.0 * latest_return,
                "benchmark_return_1d_pct": 100.0 * latest_benchmark_return,
                "relative_1d_pp": 100.0 * latest_relative_return,
                "prior20_daily_return_mean_pct": 100.0 * prior20_mean,
                "prior20_daily_return_sigma_pct": 100.0 * prior20_sigma,
                "downside_shock_z": _safe_float(downside_shock_z),
                "downside_shock_z_threshold": DOWNSIDE_SHOCK_Z_THRESHOLD,
                "downside_shock": downside_shock,
                "prior10_closing_low": prior10_low,
                "closing_breakdown_10d": closing_breakdown,
            },
        }
    )
    result["policies"] = dict(v1["policies"])
    result["policies"]["E_downside_guard_v2"] = v2_action.startswith(
        "PAPER_ENTRY_ELIGIBLE"
    )
    return result
