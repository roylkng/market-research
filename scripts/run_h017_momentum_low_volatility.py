"""Run frozen H017 momentum plus low-volatility independent challenge."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

import run_h016_nse_style_dual_momentum as h16

MARKET_START = date(2016, 11, 1)
MARKET_END = date(2020, 5, 31)
DECISION_MONTHS = (
    (2017, 11),
    (2018, 5),
    (2018, 11),
    (2019, 5),
    (2019, 11),
)
RANDOM_SEED = 1717
RANDOM_DRAWS = 10_000


def mid_percentile(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("H017 percentile input must be a finite nonempty vector")
    order = np.argsort(values, kind="stable")
    sorted_values = values[order]
    result = np.zeros(len(values), dtype=float)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and sorted_values[end] == sorted_values[start]:
            end += 1
        midpoint = (start + 0.5 * (end - start)) / len(values)
        result[order[start:end]] = midpoint
        start = end
    return result


def freeze_selections(sessions, prices, actions):
    positions = {day: idx for idx, day in enumerate(sessions)}
    cohorts = []
    for year, month in DECISION_MONTHS:
        decision = h16.month_end_session(sessions, year, month)
        if decision is None:
            raise ValueError(f"no H017 decision session for {year}-{month:02d}")
        i = positions[decision]
        if i + 1 >= len(sessions):
            raise ValueError(f"no H017 entry session after {decision}")
        exit_year, exit_month = h16.shifted_month(year, month, 6)
        exit_day = h16.month_end_session(sessions, exit_year, exit_month)
        if exit_day is None or exit_day <= decision:
            raise ValueError(f"no H017 semiannual exit after {decision}")

        eligible = h16.company_candidates_at_decision(sessions, prices, actions, decision)
        momentum_z = np.asarray([float(row["weighted_z"]) for row in eligible])
        inverse_vol = np.asarray([1.0 / float(row["vol_1y"]) for row in eligible])
        low_vol_std = float(np.std(inverse_vol, ddof=1))
        if not math.isfinite(low_vol_std) or low_vol_std <= 0:
            raise ValueError(f"degenerate low-volatility cross-section on {decision}")
        low_vol_z = (inverse_vol - float(np.mean(inverse_vol))) / low_vol_std
        momentum_percentile = mid_percentile(momentum_z)
        low_vol_percentile = mid_percentile(low_vol_z)
        composite = 0.5 * momentum_percentile + 0.5 * low_vol_percentile
        for row, low_raw, low_z, mom_pct, low_pct, score in zip(
            eligible,
            inverse_vol,
            low_vol_z,
            momentum_percentile,
            low_vol_percentile,
            composite,
        ):
            row["low_vol_raw"] = float(low_raw)
            row["low_vol_z"] = float(low_z)
            row["momentum_percentile"] = float(mom_pct)
            row["low_vol_percentile"] = float(low_pct)
            row["h017_score"] = float(score)

        count = max(30, math.ceil(len(eligible) * 0.10))
        selected = sorted(
            eligible,
            key=lambda row: (-float(row["h017_score"]), str(row["symbol"])),
        )[:count]
        cohorts.append(
            {
                "decision_date": decision.isoformat(),
                "entry_date": sessions[i + 1].isoformat(),
                "exit_date": exit_day.isoformat(),
                "eligible_count": len(eligible),
                "selected_count": count,
                "selected_symbols": [row["symbol"] for row in selected],
                "eligible": eligible,
            }
        )
    return cohorts


def select(rows, key: str, count: int):
    return sorted(rows, key=lambda row: (-float(row[key]), str(row["symbol"])))[:count]


def evaluate(cohorts):
    primary_rows = []
    comparator_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    all_eligible = []
    cohort_results = []
    for cohort in cohorts:
        rows = cohort["eligible_with_outcomes"]
        count = int(cohort["selected_count"])
        primary = select(rows, "h017_score", count)
        primary_rows.extend(primary)
        comparator_rows["momentum_only"].extend(select(rows, "normalized_momentum", count))
        comparator_rows["low_vol_only"].extend(select(rows, "low_vol_raw", count))
        comparator_rows["raw12"].extend(select(rows, "r12", count))
        all_eligible.extend(rows)
        cohort_results.append(
            {
                "decision_date": cohort["decision_date"],
                "entry_date": cohort["entry_date"],
                "exit_date": cohort["exit_date"],
                "eligible_count": cohort["eligible_count"],
                "selected_count": cohort["selected_count"],
                **h16.metrics(primary),
            }
        )
    if len(cohort_results) != len(DECISION_MONTHS):
        raise ValueError("not all frozen H017 cohorts were evaluated")

    primary = h16.metrics(primary_rows)
    comparators = {name: h16.metrics(rows) for name, rows in comparator_rows.items()}
    full = h16.metrics(all_eligible)
    positive_cohorts = sum(float(row["mean_gross_excess"]) > 0 for row in cohort_results)

    rng = np.random.default_rng(RANDOM_SEED)
    random_means = np.empty(RANDOM_DRAWS, dtype=float)
    for draw in range(RANDOM_DRAWS):
        sampled = []
        for cohort in cohorts:
            rows = cohort["eligible_with_outcomes"]
            indexes = rng.choice(
                len(rows), size=int(cohort["selected_count"]), replace=False
            )
            sampled.extend(float(rows[index]["gross_excess"]) for index in indexes)
        random_means[draw] = float(np.mean(sampled))
    observed = float(primary["mean_gross_excess"])
    random_p = float((1 + np.sum(random_means >= observed)) / (RANDOM_DRAWS + 1))

    positive_by_isin = defaultdict(float)
    for row in primary_rows:
        positive_by_isin[str(row["isin"])] += max(0.0, float(row["gross_stock_return"]))
    positive_total = sum(positive_by_isin.values())
    concentration = (
        max(positive_by_isin.values()) / positive_total if positive_total > 0 else None
    )
    cohort_means = [float(row["mean_gross_excess"]) for row in cohort_results]
    consecutive_fail = any(
        cohort_means[index] <= 0 and cohort_means[index + 1] <= 0
        for index in range(len(cohort_means) - 1)
    )

    gates = {
        "all_five_cohorts_evaluable": len(cohort_results) == 5,
        "selected_observations_ge_300": len(primary_rows) >= 300,
        "fill_rate_ge_98pct": float(primary["fill_rate"]) >= 0.98,
        "lower_bound_rate_le_2pct": float(primary["lower_bound_rate"]) <= 0.02,
        "mean_gross_excess_gt_2pp": observed > 0.02,
        "median_gross_excess_gt_0": float(primary["median_gross_excess"]) > 0,
        "beat_rate_ge_55pct": float(primary["gross_beat_rate"]) >= 0.55,
        "positive_cohorts_ge_4": positive_cohorts >= 4,
        "beats_full_company_cohort_by_2pp": observed
        >= float(full["mean_gross_excess"]) + 0.02,
        "random_p_le_005": random_p <= 0.05,
        "isin_concentration_le_015": concentration is not None and concentration <= 0.15,
        "no_two_consecutive_nonpositive_cohorts": not consecutive_fail,
        "mean_net_excess_gt_15pp": float(primary["mean_net_excess"]) > 0.015,
    }
    return {
        "status": "INDEPENDENT_HISTORICAL_CHALLENGE_ONLY",
        "live_capital_allowed": False,
        "external_methodology": "NSE-style 50/50 momentum and low-volatility factor percentiles",
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
    sessions, prices, index, market_manifest, diagnostics = h16.h15.acquire_market(root)
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
