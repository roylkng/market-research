"""Run frozen H013 independent robustness on legacy NSE market data."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import statistics
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import run_h010_historical_robustness as base

START = date(2022, 6, 1)
END = date(2024, 6, 30)
DECISION_START = date(2023, 1, 1)
DECISION_END = date(2024, 3, 31)
SEED = 1313
DRAWS = 10_000


def legacy_url(day: date) -> str:
    month = day.strftime("%b").upper()
    return (
        "https://archives.nseindia.com/content/historical/EQUITIES/"
        f"{day.year}/{month}/cm{day.strftime('%d')}{month}{day.year}bhav.csv.zip"
    )


def parse_legacy(raw_zip: bytes, session_date: date) -> dict[str, dict[str, object]]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            names = archive.namelist()
            if len(names) != 1 or not names[0].lower().endswith(".csv"):
                raise ValueError("legacy bhavcopy must contain one CSV")
            text = archive.read(names[0]).decode("utf-8-sig")
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid legacy bhavcopy: {exc}") from exc
    reader = csv.DictReader(io.StringIO(text))
    required = {"SYMBOL", "SERIES", "OPEN", "HIGH", "LOW", "CLOSE", "TOTTRDQTY", "TOTTRDVAL"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError("legacy bhavcopy header mismatch")
    rows = {}
    for row in reader:
        if str(row.get("SERIES") or "").strip().upper() != "EQ":
            continue
        symbol = str(row.get("SYMBOL") or "").strip().upper()
        if not symbol:
            continue
        try:
            values = {
                "open": float(row["OPEN"]),
                "high": float(row["HIGH"]),
                "low": float(row["LOW"]),
                "close": float(row["CLOSE"]),
                "volume": float(row["TOTTRDQTY"]),
                "turnover": float(row["TOTTRDVAL"]),
            }
        except (KeyError, TypeError, ValueError):
            continue
        if min(values["open"], values["high"], values["low"], values["close"]) <= 0:
            continue
        if values["volume"] < 0 or values["turnover"] < 0:
            continue
        if not all(math.isfinite(value) for value in values.values()):
            continue
        if symbol in rows:
            raise ValueError(f"duplicate EQ row for {symbol} on {session_date}")
        rows[symbol] = {
            "date": session_date.isoformat(),
            "isin": str(row.get("ISIN") or "").strip(),
            **values,
        }
    if not rows:
        raise ValueError(f"no usable EQ rows on {session_date}")
    return rows


def month_ends(sessions: list[date]) -> list[date]:
    result = []
    cursor = DECISION_START
    while cursor <= DECISION_END:
        days = [day for day in sessions if day.year == cursor.year and day.month == cursor.month]
        if days:
            result.append(days[-1])
        cursor = date(
            cursor.year + (cursor.month == 12),
            1 if cursor.month == 12 else cursor.month + 1,
            1,
        )
    return result


def evaluate(root: Path, sessions, prices, index, actions) -> None:
    positions = {day: idx for idx, day in enumerate(sessions)}
    cohorts = []
    selected_all = []
    eligible_all = []
    for decision in month_ends(sessions):
        i = positions[decision]
        record = {"decision_date": decision.isoformat()}
        if i < 125 or i + 60 >= len(sessions):
            record.update(status="COVERAGE_FAIL", reason="calendar")
            cohorts.append(record)
            continue
        start = sessions[i - 125]
        entry = sessions[i + 1]
        exit_day = sessions[i + 60]
        sma120 = statistics.mean(index[sessions[j]]["close"] for j in range(i - 119, i + 1))
        nifty60 = index[decision]["close"] / index[sessions[i - 60]]["close"] - 1
        active = index[decision]["close"] > sma120 and nifty60 > 0
        record.update(
            regime_active=active,
            entry_date=entry.isoformat(),
            exit_date=exit_day.isoformat(),
        )
        if not active:
            record["status"] = "REGIME_OFF"
            cohorts.append(record)
            continue
        required = sessions[i - 125 : i + 61]
        liquidity_days = sessions[i - 19 : i + 1]
        eligible = []
        for symbol, bars in prices.items():
            if any(day not in bars for day in required):
                continue
            median_turnover = statistics.median(
                float(bars[day]["turnover"]) for day in liquidity_days
            )
            if median_turnover < 20_000_000:
                continue
            if any(start < action.ex_date <= exit_day for action in actions.get(symbol, ())):
                continue
            entry_bar = bars[entry]
            if abs(float(entry_bar["high"]) - float(entry_bar["low"])) < 1e-12:
                continue
            closes = np.asarray([float(bars[sessions[j]]["close"]) for j in range(i - 125, i - 4)])
            log_returns = np.diff(np.log(closes))
            volatility = float(np.std(log_returns, ddof=1) * math.sqrt(120))
            raw120 = float(closes[-1] / closes[0] - 1)
            if not math.isfinite(volatility) or volatility <= 0:
                continue
            stock_return = float(bars[exit_day]["close"]) / float(entry_bar["open"]) - 1
            benchmark_return = index[exit_day]["close"] / index[entry]["open"] - 1
            eligible.append(
                {
                    "decision_date": decision.isoformat(),
                    "symbol": symbol,
                    "score": raw120 / volatility,
                    "raw120skip5": raw120,
                    "mom60": float(bars[decision]["close"]) / float(bars[sessions[i - 60]]["close"])
                    - 1,
                    "mom20": float(bars[decision]["close"]) / float(bars[sessions[i - 20]]["close"])
                    - 1,
                    "stock_return": stock_return,
                    "nifty500_return": benchmark_return,
                    "excess": stock_return - benchmark_return,
                }
            )
        record["eligible_count"] = len(eligible)
        if len(eligible) < 200:
            record.update(status="COVERAGE_FAIL", reason="eligible_lt_200")
            cohorts.append(record)
            continue
        count = max(20, math.ceil(len(eligible) * 0.10))
        selected = sorted(eligible, key=lambda row: (-row["score"], row["symbol"]))[:count]
        record.update(
            status="ACTIVE",
            selected_count=count,
            mean_excess=float(np.mean([row["excess"] for row in selected])),
            median_excess=float(np.median([row["excess"] for row in selected])),
            beat_rate=float(np.mean([row["excess"] > 0 for row in selected])),
        )
        cohorts.append(record)
        selected_all.extend(selected)
        eligible_all.extend(eligible)
    active = [row for row in cohorts if row.get("status") == "ACTIVE"]
    if not selected_all:
        raise ValueError("no active H013 selections")
    mean_excess = float(np.mean([row["excess"] for row in selected_all]))
    median_excess = float(np.median([row["excess"] for row in selected_all]))
    beat_rate = float(np.mean([row["excess"] > 0 for row in selected_all]))
    positive_cohort_rate = float(np.mean([row["mean_excess"] > 0 for row in active]))
    grouped = {
        row["decision_date"]: [
            item for item in eligible_all if item["decision_date"] == row["decision_date"]
        ]
        for row in active
    }
    comparator_means = {}
    for key in ("raw120skip5", "mom60", "mom20"):
        values = []
        for cohort in active:
            group = grouped[cohort["decision_date"]]
            values.extend(
                sorted(group, key=lambda row: (-row[key], row["symbol"]))[
                    : int(cohort["selected_count"])
                ]
            )
        comparator_means[key] = float(np.mean([row["excess"] for row in values]))
    full_mean = float(np.mean([row["excess"] for row in eligible_all]))
    rng = np.random.default_rng(SEED)
    random_means = []
    for _ in range(DRAWS):
        values = []
        for cohort in active:
            group = grouped[cohort["decision_date"]]
            indexes = rng.choice(len(group), size=int(cohort["selected_count"]), replace=False)
            values.extend(group[idx]["excess"] for idx in indexes)
        random_means.append(float(np.mean(values)))
    random_p = (1 + sum(value >= mean_excess for value in random_means)) / (DRAWS + 1)
    positive_by_symbol = defaultdict(float)
    for row in selected_all:
        if row["stock_return"] > 0:
            positive_by_symbol[row["symbol"]] += row["stock_return"]
    positive_total = sum(positive_by_symbol.values())
    concentration = max(positive_by_symbol.values()) / positive_total if positive_total else None
    quarters = defaultdict(list)
    for cohort in active:
        day = date.fromisoformat(cohort["decision_date"])
        quarters[f"{day.year}Q{(day.month - 1) // 3 + 1}"].append(cohort["mean_excess"])
    quarter_medians = {
        key: float(np.median(values)) for key, values in quarters.items() if len(values) >= 2
    }
    gates = {
        "active_cohorts_ge_5": len(active) >= 5,
        "selected_observations_ge_500": len(selected_all) >= 500,
        "mean_excess_gt_2pp": mean_excess > 0.02,
        "median_excess_gt_0": median_excess > 0,
        "beat_rate_ge_52pct": beat_rate >= 0.52,
        "positive_cohort_rate_ge_two_thirds": positive_cohort_rate >= 2 / 3,
        "beats_raw120": mean_excess >= comparator_means["raw120skip5"],
        "beats_prior60": mean_excess >= comparator_means["mom60"],
        "beats_full_by_2pp": mean_excess >= full_mean + 0.02,
        "random_p_le_005": random_p <= 0.05,
        "concentration_le_015": concentration is not None and concentration <= 0.15,
        "quarter_stability": all(value > 0 for value in quarter_medians.values()),
    }
    summary = {
        "status": "HISTORICAL_ROBUSTNESS_ONLY",
        "live_capital_allowed": False,
        "common_sessions": len(sessions),
        "symbols": len(prices),
        "active_cohorts": len(active),
        "selected_observations": len(selected_all),
        "mean_selected_excess": mean_excess,
        "median_selected_excess": median_excess,
        "selected_beat_rate": beat_rate,
        "active_cohort_positive_rate": positive_cohort_rate,
        "raw120_mean_excess": comparator_means["raw120skip5"],
        "prior60_mean_excess": comparator_means["mom60"],
        "prior20_mean_excess": comparator_means["mom20"],
        "full_eligible_mean_excess": full_mean,
        "matched_random_p_mean": random_p,
        "max_symbol_positive_return_concentration": concentration,
        "quarter_median_active_excess": quarter_medians,
        "gates": gates,
        "pass": all(gates.values()),
    }
    base.dump(root / "robustness-summary.json", summary)
    base.dump(root / "cohorts.json", cohorts)
    with (root / "selected.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected_all[0]))
        writer.writeheader()
        writer.writerows(selected_all)
    print(json.dumps(summary, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    root = Path(parser.parse_args().out)
    root.mkdir(parents=True, exist_ok=True)
    base.MARKET_START = START
    base.MARKET_END = END
    base.udiff_url = legacy_url
    base.parse_udiff = parse_legacy
    sessions, prices, index, market_manifest = base.acquire_market(root)
    actions, action_manifest = base.acquire_actions(root)
    base.dump(root / "source-manifest.json", market_manifest + action_manifest)
    evaluate(root, sessions, prices, index, actions)


if __name__ == "__main__":
    main()
