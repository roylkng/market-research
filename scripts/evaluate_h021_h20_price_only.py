"""Reproduce H021's first matured H20 official *price-only* measurement.

This does not certify trade execution, dividend entitlements, corporate-action-adjusted
total returns, CAS closing auction eligibility, sector-relative excess, or live capital.
Only sealed H021-alone first-cohort inputs are consulted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = Path("research/prospective/h021")
INTENT = BASE / "intents/2026-10-09-primary-entry-intent-v1.json"
COMPARISON = BASE / "comparisons/2026-10-09-primary-revision-v1.json"
PRIOR_MANIFEST = BASE / "captures/2026-09-11-full-u001-v1.manifest.json"
CURRENT_MANIFEST = BASE / "captures/2026-10-09-full-u001-v1.manifest.json"
ENTRY = BASE / "entry-observations/2026-10-12-first-entry-v1.json"
CALENDAR = BASE / "amendments/h021-p023-nov08-calendar-v1.json"
EXIT = BASE / "special-sessions/2026-11-08/2026-11-08-original-ohlc-v1.json"
REPORT = BASE / "outcomes/2026-10-09-h20-source-only-diagnostic-v1.json"
SOURCE_VERSION = "H021-public-stockanalysis-spgi-plus-trendlyne-secondary-v1"
UNIVERSE_SHA = "8026e81faee3e913d2fba1dba72d60603b69fa07"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read(path: Path, source_blobs: dict[str, str]) -> dict:
    raw = (ROOT / path).read_bytes()
    blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    source_blobs[str(path)] = blob
    result = json.loads(raw)
    require(isinstance(result, dict), f"not a JSON object: {path}")
    return result


def percentage(entry: float, exit_price: float) -> float:
    require(entry > 0 and math.isfinite(entry) and math.isfinite(exit_price), "invalid price")
    return 100.0 * (exit_price / entry - 1.0)


def number(n: float) -> float:
    require(math.isfinite(n), "nonfinite metric")
    return round(n, 6)


def report() -> dict:
    source_blobs: dict[str, str] = {}
    comparison = read(COMPARISON, source_blobs)
    intent = read(INTENT, source_blobs)
    prior = read(PRIOR_MANIFEST, source_blobs)
    current = read(CURRENT_MANIFEST, source_blobs)
    calendar = read(CALENDAR, source_blobs)
    first = read(ENTRY, source_blobs)
    last = read(EXIT, source_blobs)

    require(comparison["hypothesis_id"] == "H021", "not H021")
    require(comparison["current_capture_date_ist"] == "2026-10-09", "wrong cohort")
    require(comparison["prior_capture_date_ist"] == "2026-09-11", "wrong revision prior")
    require(28 <= comparison["capture_interval_days"] <= 35, "revision window changed")
    require(intent["source"]["comparison_git_blob_sha"] == source_blobs[str(COMPARISON)], "comparison blob changed")
    require(comparison["universe_git_blob_sha"] == UNIVERSE_SHA, "universe changed")
    for manifest in (prior, current):
        require(manifest["source_version"] == SOURCE_VERSION, "source version changed")
        require(manifest["universe_git_blob_sha"] == UNIVERSE_SHA, "source universe changed")
        require(manifest["coverage_summary"]["total"] == 100, "frozen 100-name panel changed")

    observations = comparison["revision_observations"]
    require(len(observations) == 100, "missing frozen comparison row")
    eligible = [r for r in observations if r["primary_signal_reason"] == "ELIGIBLE"]
    require(len(eligible) == comparison["primary_signal_available_count"] == 97, "eligible denominator changed")
    require(all(r["analyst_count_prior"] >= 5 and r["analyst_count_current"] >= 5
                and r["source_compatible"] and r["period_compatible"]
                and r["eps_currency_compatible"] for r in eligible), "primary eligibility drift")
    nominal = max(1, math.ceil(len(eligible) * 0.10))
    cutoff = sorted((r["eps_revision_pct"] for r in eligible), reverse=True)[nominal - 1]
    selected = comparison["primary_top_decile_symbols"]
    actual_set = {r["symbol"] for r in eligible if r["eps_revision_pct"] >= cutoff}
    require(len(selected) == len(actual_set) == comparison["primary_top_decile_count"] == 10, "top-decile count drift")
    require(set(selected) == actual_set, "EPS-only rank or tie-inclusive selection changed")
    require([r["symbol"] for r in intent["selected_observations"]] == selected, "intent selection changed")
    require(first["source_intent_id"] == intent["intent_id"], "entry intent changed")
    require(first["session_date_ist"] == intent["entry_plan"]["session_date_ist"], "entry session changed")
    require(first["benchmark_observation"]["basis"] == "PRICE_INDEX_NOT_TRI", "benchmark basis changed")

    dates = calendar["H021_20_completed_sessions_count_entry_as_one"]
    require(len(dates) == 20 and len(set(dates)) == 20, "H20 horizon not complete")
    require(dates[0] == "2026-10-12" and dates[-1] == "2026-11-08", "H20 clock changed")
    require(calendar["frozen_h021_p003_intent_id"] == intent["intent_id"], "wrong frozen clock intent")
    require(last["original_first_cohort_intent_id"] == intent["intent_id"], "wrong endpoint cohort")
    require(last["original_clock_amendment_sha256"] == calendar["amendment_sha256"], "Muhurat clock mismatch")
    require(last["special_session_date_ist"] == dates[-1], "wrong NSE endpoint")
    require(last["original_stock_and_index_row_coverage_complete"], "Muhurat source coverage incomplete")
    require(last["benchmark"]["basis"] == "ORIGINAL_NSE_PRICE_INDEX_NOT_TRI", "Muhurat index basis changed")
    require(last["selected_original_stocks"] == len(selected), "Muhurat stock count changed")

    sessions: list[dict] = []
    for day in dates:
        if day == dates[0]:
            packet = first
            rows = [{
                "symbol": r["symbol"], "isin": r["isin"], "series": r["series"],
                "open": r["open_price_inr"], "close": r["close_price_inr"],
                "low": r["low_price_inr"],
            } for r in packet["stock_observations"]]
            benchmark = packet["benchmark_observation"]
            b_open = benchmark["open_index_value"]
            b_close = benchmark["close_index_value"]
        elif day == dates[-1]:
            packet = last
            rows = [{
                "symbol": r["symbol"], "isin": r["isin"], "series": r["series"],
                "open": r["original_unadjusted_ohlc_inr"]["open_inr"],
                "close": r["original_unadjusted_ohlc_inr"]["close_inr"],
                "low": r["original_unadjusted_ohlc_inr"]["low_inr"],
            } for r in packet["stocks"]]
            b_open = packet["benchmark"]["open"]
            b_close = packet["benchmark"]["close"]
        else:
            packet = read(BASE / f"daily-prices/{day}-v1.json", source_blobs)
            require(packet["session_date_ist"] == day, "daily session date drift")
            require(packet["source_intent_id"] == intent["intent_id"], "daily intent drift")
            require(packet["observed_stock_count"] == len(selected), "daily source not complete")
            require(packet["capture_state"] == "SOURCE_COMPLETE", "daily source not complete")
            require(packet["benchmark"]["basis"] == "PRICE_INDEX_NOT_TRI", "daily index not frozen price basis")
            rows = [{
                "symbol": r["symbol"], "isin": r["isin"], "series": r["series"],
                "open": r["ohlc"]["open_inr"], "close": r["ohlc"]["close_inr"],
                "low": r["ohlc"]["low_inr"],
            } for r in packet["stock_rows"]]
            b_open = packet["benchmark"]["open"]
            b_close = packet["benchmark"]["close"]

        require({r["symbol"] for r in rows} == set(selected), f"{day}: stock set drift")
        require(len(rows) == len(selected), f"{day}: duplicate stock row")
        require(all(r["series"] == "EQ" for r in rows), f"{day}: non-EQ instrument")
        require(all(isinstance(r[k], (float, int)) and r[k] > 0
                    for r in rows for k in ("open", "close", "low")), f"{day}: invalid stock OHLC")
        require(isinstance(b_open, (float, int)) and b_open > 0
                and isinstance(b_close, (float, int)) and b_close > 0,
                f"{day}: missing Nifty 500 source")
        sessions.append({"date": day, "rows": {r["symbol"]: r for r in rows},
                         "benchmark_open": b_open, "benchmark_close": b_close})

    start, end = sessions[0], sessions[-1]
    benchmark_return = percentage(start["benchmark_open"], end["benchmark_close"])
    by_name = []
    original_isins = {r["symbol"]: r["isin"] for r in first["stock_observations"]}
    for symbol in selected:
        entry = start["rows"][symbol]["open"]
        close = end["rows"][symbol]["close"]
        require(all(s["rows"][symbol]["isin"] == original_isins[symbol]
                    for s in sessions), f"{symbol}: ISIN drift")
        raw = percentage(entry, close)
        lowest = min(sessions, key=lambda s: s["rows"][symbol]["low"])
        adverse = percentage(entry, lowest["rows"][symbol]["low"])
        by_name.append({
            "symbol": symbol, "isin": original_isins[symbol],
            "entry_open_inr": entry, "h20_close_inr": close,
            "unadjusted_price_return_pct": number(raw),
            "price_index_excess_pp": number(raw - benchmark_return),
            "max_adverse_excursion_from_entry_open_pct": number(adverse),
            "mae_low_session_date_ist": lowest["date"],
            "official_price_source_complete": True,
            "economic_return_verified": False,
            "source_basis": "UNADJUSTED_NSE_EQ_OHLC_NOT_ACTUAL_TRADES",
            "corporate_action_and_dividend_adjustment_verified": False,
            "special_session_close_method_verified": False,
        })

    raw = [r["unadjusted_price_return_pct"] for r in by_name]
    excess = [r["price_index_excess_pp"] for r in by_name]
    gains = sorted((r for r in by_name if r["unadjusted_price_return_pct"] > 0),
                   key=lambda r: r["unadjusted_price_return_pct"], reverse=True)
    total_gross = sum(r["unadjusted_price_return_pct"] for r in gains)
    return {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "cohort_selection_date_ist": "2026-10-09",
        "as_of_date_ist": "2026-11-13",
        "horizon_completed_sessions": 20,
        "horizon_entry_open_date_ist": dates[0],
        "horizon_exit_close_date_ist": dates[-1],
        "horizon_calendar_matured": True,
        "classification": "CALENDAR_MATURED_SOURCE_COMPLETE_PRICE_ONLY_NOT_VALIDATED_ECONOMIC_OUTCOME",
        "outcome_economic_status": "BLOCKED_NOT_PROMOTABLE",
        "outcome_reason": "CAS-security close convention, all share actions/dividend entitlements, benchmark total-return basis, actual executable fills and frozen implementation costs are not independently cleared",
        "frozen_source_version": SOURCE_VERSION,
        "frozen_universe_git_blob_sha": UNIVERSE_SHA,
        "primary_revision_interval_days": comparison["capture_interval_days"],
        "primary_coverage": {
            "frozen_u001_symbols": 100, "eligible": len(eligible),
            "top_decile_selected": len(selected),
            "exclusions": comparison["primary_signal_reason_counts"],
            "all_selected_h20_original_stock_price_rows_observed": True,
            "selected_stocks_with_complete_20_session_ohlc": len(by_name),
            "benchmark_original_endpoint_open_and_close_observed": True,
            "independent_complete_corporate_action_coverage": False,
            "eligible_economic_returns": 0,
            "economic_exclusion_reason": "FULL_INTERVAL_CORPORATE_ACTION_AND_CAS_CLOSE_CONVENTION_NOT_CLEARED",
        },
        "nifty500_price_index": {
            "entry_open": start["benchmark_open"], "h20_close": end["benchmark_close"],
            "unadjusted_return_pct": number(benchmark_return), "total_return_index": False,
        },
        "price_only_selected_stock_observations": by_name,
        "price_only_descriptive_statistics_not_frozen_economic_outcome": {
            "selected_count": len(by_name),
            "mean_raw_price_return_pct": number(statistics.mean(raw)),
            "median_raw_price_return_pct": number(statistics.median(raw)),
            "mean_nifty500_price_index_excess_pp": number(statistics.mean(excess)),
            "median_nifty500_price_index_excess_pp": number(statistics.median(excess)),
            "nifty500_price_index_beat_rate_pct": number(100 * sum(x > 0 for x in excess) / len(excess)),
            "max_adverse_excursion_worst_selected_stock_pct": number(min(
                r["max_adverse_excursion_from_entry_open_pct"] for r in by_name)),
            "equal_notional_gross_positive_pnl_concentration": {
                "positive_stock_count": len(gains),
                "top_positive_stock": gains[0]["symbol"] if gains else None,
                "top_one_share_of_positive_gross_pct": number(
                    100 * gains[0]["unadjusted_price_return_pct"] / total_gross) if gains else None,
                "top_three_share_of_positive_gross_pct": number(
                    100 * sum(r["unadjusted_price_return_pct"] for r in gains[:3])
                    / total_gross) if gains else None,
                "weights_not_frozen_in_h021": True,
            },
        },
        "frozen_cost_sensitivity": {
            "state": "UNDEFINED_BY_FROZEN_H021_CONTRACT",
            "fixed_h021_roundtrip_cost_pp": None,
            "after_cost_excess_reported_as_frozen": False,
            "for_nonnegative_uniform_roundtrip_cost_c_pp_mean_excess_formula":
                "price_only_mean_excess_pp - c",
        },
        "sector_relative_excess": {
            "state": "NOT_AVAILABLE_NO_PREVIOUSLY_FROZEN_H021_SECTOR_MAPPING_AND_INDEX_SERIES",
            "values": None,
        },
        "known_specific_semantic_risks": [
            "VEDL NSE-ex-date 2026-10-14, INR 5 dividend per share; hypothetical settlement/entitlement and receipt unverified",
            "IDEA percentage EPS improvement in frozen rank arose from more negative EPS denominator; do not rewrite original selection",
            "2026-11-08 was a special Sunday NSE session with distinct CAS and non-CAS closing conventions; exact per-security CAS classification unresolved",
            "Raw NSE EQ share-price observations cannot be presented as split/bonus/dividend-adjusted economic returns",
            "Nifty 500 series is the NSE price index, not a verified total-return index",
            "The entry open is an observed NSE OHLC proxy, not a verified executable fill",
        ],
        "provenance": {
            "h021_prospective_contract": "research/H021_PROSPECTIVE_PROTOCOL_V1.md",
            "h021_comparison_contract": "research/H021_COMPARISON_CONTRACT_V1.md",
            "original_input_git_blob_shas": dict(sorted((k, v) for k, v in source_blobs.items()
                                                  if "/daily-prices/" not in k)),
            "interim_official_daily_price_source_paths": [
                str(BASE / f"daily-prices/{day}-v1.json") for day in dates[1:-1]
            ],
            "original_2026_11_08_udiff_sha256": last["original_udiff_source_receipt"]["sha256"],
            "original_2026_11_08_nifty500_csv_sha256": last["original_index_source_receipt"]["sha256"],
            "original_2026_10_12_udiff_sha256": first["source_receipts"]["udiff"]["raw_sha256"],
            "original_2026_10_12_nifty500_csv_sha256": first["source_receipts"]["index"]["raw_sha256"],
            "official_session_dates": dates,
            "verification_script": "scripts/evaluate_h021_h20_price_only.py",
        },
        "h021_primary_selection_modified": False,
        "h013_h019_h020_pf001_or_ensemble_used": False,
        "live_capital_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path,
                        help="Compare the generated evaluation against a sealed JSON artifact")
    args = parser.parse_args()
    generated = report()
    if args.verify:
        sealed = json.loads(args.verify.read_text(encoding="utf-8"))
        require(sealed == generated, "H021 H20 price-only artifact does not reproduce")
        print("H021 H20 source-only artifact verified")
    else:
        print(json.dumps(generated, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
