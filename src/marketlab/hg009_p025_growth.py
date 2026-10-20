"""HG009 P025: post-hoc H1 growth-balance and pre-H5-exit sensitivity.

This is descriptive conditional-on-observed price math, not total return,
prospective H1 validation, causal LLM alpha or an investment recommendation.
No future market price enters the October 5 earnings baseline or the
original 300-company selection.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from marketlab.alpha import AlphaContractError, digest

ID = "HG009-P025-OCT21-H1-GROWTH-BALANCE-v1"
ARMS = ("SELECTED", "ONE_LANE", "ZERO_LANE")
BINS = ("NEGATIVE", "ZERO_TO_15", "ABOVE_15", "UNAVAILABLE")
DATES = {
    1: ("2026-10-15",),
    5: ("2026-10-15", "2026-10-16", "2026-10-19", "2026-10-21", "2026-10-22"),
}
SOURCES = {
    "baseline": (
        "research/hg009/hg009-p005-source-baseline-300-v1.json",
        "67eb4b6d21c26123328bd529af5f74cab907b5b1",
        "packet_sha256",
        "09b31afc59b2b2b5cd3278ee4c73a5cff4c12dc835486fd9a0726ad45202b25e",
    ),
    "H1": (
        "research/hg009/price-diagnostics/HG009-P006-H1-20261015-v1.json",
        "2cca82f5598504ee280320e2d757d7a75c581d7b",
        "evaluation_sha256",
        "811fbb1e18481b43ab5b4c6f9bda827b3bb83709c2388b2c7f55038a856ed2b3",
    ),
}
H5_SOURCE = "research/hg009/price-diagnostics/HG009-P006-H5-20261015-v1.json"


def _sealed(data: dict, key: str) -> None:
    unsigned = copy.deepcopy(data)
    saved = unsigned.pop(key, None)
    if not isinstance(saved, str) or digest(unsigned) != saved:
        raise AlphaContractError(f"P025 original {key} signature mismatch")


def _load_pinned(root: Path, key: str) -> dict:
    path, git_blob, sig_key, sig_value = SOURCES[key]
    raw = (root / path).read_bytes()
    computed = hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()
    if computed != git_blob:
        raise AlphaContractError("P025 historical Git evidence changed")
    item = json.loads(raw)
    _sealed(item, sig_key)
    if item[sig_key] != sig_value:
        raise AlphaContractError("P025 historical source content SHA changed")
    return item


def load_sources(root: Path, horizon: int) -> tuple[dict, dict]:
    if horizon not in DATES:
        raise AlphaContractError("P025 supports H1 and H5 only")
    base = _load_pinned(root, "baseline")
    if horizon == 1:
        market = _load_pinned(root, "H1")
    else:
        path = root / H5_SOURCE
        if not path.is_file():
            raise FileNotFoundError("HG009 P006 H5 outcome source not yet published")
        market = json.loads(path.read_text(encoding="utf-8"))
        _sealed(market, "evaluation_sha256")
    return base, market


def _bucket(value: object) -> str:
    if value is None:
        return "UNAVAILABLE"
    if type(value) not in (int, float) or not math.isfinite(value):
        raise AlphaContractError("P025 source revenue growth is non-finite")
    if value < 0:
        return "NEGATIVE"
    return "ZERO_TO_15" if value <= 15 else "ABOVE_15"


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "median": None,
                "trimmed10": None, "positive": 0, "p10": None, "p90": None}
    ordered = sorted(values)
    n = len(ordered)
    cut = int(n * .1)
    inner = ordered[cut:n-cut] if cut else ordered
    return {
        "n": n,
        "mean": round(statistics.fmean(ordered), 6),
        "median": round(statistics.median(ordered), 6),
        "trimmed10": round(statistics.fmean(inner), 6),
        "positive": sum(x > 0 for x in ordered),
        "p10": round(ordered[int((n-1)*.1)], 6),
        "p90": round(ordered[int((n-1)*.9)], 6),
    }


def build_report(baseline: dict, market: dict, *, horizon: int) -> dict:
    if horizon not in DATES:
        raise AlphaContractError("P025 unknown fixed NSE horizon")
    _sealed(baseline, "packet_sha256")
    _sealed(market, "evaluation_sha256")
    if (
        baseline.get("data_source_snapshot_date") != "2026-10-05"
        or baseline.get("method_review_date") != "2026-10-14"
        or baseline.get("future_market_returns_observed") is not False
        or baseline.get("unique_frozen_identity_count") != 300
        or market.get("evaluation_id")
           != "HG009-P006-CAUSAL-ORIGINAL-PRICE-DIAGNOSTIC-v1"
        or market.get("horizon_sessions") != horizon
        or market.get("first_entry_date") != "2026-10-15"
        or market.get("official_exit_date") != DATES[horizon][-1]
        or tuple(market.get("exact_frozen_holding_sessions", [])) != DATES[horizon]
        or market.get("original_universe_size") != 300
        or len(market.get("original_symbol_isin_rows", [])) != 300
        or len(market.get("official_source_evidence", [])) != horizon
        or market.get("corporate_action_economic_total_returns_ready") is not False
        or market.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("P025 original NSE/baseline identity or time drift")
    original = {}
    for row in baseline["source_identity_metric_rows"]:
        key = (row["arm"], row["symbol"], row["isin"])
        if row["arm"] not in ARMS or key in original:
            raise AlphaContractError("P025 duplicate pre-entry company")
        if row.get("price_return_opened") is not False:
            raise AlphaContractError("P025 pre-entry baseline opened future return")
        original[key] = row
    if len(original) != 300:
        raise AlphaContractError("P025 baseline lost a source identity")
    selected_weight_source = Counter()
    rows_by_arm = {a: [] for a in ARMS}
    seen = set()
    for row in market["original_symbol_isin_rows"]:
        arm = row.get("arm")
        key = (arm, row.get("symbol"), row.get("frozen_isin"))
        if key not in original or key in seen:
            raise AlphaContractError("P025 signed market source membership mismatch")
        seen.add(key)
        base_row = original[key]
        category = _bucket(base_row["original_earnings_metrics"].get(
            "revenue_yoy_pct"
        ))
        if arm == "SELECTED":
            selected_weight_source[category] += 1
        fraction = row.get("unadjusted_gross_stock_price_change_fraction")
        complete = row.get("source_complete_all_intermediate_dates")
        if fraction is None:
            if complete is not False:
                raise AlphaContractError("P025 missingness converted into fake price")
            percent = None
        else:
            if (
                complete is not True
                or type(fraction) not in (int, float)
                or not math.isfinite(fraction)
                or fraction <= -1
            ):
                raise AlphaContractError("P025 invalid original NSE EQ price fraction")
            percent = fraction * 100
        rows_by_arm[arm].append((category, percent))
    if len(seen) != 300 or any(len(x) != 100 for x in rows_by_arm.values()):
        raise AlphaContractError("P025 missing fixed 100-per-arm source slots")
    weights = {b: selected_weight_source[b] / 100 for b in BINS}
    if sum(weights.values()) != 1:
        raise AlphaContractError("P025 impossible selected growth weights")
    summary = {}
    for arm in ARMS:
        priced = [v for _, v in rows_by_arm[arm] if v is not None]
        stats = _stats(priced)
        signed = market["arm_descriptive_statistics"][arm]
        if (
            stats["n"] != signed["priced_observation_count"]
            or abs(stats["mean"]-signed["mean_price_change_pct_if_observed"]) > 1e-6
            or abs(stats["median"]-signed["median_price_change_pct_if_observed"]) > 1e-6
        ):
            raise AlphaContractError("P025 daily signed statistics inconsistent")
        strata = {}
        weighted = 0.0
        complete_strata = True
        for bucket in BINS:
            declared = [v for b, v in rows_by_arm[arm] if b == bucket]
            available = [v for v in declared if v is not None]
            mean = statistics.fmean(available) if available else None
            strata[bucket] = {
                "source_population": len(declared),
                "observed": len(available),
                "missing": len(declared)-len(available),
                "conditional_mean_pct": round(mean, 6) if mean is not None else None,
            }
            if weights[bucket]:
                if mean is None:
                    complete_strata = False
                else:
                    weighted += weights[bucket] * mean
        summary[arm] = {
            "fixed_population": 100,
            "priced": len(priced),
            "missing": 100-len(priced),
            "conditional_observed": stats,
            "growth_buckets": strata,
            "growth_standardized_conditional_mean_pct": (
                round(weighted, 6) if complete_strata else None
            ),
        }
    gaps = {}
    for arm in ("ONE_LANE", "ZERO_LANE"):
        selected = summary["SELECTED"]
        compared = summary[arm]
        sa = selected["growth_standardized_conditional_mean_pct"]
        sb = compared["growth_standardized_conditional_mean_pct"]
        gaps[f"SELECTED_MINUS_{arm}"] = {
            "raw_observed_mean_gap_pp": round(
                selected["conditional_observed"]["mean"]-
                compared["conditional_observed"]["mean"], 6
            ),
            "growth_standardized_mean_gap_pp": (
                round(sa-sb, 6) if sa is not None and sb is not None else None
            ),
            "causal_or_after_cost_alpha_proven": False,
            "two_sided_p_value": None,
        }
    result = {
        "schema_version": 1,
        "report_id": ID,
        "method_developed_on": "2026-10-21",
        "historical_features_as_of": "2026-10-05",
        "first_entry": "2026-10-15",
        "exit_date": DATES[horizon][-1],
        "horizon_sessions": horizon,
        "original_prior_sha256": baseline["packet_sha256"],
        "original_price_report_sha256": market["evaluation_sha256"],
        "selected_source_growth_bucket_weights": weights,
        "buckets_negative_less_than_zero_and_middle_at_most_15pct": list(BINS),
        "diagnostics": summary,
        "gaps": gaps,
        "method_selected_after_h1_price_observed": True,
        "h5_exit_not_independent_of_observed_h1_prices": True,
        "posthoc_one_event_not_prospective_multi_date_alpha": True,
        "missing_prices_not_zero_imputed": True,
        "sector_size_beta_profitability_not_balanced": True,
        "corporate_actions_dividends_not_reconciled": True,
        "research_not_actual_portfolio_or_investment_advice": True,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result


def validate_report(result: dict, *, baseline: dict, market: dict) -> None:
    _sealed(result, "report_sha256")
    if result != build_report(baseline, market, horizon=result["horizon_sessions"]):
        raise AlphaContractError("P025 report failed deterministic source replay")
