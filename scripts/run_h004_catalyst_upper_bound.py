#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import run_h004_earnings_replay as base

PRIMARY_TURNOVER = 20_000_000.0
VALID_SESSIONS = 10


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", required=True)
    p.add_argument("--episodes", required=True)
    p.add_argument("--momentum-summary", required=True)
    p.add_argument("--price-start", default="2025-05-01")
    p.add_argument("--price-end", default="2026-08-31")
    p.add_argument("--out", required=True)
    return p.parse_args()


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def decision_session(sessions: list[date], ts: datetime) -> date | None:
    return base.decision_session(sessions, ts)


def row_index(rows: list[dict[str, Any]], d: date) -> int | None:
    dates = [row["date"] for row in rows]
    i = bisect_left(dates, d)
    if i < len(rows) and rows[i]["date"] == d:
        return i
    return None


def pre_index(rows: list[dict[str, Any]], decision_idx: int, ts: datetime) -> int | None:
    decision_date = rows[decision_idx]["date"]
    market_close = datetime.strptime("15:30:00", "%H:%M:%S").time()
    if ts.date() == decision_date and ts.time() > market_close:
        return decision_idx
    return decision_idx - 1 if decision_idx >= 1 else None


def features(rows: list[dict[str, Any]], idx: int) -> dict[str, Any] | None:
    return base.pre_event_features(rows, idx)


def trigger(rows: list[dict[str, Any]], decision_idx: int) -> tuple[int | None, list[str]]:
    stop = min(len(rows) - 2, decision_idx + VALID_SESSIONS)
    for idx in range(decision_idx + 1, stop + 1):
        if idx < 60:
            continue
        prior20 = rows[idx - 20 : idx]
        prior5 = base.safe_pct(rows[idx]["close"], rows[idx - 5]["close"])
        if prior5 >= 15.0:
            break
        conds: list[str] = []
        one_day = base.safe_pct(rows[idx]["close"], rows[idx - 1]["close"])
        if 2.0 <= one_day <= 8.0:
            conds.append("EARLY_PRICE_RECOGNITION")
        medvol = statistics.median(row["volume"] for row in prior20)
        if medvol > 0 and rows[idx]["volume"] / medvol >= 2.0:
            conds.append("ABNORMAL_VOLUME")
        high60 = max(row["high"] for row in rows[idx - 60 : idx])
        if rows[idx]["close"] >= 0.95 * high60:
            conds.append("NEAR_60D_HIGH")
        flat_positive_circuit = (
            abs(rows[idx]["high"] - rows[idx]["low"]) < 1e-9
            and abs(rows[idx]["close"] - rows[idx]["high"]) < 1e-9
            and one_day >= 4.9
        )
        if len(conds) >= 2 and not flat_positive_circuit:
            return idx, conds
    return None, []


def outcome(rows: list[dict[str, Any]], entry_idx: int) -> dict[str, Any] | None:
    return base.outcome_from_entry(rows, entry_idx)


