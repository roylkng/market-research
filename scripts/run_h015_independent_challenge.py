"""Run frozen H015 point-in-time company-selection challenge on legacy NSE data."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import statistics
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import run_h010_historical_robustness as base

MARKET_START = date(2022, 6, 1)
MARKET_END = date(2024, 6, 30)
DECISION_START = date(2023, 1, 1)
DECISION_END = date(2024, 3, 31)
MIN_TURNOVER = 20_000_000.0
RANDOM_SEED = 1515
RANDOM_DRAWS = 10_000
FRICTION = 0.005


def parse_nifty500_source_date(raw_csv: bytes, session_date: date) -> dict[str, float]:
    """Parse Nifty 500, allowing only source-date-confirmed MM-DD transposition."""
    try:
        return base.parse_nifty500(raw_csv, session_date)
    except ValueError:
        text = raw_csv.decode("utf-8-sig")
        rows = [
            row
            for row in csv.DictReader(io.StringIO(text))
            if " ".join(str(row.get("Index Name") or "").split()).casefold() == "nifty 500"
        ]
        if len(rows) != 1:
            raise
        row = rows[0]
        parts = str(row.get("Index Date") or "").strip().split("-")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise
        fallback_date = date(int(parts[2]), int(parts[0]), int(parts[1]))
        if fallback_date != session_date:
            raise
        opened = float(row["Open Index Value"])
        closed = float(row["Closing Index Value"])
        if not all(math.isfinite(value) and value > 0 for value in (opened, closed)):
            raise ValueError("nonpositive Nifty 500 OHLC in source-date fallback")
        return {"open": opened, "close": closed}


def legacy_bhavcopy_url(day: date) -> str:
    month = day.strftime("%b").upper()
    return (
        "https://archives.nseindia.com/content/historical/EQUITIES/"
        f"{day.year}/{month}/cm{day.strftime('%d')}{month}{day.year}bhav.csv.zip"
    )


def parse_legacy_bhavcopy(raw_zip: bytes, session_date: date) -> dict[str, dict[str, object]]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            names = archive.namelist()
            if len(names) != 1 or not names[0].lower().endswith(".csv"):
                raise ValueError("legacy bhavcopy must contain exactly one CSV")
            text = archive.read(names[0]).decode("utf-8-sig")
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid legacy bhavcopy: {exc}") from exc
    reader = csv.DictReader(io.StringIO(text))
    required = {
        "SYMBOL",
        "SERIES",
        "OPEN",
        "HIGH",
        "LOW",
        "CLOSE",
        "TOTTRDQTY",
        "TOTTRDVAL",
        "ISIN",
    }
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise ValueError("legacy bhavcopy header mismatch")
    result: dict[str, dict[str, object]] = {}
    for row in reader:
        if str(row.get("SERIES") or "").strip().upper() != "EQ":
            continue
        symbol = str(row.get("SYMBOL") or "").strip().upper()
        isin = str(row.get("ISIN") or "").strip().upper()
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
        if not all(math.isfinite(value) for value in values.values()):
            continue
        if min(values["open"], values["high"], values["low"], values["close"]) <= 0:
            continue
        if values["volume"] < 0 or values["turnover"] < 0:
            continue
        if symbol in result:
            raise ValueError(f"duplicate EQ row for {symbol} on {session_date}")
        result[symbol] = {
            "date": session_date.isoformat(),
            "isin": isin,
            **values,
        }
    if not result:
        raise ValueError(f"no usable EQ rows on {session_date}")
    return result


def calendar_days(start: date, end: date) -> list[date]:
    days = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def fetch_market_day(day: date):
    b_url = legacy_bhavcopy_url(day)
    i_url = base.index_snapshot_url(day)
    b_raw, b_meta = base.fetch_public(b_url, kind="legacy-bhavcopy", attempts=4)
    i_raw, i_meta = base.fetch_public(i_url, kind="index", attempts=4)
    return day, b_url, b_raw, b_meta, i_url, i_raw, i_meta


def acquire_market(root: Path):
    days = calendar_days(MARKET_START, MARKET_END)
    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch_market_day, day) for day in days]
        for number, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if number % 100 == 0:
                print(f"market requests {number}/{len(days)}", flush=True)

    prices: dict[str, dict[date, dict[str, object]]] = defaultdict(dict)
    index: dict[date, dict[str, float]] = {}
    sessions: list[date] = []
    manifest: list[dict[str, object]] = []
    diagnostics = {
        "index_only_dates": [],
        "bhavcopy_without_index": [],
        "parse_errors": [],
        "serial_retries": [],
    }

    for day, b_url, b_raw, b_meta, i_url, i_raw, i_meta in sorted(
        results, key=lambda item: item[0]
    ):
        if b_raw is not None and i_raw is None:
            retry_raw, retry_meta = base.fetch_public(i_url, kind="index-serial-retry", attempts=8)
            diagnostics["serial_retries"].append(
                {
                    "date": day.isoformat(),
                    "side": "index",
                    "initial_status": i_meta.get("status"),
                    "retry_status": retry_meta.get("status"),
                }
            )
            if retry_raw is not None:
                i_raw, i_meta = retry_raw, retry_meta
        elif b_raw is None and i_raw is not None:
            retry_raw, retry_meta = base.fetch_public(
                b_url, kind="legacy-bhavcopy-serial-retry", attempts=8
            )
            diagnostics["serial_retries"].append(
                {
                    "date": day.isoformat(),
                    "side": "bhavcopy",
                    "initial_status": b_meta.get("status"),
                    "retry_status": retry_meta.get("status"),
                }
            )
            if retry_raw is not None:
                b_raw, b_meta = retry_raw, retry_meta

        if b_raw is None:
            if i_raw is not None:
                diagnostics["index_only_dates"].append(day.isoformat())
                manifest.append(base.retain(root, i_raw, url=i_url, kind="index-only"))
            continue
        if i_raw is None:
            diagnostics["bhavcopy_without_index"].append(
                {
                    "date": day.isoformat(),
                    "bhavcopy_status": b_meta.get("status"),
                    "index_status": i_meta.get("status"),
                }
            )
            manifest.append(base.retain(root, b_raw, url=b_url, kind="legacy-bhavcopy"))
            continue

        b_retained = base.retain(root, b_raw, url=b_url, kind="legacy-bhavcopy")
        i_retained = base.retain(root, i_raw, url=i_url, kind="index")
        manifest.extend([b_retained, i_retained])
        try:
            equities = parse_legacy_bhavcopy(b_raw, day)
            nifty = parse_nifty500_source_date(i_raw, day)
        except ValueError as exc:
            diagnostics["parse_errors"].append({"date": day.isoformat(), "error": str(exc)})
            continue
        sessions.append(day)
        index[day] = nifty
        for symbol, bar in equities.items():
            prices[symbol][day] = bar

    base.dump(root / "market-acquisition-diagnostics.json", diagnostics)
    base.dump(root / "market-source-manifest.json", manifest)
    if diagnostics["bhavcopy_without_index"]:
        raise ValueError(
            "official Nifty 500 source unavailable on "
            f"{len(diagnostics['bhavcopy_without_index'])} retained equity sessions"
        )
    if diagnostics["parse_errors"]:
        raise ValueError(f"market parse errors on {len(diagnostics['parse_errors'])} dates")
    sessions = sorted(set(sessions))
    if len(sessions) < 400:
        raise ValueError(f"insufficient common market sessions: {len(sessions)}")
    return sessions, prices, index, manifest, diagnostics


def month_ends(sessions: list[date]) -> list[date]:
    result = []
    cursor = DECISION_START
    while cursor <= DECISION_END:
        days = [day for day in sessions if day.year == cursor.year and day.month == cursor.month]
        if days:
            result.append(days[-1])
        cursor = date(
            cursor.year + int(cursor.month == 12),
            1 if cursor.month == 12 else cursor.month + 1,
            1,
        )
    return result


def predecision_action_crossing(actions, start: date, decision: date) -> bool:
    return any(start < action.ex_date <= decision for action in actions)


def build_point_in_time_cohorts(sessions, prices, index, actions):
    positions = {day: idx for idx, day in enumerate(sessions)}
    cohorts = []
    for decision in month_ends(sessions):
        i = positions[decision]
        cohort = {"decision_date": decision.isoformat()}
        if i < 125 or i + 60 >= len(sessions):
            cohort.update(status="COVERAGE_FAIL", reason="calendar")
            cohorts.append(cohort)
            continue
        start = sessions[i - 125]
        history = sessions[i - 125 : i + 1]
        liquidity_days = sessions[i - 19 : i + 1]
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
            if (
                statistics.median(float(bars[day]["turnover"]) for day in liquidity_days)
                < MIN_TURNOVER
            ):
                continue
            if predecision_action_crossing(actions.get(symbol, ()), start, decision):
                continue
            closes = np.asarray([float(bars[day]["close"]) for day in sessions[i - 125 : i - 4]])
            log_returns = np.diff(np.log(closes))
            volatility = float(np.std(log_returns, ddof=1) * math.sqrt(120))
            if not math.isfinite(volatility) or volatility <= 0:
                continue
            raw120 = float(closes[-1] / closes[0] - 1)
            candidate = {
                "decision_date": decision.isoformat(),
                "symbol": symbol,
                "isin": isin,
                "score": raw120 / volatility,
                "raw120skip5": raw120,
                "mom60": float(bars[decision]["close"]) / float(bars[sessions[i - 60]]["close"])
                - 1,
                "mom20": float(bars[decision]["close"]) / float(bars[sessions[i - 20]]["close"])
                - 1,
                "mom60_20_sessions_ago": float(bars[sessions[i - 20]]["close"])
                / float(bars[sessions[i - 80]]["close"])
                - 1,
            }
            existing = by_isin.get(isin)
            if existing is None or symbol < str(existing["symbol"]):
                by_isin[isin] = candidate
        eligible = sorted(by_isin.values(), key=lambda row: str(row["symbol"]))
        cohort["eligible_count"] = len(eligible)
        if len(eligible) < 200:
            cohort.update(status="COVERAGE_FAIL", reason="eligible_company_equities_lt_200")
            cohorts.append(cohort)
            continue
        sma120 = statistics.mean(index[sessions[j]]["close"] for j in range(i - 119, i + 1))
        nifty60 = index[decision]["close"] / index[sessions[i - 60]]["close"] - 1
        breadth_now = float(np.mean([float(row["mom60"]) > 0 for row in eligible]))
        breadth_20 = float(np.mean([float(row["mom60_20_sessions_ago"]) > 0 for row in eligible]))
        breadth_change = breadth_now - breadth_20
        broad_regime = index[decision]["close"] > sma120 and nifty60 > 0
        breadth_confirmed = breadth_now >= 0.55 or breadth_change >= 0.10
        cohort.update(
            nifty500_above_120sma=index[decision]["close"] > sma120,
            nifty500_prior60_positive=nifty60 > 0,
            breadth_now=breadth_now,
            breadth_20_sessions_ago=breadth_20,
            breadth_change_20=breadth_change,
            breadth_confirmed=breadth_confirmed,
        )
        if not (broad_regime and breadth_confirmed):
            cohort.update(status="REGIME_OFF", eligible=eligible)
            cohorts.append(cohort)
            continue
        count = max(20, math.ceil(len(eligible) * 0.10))
        selected_symbols = [
            row["symbol"]
            for row in sorted(eligible, key=lambda row: (-float(row["score"]), str(row["symbol"])))[
                :count
            ]
        ]
        cohort.update(
            status="ACTIVE",
            selected_count=count,
            selected_symbols=selected_symbols,
            eligible=eligible,
            entry_date=sessions[i + 1].isoformat(),
            exit_date=sessions[i + 60].isoformat(),
        )
        cohorts.append(cohort)
    return cohorts


def future_share_factor(actions, entry: date, exit_day: date) -> tuple[float | None, str | None]:
    factor = 1.0
    for action in actions:
        if not (entry < action.ex_date <= exit_day):
            continue
        if action.unresolved or action.factor is None:
            return None, action.subject
        factor *= action.factor
    return factor, None


def realized_outcome(symbol, decision_isin, entry, exit_day, prices, index, actions):
    bars = prices.get(symbol, {})
    entry_bar = bars.get(entry)
    benchmark_return = index[exit_day]["close"] / index[entry]["open"] - 1
    if entry_bar is None:
        return {
            "execution_status": "NO_FILL_MISSING_ENTRY_BAR",
            "gross_stock_return": 0.0,
            "net_stock_return": 0.0,
            "benchmark_return": benchmark_return,
            "gross_excess": -benchmark_return,
            "net_excess": -benchmark_return,
            "lower_bound": False,
            "filled": False,
        }
    if str(entry_bar.get("isin") or "").strip().upper() != decision_isin:
        return {
            "execution_status": "NO_FILL_IDENTITY_CHANGED",
            "gross_stock_return": 0.0,
            "net_stock_return": 0.0,
            "benchmark_return": benchmark_return,
            "gross_excess": -benchmark_return,
            "net_excess": -benchmark_return,
            "lower_bound": False,
            "filled": False,
        }
    if abs(float(entry_bar["high"]) - float(entry_bar["low"])) < 1e-12:
        return {
            "execution_status": "NO_FILL_FLAT_ENTRY",
            "gross_stock_return": 0.0,
            "net_stock_return": 0.0,
            "benchmark_return": benchmark_return,
            "gross_excess": -benchmark_return,
            "net_excess": -benchmark_return,
            "lower_bound": False,
            "filled": False,
        }
    factor, unresolved = future_share_factor(actions.get(symbol, ()), entry, exit_day)
    exit_bar = bars.get(exit_day)
    if factor is None or exit_bar is None:
        gross = -1.0
        return {
            "execution_status": (
                "LOWER_BOUND_UNRESOLVED_ACTION" if unresolved else "LOWER_BOUND_MISSING_EXIT_BAR"
            ),
            "gross_stock_return": gross,
            "net_stock_return": -1.0,
            "benchmark_return": benchmark_return,
            "gross_excess": gross - benchmark_return,
            "net_excess": -1.0 - benchmark_return,
            "lower_bound": True,
            "filled": True,
            "unresolved_subject": unresolved,
        }
    gross = float(exit_bar["close"]) * float(factor) / float(entry_bar["open"]) - 1
    net = max(-1.0, gross - FRICTION)
    return {
        "execution_status": "FILLED_RESOLVED",
        "gross_stock_return": gross,
        "net_stock_return": net,
        "benchmark_return": benchmark_return,
        "gross_excess": gross - benchmark_return,
        "net_excess": net - benchmark_return,
        "lower_bound": False,
        "filled": True,
    }


def attach_outcomes(cohorts, sessions, prices, index, actions):
    by_day = {day.isoformat(): day for day in sessions}
    for cohort in cohorts:
        if cohort.get("status") != "ACTIVE":
            continue
        entry = by_day[str(cohort["entry_date"])]
        exit_day = by_day[str(cohort["exit_date"])]
        enriched = []
        for row in cohort["eligible"]:
            item = dict(row)
            item.update(
                realized_outcome(
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


def select_by(rows, key: str, count: int):
    return sorted(rows, key=lambda row: (-float(row[key]), str(row["symbol"])))[:count]


def aggregate_metrics(rows):
    gross_excess = np.asarray([float(row["gross_excess"]) for row in rows])
    net_excess = np.asarray([float(row["net_excess"]) for row in rows])
    raw = np.asarray([float(row["gross_stock_return"]) for row in rows])
    return {
        "observations": len(rows),
        "mean_gross_excess": float(np.mean(gross_excess)),
        "median_gross_excess": float(np.median(gross_excess)),
        "gross_beat_rate": float(np.mean(gross_excess > 0)),
        "mean_net_excess": float(np.mean(net_excess)),
        "median_net_excess": float(np.median(net_excess)),
        "mean_gross_stock_return": float(np.mean(raw)),
        "fill_rate": float(np.mean([bool(row["filled"]) for row in rows])),
        "lower_bound_rate": float(np.mean([bool(row["lower_bound"]) for row in rows])),
    }


def evaluate(cohorts):
    active = [cohort for cohort in cohorts if cohort.get("status") == "ACTIVE"]
    primary_rows = []
    comparator_rows = defaultdict(list)
    all_eligible_rows = []
    cohort_results = []
    for cohort in active:
        rows = cohort["eligible_with_outcomes"]
        count = int(cohort["selected_count"])
        primary = select_by(rows, "score", count)
        raw120 = select_by(rows, "raw120skip5", count)
        mom60 = select_by(rows, "mom60", count)
        mom20 = select_by(rows, "mom20", count)
        primary_rows.extend(primary)
        comparator_rows["raw120"].extend(raw120)
        comparator_rows["mom60"].extend(mom60)
        comparator_rows["mom20"].extend(mom20)
        all_eligible_rows.extend(rows)
        metrics = aggregate_metrics(primary)
        cohort_results.append(
            {
                "decision_date": cohort["decision_date"],
                "selected_count": count,
                "eligible_count": cohort["eligible_count"],
                "breadth_now": cohort["breadth_now"],
                "breadth_change_20": cohort["breadth_change_20"],
                **metrics,
            }
        )
    if not primary_rows:
        raise ValueError("H015 produced no active selected observations")

    primary_metrics = aggregate_metrics(primary_rows)
    comparator_metrics = {name: aggregate_metrics(rows) for name, rows in comparator_rows.items()}
    full_metrics = aggregate_metrics(all_eligible_rows)
    positive_cohort_rate = float(
        np.mean([float(row["mean_gross_excess"]) > 0 for row in cohort_results])
    )

    rng = np.random.default_rng(RANDOM_SEED)
    random_means = np.empty(RANDOM_DRAWS, dtype=float)
    for draw in range(RANDOM_DRAWS):
        values = []
        for cohort in active:
            rows = cohort["eligible_with_outcomes"]
            idx = rng.choice(len(rows), size=int(cohort["selected_count"]), replace=False)
            values.extend(float(rows[pos]["gross_excess"]) for pos in idx)
        random_means[draw] = float(np.mean(values))
    observed_mean = float(primary_metrics["mean_gross_excess"])
    random_p = float((1 + np.sum(random_means >= observed_mean)) / (RANDOM_DRAWS + 1))

    positive_by_isin = defaultdict(float)
    for row in primary_rows:
        positive_by_isin[str(row["isin"])] += max(0.0, float(row["gross_stock_return"]))
    positive_total = sum(positive_by_isin.values())
    concentration = max(positive_by_isin.values()) / positive_total if positive_total > 0 else None

    quarters = defaultdict(list)
    for row in cohort_results:
        day = date.fromisoformat(str(row["decision_date"]))
        quarters[f"{day.year}Q{(day.month - 1) // 3 + 1}"].append(float(row["mean_gross_excess"]))
    quarter_medians = {
        quarter: float(np.median(values))
        for quarter, values in quarters.items()
        if len(values) >= 2
    }

    gates = {
        "active_cohorts_ge_5": len(active) >= 5,
        "selected_company_observations_ge_500": len(primary_rows) >= 500,
        "fill_rate_ge_98pct": float(primary_metrics["fill_rate"]) >= 0.98,
        "lower_bound_rate_le_2pct": float(primary_metrics["lower_bound_rate"]) <= 0.02,
        "mean_gross_excess_gt_2pp": observed_mean > 0.02,
        "median_gross_excess_gt_0": float(primary_metrics["median_gross_excess"]) > 0,
        "gross_beat_rate_ge_52pct": float(primary_metrics["gross_beat_rate"]) >= 0.52,
        "positive_cohort_rate_ge_two_thirds": positive_cohort_rate >= 2 / 3,
        "beats_raw120": observed_mean >= float(comparator_metrics["raw120"]["mean_gross_excess"]),
        "beats_prior60": observed_mean >= float(comparator_metrics["mom60"]["mean_gross_excess"]),
        "beats_full_company_cohort_by_2pp": observed_mean
        >= float(full_metrics["mean_gross_excess"]) + 0.02,
        "random_p_le_005": random_p <= 0.05,
        "isin_concentration_le_015": concentration is not None and concentration <= 0.15,
        "quarter_stability": all(value > 0 for value in quarter_medians.values()),
        "mean_net_excess_gt_15bp": float(primary_metrics["mean_net_excess"]) > 0.015,
    }
    return {
        "status": "INDEPENDENT_HISTORICAL_CHALLENGE_ONLY",
        "live_capital_allowed": False,
        "active_cohorts": len(active),
        "selected_observations": len(primary_rows),
        "primary": primary_metrics,
        "comparators": comparator_metrics,
        "full_eligible_company_cohort": full_metrics,
        "positive_active_cohort_rate": positive_cohort_rate,
        "matched_random_seed": RANDOM_SEED,
        "matched_random_draws": RANDOM_DRAWS,
        "matched_random_p_mean": random_p,
        "max_isin_positive_return_concentration": concentration,
        "quarter_median_active_excess": quarter_medians,
        "cohorts": cohort_results,
        "gates": gates,
        "pass": all(gates.values()),
    }, primary_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    root = Path(parser.parse_args().out)
    root.mkdir(parents=True, exist_ok=True)

    sessions, prices, index, market_manifest, diagnostics = acquire_market(root)
    base.MARKET_START = MARKET_START
    base.MARKET_END = MARKET_END
    actions, action_manifest = base.acquire_actions(root)
    base.dump(root / "source-manifest.json", market_manifest + action_manifest)

    point_in_time = build_point_in_time_cohorts(sessions, prices, index, actions)
    frozen = []
    for cohort in point_in_time:
        retained = {key: value for key, value in cohort.items() if key != "eligible"}
        if "eligible" in cohort:
            retained["eligible"] = cohort["eligible"]
        frozen.append(retained)
    base.dump(root / "point-in-time-selections.json", frozen)

    with_outcomes = attach_outcomes(point_in_time, sessions, prices, index, actions)
    summary, selected = evaluate(with_outcomes)
    summary["common_sessions"] = len(sessions)
    summary["market_symbols"] = len(prices)
    summary["market_acquisition_diagnostics"] = diagnostics
    base.dump(root / "challenge-summary.json", summary)

    with (root / "selected.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
