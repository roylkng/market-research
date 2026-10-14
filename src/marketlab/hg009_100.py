"""HG009-D001: deterministic 100-company *exploratory* full-market research cohort.

An original HG001-D001 full-market source has 2,319 NSE identities, 79 with
three independent opportunity lanes and 395 with two. This is NOT the separate
Nifty-200/U001 top-100 earnings cohort. Freeze 28 previously defined clean,
outside-U001, three-lane identities plus 24 equally hash-sampled from each of
the three no-caution, outside-U001, >=1cr median-turnover two-lane strata.

Research diversity is the goal, not retrospective return optimization.
Random-looking hash selection is deterministic once the October 5 source SHA,
method version, symbols and ISINs are frozen. No price outcome enters ranking.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest

COHORT_ID = "HG009-D001-100-DIVERSIFIED-RESEARCH-v1"
FROZEN_SOURCE_SHA = "79e6b068f95c890e4ef88be62ffe2e8dfb94fabbf293770804e64aaa82d6e5ff"
FROZEN_ROUTER_ID = "HG001-D001-v1"
SOURCE_WORKFLOW_RUN_ID = 37258053642
SOURCE_ARTIFACT_ID = 11323461912
FROZEN_METHOD_DATE = "2026-10-14"
DOUBLE_MIN_MEDIAN_VALUE_INR = 10_000_000
TRIPLE_COUNT = 28
PAIRED_QUOTA = 24
TOTAL_SELECTION = 100
PAIRS = (
    "ASSET_OR_CAPACITY_ANOMALY+CURRENT_SPECIAL_SITUATION",
    "EARNINGS_INFLECTION+ASSET_OR_CAPACITY_ANOMALY",
    "EARNINGS_INFLECTION+CURRENT_SPECIAL_SITUATION",
)
TRIPLE_LANES = (
    "EARNINGS_INFLECTION",
    "ASSET_OR_CAPACITY_ANOMALY",
    "CURRENT_SPECIAL_SITUATION",
)


def _frozen_router_check(source: dict[str, Any]) -> None:
    actual = str(source.get("router_sha256") or "")
    unsigned = copy.deepcopy(source)
    unsigned.pop("router_sha256", None)
    if (
        source.get("router_id") != FROZEN_ROUTER_ID
        or source.get("identity_count") != 2319
        or source.get("active_research_candidate_count") != 1423
        or source.get("return_outcomes_opened") is not False
        or source.get("model_fitted") is not False
        or source.get("portfolio_eligibility_allowed") is not False
        or source.get("live_capital_allowed") is not False
        or actual != FROZEN_SOURCE_SHA
        or digest(unsigned) != FROZEN_SOURCE_SHA
    ):
        raise AlphaContractError("HG009 original 2319-name source was altered")
    rows = source.get("rows")
    if not isinstance(rows, list) or len(rows) != 2319:
        raise AlphaContractError("HG009 original full-market rows missing")
    symbols = [row.get("symbol") for row in rows]
    isins = [row.get("isin") for row in rows]
    if (
        len(set(symbols)) != 2319
        or any(not isinstance(s, str) or not s for s in symbols)
        or any(not isinstance(i, str) or len(i) != 12 for i in isins)
        or len(set(zip(symbols, isins, strict=True))) != 2319
    ):
        raise AlphaContractError("HG009 original full-market symbol/ISIN collision")
    for row in rows:
        if (
            row.get("return_outcomes_opened") is not False
            or row.get("live_capital_allowed") is not False
            or row.get("portfolio_eligibility_allowed") is not False
        ):
            raise AlphaContractError("HG009 source has outcome or capital contamination")


def _clean_outside_member(row: dict[str, Any]) -> bool:
    return (
        row.get("in_existing_u001") is False
        and row.get("governance_caution_count") == 0
        and row.get("governance_caution_flags") == []
        and row.get("asset_caution_flags") == []
        and row.get("research_route") == "CONVERGENT_DEEP_DIVE"
        and row.get("portfolio_eligibility_allowed") is False
        and row.get("return_outcomes_opened") is False
    )


def _double_pair(row: dict[str, Any]) -> str:
    lanes = row.get("active_opportunity_lanes")
    if not isinstance(lanes, list) or len(lanes) != 2:
        raise AlphaContractError("HG009 candidate has invalid two-lane set")
    return "+".join(lanes)


def _sample_key(row: dict[str, Any], pair: str) -> str:
    return hashlib.sha256(
        (
            FROZEN_SOURCE_SHA + "|" + COHORT_ID + "|" + pair + "|"
            + row["symbol"] + "|" + row["isin"]
        ).encode("utf-8")
    ).hexdigest()


def _extract(row: dict[str, Any], *, class_label: str, seed_hash: str | None) -> dict:
    turnover = row.get("median_daily_turnover_inr")
    if type(turnover) not in (float, int) or not math.isfinite(turnover) or turnover <= 0:
        raise AlphaContractError("HG009 selected company lacks historical turnover")
    data = {
        "symbol": row["symbol"],
        "isin": row["isin"],
        "research_class": class_label,
        "lane_count": row["active_opportunity_lane_count"],
        "active_lanes": row["active_opportunity_lanes"],
        "earnings_inflection_state": row["earnings_inflection_state"],
        "asset_opportunity_flags": row["asset_opportunity_flags"],
        "special_situation_categories": row["special_situation_categories"],
        "median_daily_turnover_inr_source_not_capacity": turnover,
        "source_liquidity_band": row["liquidity_band"],
        "governance_flags": row["governance_caution_flags"],
        "asset_cautions": row["asset_caution_flags"],
        "deterministic_sample_hash": seed_hash,
        "full_frozen_router_row_sha256": digest(row),
        "in_existing_u001": False,
        "future_return_predicted": False,
        "investable_decision": False,
    }
    return data


def build_hg009_100(source: dict[str, Any]) -> dict[str, Any]:
    _frozen_router_check(source)
    rows = source["rows"]
    triple = [
        row for row in rows
        if _clean_outside_member(row)
        and row["active_opportunity_lane_count"] == 3
        and row["active_opportunity_lanes"] == list(TRIPLE_LANES)
    ]
    if len(triple) != TRIPLE_COUNT:
        raise AlphaContractError("HG009 frozen 28 three-lane cohort changed")
    pairs = Counter()
    selected = [
        _extract(row, class_label="ORIGINAL_THREE_LANES", seed_hash=None)
        for row in triple
    ]
    source_candidate_count = {}
    sampled_per_pair = {}
    for pair in PAIRS:
        eligible = [
            row for row in rows
            if _clean_outside_member(row)
            and row["active_opportunity_lane_count"] == 2
            and _double_pair(row) == pair
            and type(row.get("median_daily_turnover_inr")) in (float, int)
            and math.isfinite(row["median_daily_turnover_inr"])
            and row["median_daily_turnover_inr"] >= DOUBLE_MIN_MEDIAN_VALUE_INR
        ]
        if len(eligible) < PAIRED_QUOTA:
            raise AlphaContractError(f"HG009 has fewer than 24 eligible cases for {pair}")
        source_candidate_count[pair] = len(eligible)
        eligible.sort(key=lambda row: (_sample_key(row, pair), row["symbol"]))
        chosen = eligible[:PAIRED_QUOTA]
        sampled_per_pair[pair] = sorted(row["symbol"] for row in chosen)
        pairs[pair] = len(chosen)
        selected.extend(
            _extract(
                row,
                class_label=pair,
                seed_hash=_sample_key(row, pair),
            )
            for row in chosen
        )
    selected.sort(key=lambda row: (row["symbol"], row["isin"]))
    if (
        len(selected) != TOTAL_SELECTION
        or len({row["symbol"] for row in selected}) != TOTAL_SELECTION
        or len({row["isin"] for row in selected}) != TOTAL_SELECTION
        or dict(pairs) != {pair: PAIRED_QUOTA for pair in PAIRS}
    ):
        raise AlphaContractError("HG009 cannot yield unique 100 source-safe names")
    result = {
        "schema_version": 1,
        "cohort_id": COHORT_ID,
        "frozen_method_date": FROZEN_METHOD_DATE,
        "source_type": "IMMUTABLE_OCT05_FULL_MARKET_DEVELOPMENT_ROUTER",
        "original_router_id": FROZEN_ROUTER_ID,
        "original_router_sha256": FROZEN_SOURCE_SHA,
        "original_source_workflow_run_id": SOURCE_WORKFLOW_RUN_ID,
        "original_source_artifact_id": SOURCE_ARTIFACT_ID,
        "source_population_size": len(rows),
        "source_three_lane_count": TRIPLE_COUNT,
        "double_min_prior_liquidity_inr": DOUBLE_MIN_MEDIAN_VALUE_INR,
        "source_double_eligible_counts_by_pair": source_candidate_count,
        "double_quota_per_pair": PAIRED_QUOTA,
        "chosen_double_symbols_by_pair": sampled_per_pair,
        "selected_count": TOTAL_SELECTION,
        "selected_3lane_count": TRIPLE_COUNT,
        "selected_2lane_count": 3 * PAIRED_QUOTA,
        "selected": selected,
        "selected_symbols_sorted": [row["symbol"] for row in selected],
        "original_HG002_28_members_preserved": True,
        "source_selection_uses_future_returns": False,
        "selection_method_optimized_on_historical_returns": False,
        "selection_method_optimized_for_expected_alpha": False,
        "price_or_market_cap_used_for_selection": False,
        "liquidity_is_executable_order_capacity": False,
        "scientifically_confirmed_return_alpha": False,
        "expected_return_or_price_target_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["cohort_sha256"] = digest(result)
    return result


def load_hg001_router(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if path.suffix == ".gz":
        try:
            raw = gzip.decompress(raw)
        except OSError as exc:
            raise AlphaContractError("HG009 invalid archived source gzip") from exc
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise AlphaContractError("HG009 original source must be object")
    _frozen_router_check(parsed)
    return parsed


def validate_hg009_100(result: dict[str, Any], *, source: dict[str, Any]) -> None:
    actual_sha = result.get("cohort_sha256")
    unsigned = dict(result)
    unsigned.pop("cohort_sha256", None)
    if actual_sha != digest(unsigned):
        raise AlphaContractError("HG009 cohort seal SHA mismatch")
    expected = build_hg009_100(source)
    if expected != result:
        raise AlphaContractError("HG009 100-company selection not reproducible")
