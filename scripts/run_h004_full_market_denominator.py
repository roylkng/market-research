#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import run_h004_earnings_replay as market

PRIMARY_TURNOVER = 20_000_000.0
DISCOVERY_TURNOVER = 2_500_000.0
BUDGETS = (1, 2, 3, 5, 10)


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2025-10-01")
    parser.add_argument("--end", default="2026-07-31")
    parser.add_argument("--price-start", default="2025-05-01")
    parser.add_argument("--price-end", default="2026-08-31")
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def safe_return(a: float, b: float) -> float:
    return (a / b - 1.0) * 100.0


def percentile_map(values: list[float]) -> list[float]:
    if not values:
        return []
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    out = [0.0] * len(values)
    n = len(values)
    i = 0
    while i < n:
        j = i + 1
        while j < n and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = ((i + 1) + j) / 2.0
        pct = avg_rank / n
        for k in range(i, j):
            out[indexed[k][0]] = pct
        i = j
    return out


def outcome(rows: list[dict[str, Any]], decision_idx: int) -> dict[str, Any] | None:
    entry_idx = decision_idx + 1
    if entry_idx + 19 >= len(rows):
        return None
    entry = rows[entry_idx]["open"]
    forward = rows[entry_idx : entry_idx + 20]
    max_ret = max(row["high"] for row in forward) / entry - 1.0
    hit_offset = None
    for offset, row in enumerate(forward):
        if row["high"] / entry - 1.0 >= 0.25:
            hit_offset = offset
            break
    return {
        "entry_idx": entry_idx,
        "entry_date": rows[entry_idx]["date"].isoformat(),
        "entry_open": entry,
        "max_20d_return_pct": max_ret * 100.0,
        "close_20d_return_pct": (forward[-1]["close"] / entry - 1.0) * 100.0,
        "explosive_20d": max_ret >= 0.25,
        "hit_offset": hit_offset,
        "hit_idx": entry_idx + hit_offset if hit_offset is not None else None,
        "hit_date": (
            rows[entry_idx + hit_offset]["date"].isoformat() if hit_offset is not None else None
        ),
    }


def row_features(rows: list[dict[str, Any]], idx: int) -> dict[str, Any] | None:
    if idx < 60:
        return None
    prior20 = rows[idx - 20 : idx]
    median_turnover = statistics.median(row["turnover"] for row in prior20)
    median_volume = statistics.median(row["volume"] for row in prior20)
    close = rows[idx]["close"]
    r1 = safe_return(close, rows[idx - 1]["close"])
    r5 = safe_return(close, rows[idx - 5]["close"])
    r20 = safe_return(close, rows[idx - 20]["close"])
    volume_ratio = rows[idx]["volume"] / median_volume if median_volume > 0 else 0.0
    return {
        "median_turnover": median_turnover,
        "r1": r1,
        "r5": r5,
        "r20": r20,
        "volume_ratio": volume_ratio,
        "pre_momentum": r1 < 8.0 and r5 < 10.0 and r20 < 20.0,
        "flat_positive_circuit_proxy": (
            abs(rows[idx]["high"] - rows[idx]["low"]) < 1e-9
            and abs(rows[idx]["close"] - rows[idx]["high"]) < 1e-9
            and r1 >= 4.9
        ),
    }


def build_episodes(
    prices: dict[str, list[dict[str, Any]]],
    start: date,
    end: date,
    liquidity_min: float,
    liquidity_max: float | None = None,
) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    for symbol, rows in prices.items():
        suppressed_through = -1
        for idx in range(60, len(rows) - 20):
            d = rows[idx]["date"]
            if d < start or d > end or idx <= suppressed_through:
                continue
            features = row_features(rows, idx)
            if features is None:
                continue
            turnover = features["median_turnover"]
            if turnover < liquidity_min or (liquidity_max is not None and turnover >= liquidity_max):
                continue
            if not features["pre_momentum"]:
                continue
            result = outcome(rows, idx)
            if result is None or not result["explosive_20d"]:
                continue
            hit_idx = result["hit_idx"]
            if hit_idx is None:
                continue
            episodes.append(
                {
                    "symbol": symbol,
                    "start_date": d.isoformat(),
                    "entry_date": result["entry_date"],
                    "hit_date": result["hit_date"],
                    "sessions_from_entry_to_hit": result["hit_offset"],
                    "entry_open": result["entry_open"],
                    "max_20d_return_pct": result["max_20d_return_pct"],
                    "close_20d_return_pct": result["close_20d_return_pct"],
                    "median_20d_traded_value_inr": turnover,
                    "prior_1d_return_pct": features["r1"],
                    "prior_5d_return_pct": features["r5"],
                    "prior_20d_return_pct": features["r20"],
                    "_start_idx": idx,
                    "_hit_idx": hit_idx,
                }
            )
            suppressed_through = hit_idx
    return episodes


def momentum_candidates(
    prices: dict[str, list[dict[str, Any]]], start: date, end: date
) -> dict[date, list[dict[str, Any]]]:
    daily: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for symbol, rows in prices.items():
        for idx in range(60, len(rows) - 20):
            d = rows[idx]["date"]
            if d < start or d > end:
                continue
            features = row_features(rows, idx)
            if features is None or features["median_turnover"] < PRIMARY_TURNOVER:
                continue
            if features["r5"] <= 0.0 or features["r20"] <= 0.0 or features["volume_ratio"] < 1.0:
                continue
            if features["flat_positive_circuit_proxy"]:
                continue
            result = outcome(rows, idx)
            if result is None:
                continue
            daily[d].append(
                {
                    "symbol": symbol,
                    "idx": idx,
                    "r5": features["r5"],
                    "r20": features["r20"],
                    "volume_ratio": features["volume_ratio"],
                    "outcome": result,
                }
            )
    for d, candidates in daily.items():
        p5 = percentile_map([row["r5"] for row in candidates])
        p20 = percentile_map([row["r20"] for row in candidates])
        pv = percentile_map([row["volume_ratio"] for row in candidates])
        for i, row in enumerate(candidates):
            row["score"] = (p5[i] + p20[i] + pv[i]) / 3.0
        candidates.sort(key=lambda row: (-row["score"], row["symbol"]))
    return daily


