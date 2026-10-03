from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

MIN_SESSIONS = 205


def _return(series: pd.Series, sessions: int) -> float:
    if len(series) <= sessions:
        return float("nan")
    return float(series.iloc[-1] / series.iloc[-1 - sessions] - 1.0)


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return number


def rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)
    avg_gain = gains.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    loss = float(avg_loss.iloc[-1])
    gain = float(avg_gain.iloc[-1])
    if loss == 0.0:
        return 100.0 if gain > 0.0 else 50.0
    rs = gain / loss
    return float(100.0 - 100.0 / (1.0 + rs))


def macd_histogram(close: pd.Series) -> float:
    fast = close.ewm(span=12, adjust=False).mean()
    slow = close.ewm(span=26, adjust=False).mean()
    macd = fast - slow
    signal = macd.ewm(span=9, adjust=False).mean()
    return float((macd - signal).iloc[-1])


def _market_regime(close: pd.Series) -> dict[str, Any]:
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    ret20 = _return(close, 20)
    ret60 = _return(close, 60)
    last = float(close.iloc[-1])
    bearish = bool(
        (last < float(sma20.iloc[-1]) < float(sma50.iloc[-1]))
        or (ret20 <= -0.04 and last < float(sma50.iloc[-1]))
    )
    bullish = bool(
        last > float(sma20.iloc[-1]) > float(sma50.iloc[-1]) > float(sma200.iloc[-1])
        and ret20 > 0
    )
    state = "BULLISH" if bullish else "BEARISH" if bearish else "MIXED"
    return {
        "state": state,
        "close": last,
        "return_20d_pct": 100 * ret20,
        "return_60d_pct": 100 * ret60,
        "sma20": float(sma20.iloc[-1]),
        "sma50": float(sma50.iloc[-1]),
        "sma200": float(sma200.iloc[-1]),
    }


