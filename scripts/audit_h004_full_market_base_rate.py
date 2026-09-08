#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

import run_h004_earnings_replay as market
import run_h004_full_market_denominator as hr003


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2025-10-01")
    p.add_argument("--end", default="2026-07-31")
    p.add_argument("--price-start", default="2025-05-01")
    p.add_argument("--price-end", default="2026-08-31")
    p.add_argument("--out", required=True)
    return p.parse_args()


def main() -> None:
    ns = parse_args()
    start = date.fromisoformat(ns.start)
    end = date.fromisoformat(ns.end)
    sessions, prices = market.load_prices(date.fromisoformat(ns.price_start), date.fromisoformat(ns.price_end))
    total_liquid = 0
    premomentum = []
    by_quarter = defaultdict(lambda: {"n": 0, "hits": 0})
    for rows in prices.values():
        for idx in range(60, len(rows) - 20):
            d = rows[idx]["date"]
            if d < start or d > end:
                continue
            feat = hr003.row_features(rows, idx)
            if feat is None or feat["median_turnover"] < hr003.PRIMARY_TURNOVER:
                continue
            total_liquid += 1
            if not feat["pre_momentum"]:
                continue
            result = hr003.outcome(rows, idx)
            if result is None:
                continue
            premomentum.append(result)
            q = f"{d.year}-Q{(d.month - 1) // 3 + 1}"
            by_quarter[q]["n"] += 1
            by_quarter[q]["hits"] += int(result["explosive_20d"])
    hits = sum(int(row["explosive_20d"]) for row in premomentum)
    report = {
        "schema_version": 1,
        "status": "BASE_RATE_DIAGNOSTIC",
        "market_sessions_loaded": len(sessions),
        "primary_liquid_candidate_days": total_liquid,
        "pre_momentum_candidate_days": len(premomentum),
        "pre_momentum_explosive_candidate_days": hits,
        "pre_momentum_explosive_base_rate": hits / len(premomentum) if premomentum else None,
        "median_max_20d_return_pct": statistics.median(row["max_20d_return_pct"] for row in premomentum) if premomentum else None,
        "median_close_20d_return_pct": statistics.median(row["close_20d_return_pct"] for row in premomentum) if premomentum else None,
        "by_quarter": {
            q: {**vals, "base_rate": vals["hits"] / vals["n"] if vals["n"] else None}
            for q, vals in sorted(by_quarter.items())
        },
    }
    Path(ns.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
