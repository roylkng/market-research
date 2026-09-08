"""Run frozen H016 NSE-style dual-horizon momentum challenge."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

import run_h015_independent_challenge as h15

MARKET_START = date(2019, 11, 1)
MARKET_END = date(2023, 5, 31)
DECISION_MONTHS = (
    (2020, 11),
    (2021, 5),
    (2021, 11),
    (2022, 5),
    (2022, 11),
)
MIN_TURNOVER = 20_000_000.0
RANDOM_SEED = 1616
RANDOM_DRAWS = 10_000
FRICTION = 0.005


def shifted_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def month_end_session(sessions: list[date], year: int, month: int) -> date | None:
    matches = [day for day in sessions if day.year == year and day.month == month]
    return matches[-1] if matches else None


def company_candidates_at_decision(
    sessions: list[date],
    prices: dict[str, dict[date, dict[str, object]]],
    actions,
    decision: date,
) -> list[dict[str, object]]:
    positions = {day: idx for idx, day in enumerate(sessions)}
    i = positions[decision]
    year6, month6 = shifted_month(decision.year, decision.month, -6)
    year12, month12 = shifted_month(decision.year, decision.month, -12)
    p6_day = month_end_session(sessions, year6, month6)
    p12_day = month_end_session(sessions, year12, month12)
    if p6_day is None or p12_day is None or not (p12_day < p6_day < decision):
        raise ValueError(f"missing frozen 6/12-month anchor for {decision}")
    start_idx = positions[p12_day]
    history = sessions[start_idx : i + 1]
    liquidity_days = sessions[i - 19 : i + 1]
    if len(liquidity_days) != 20:
        raise ValueError(f"insufficient liquidity calendar for {decision}")

    by_isin: dict[str, dict[str, object]] = {}
    for symbol, bars in prices.items():
        decision_bar = bars.get(decision)
        if decision_bar is None:
            continue
        isin = str(decision_bar.get("isin") or "").strip().upper()
        if len(isin) != 12 or not isin.startswith("INE"):
            continue
        if any(day not in bars for day in history):
            continue
        if statistics.median(float(bars[day]["turnover"]) for day in liquidity_days) < MIN_TURNOVER:
            continue
        if h15.predecision_action_crossing(actions.get(symbol, ()), p12_day, decision):
            continue
        closes = np.asarray([float(bars[day]["close"]) for day in history], dtype=float)
        if len(closes) < 200 or not np.isfinite(closes).all() or np.any(closes <= 0):
            continue
        log_returns = np.diff(np.log(closes))
        vol_1y = float(np.std(log_returns, ddof=1) * math.sqrt(252))
        if not math.isfinite(vol_1y) or vol_1y <= 0:
            continue
        p0 = float(bars[decision]["close"])
        p6 = float(bars[p6_day]["close"])
        p12 = float(bars[p12_day]["close"])
        r6 = p0 / p6 - 1
        r12 = p0 / p12 - 1
        candidate = {
            "decision_date": decision.isoformat(),
            "symbol": symbol,
            "isin": isin,
            "p6_date": p6_day.isoformat(),
            "p12_date": p12_day.isoformat(),
            "r6": r6,
            "r12": r12,
            "vol_1y": vol_1y,
            "mr6": r6 / vol_1y,
            "mr12": r12 / vol_1y,
        }
        existing = by_isin.get(isin)
        if existing is None or symbol < str(existing["symbol"]):
            by_isin[isin] = candidate

    candidates = sorted(by_isin.values(), key=lambda row: str(row["symbol"]))
    if len(candidates) < 300:
        raise ValueError(
            f"H016 requires >=300 point-in-time companies on {decision}; found {len(candidates)}"
        )
    mr6 = np.asarray([float(row["mr6"]) for row in candidates])
    mr12 = np.asarray([float(row["mr12"]) for row in candidates])
    std6 = float(np.std(mr6, ddof=1))
    std12 = float(np.std(mr12, ddof=1))
    if not math.isfinite(std6) or not math.isfinite(std12) or std6 <= 0 or std12 <= 0:
        raise ValueError(f"degenerate H016 cross-section on {decision}")
    z6 = (mr6 - float(np.mean(mr6))) / std6
    z12 = (mr12 - float(np.mean(mr12))) / std12
    weighted = 0.5 * z12 + 0.5 * z6
    for row, value6, value12, value in zip(candidates, z6, z12, weighted):
        row["z6"] = float(value6)
        row["z12"] = float(value12)
        row["weighted_z"] = float(value)
        row["normalized_momentum"] = (
            1.0 + float(value) if value >= 0 else 1.0 / (1.0 - float(value))
        )
    return candidates


def freeze_selections(sessions, prices, actions):
    positions = {day: idx for idx, day in enumerate(sessions)}
    cohorts = []
    for year, month in DECISION_MONTHS:
        decision = month_end_session(sessions, year, month)
        if decision is None:
            raise ValueError(f"no decision session for {year}-{month:02d}")
        i = positions[decision]
        if i + 1 >= len(sessions):
            raise ValueError(f"no target entry session after {decision}")
        exit_year, exit_month = shifted_month(year, month, 6)
        exit_day = month_end_session(sessions, exit_year, exit_month)
        if exit_day is None or exit_day <= decision:
            raise ValueError(f"no frozen semiannual exit after {decision}")
        eligible = company_candidates_at_decision(sessions, prices, actions, decision)
        count = max(30, math.ceil(len(eligible) * 0.10))
        selected = sorted(
            eligible,
            key=lambda row: (-float(row["normalized_momentum"]), str(row["symbol"])),
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


def attach_outcomes(cohorts, sessions, prices, index, actions):
    dates = {day.isoformat(): day for day in sessions}
    for cohort in cohorts:
        entry = dates[str(cohort["entry_date"])]
        exit_day = dates[str(cohort["exit_date"])]
        enriched = []
        for row in cohort["eligible"]:
            item = dict(row)
            item.update(
                h15.realized_outcome(
                    str(row["symbol"]),
                    str(row["isin"]),
                    entry,
                    exit_day,
                    prices,
                    index,
                    actions,
                )
            )
            enriched.append(item)
        cohort["eligible_with_outcomes"] = enriched
    return cohorts


def select(rows, key: str, count: int):
    return sorted(rows, key=lambda row: (-float(row[key]), str(row["symbol"])))[:count]


def metrics(rows):
    gross_excess = np.asarray([float(row["gross_excess"]) for row in rows])
    net_excess = np.asarray([float(row["net_excess"]) for row in rows])
    return {
        "observations": len(rows),
        "mean_gross_excess": float(np.mean(gross_excess)),
        "median_gross_excess": float(np.median(gross_excess)),
        "gross_beat_rate": float(np.mean(gross_excess > 0)),
        "mean_net_excess": float(np.mean(net_excess)),
        "median_net_excess": float(np.median(net_excess)),
        "fill_rate": float(np.mean([bool(row["filled"]) for row in rows])),
        "lower_bound_rate": float(np.mean([bool(row["lower_bound"]) for row in rows])),
        "mean_gross_stock_return": float(
            np.mean([float(row["gross_stock_return"]) for row in rows])
        ),
    }


def evaluate(cohorts):
    primary_rows = []
    comparator_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    all_eligible = []
    cohort_results = []
    for cohort in cohorts:
        rows = cohort["eligible_with_outcomes"]
        count = int(cohort["selected_count"])
        primary = select(rows, "normalized_momentum", count)
        primary_rows.extend(primary)
        comparator_rows["raw6"].extend(select(rows, "r6", count))
        comparator_rows["raw12"].extend(select(rows, "r12", count))
        comparator_rows["mr6"].extend(select(rows, "mr6", count))
        comparator_rows["mr12"].extend(select(rows, "mr12", count))
        all_eligible.extend(rows)
        result = metrics(primary)
        cohort_results.append(
            {
                "decision_date": cohort["decision_date"],
                "entry_date": cohort["entry_date"],
                "exit_date": cohort["exit_date"],
                "eligible_count": cohort["eligible_count"],
                "selected_count": cohort["selected_count"],
                **result,
            }
        )
    if len(cohort_results) != len(DECISION_MONTHS):
        raise ValueError("not all frozen H016 cohorts were evaluated")

    primary = metrics(primary_rows)
    comparators = {name: metrics(rows) for name, rows in comparator_rows.items()}
    full = metrics(all_eligible)
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
        "external_methodology": "NSE-style 6m/12m volatility-adjusted momentum z-score",
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

    h15.MARKET_START = MARKET_START
    h15.MARKET_END = MARKET_END
    sessions, prices, index, market_manifest, diagnostics = h15.acquire_market(root)
    h15.base.MARKET_START = MARKET_START
    h15.base.MARKET_END = MARKET_END
    actions, action_manifest = h15.base.acquire_actions(root)
    h15.base.dump(root / "source-manifest.json", market_manifest + action_manifest)

    frozen = freeze_selections(sessions, prices, actions)
    h15.base.dump(root / "point-in-time-selections.json", frozen)

    with_outcomes = attach_outcomes(frozen, sessions, prices, index, actions)
    summary, selected = evaluate(with_outcomes)
    summary["common_sessions"] = len(sessions)
    summary["market_symbols"] = len(prices)
    summary["market_acquisition_diagnostics"] = diagnostics
    h15.base.dump(root / "challenge-summary.json", summary)

    fieldnames = sorted({key for row in selected for key in row})
    with (root / "selected.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(selected)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