def compute_snapshot(
    stock: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    symbol: str,
    design_influenced: bool = False,
) -> dict[str, Any]:
    required = {"adj_close", "volume"}
    if not required.issubset(stock.columns) or not required.issubset(benchmark.columns):
        return {"symbol": symbol, "action": "BLOCKED_DATA", "reason": "missing required columns"}

    stock = stock.dropna(subset=["adj_close"]).copy()
    benchmark = benchmark.dropna(subset=["adj_close"]).copy()
    common = stock.index.intersection(benchmark.index)
    stock = stock.loc[common]
    benchmark = benchmark.loc[common]
    if len(stock) < MIN_SESSIONS:
        return {
            "symbol": symbol,
            "action": "BLOCKED_DATA",
            "reason": f"insufficient common sessions: {len(stock)} < {MIN_SESSIONS}",
        }

    close = stock["adj_close"].astype(float)
    bench = benchmark["adj_close"].astype(float)
    volume = stock["volume"].astype(float).fillna(0.0)

    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    ret5 = _return(close, 5)
    ret20 = _return(close, 20)
    ret60 = _return(close, 60)
    rel20 = ret20 - _return(bench, 20)
    rel60 = ret60 - _return(bench, 60)
    last = float(close.iloc[-1])
    sma20_last = float(sma20.iloc[-1])
    sma50_last = float(sma50.iloc[-1])
    sma200_last = float(sma200.iloc[-1])
    sma20_slope5 = float(sma20.iloc[-1] / sma20.iloc[-6] - 1.0)

    prior20 = close.iloc[-21:-1]
    last10 = close.iloc[-10:]
    previous20 = close.iloc[-30:-10]
    breakout20 = bool(last > float(prior20.max()) * 1.002)
    higher_low = bool(float(last10.min()) > float(previous20.min()) * 1.005)
    low60 = float(close.iloc[-60:].min())
    high60 = float(close.iloc[-60:].max())
    near_60d_low = last / low60 - 1.0
    distance_60d_high = last / high60 - 1.0

    prior_volume = volume.iloc[-25:-5]
    prior_volume_median = float(prior_volume.median()) if len(prior_volume) else 0.0
    last5_volume_mean = float(volume.iloc[-5:].mean())
    volume_ratio = last5_volume_mean / prior_volume_median if prior_volume_median > 0 else float("nan")

    daily_returns = close.pct_change().dropna()
    vol20_ann = float(daily_returns.iloc[-20:].std(ddof=1) * np.sqrt(252.0))
    rsi14 = rsi(close)
    macd_hist = macd_histogram(close)
    bollinger_std = float(close.rolling(20).std(ddof=1).iloc[-1])
    bollinger_z = float((last - sma20_last) / bollinger_std) if bollinger_std > 0 else 0.0

    market = _market_regime(bench)
    market_bearish = market["state"] == "BEARISH"

    falling = bool(
        (last < sma20_last < sma50_last and sma20_slope5 < 0.0 and ret20 < 0.0)
        or (ret20 <= -0.08 and rel20 < 0.0)
    )
    base_candidate = bool(
        near_60d_low <= 0.08
        and abs(ret20) <= 0.08
        and not breakout20
        and not (last > sma20_last > sma50_last)
    )
    trend_confirmed = bool(
        last > sma20_last > sma50_last
        and sma20_slope5 > 0.0
        and ret20 > 0.0
        and ret60 > 0.0
        and rel20 > 0.0
    )
    reversal_confirmed = bool(
        last > sma20_last
        and sma20_slope5 > 0.0
        and higher_low
        and ret5 > 0.0
        and rel20 > -0.01
        and 42.0 <= rsi14 <= 70.0
    )
    pullback_candidate = bool(
        sma50_last > sma200_last
        and ret60 > 0.0
        and rel60 > 0.0
        and last >= sma50_last * 0.97
        and last <= sma20_last * 1.04
        and not falling
    )
    extended = bool(last / sma20_last - 1.0 >= 0.10 or rsi14 >= 72.0 or ret20 >= 0.18)

    score = 0
    score += 18 if last > sma20_last else 0
    score += 10 if sma20_last > sma50_last else 0
    score += 8 if sma50_last > sma200_last else 0
    score += 10 if sma20_slope5 > 0.0 else 0
    score += 10 if ret20 > 0.0 else 0
    score += 10 if rel20 > 0.0 else 0
    score += 10 if rel60 > 0.0 else 0
    score += 10 if higher_low else 0
    score += 7 if volume_ratio >= 1.10 else 0
    score += 7 if 45.0 <= rsi14 <= 65.0 else 0
    if market_bearish:
        score -= 10
    if extended:
        score -= 15
    score = max(0, min(100, score))

    if extended:
        action = "WAIT_PULLBACK"
        reason = "price is extended under frozen v1 thresholds"
    elif market_bearish:
        if trend_confirmed and rel20 >= 0.05 and rel60 > 0.0 and score >= 60:
            action = "PAPER_ENTRY_ELIGIBLE_TREND"
            reason = "strong stock-relative trend survives bearish-market penalty"
        elif falling:
            action = "WAIT_FALLING"
            reason = "stock decline remains unresolved in a bearish market regime"
        elif base_candidate:
            action = "WAIT_BASE"
            reason = "near a recent low, but reversal is not confirmed in bearish regime"
        elif pullback_candidate or reversal_confirmed:
            action = "WAIT_CONFIRMATION"
            reason = "constructive stock structure, but bearish market requires stronger confirmation"
        else:
            action = "WAIT_CONFIRMATION"
            reason = "no high-confidence timing state under bearish market regime"
    elif trend_confirmed and score >= 55:
        action = "PAPER_ENTRY_ELIGIBLE_TREND"
        reason = "trend and relative-strength conditions are confirmed"
    elif reversal_confirmed and score >= 50:
        action = "PAPER_ENTRY_ELIGIBLE_REVERSAL"
        reason = "higher-low/reversal conditions are confirmed"
    elif falling:
        action = "WAIT_FALLING"
        reason = "downtrend remains unresolved"
    elif base_candidate:
        action = "WAIT_BASE"
        reason = "base candidate without confirmed reversal"
    elif pullback_candidate:
        action = "WAIT_PULLBACK_CONFIRMATION"
        reason = "longer trend is constructive, current pullback needs resumption evidence"
    else:
        action = "WAIT_CONFIRMATION"
        reason = "no frozen entry condition is satisfied"

    return {
        "symbol": symbol,
        "as_of_session": str(stock.index[-1].date()),
        "design_influenced": design_influenced,
        "action": action,
        "reason": reason,
        "timing_score_0_100_not_probability": score,
        "market_regime": market["state"],
        "close_adjusted": last,
        "return_5d_pct": 100 * ret5,
        "return_20d_pct": 100 * ret20,
        "return_60d_pct": 100 * ret60,
        "relative_20d_pp": 100 * rel20,
        "relative_60d_pp": 100 * rel60,
        "sma20": sma20_last,
        "sma50": sma50_last,
        "sma200": sma200_last,
        "sma20_slope_5d_pct": 100 * sma20_slope5,
        "rsi14": rsi14,
        "macd_histogram": macd_hist,
        "bollinger_z": bollinger_z,
        "realized_volatility_20d_ann_pct": 100 * vol20_ann,
        "volume_ratio_last5_vs_prior20_median": _safe_float(volume_ratio),
        "near_60d_low_pct": 100 * near_60d_low,
        "distance_from_60d_high_pct": 100 * distance_60d_high,
        "policies": {
            "A_immediate_business_signal": True,
            "B_simple_trend": trend_confirmed and not extended,
            "C_early_reversal_or_pullback": (reversal_confirmed or pullback_candidate) and not extended,
            "D_multivariate_v1": action.startswith("PAPER_ENTRY_ELIGIBLE"),
        },
        "flags": {
            "falling": falling,
            "base_candidate": base_candidate,
            "trend_confirmed": trend_confirmed,
            "reversal_confirmed": reversal_confirmed,
            "pullback_candidate": pullback_candidate,
            "breakout_20d": breakout20,
            "higher_low": higher_low,
            "extended": extended,
        },
        "benchmark": market,
    }
