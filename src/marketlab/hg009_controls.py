"""HG009-P001: frozen outcome-blind one-lane and zero-lane comparators.

Take 100 selected names from HG009-D001 and 100 matched *by original
historical liquidity band* in each of the 0-lane and 1-lane groups.
This is not industry, size or risk matching. The comparisons are descriptive
and observational, NOT a causal estimate of stock-picking alpha.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_100 import (
    COHORT_ID as HG009_COHORT_ID,
    FROZEN_SOURCE_SHA,
    _frozen_router_check,
    load_hg001_router,
    validate_hg009_100,
)

CONTROL_ID = "HG009-P001-FROZEN-100-ONE-AND-ZERO-LANE-COMPARATORS-v1"
FROZEN_DATE = "2026-10-14"
FIRST_MARKET_ENTRY = "2026-10-15"
MATCHING = "EXACT_PRIOR_SOURCE_LIQUIDITY_BAND_ONLY_NO_RETURN_MOMENTUM"
CONTROL_LANES = (0, 1)
FROZEN_HG009_COHORT_SHA = (
    "e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5"
)
BANDS = (
    "L1_10CR_PLUS",
    "L2_5_TO_10CR",
    "L3_2_TO_5CR",
    "L4_1_TO_2CR",
    "L5_20L_TO_1CR",
    "L6_BELOW_20L",
    "OBSERVATION_INSUFFICIENT",
)
ALLOWED_ROUTES = {
    0: frozenset({"BACKLOG_NO_ACTIVE_LANE"}),
    1: frozenset({
        "EARNINGS_INFLECTION_DEEP_DIVE",
        "ASSET_ANOMALY_DEEP_DIVE",
        "SPECIAL_SITUATION_UNDERWRITE",
    }),
}


def _clean_control(row: dict[str, Any], *, lane_count: int) -> bool:
    turnover = row.get("median_daily_turnover_inr")
    return (
        row.get("active_opportunity_lane_count") == lane_count
        and row.get("research_route") in ALLOWED_ROUTES[lane_count]
        and row.get("in_existing_u001") is False
        and row.get("governance_caution_count") == 0
        and row.get("governance_caution_flags") == []
        and row.get("asset_caution_flags") == []
        and row.get("return_outcomes_opened") is False
        and row.get("portfolio_eligibility_allowed") is False
        and row.get("live_capital_allowed") is False
        and isinstance(turnover, (float, int))
        and not isinstance(turnover, bool)
        and math.isfinite(turnover)
        and turnover >= 0
    )


def _sample_key(row: dict[str, Any], *, lane_count: int, band: str) -> str:
    string = "|".join((
        FROZEN_SOURCE_SHA,
        CONTROL_ID,
        str(lane_count),
        band,
        str(row["symbol"]),
        str(row["isin"]),
    ))
    return hashlib.sha256(string.encode("utf-8")).hexdigest()


def _control_record(
    row: dict[str, Any], *, lane_count: int, band: str
) -> dict[str, Any]:
    return {
        "symbol": row["symbol"],
        "isin": row["isin"],
        "original_hg001_row_sha256": digest(row),
        "control_lane_count": lane_count,
        "source_liquidity_band": band,
        "source_median_daily_turnover_inr_not_current": (
            row["median_daily_turnover_inr"]
        ),
        "source_research_route": row["research_route"],
        "control_sample_sha256": _sample_key(
            row, lane_count=lane_count, band=band
        ),
        "future_price_labels_opened": False,
        "capital_allowed": False,
    }


def build_hg009_control_manifest(
    source: dict[str, Any], selected: dict[str, Any]
) -> dict[str, Any]:
    _frozen_router_check(source)
    validate_hg009_100(selected, source=source)
    if (
        selected.get("cohort_id") != HG009_COHORT_ID
        or selected.get("cohort_sha256") != FROZEN_HG009_COHORT_SHA
        or selected.get("selected_count") != 100
    ):
        raise AlphaContractError("HG009 P001 selected cohort source changed")
    selected_bands = Counter(
        item["source_liquidity_band"] for item in selected["selected"]
    )
    if set(selected_bands) != set(BANDS):
        raise AlphaContractError("HG009 P001 unknown selected liquidity bands")
    selected_ids = {
        (row["symbol"], row["isin"]) for row in selected["selected"]
    }
    if len(selected_ids) != 100:
        raise AlphaContractError("HG009 P001 duplicate selected identities")

    controls: dict[str, list[dict[str, Any]]] = {}
    candidate_counts: dict[str, dict[str, int]] = {}
    chosen_by_band: dict[str, dict[str, list[str]]] = {}
    for lane_count in CONTROL_LANES:
        name = "ZERO_LANE" if lane_count == 0 else "ONE_LANE"
        lane_chosen: list[dict[str, Any]] = []
        available: dict[str, int] = {}
        selected_by_band: dict[str, list[str]] = {}
        for band in BANDS:
            pool = [
                row for row in source["rows"]
                if _clean_control(row, lane_count=lane_count)
                and row.get("liquidity_band") == band
                and (row["symbol"], row["isin"]) not in selected_ids
            ]
            required = selected_bands[band]
            if len(pool) < required:
                raise AlphaContractError(
                    f"HG009 P001 {name} lacks matched source controls for {band}"
                )
            pool.sort(key=lambda row: (
                _sample_key(row, lane_count=lane_count, band=band),
                row["symbol"],
                row["isin"],
            ))
            picked = pool[:required]
            lane_chosen.extend(
                _control_record(row, lane_count=lane_count, band=band)
                for row in picked
            )
            available[band] = len(pool)
            selected_by_band[band] = sorted(row["symbol"] for row in picked)
        lane_chosen.sort(key=lambda row: (row["symbol"], row["isin"]))
        if len(lane_chosen) != 100 or len({
            row["symbol"] for row in lane_chosen
        }) != 100:
            raise AlphaContractError("HG009 P001 incomplete control lane")
        controls[name] = lane_chosen
        candidate_counts[name] = available
        chosen_by_band[name] = selected_by_band

    zero_ids = {(row["symbol"], row["isin"]) for row in controls["ZERO_LANE"]}
    one_ids = {(row["symbol"], row["isin"]) for row in controls["ONE_LANE"]}
    if zero_ids & one_ids or zero_ids & selected_ids or one_ids & selected_ids:
        raise AlphaContractError("HG009 P001 selected and controls overlap")

    result: dict[str, Any] = {
        "schema_version": 1,
        "control_id": CONTROL_ID,
        "method_frozen_date": FROZEN_DATE,
        "earliest_future_market_entry_session": FIRST_MARKET_ENTRY,
        "source_cohort_id": HG009_COHORT_ID,
        "source_cohort_sha256": FROZEN_HG009_COHORT_SHA,
        "original_hg001_router_sha256": FROZEN_SOURCE_SHA,
        "matching_method": MATCHING,
        "matched_dimensions": [
            "OUTSIDE_U001",
            "SOURCE_BASED_GOVERNANCE_CAUTION_ZERO",
            "SOURCE_BASED_ASSET_CAUTION_ZERO",
            "EXACT_HISTORICAL_LIQUIDITY_BAND",
        ],
        "not_matched_dimensions": [
            "INDUSTRY_OR_SECTOR",
            "COMPANY_SIZE_OR_ENTERPRISE_VALUE",
            "FACTOR_BETAS",
            "SALES_QUALITY_OR_ACCOUNTING_REGIME",
            "ACTUAL_BID_ASK_SPREAD_AND_TICKET_CAPACITY",
        ],
        "matching_is_not_causal_identification": True,
        "hashed_deterministic_control_selection_not_alpha_optimization": True,
        "selected_company_count": 100,
        "zero_lane_control_company_count": 100,
        "one_lane_control_company_count": 100,
        "total_unique_observation_identities": 300,
        "selected_source_band_quotas": {
            band: selected_bands[band] for band in BANDS
        },
        "source_eligible_pool_counts_per_band": candidate_counts,
        "selected_control_symbols_per_band": chosen_by_band,
        "controls": controls,
        "entry_observation_only_if_source_exists": True,
        "stocks_missing_EQ_or_ISIN_at_entry_remain_reported_missing": True,
        "price_index_benchmark_is_not_total_return": True,
        "baseline_performance_and_returns_opened": False,
        "future_price_or_excess_return_computed": False,
        "investment_recommendations_generated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["manifest_sha256"] = digest(result)
    return result


def verify_hg009_controls(
    manifest: dict[str, Any],
    *,
    source: dict[str, Any],
    selected: dict[str, Any],
) -> None:
    stored = manifest.get("manifest_sha256")
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("HG009 P001 manifest SHA changed")
    expected = build_hg009_control_manifest(source, selected)
    if expected != manifest:
        raise AlphaContractError("HG009 P001 control selection not reproducible")


def load_hg009_inputs(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source = load_hg001_router(
        repo_root / "research/hg009/original-hg001-d001-router-20261005.json.gz"
    )
    path = (
        repo_root / "research/hg009/"
        "hg009-d001-100-experimental-companies-v1.json"
    )
    selected = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(selected, dict):
        raise AlphaContractError("HG009 P001 selected cohort is not an object")
    return source, selected
