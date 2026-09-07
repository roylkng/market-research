from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from marketlab import h002_historical_outcomes as outcomes


def cluster_bootstrap_spread_fast(
    frame: pd.DataFrame,
    *,
    iterations: int = 10_000,
    seed: int = 19,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Exact vectorized equivalent of the H002 company-cluster bootstrap.

    Each bootstrap replicate samples companies with replacement, then includes
    every observation belonging to each sampled company block.  Pre-aggregating
    each company's positive/negative sums and counts is algebraically identical
    to repeatedly concatenating the underlying rows, but avoids dataframe work
    inside the 10,000-replicate Python loop.
    """

    clean = frame[["symbol", "bucket", "excess_return_pct"]].copy()
    clean["excess_return_pct"] = pd.to_numeric(
        clean["excess_return_pct"], errors="coerce"
    )
    clean = clean.dropna()
    symbols = sorted(clean["symbol"].unique())
    if len(symbols) < 3:
        raise outcomes.HistoricalOutcomeError(
            "company-cluster bootstrap requires at least three companies"
        )

    positive_sums: list[float] = []
    positive_counts: list[int] = []
    negative_sums: list[float] = []
    negative_counts: list[int] = []
    for symbol in symbols:
        block = clean.loc[clean["symbol"] == symbol]
        positive = block.loc[
            block["bucket"] == "POSITIVE", "excess_return_pct"
        ].to_numpy(dtype=float)
        negative = block.loc[
            block["bucket"] == "NEGATIVE", "excess_return_pct"
        ].to_numpy(dtype=float)
        positive_sums.append(float(positive.sum()))
        positive_counts.append(len(positive))
        negative_sums.append(float(negative.sum()))
        negative_counts.append(len(negative))

    pos_sum = np.asarray(positive_sums, dtype=float)
    pos_count = np.asarray(positive_counts, dtype=np.int64)
    neg_sum = np.asarray(negative_sums, dtype=float)
    neg_count = np.asarray(negative_counts, dtype=np.int64)

    rng = np.random.default_rng(seed)
    # A single 2-D choice call consumes the same RNG stream as the previous
    # repeated 1-D calls, preserving the frozen seed's bootstrap sample sequence.
    selected = rng.choice(
        len(symbols),
        size=(iterations, len(symbols)),
        replace=True,
    )
    sampled_pos_count = pos_count[selected].sum(axis=1)
    sampled_neg_count = neg_count[selected].sum(axis=1)
    usable = (sampled_pos_count > 0) & (sampled_neg_count > 0)

    sampled_pos_mean = pos_sum[selected].sum(axis=1)[usable] / sampled_pos_count[usable]
    sampled_neg_mean = neg_sum[selected].sum(axis=1)[usable] / sampled_neg_count[usable]
    spreads = sampled_pos_mean - sampled_neg_mean

    if len(spreads) < iterations * 0.9:
        raise outcomes.HistoricalOutcomeError(
            "too many cluster-bootstrap samples lacked both signal groups"
        )
    alpha = 1.0 - confidence
    return {
        "cluster_unit": "symbol",
        "unique_companies": len(symbols),
        "iterations_requested": iterations,
        "iterations_used": len(spreads),
        "seed": seed,
        "confidence": confidence,
        "low": float(np.quantile(spreads, alpha / 2.0)),
        "high": float(np.quantile(spreads, 1.0 - alpha / 2.0)),
    }


def phase_b_manifest_fast(**kwargs: Any) -> dict[str, Any]:
    """Build the canonical Phase-B manifest with only the bootstrap implementation swapped."""

    original = outcomes._cluster_bootstrap_spread
    outcomes._cluster_bootstrap_spread = cluster_bootstrap_spread_fast
    try:
        return outcomes.phase_b_manifest(**kwargs)
    finally:
        outcomes._cluster_bootstrap_spread = original
