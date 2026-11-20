"""Reproduce only newly matured H021-alone P005 H20 price-only cohorts.

Reads immutable pre-entry intents and original, SHA256-verified NSE UDiFF and
Nifty 500 price-index source archives already sealed by the H021 source stream.
No return data enters the frozen EPS selection. This is NOT an economic-return,
TRI-alpha, trade-fill or live-capital certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from marketlab.h021_cohort_source import _verify_p005_intent
from marketlab.pf001_marketdata import (
    PF001MarketDataError,
    parse_pf001_nifty500_index,
    parse_pf001_udiff_equity,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/prospective/h021"
CALENDAR = ROOT / (
    "research/prospective/calendars/FY27-Q2-2026-09-06/"
    "NSE-CM-FY27Q2-v2-Nov08-Muhurat.json"
)
AS_OF = "2026-11-20"
TARGETS = ("2026-10-16", "2026-10-23")
FROZEN_UNIVERSE = "8026e81faee3e913d2fba1dba72d60603b69fa07"
FROZEN_SOURCE = "H021-public-stockanalysis-spgi-plus-trendlyne-secondary-v1"
OUTPUT = BASE / "outcomes"
SPECIAL = BASE / "special-sessions/2026-11-08/2026-11-08-original-ohlc-v1.json"


def require(check: bool, why: str) -> None:
    if not check:
        raise ValueError(why)


def json_read(path: Path, audit: dict[str, str]) -> dict:
    raw = path.read_bytes()
    rel = path.relative_to(ROOT).as_posix()
    audit[rel] = hashlib.sha256(raw).hexdigest()
    obj = json.loads(raw)
    require(isinstance(obj, dict), f"{rel}: expected JSON object")
    return obj


def verified_original(folder: Path, sha: str, ext: str) -> bytes:
    require(isinstance(sha, str) and len(sha) == 64, "original source SHA missing")
    raw = (folder / "raw/sha256" / f"{sha}.{ext}").read_bytes()
    require(hashlib.sha256(raw).hexdigest() == sha, "original NSE bytes SHA mismatch")
    return raw


def pct(first: float, last: float) -> float:
    require(first > 0 and last > 0 and math.isfinite(first) and math.isfinite(last),
            "invalid price for return calculation")
    return 100 * (last / first - 1)


def q(value: float) -> float:
    require(math.isfinite(value), "non-finite metric")
    return round(value, 6)


def evaluation(cohort: str) -> dict:
    require(cohort in TARGETS, "unfrozen/new H021 target")
    audit: dict[str, str] = {}
    comparison_path = BASE / "comparisons" / f"{cohort}-primary-revision-v1.json"
    manifest_path = BASE / "captures" / f"{cohort}-full-u001-v1.manifest.json"
    intent_path = BASE / "intents" / f"{cohort}-primary-entry-intent-v2.json"
    comparison = json_read(comparison_path, audit)
    manifest = json_read(manifest_path, audit)
    intent = json_read(intent_path, audit)
    calendar = json_read(CALENDAR, audit)
    special = json_read(SPECIAL, audit)

    source_cohort, entry_day, identities = _verify_p005_intent(intent)
    require(source_cohort == cohort, "frozen P005 intent date drift")
    require(comparison["hypothesis_id"] == "H021", "not H021-alone comparison")
    require(comparison["current_capture_date_ist"] == cohort, "comparison identity drift")
    require(comparison["prior_capture_date_ist"] ==
            intent["source"]["prior_capture_date_ist"], "frozen prior drift")
    require(comparison["capture_interval_days"] ==
            intent["source"]["capture_interval_days"], "source interval drift")
    require(28 <= comparison["capture_interval_days"] <= 35, "28-35 day rule changed")
    require((date.fromisoformat(cohort) -
             date.fromisoformat(comparison["prior_capture_date_ist"])).days ==
            comparison["capture_interval_days"], "comparison chronology mismatch")
    require(comparison_path.read_bytes() and
            hashlib.sha256(comparison_path.read_bytes()).hexdigest() ==
            intent["source"]["comparison_raw_sha256"], "comparison source hash drift")
    require(hashlib.sha256(manifest_path.read_bytes()).hexdigest() ==
            intent["source"]["capture_manifest_raw_sha256"], "sealed manifest hash drift")
    for document in (comparison, manifest):
        require(document["source_version"] == FROZEN_SOURCE, "source version drift")
        require(document["universe_git_blob_sha"] == FROZEN_UNIVERSE, "U001 identity drift")
    require(manifest["coverage_summary"]["total"] == 100, "not frozen U001")
    rows = comparison["revision_observations"]
    require(len(rows) == 100 and len({r["symbol"] for r in rows}) == 100,
            "missing or duplicated frozen U001 observations")
    eligible = [r for r in rows if r["primary_signal_reason"] == "ELIGIBLE"]
    require(len(eligible) == comparison["primary_signal_available_count"] ==
            intent["eligible_count"], "eligible denominator drift")
    require(all(r["analyst_count_current"] >= 5 and
                r["analyst_count_prior"] >= 5 and
                r["source_compatible"] and r["period_compatible"] and
                r["eps_currency_compatible"] for r in eligible),
            "H021 EPS-only primary coverage semantics drift")
    threshold_rank = max(1, math.ceil(0.10 * len(eligible)))
    cutoff = sorted((r["eps_revision_pct"] for r in eligible),
                    reverse=True)[threshold_rank - 1]
    selected = comparison["primary_top_decile_symbols"]
    true_selection = {r["symbol"] for r in eligible if r["eps_revision_pct"] >= cutoff}
    require(set(selected) == true_selection == set(identities),
            "EPS-only, inclusive-tie selection drift")
    require(len(selected) == len(true_selection) ==
            comparison["primary_top_decile_count"] == intent["selected_count"],
            "top decile denominator/count drift")
    require([r["symbol"] for r in intent["selected_observations"]] == selected,
            "pre-entry intent differs from sealed comparison rank")
    require(abs(cutoff - comparison["primary_top_decile_cutoff_eps_revision_pct"]) <
            1e-10, "EPS threshold changed")

    all_sessions = [s["session_date"] for s in calendar["sessions"]
                    if s["session_date"] <= AS_OF]
    require(len(all_sessions) == len(set(all_sessions)), "duplicate NSE sessions")
    require(cohort in all_sessions and entry_day in all_sessions,
            "entry/capture not in NSE completed session calendar")
    require(all_sessions[all_sessions.index(cohort) + 1] == entry_day,
            "next completed-session open not preserved")
    require(datetime.fromisoformat(intent["prepared_at_utc"]) <
            datetime.fromisoformat(intent["planned_entry"]["open_timestamp_utc"]),
            "intent finalized after the next open")
    holding = all_sessions[all_sessions.index(entry_day):]
    require(len(holding) >= 20, "H021 secondary horizon not matured")
    dates = holding[:20]
    require(dates[0] == entry_day and dates[-1] <= AS_OF,
            "H021 20-session clock invalid")
    require(dates.count("2026-11-08") == 1,
            "frozen special Sunday NSE session not incorporated")
    require(special["special_session_date_ist"] == "2026-11-08" and
            special["original_stock_and_index_row_coverage_complete"] is True,
            "special original NSE sources not verified")
    require(special["original_udiff_source_receipt"]["status"] == "OK" and
            special["original_index_source_receipt"]["status"] == "OK",
            "special source receipts missing")

    source_chain = []
    paths: dict[str, dict[str, dict]] = {s: {} for s in selected}
    for day in dates:
        if day == "2026-11-08":
            receipts = (special["original_udiff_source_receipt"],
                        special["original_index_source_receipt"])
            directory = SPECIAL.parent
        else:
            packet = json_read(BASE / "daily-prices" / f"{day}-v1.json", audit)
            require(packet["session_date_ist"] == day and
                    packet["capture_state"] in {"SOURCE_COMPLETE", "SOURCE_INCOMPLETE"},
                    "daily original source state/date invalid")
            require(packet["benchmark"]["status"] == "OFFICIAL_INDEX_OHLC",
                    "daily Nifty 500 original source not ready")
            receipts = packet["stock_source"], packet["index_source"]
            directory = BASE / "daily-prices"
        equity, index = receipts
        require(all(r["status"] == "OK" and r["http_status"] == 200 for r in receipts),
                "original official NSE source not captured")
        udiff = verified_original(directory, equity["sha256"], "zip")
        index_csv = verified_original(directory, index["sha256"], "csv")
        b = parse_pf001_nifty500_index(index_csv, session_date=date.fromisoformat(day))
        require(b.index_name == "Nifty 500", "wrong benchmark index")
        if day == "2026-11-08":
            require(abs(b.open_price - special["benchmark"]["open"]) < 1e-5 and
                    abs(b.close_price - special["benchmark"]["close"]) < 1e-5,
                    "special-session original benchmark disagrees with pinned packet")
        else:
            require(abs(b.open_price - packet["benchmark"]["open"]) < 1e-5 and
                    abs(b.close_price - packet["benchmark"]["close"]) < 1e-5,
                    "original Nifty 500 archive disagrees with pinned daily packet")
        stock_rows = {}
        for sym in selected:
            try:
                bar = parse_pf001_udiff_equity(
                    udiff, symbol=sym, expected_isin=identities[sym],
                    session_date=date.fromisoformat(day)
                )
            except PF001MarketDataError as exc:
                stock_rows[sym] = {"reason": type(exc).__name__, "ohlc": None}
            else:
                stock_rows[sym] = {
                    "reason": None,
                    "ohlc": {"open": bar.open_price, "high": bar.high_price,
                             "low": bar.low_price, "close": bar.close_price},
                }
            paths[sym][day] = stock_rows[sym]
        source_chain.append({
            "session_date_ist": day,
            "udiff_sha256": equity["sha256"],
            "nifty500_original_csv_sha256": index["sha256"],
            "Nifty500_open": b.open_price,
            "Nifty500_close": b.close_price,
            "stocks_with_original_OHLC": sum(
                r["ohlc"] is not None for r in stock_rows.values()),
            "special_session": day == "2026-11-08",
        })
        if day == entry_day:
            first_packet_path = (BASE / "future-cohorts/source-packets" /
                                 cohort / f"{day}-v1.json")
            if first_packet_path.exists():
                source_packet = json_read(first_packet_path, audit)
                require(source_packet["intent_sha256"] == intent["packet_sha256"] and
                        source_packet["original_udiff_sha256"] == equity["sha256"] and
                        source_packet["original_nifty_500_sha256"] == index["sha256"],
                        "pre-existing source-fanout entry packet drift")
                require(source_packet["first_planned_entry_session"] == entry_day,
                        "pre-sealed entry source role changed")

    b_return = pct(source_chain[0]["Nifty500_open"],
                   source_chain[-1]["Nifty500_close"])
    outcomes = []
    exclusions = []
    for sym in selected:
        history = paths[sym]
        missing = [{"session": day, "reason": history[day]["reason"]}
                   for day in dates if history[day]["ohlc"] is None]
        if missing:
            exclusions.append({"symbol": sym, "reasons": missing})
            outcomes.append({"symbol": sym, "isin": identities[sym],
                             "complete": False, "missing_sources": missing})
            continue
        entry = history[entry_day]["ohlc"]["open"]
        exit_close = history[dates[-1]]["ohlc"]["close"]
        worst_date = min(dates, key=lambda day: history[day]["ohlc"]["low"])
        worst_low = history[worst_date]["ohlc"]["low"]
        stock_return = pct(entry, exit_close)
        outcomes.append({
            "symbol": sym, "isin": identities[sym], "complete": True,
            "entry_open_inr": entry, "h20_close_inr": exit_close,
            "raw_unadjusted_price_return_pct": q(stock_return),
            "nifty500_price_index_excess_pp": q(stock_return - b_return),
            "mae_from_entry_open_pct": q(pct(entry, worst_low)),
            "mae_low_date_ist": worst_date,
            "original_Eq_source": "OFFICIAL_NSE_UNADJUSTED_OHLC_NOT_EXECUTABLE_FILL",
            "economic_total_return_verified": False,
        })

    valid = [r for r in outcomes if r["complete"]]
    excess = [r["nifty500_price_index_excess_pp"] for r in valid]
    raw_returns = [r["raw_unadjusted_price_return_pct"] for r in valid]
    winners = sorted((r for r in valid if r["raw_unadjusted_price_return_pct"] > 0),
                     key=lambda r: r["raw_unadjusted_price_return_pct"], reverse=True)
    gross_pos = sum(r["raw_unadjusted_price_return_pct"] for r in winners)
    mean_x = q(statistics.mean(excess)) if excess else None
    metrics = {
        "mean_raw_unadjusted_price_return_pct": q(statistics.mean(raw_returns)) if valid else None,
        "median_raw_unadjusted_price_return_pct": q(statistics.median(raw_returns)) if valid else None,
        "mean_nifty500_price_index_excess_pp": mean_x,
        "median_nifty500_price_index_excess_pp": q(statistics.median(excess)) if valid else None,
        "nifty500_price_index_beat_rate_pct": q(100 * sum(x > 0 for x in excess) / len(valid)) if valid else None,
        "worst_stock_max_adverse_excursion_from_entry_open_pct": q(min(
            r["mae_from_entry_open_pct"] for r in valid)) if valid else None,
        "positive_price_pnl_concentration_equal_notional": {
            "positive_raw_stock_count": len(winners),
            "top_winner": winners[0]["symbol"] if winners else None,
            "largest_positive_share_pct": q(100 * winners[0]["raw_unadjusted_price_return_pct"] /
                                            gross_pos) if winners else None,
            "top_three_positive_share_pct": q(100 * sum(
                r["raw_unadjusted_price_return_pct"] for r in winners[:3]) /
                gross_pos) if winners else None,
            "weights_frozen_in_H021": False,
        },
    }
    return {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "cohort_date_ist": cohort,
        "as_of_date_ist": AS_OF,
        "horizon_completed_nse_sessions": 20,
        "frozen_entry_session": entry_day,
        "frozen_entry_price_proxy": "NEXT_COMPLETED_SESSION_OPEN_NOT_EXECUTABLE_FILL",
        "h20_exit_session": dates[-1],
        "h20_calendar_matured": True,
        "classification": "ORIGINAL_NSE_PRICE_ONLY_DIAGNOSTIC_NOT_ECONOMIC_OUTCOME",
        "economic_outcome_gate": "BLOCKED_UNVERIFIED_CORPORATE_ACTIONS_DIVIDENDS_FILLS_AND_NIFTY500_TRI",
        "comparison_prior_date_ist": comparison["prior_capture_date_ist"],
        "primary_revision_28_to_35_days": comparison["capture_interval_days"],
        "frozen_universe_git_blob_sha": FROZEN_UNIVERSE,
        "frozen_eps_source_version": FROZEN_SOURCE,
        "selected_symbols_frozen_eps_only_tie_inclusive": selected,
        "primary_coverage": {
            "U001": 100, "primary_eligible": len(eligible),
            "selected": len(selected),
            "primary_reason_counts": comparison["primary_signal_reason_counts"],
            "selected_complete_original_stock_price_paths": len(valid),
            "benchmark_sessions_original_source_complete": len(source_chain),
            "selected_stock_missing_OHLC_reasons": exclusions,
            "economic_adjusted_complete": 0,
            "economic_exclusion_reasons": [
                "full-interval NSE corporate actions and cash-dividend entitlements not reconciled",
                "security-specific November 8 CAS/non-CAS close convention unresolved",
                "entry open not proven executable fill",
                "Nifty 500 observed price index is not TRI",
                "no frozen H021-specific all-in implementation-cost scalar",
            ],
        },
        "nifty_500_price_index": {
            "basis": "ORIGINAL_NSE_UNADJUSTED_PRICE_INDEX_NOT_TRI",
            "entry_open": source_chain[0]["Nifty500_open"],
            "exit_close": source_chain[-1]["Nifty500_close"],
            "raw_index_return_pct": q(b_return),
        },
        "selected_stock_price_only_observations": outcomes,
        "price_only_descriptive_metrics_not_h021_validated_alpha": metrics,
        "frozen_sector_relative_excess": {
            "status": "UNCOMPUTED_NO_PRIOR_FROZEN_H021_SECTOR_MAPPING_WITH_MATCHED_INDEX_SERIES",
            "excess": None,
        },
        "frozen_cost_sensitivity": {
            "status": "NO_FIXED_ALL_IN_H021_COST_SCALAR_IN_FROZEN_PROTOCOL",
            "round_trip_pp": None,
            "after_cost_economic_alpha": None,
            "formula_for_uniform_nonnegative_cost_c_pp": "unadjusted_mean_price_index_excess_pp - c",
            "illustrative_nonfrozen_roundtrip_cost_pp": [0.10, 0.22, 0.50, 1.00],
            "illustrative_price_only_mean_excess_after_cost_pp": [
                q(mean_x - c) for c in (0.10, 0.22, 0.50, 1.00)
            ] if mean_x is not None else None,
        },
        "complete_20_session_original_source_chain": source_chain,
        "source_input_sha256": dict(sorted(audit.items())),
        "original_NSE_source_receipts": True,
        "h021_selection_modified": False,
        "h013_h019_h020_pf001_or_ensemble_included": False,
        "live_capital_allowed": False,
        "implementation": "scripts/evaluate_h021_nov20_h20_price_only.py",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    for cohort in TARGETS:
        report = evaluation(cohort)
        path = OUTPUT / f"{cohort}-h20-source-only-diagnostic-v1.json"
        data = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                require(path.read_text(encoding="utf-8") == data,
                        "cannot overwrite divergent immutable H021 outcome")
            else:
                with path.open("x", encoding="utf-8") as handle:
                    handle.write(data)
        if args.verify:
            require(path.exists() and path.read_text(encoding="utf-8") == data,
                    "sealed H021 H20 outcome failed independent source replay")
        print(json.dumps({
            "cohort": cohort, "entry": report["frozen_entry_session"],
            "exit": report["h20_exit_session"],
            "selected": len(report["selected_symbols_frozen_eps_only_tie_inclusive"]),
            "fully_observed": report["primary_coverage"]["selected_complete_original_stock_price_paths"],
            "statistics": report["price_only_descriptive_metrics_not_h021_validated_alpha"],
            "classification": report["classification"],
            "economic_alpha_verified": False,
        }, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