def quarter(d: date) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def main() -> None:
    ns = args()
    candidates = json.loads(Path(ns.candidates).read_text())
    episodes = json.loads(Path(ns.episodes).read_text())
    momentum = json.loads(Path(ns.momentum_summary).read_text())
    sessions, prices = base.load_prices(date.fromisoformat(ns.price_start), date.fromisoformat(ns.price_end))

    stage1 = []
    stage2_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    excluded = Counter()
    for candidate in candidates:
        symbol = str(candidate.get("symbol") or "").strip().upper()
        rows = prices.get(symbol)
        if not rows:
            excluded["NO_PRICE_SYMBOL"] += 1
            continue
        try:
            ts = parse_ts(str(candidate["exchange_timestamp"]))
        except Exception:
            excluded["BAD_TIMESTAMP"] += 1
            continue
        d = decision_session(sessions, ts)
        if d is None:
            excluded["NO_DECISION_SESSION"] += 1
            continue
        didx = row_index(rows, d)
        if didx is None:
            excluded["NO_SYMBOL_ROW_ON_DECISION"] += 1
            continue
        pidx = pre_index(rows, didx, ts)
        if pidx is None:
            excluded["NO_PRE_EVENT_ROW"] += 1
            continue
        feat = features(rows, pidx)
        if feat is None:
            excluded["INSUFFICIENT_HISTORY"] += 1
            continue
        if feat["median_20d_traded_value_inr"] < PRIMARY_TURNOVER:
            excluded["BELOW_PRIMARY_LIQUIDITY"] += 1
            continue
        pre_momentum = (
            feat["prior_1d_return_pct"] < 8.0
            and feat["prior_5d_return_pct"] < 10.0
            and feat["prior_20d_return_pct"] < 20.0
        )
        if not pre_momentum:
            excluded["ALREADY_MOVING"] += 1
            continue
        s1 = {
            "candidate_id": candidate["candidate_id"],
            "symbol": symbol,
            "candidate_timestamp": candidate["exchange_timestamp"],
            "decision_date": d.isoformat(),
            "retained_families": candidate.get("retained_families") or [],
            "median_20d_traded_value_inr": feat["median_20d_traded_value_inr"],
            "prior_1d_return_pct": feat["prior_1d_return_pct"],
            "prior_5d_return_pct": feat["prior_5d_return_pct"],
            "prior_20d_return_pct": feat["prior_20d_return_pct"],
        }
        stage1.append(s1)
        tidx, conds = trigger(rows, didx)
        if tidx is None:
            continue
        entry_idx = tidx + 1
        result = outcome(rows, entry_idx)
        if result is None:
            continue
        trigger_date = rows[tidx]["date"].isoformat()
        key = (symbol, trigger_date)
        signal = {
            **s1,
            "trigger_date": trigger_date,
            "trigger_conditions": conds,
            "entry_date": result["entry_date"],
            "max_20d_return_pct": result["max_20d_return_pct"],
            "close_20d_return_pct": result["close_20d_return_pct"],
            "explosive_20d": result["explosive_20d"],
            "lead_sessions_to_25pct": result["lead_sessions_to_25pct"],
        }
        # Multiple filings can point to the same executable recognition day. Collapse them.
        if key not in stage2_by_key:
            stage2_by_key[key] = signal
        else:
            previous = stage2_by_key[key]
            previous["candidate_id"] = sorted({previous["candidate_id"], candidate["candidate_id"]})[0]
            previous["retained_families"] = sorted(set(previous["retained_families"]) | set(signal["retained_families"]))

    stage2 = list(stage2_by_key.values())
    stage2.sort(key=lambda row: (row["trigger_date"], row["symbol"]))
    hits = [row for row in stage2 if row["explosive_20d"]]
    leads = [row["lead_sessions_to_25pct"] for row in hits if row["lead_sessions_to_25pct"] is not None]

    signals_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in stage2:
        signals_by_symbol[signal["symbol"]].append(signal)

    recalled = []
    for episode in episodes:
        start = episode["start_date"]
        hit = episode["hit_date"]
        matches = [
            signal
            for signal in signals_by_symbol.get(episode["symbol"], [])
            if start <= signal["trigger_date"] < hit
        ]
        if not matches:
            continue
        matches.sort(key=lambda row: row["trigger_date"])
        recalled.append({"episode": episode, "signal": matches[0]})

    qstats = {}
    for q in sorted({quarter(date.fromisoformat(row["trigger_date"])) for row in stage2}):
        rows = [row for row in stage2 if quarter(date.fromisoformat(row["trigger_date"])) == q]
        qhits = [row for row in rows if row["explosive_20d"]]
        qstats[q] = {
            "signals": len(rows),
            "hits": len(qhits),
            "precision": len(qhits) / len(rows) if rows else None,
        }

    baseline_rows = momentum.get("momentum_baselines") or []
    closest = min(
        baseline_rows,
        key=lambda row: abs(int(row.get("signal_count") or 0) - len(stage2)),
        default=None,
    )

    summary = {
        "schema_version": 1,
        "experiment": "H004-HR004-CATALYST-UPPER-BOUND",
        "status": "UPPER_BOUND_NOT_REAL_SIGNAL",
        "live_capital_allowed": False,
        "filtered_candidate_count": len(candidates),
        "primary_pre_momentum_stage1_candidate_count": len(stage1),
        "candidate_derived_stage2_signal_count": len(stage2),
        "candidate_derived_stage2_hit_count": len(hits),
        "stage2_precision_upper_bound": len(hits) / len(stage2) if stage2 else None,
        "full_market_primary_episode_count": len(episodes),
        "full_market_episode_recall_count_upper_bound": len(recalled),
        "full_market_episode_recall_upper_bound": len(recalled) / len(episodes) if episodes else None,
        "median_lead_sessions_to_25pct": statistics.median(leads) if leads else None,
        "median_stage2_max_20d_return_pct": statistics.median(row["max_20d_return_pct"] for row in stage2) if stage2 else None,
        "median_stage2_close_20d_return_pct": statistics.median(row["close_20d_return_pct"] for row in stage2) if stage2 else None,
        "excluded_candidates": dict(sorted(excluded.items())),
        "by_trigger_quarter": qstats,
        "closest_frozen_momentum_budget": closest,
        "interpretation_rule": "Actual semantically graded catalyst performance cannot exceed this return-blind filtered-candidate ceiling under the same tape trigger.",
    }
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out.parent / "upper-bound-stage2-signals.json").write_text(json.dumps(stage2, indent=2, sort_keys=True) + "\n")
    (out.parent / "upper-bound-recalled-episodes.json").write_text(json.dumps(recalled, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
