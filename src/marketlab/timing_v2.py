from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from marketlab.timing import compute_snapshot

MIN_ABSOLUTE_RELATIVE_SHOCK = 0.02
RELATIVE_SHOCK_SIGMA_MULTIPLIER = 1.5
RELATIVE_VOL_LOOKBACK = 20


def _aligned_close(stock: pd.DataFrame, benchmark: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    stock_clean = stock.dropna(subset=["adj_close"]).copy()
    benchmark_clean = benchmark.dropna(subset=["adj_close"]).copy()
    common = stock_clean.index.intersection(benchmark_clean.index)
    stock_close = stock_clean.loc[common, "adj_close"].astype(float)
    benchmark_close = benchmark_clean.loc[common, "adj_close"].astype(float)
    return stock_close, benchmark_close


def compute_snapshot_v2(
    stock: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    symbol: str,
    design_influenced: bool = False,
) -> dict[str, Any]:
    """Preserve H020-v1 and defer otherwise-eligible entries after an adverse shock."""
    result = compute_snapshot(
        stock,
        benchmark,
        symbol=symbol,
        design_influenced=design_influenced,
    )
    result["challenger_version"] = "H020-V2-ADVERSE-SHOCK-1"
    if result.get("action") == "BLOCKED_DATA":
        return result

    stock_close, benchmark_close = _aligned_close(stock, benchmark)
    if len(stock_close) < RELATIVE_VOL_LOOKBACK + 2:
        result["action"] = "BLOCKED_DATA"
        result["reason"] = "insufficient aligned history for H020-v2 relative-shock guard"
        return result

    stock_returns = stock_close.pct_change()
    benchmark_returns = benchmark_close.pct_change()
    relative_returns = stock_returns - benchmark_returns

    stock_return_1d = float(stock_returns.iloc[-1])
    benchmark_return_1d = float(benchmark_returns.iloc[-1])
    relative_return_1d = float(relative_returns.iloc[-1])
    prior_relative = relative_returns.iloc[-1 - RELATIVE_VOL_LOOKBACK : -1].dropna()
    if len(prior_relative) != RELATIVE_VOL_LOOKBACK:
        result["action"] = "BLOCKED_DATA"
        result["reason"] = "incomplete H020-v2 prior relative-volatility window"
        return result

    prior_relative_vol = float(prior_relative.std(ddof=1))
    if not np.isfinite(prior_relative_vol) or prior_relative_vol <= 0.0:
        shock_threshold = MIN_ABSOLUTE_RELATIVE_SHOCK
        shock_sigma = None
    else:
        shock_threshold = max(
            MIN_ABSOLUTE_RELATIVE_SHOCK,
            RELATIVE_SHOCK_SIGMA_MULTIPLIER * prior_relative_vol,
        )
        shock_sigma = relative_return_1d / prior_relative_vol

    adverse_shock = bool(stock_return_1d < 0.0 and relative_return_1d <= -shock_threshold)
    v1_action = str(result["action"])
    if v1_action.startswith("PAPER_ENTRY_ELIGIBLE") and adverse_shock:
        result["action"] = "WAIT_SHOCK_CONFIRMATION"
        result["reason"] = (
            "v1 entry is deferred after a materially negative one-session stock-relative shock; "
            "require a later completed-session confirmation"
        )

    result["v1_action_before_shock_guard"] = v1_action
    result["return_1d_pct"] = 100.0 * stock_return_1d
    result["benchmark_return_1d_pct"] = 100.0 * benchmark_return_1d
    result["relative_1d_pp"] = 100.0 * relative_return_1d
    result["prior_relative_volatility_20d_daily_pct"] = 100.0 * prior_relative_vol
    result["adverse_shock_threshold_pp"] = 100.0 * shock_threshold
    result["relative_shock_sigma"] = shock_sigma
    result.setdefault("flags", {})["adverse_relative_shock_v2"] = adverse_shock
    result.setdefault("policies", {})["D_multivariate_v2"] = str(result["action"]).startswith(
        "PAPER_ENTRY_ELIGIBLE"
    )
    return result
