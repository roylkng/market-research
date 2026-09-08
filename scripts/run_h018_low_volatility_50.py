"""Run frozen H018 standalone Low Volatility 50 independent challenge."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import h018_checkpoint_market as h018_market
import numpy as np
import run_h016_nse_style_dual_momentum as h16

MARKET_START = date(2013, 11, 1)
MARKET_END = date(2017, 5, 31)
DECISION_MONTHS = (
    (2014, 11),
    (2015, 5),
    (2015, 11),
    (2016, 5),
    (2016, 11),
)
SELECT_COUNT = 50
RANDOM_SEED = 1818
RANDOM_DRAWS = 10_000


def freeze_selections(sessions, prices, actions):
    positions = {day: idx for idx, day in enumerate(sessions)}
    cohorts = []
    for year, month in DECISION_MONTHS:
        decision = h16.month_end_session(sessions, year, month)
        if decision is None:
            raise ValueError(f"no H018 decision session for {year}-{month:02d}")
        i = positions[decision]
        if i + 1 >= len(sessions):
            raise ValueError(f"no H018 entry session after {decision}")
        exit_year, exit_month = h16.shifted_month(year, month, 6)
        exit_day = h16.month_end_session(sessions, exit_year, exit_month)
        if exit_day is None or exit_day <= decision:
            raise ValueError(f"no H018 semiannual exit after {decision}")
        eligible = h16.company_candidates_at_decision(sessions, prices, actions, decision)
        if len(eligible) < 300:
            raise ValueError(f"H018 requires >=300 eligible companies; found {len(eligible)}")
        for row in eligible:
            row["low_vol_score"] = 1.0 / float(row["vol_1y"])
        selected = sorted(
            eligible,
            key=lambda row: (-float(row["low_vol_score"]), str(row["symbol"])),
        )[:SELECT_COUNT]
        cohorts.append(
            {
                "decision_date": decision.isoformat(),
                "entry_date": sessions[i + 1].isoformat(),
                "exit_date": exit_day.isoformat(),
                "eligible_count": len(eligible),
                "selected_count": SELECT_COUNT,
                "selected_symbols": [row["symbol"] for row in selected],
                "eligible": eligible,
            }
        )
    return cohorts


def select(rows, key: str):
    return sorted(rows, key=lambda row: (-float(row[key]), str(row["symbol"])))[:SELECT_COUNT]


def evaluate(cohorts):
    primary_rows = []
    momentum_rows = []
    raw12_rows = []
    all_eligible = []
    cohort_results = []
    for cohort in cohorts:
        rows = cohort["eligible_with_outcomes"]
        primary = select(rows, "low_vol_score")
        primary_rows.extend(primary)
        momentum_rows.extend(select(rows, "normalized_momentum"))
        raw12_rows.extend(select(rows, "r12"))
        all_eligible.extend(rows)
        cohort_results.append(
            {
                "decision_date": cohort["decision_date"],
                "entry_date": cohort["entry_date"],
                "exit_date": cohort["exit_date"],
                "eligible_count": cohort["eligible_count"],
                "selected_count": SELECT_COUNT,
                **h16.metrics(primary),
            }
        )
    if len(cohort_results) != len(DECISION_MONTHS):
        raise ValueError("not all frozen H018 cohorts were evaluated")
    if len(primary_rows) != SELECT_COUNT * len(DECISION_MONTHS):
        raise ValueError("H018 selected observation count mismatch")

    primary = h16.metrics(primary_rows)
    comparators = {
        "momentum_only": h16.metrics(momentum_rows),
        "raw12": h16.metrics(raw12_rows),
    }
    full = h16.metrics(all_eligible)
    positive_cohorts = sum(float(row["mean_gross_excess"]) > 0 for row in cohort_results)

    rng = np.random.default_rng(RANDOM_SEED)
    random_means = np.empty(RANDOM_DRAWS, dtype=float)
    for draw in range(RANDOM_DRAWS):
        sampled = []
        for cohort in cohorts:
            rows = cohort["eligible_with_outcomes"]
            indexes = rng.choice(len(rows), size=SELECT_COUNT, replace=False)
            sampled.extend(float(rows[index]["gross_excess"]) for index in indexes)
        random_means[draw] = float(np.mean(sampled))
    observed = float(primary["mean_gross_excess"])
    random_p = float((1 + np.sum(random_means >= observed)) / (RANDOM_DRAWS + 1))

    positive_by_isin = defaultdict(float)
    for row in primary_rows:
        positive_by_isin[str(row["isin"])] += max(0.0, float(row["gross_stock_return"]))
    positive_total = sum(positive_by_isin.values())
    concentration = max(positive_by_isin.values()) / positive_total if positive_total > 0 else None
    cohort_means = [float(row["mean_gross_excess"]) for row in cohort_results]
    consecutive_fail = any(
        cohort_means[index] <= 0 and cohort_means[index + 1] <= 0
        for index in range(len(cohort_means) - 1)
    )

    gates = {
        "all_five_cohorts_evaluable": len(cohort_results) == 5,
        "exactly_250_selected_observations": len(primary_rows) == 250,
        "fill_rate_ge_98pct": float(primary["fill_rate"]) >= 0.98,
        "lower_bound_rate_le_2pct": float(primary["lower_bound_rate"]) <= 0.02,
        "mean_gross_excess_gt_2pp": observed > 0.02,
        "median_gross_excess_gt_0": float(primary["median_gross_excess"]) > 0,
        "beat_rate_ge_55pct": float(primary["gross_beat_rate"]) >= 0.55,
        "positive_cohorts_ge_4": positive_cohorts >= 4,
        "beats_full_company_cohort_by_2pp": observed >= float(full["mean_gross_excess"]) + 0.02,
        "random_p_le_005": random_p <= 0.05,
        "isin_concentration_le_015": concentration is not None and concentration <= 0.15,
        "no_two_consecutive_nonpositive_cohorts": not consecutive_fail,
        "mean_net_excess_gt_15pp": float(primary["mean_net_excess"]) > 0.015,
    }
    return {
        "status": "INDEPENDENT_HISTORICAL_CHALLENGE_ONLY",
        "live_capital_allowed": False,
        "external_methodology": "NSE-style standalone one-year Low Volatility 50",
        "cohort_results": cohort_results,
        "selected_observations": len(primary_rows),
        "primary": primary,
        "comparators": comparators,
        "full_eligible_company_cohort": full,
        "positive_cohort_count": positive_cohorts,
        "matched_random_seed": RANDOM_SEED,
        "matched_random_draws": RANDOM_DRAWS,
        "matched_random_p_mean": random_p,
        "max_isin_positive_return_concentration": concentration,
        "gates": gates,
        "pass": all(gates.values()),
    }, primary_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    root = Path(parser.parse_args().out)
    root.mkdir(parents=True, exist_ok=True)

    h16.h15.MARKET_START = MARKET_START
    h16.h15.MARKET_END = MARKET_END
    sessions, prices, index, market_manifest, diagnostics = h018_market.acquire_market(root)
    h16.h15.base.MARKET_START = MARKET_START
    h16.h15.base.MARKET_END = MARKET_END
    actions, action_manifest = h16.h15.base.acquire_actions(root)
    h16.h15.base.dump(root / "source-manifest.json", market_manifest + action_manifest)

    frozen = freeze_selections(sessions, prices, actions)
    h16.h15.base.dump(root / "point-in-time-selections.json", frozen)

    with_outcomes = h16.attach_outcomes(frozen, sessions, prices, index, actions)
    summary, selected = evaluate(with_outcomes)
    summary["common_sessions"] = len(sessions)
    summary["market_symbols"] = len(prices)
    summary["market_acquisition_diagnostics"] = diagnostics
    h16.h15.base.dump(root / "challenge-summary.json", summary)

    fieldnames = sorted({key for row in selected for key in row})
    with (root / "selected.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(selected)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
