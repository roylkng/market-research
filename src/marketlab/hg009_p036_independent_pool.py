"""HG009 P036: source-only feasibility of a NEW matched NSE cohort.

Uses the original 741 valid NSE Total Market EQ industry identities observed
21 Oct, plus HG001's independently frozen October 5 opportunity lanes.
The initial 300 HG009 development companies are excluded completely.
This is one-level industry and liquidity matching, NOT a registered trial.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_100 import FROZEN_SOURCE_SHA, _clean_outside_member
from marketlab.hg009_controls import (
    _clean_control,
    load_hg009_inputs,
    verify_hg009_controls,
)
from marketlab.hg009_p033_rowwise import parse_nse_totalmarket_rows

ID = "HG009-P036-20261021-NEW-INDUSTRY-MATCHED-POOL-v1"
INDEX_SHA = "b5e615e961ba861c38e191f0341dd1e352a92ea9cf9e3cfebb9de621cc323134"
RECEIPT_SHA = "fd0d90408e707f68711a806090fe5b14a36f7a510db7066550d61e160c215083"
SOURCE = Path(
    "research/hg009/p033-totalmarket-rowwise/originals/sha256/"
    f"{INDEX_SHA}.csv.gz"
)
RECEIPT = Path(
    "research/hg009/p033-totalmarket-rowwise/receipts/"
    "2026-10-21T10-33-05.207160+00-00.json"
)
OLD_CONTROLS = Path("research/hg009/hg009-p001-matched-300-company-controls-v1.json")
ARMS = ("CONVERGENT_2PLUS", "ONE_SIGNAL", "ZERO_SIGNAL")
MIN_TRADED_INR = 10_000_000


def _load(root: Path) -> tuple[dict, dict, set[tuple[str, str]], dict]:
    router, selected = load_hg009_inputs(root)
    controls = json.loads((root / OLD_CONTROLS).read_text("utf-8"))
    verify_hg009_controls(controls, source=router, selected=selected)
    excluded = {
        (r["symbol"], r["isin"]) for r in selected["selected"]
    } | {
        (r["symbol"], r["isin"])
        for group in ("ONE_LANE", "ZERO_LANE")
        for r in controls["controls"][group]
    }
    if len(excluded) != 300 or router.get("router_sha256") != FROZEN_SOURCE_SHA:
        raise AlphaContractError("P036 original 300 source identities changed")
    receipt = json.loads((root / RECEIPT).read_text("utf-8"))
    unsigned = dict(receipt)
    embedded = unsigned.pop("report_sha256", None)
    if (
        embedded != RECEIPT_SHA or embedded != digest(unsigned)
        or receipt.get("source_original_sha256") != INDEX_SHA
        or receipt.get("source_first_observed_at_utc")
            != "2026-10-21T10:33:05.207160+00:00"
    ):
        raise AlphaContractError("P036 original P033 source receipt changed")
    try:
        raw = gzip.decompress((root / SOURCE).read_bytes())
    except OSError as exc:
        raise AlphaContractError("P036 archived NSE index source corrupted") from exc
    if hashlib.sha256(raw).hexdigest() != INDEX_SHA:
        raise AlphaContractError("P036 original NSE industry bytes differ")
    parsed = parse_nse_totalmarket_rows(raw)
    if (
        parsed["total_official_constituent_rows"] != 755
        or parsed["valid_unique_original_EQ_rows"] != 741
        or parsed["invalid_or_ambiguous_rows"] != 14
    ):
        raise AlphaContractError("P036 index source rows changed")
    return router, parsed["verified"], excluded, receipt


def _arm(row: dict) -> str | None:
    n = row.get("active_opportunity_lane_count")
    if n in (2, 3) and _clean_outside_member(row):
        return "CONVERGENT_2PLUS"
    if n == 1 and _clean_control(row, lane_count=1):
        return "ONE_SIGNAL"
    if n == 0 and _clean_control(row, lane_count=0):
        return "ZERO_SIGNAL"
    return None


def build_feasibility(root: Path) -> dict[str, Any]:
    router, industry, excluded, receipt = _load(root)
    groups: dict[tuple[str, str], dict[str, list[dict]]] = defaultdict(
        lambda: {arm: [] for arm in ARMS}
    )
    source_counts = Counter()
    old_seen = 0
    for row in router["rows"]:
        symbol, isin = row["symbol"], row["isin"]
        if (symbol, isin) in excluded:
            old_seen += 1
            continue
        industry_row = industry.get(symbol)
        if industry_row is None or industry_row["isin"] != isin:
            continue
        arm = _arm(row)
        turnover = row.get("median_daily_turnover_inr")
        if (
            arm is None or type(turnover) not in (float, int)
            or not math.isfinite(turnover) or turnover < MIN_TRADED_INR
        ):
            continue
        sector, band = industry_row["industry"], row.get("liquidity_band")
        if not isinstance(band, str) or not band:
            raise AlphaContractError("P036 missing original source liquidity band")
        material = (
            f"{ID}|{FROZEN_SOURCE_SHA}|{INDEX_SHA}|{arm}|"
            f"{sector}|{band}|{symbol}|{isin}"
        )
        groups[(sector, band)][arm].append({
            "symbol": symbol,
            "isin": isin,
            "arm": arm,
            "NSE_one_level_industry_source": sector,
            "original_liquidity_band": band,
            "original_HG001_row_sha256": digest(row),
            "source_selection_hash": hashlib.sha256(
                material.encode("utf-8")
            ).hexdigest(),
            "original_median_traded_inr_not_order_capacity": turnover,
        })
        source_counts[arm] += 1

    potential = {arm: [] for arm in ARMS}
    stratum_proof = []
    for (sector, band), candidates in sorted(groups.items()):
        for arm in ARMS:
            candidates[arm].sort(
                key=lambda x: (x["source_selection_hash"], x["symbol"], x["isin"])
            )
        count = min(len(candidates[arm]) for arm in ARMS)
        stratum_proof.append({
            "one_level_NSE_industry": sector,
            "source_liquidity_band": band,
            "original_eligible_count_by_arm": {
                arm: len(candidates[arm]) for arm in ARMS
            },
            "maximum_exact_industry_and_band_triplets": count,
        })
        for arm in ARMS:
            potential[arm].extend(candidates[arm][:count])
    for arm in ARMS:
        potential[arm].sort(key=lambda r: (r["symbol"], r["isin"]))
    size = len(potential[ARMS[0]])
    if any(len(potential[arm]) != size for arm in ARMS):
        raise AlphaContractError("P036 3-arm stratum count mismatch")
    keys = [(x["symbol"], x["isin"]) for arm in ARMS for x in potential[arm]]
    if len(set(keys)) != len(keys) or set(keys) & excluded:
        raise AlphaContractError("P036 old 300 identities contaminate new feasibility")
    result = {
        "schema_version": 1,
        "analysis_id": ID,
        "registered_2026_10_21_after_legacy_H1_observed": True,
        "earliest_possible_separate_trial_method_freeze": "2026-10-22",
        "source_first_observed_at_utc": receipt["source_first_observed_at_utc"],
        "original_nse_index_sha256": INDEX_SHA,
        "original_nse_index_path": str(SOURCE),
        "original_index_valid_EQ_industry_count": 741,
        "source_is_index_subset_not_all_Indian_equities": True,
        "original_HG001_source_sha256": FROZEN_SOURCE_SHA,
        "original_full_market_identities": 2319,
        "original_development_identity_count": len(excluded),
        "original_development_identities_seen": old_seen,
        "historical_cash_turnover_cutoff_inr": MIN_TRADED_INR,
        "new_eligible_source_rows_by_arm": dict(source_counts),
        "exact_one_level_industry_and_liquidity_strata": stratum_proof,
        "maximum_industry_liquidity_matched_triplets": size,
        "maximum_new_company_count_at_these_two_dimensions": 3 * size,
        "possible_identity_queue_NOT_a_registered_trial": potential,
        "old_300_development_identities_excluded": True,
        "old_H1_H5_returns_NOT_used_for_candidate_selection": True,
        "four_tier_and_financial_regime_verified": False,
        "size_float_beta_profitability_balanced": False,
        "CAS_spread_action_total_return_and_cost_verified": False,
        "new_independent_prospective_trial_activated": False,
        "return_prediction_or_investment_recommendation_created": False,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result


def validate_feasibility(root: Path, packet: dict) -> None:
    unsigned = copy.deepcopy(packet)
    sha = unsigned.pop("report_sha256", None)
    if sha != digest(unsigned):
        raise AlphaContractError("P036 feasibility report SHA mismatch")
    if packet != build_feasibility(root):
        raise AlphaContractError("P036 next cohort source feasibility changed")