def baseline_for_budget(
    daily: dict[date, list[dict[str, Any]]],
    prices: dict[str, list[dict[str, Any]]],
    episodes: list[dict[str, Any]],
    budget: int,
) -> dict[str, Any]:
    signals = [row for d in sorted(daily) for row in daily[d][:budget]]
    hits = [row for row in signals if row["outcome"]["explosive_20d"]]

    by_symbol_episode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in episodes:
        by_symbol_episode[episode["symbol"]].append(episode)

    recalled = 0
    leads: list[int] = []
    for symbol, symbol_episodes in by_symbol_episode.items():
        rows = prices[symbol]
        signal_indices = sorted(row["idx"] for row in signals if row["symbol"] == symbol)
        for episode in symbol_episodes:
            matches = [
                idx
                for idx in signal_indices
                if episode["_start_idx"] <= idx < episode["_hit_idx"]
            ]
            if not matches:
                continue
            recalled += 1
            first = matches[0]
            leads.append(max(0, episode["_hit_idx"] - (first + 1)))

    return {
        "top_n_per_day": budget,
        "signal_count": len(signals),
        "hit_count": len(hits),
        "precision": len(hits) / len(signals) if signals else None,
        "episode_recall_count": recalled,
        "episode_recall": recalled / len(episodes) if episodes else None,
        "median_lead_sessions_before_25pct": statistics.median(leads) if leads else None,
        "median_max_20d_return_pct": (
            statistics.median(row["outcome"]["max_20d_return_pct"] for row in signals)
            if signals
            else None
        ),
        "median_close_20d_return_pct": (
            statistics.median(row["outcome"]["close_20d_return_pct"] for row in signals)
            if signals
            else None
        ),
    }


def public_episode(episode: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in episode.items() if not key.startswith("_")}


def main() -> None:
    ns = args()
    start = date.fromisoformat(ns.start)
    end = date.fromisoformat(ns.end)
    price_start = date.fromisoformat(ns.price_start)
    price_end = date.fromisoformat(ns.price_end)
    out_dir = Path(ns.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sessions, prices = market.load_prices(price_start, price_end)
    print(f"loaded sessions={len(sessions)} symbols={len(prices)}")

    primary = build_episodes(prices, start, end, PRIMARY_TURNOVER)
    discovery = build_episodes(prices, start, end, DISCOVERY_TURNOVER, PRIMARY_TURNOVER)
    daily = momentum_candidates(prices, start, end)
    baselines = [baseline_for_budget(daily, prices, primary, budget) for budget in BUDGETS]

    symbol_counts = Counter(episode["symbol"] for episode in primary)
    quarter_counts: dict[str, int] = Counter(
        f"{date.fromisoformat(ep['start_date']).year}-Q{(date.fromisoformat(ep['start_date']).month - 1) // 3 + 1}"
        for ep in primary
    )
    summary = {
        "schema_version": 1,
        "experiment": "H004-HR003-FULL-MARKET-DENOMINATOR",
        "status": "HISTORICAL_RECONSTRUCTION_NOT_OUT_OF_SAMPLE",
        "live_capital_allowed": False,
        "decision_window": {"start": start.isoformat(), "end": end.isoformat()},
        "price_window": {"start": price_start.isoformat(), "end": price_end.isoformat()},
        "market_sessions_loaded": len(sessions),
        "symbols_loaded": len(prices),
        "primary_episode_count": len(primary),
        "discovery_episode_count": len(discovery),
        "primary_unique_symbols": len(symbol_counts),
        "primary_episodes_by_quarter": dict(sorted(quarter_counts.items())),
        "top_symbols_by_episode_count": symbol_counts.most_common(20),
        "momentum_baselines": baselines,
        "data_contract": {
            "market_source": "official NSE UDiFF daily bhavcopy",
            "episode_label": "next-session-open max high over next 20 symbol sessions >= +25%",
            "primary_liquidity": "median prior-20 traded value >= INR 2 crore",
            "discovery_liquidity": "INR 25 lakh <= median prior-20 traded value < INR 2 crore",
            "momentum_score": "equal mean of daily cross-sectional percentile ranks: 5d return, 20d return, volume ratio",
        },
    }

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out_dir / "primary-episodes.json").write_text(
        json.dumps([public_episode(ep) for ep in primary], indent=2, sort_keys=True) + "\n"
    )
    (out_dir / "discovery-episodes.json").write_text(
        json.dumps([public_episode(ep) for ep in discovery], indent=2, sort_keys=True) + "\n"
    )
    (out_dir / "RESULTS.md").write_text(
        "# H004-HR003 full-market denominator\n\n"
        "Status: **historical reconstruction, not out-of-sample validation**\n\n"
        "The contract was frozen before output inspection. This run defines the full liquid-market explosive-opportunity denominator and a price/volume-only baseline. It contains no accounting, filing, catalyst, valuation or news features.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
