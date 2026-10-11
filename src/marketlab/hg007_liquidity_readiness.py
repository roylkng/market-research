"""Append-only five-company casework view with 20-day official NSE turnover.

This does NOT amend earlier HG005/HG007 payoff/selection sources. It exposes
whether an illustrative INR 10 lakh ticket exceeds *1% of historical
median daily traded value*. That fraction cannot predict fills or elapsed days.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from marketlab.hg007_five_case_market_oct9 import EXPECTED_NAMES
from marketlab.hg007_liquidity_friction import validate_one_session_liquidity
from marketlab.hg007_liquidity_history import (
    build_twenty_session_liquidity,
    validate_twenty_session_liquidity,
)

OVERLAY_ID = "HG007-P037-FIVE-CASE-MULTISESSION-LIQUIDITY-CONTEXT-v1"
SOURCES = {
    "five_case_underwriting": (
        "research/hg007/hg007-p033-five-case-sambhv-source-timing-v1.json",
        "3b0caf8f0fa763528d5b37b218935f848c9f100a",
    ),
    "one_session_liquidity": (
        "research/hg007/hg007-p035-five-case-liquidity-friction-v1.json",
        "7f39738d0210f43965dedfe48c5c382caffa4b90",
    ),
    "twenty_session_liquidity": (
        "research/hg007/twenty-session-liquidity/twenty-session-liquidity-v1.json",
        "f2e3d33288a432326235bd72db1911bc17b742ea",
    ),
}
TICKET_INR = 1_000_000
REFERENCE_PARTICIPATION_PERCENT = 1


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_verified_issuer_sources(root: Path) -> tuple[dict, dict, dict, dict]:
    outputs: dict[str, dict] = {}
    receipts: dict[str, dict] = {}
    for label, (source_path, expected_blob) in SOURCES.items():
        raw = (root / source_path).read_bytes()
        if _blob(raw) != expected_blob:
            raise ValueError(f"{label}: original research source Git blob changed")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise TypeError(f"{label}: original source must be a JSON object")
        outputs[label] = payload
        receipts[label] = {
            "path": source_path,
            "git_blob_sha": expected_blob,
            "original_bytes_sha256": hashlib.sha256(raw).hexdigest(),
        }

    long = outputs["twenty_session_liquidity"]
    one = outputs["one_session_liquidity"]
    validate_one_session_liquidity(one)
    validate_twenty_session_liquidity(long)
    rebuilt = build_twenty_session_liquidity(root)
    if rebuilt != long:
        raise ValueError("20-session original NSE UDiFF source no longer reproduces packet")
    return outputs["five_case_underwriting"], one, long, receipts


def _require_positive(value: object, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite positive from source")
    return float(value)


def build_five_case_liquidity_overlay(
    underwriting: dict[str, Any],
    p035: dict[str, Any],
    p036: dict[str, Any],
    receipts: dict[str, dict],
) -> dict[str, Any]:
    if (
        underwriting.get("overlay_id")
        != "HG007-P033-FIVE-CASE-UNDERWRITING-LATEST-SAMBHV-v1"
        or underwriting.get("original_five_case_count") != 5
        or underwriting.get("live_capital_allowed") is not False
        or underwriting.get("source_probabilities_or_expected_returns_published") != 0
    ):
        raise ValueError("original five-company economic evidence baseline changed")
    companies = underwriting.get("casework")
    if not isinstance(companies, list) or tuple(x.get("symbol") for x in companies) != EXPECTED_NAMES:
        raise ValueError("five originally frozen underlying companies missing")
    validate_one_session_liquidity(p035)
    validate_twenty_session_liquidity(p036)
    if (
        p036["observed_complete_session_count"] != 20
        or p036["source_status"] != "COMPLETE_ORIGINAL_20_SESSION_EQUITY_EVIDENCE"
        or p036["source_window_first_session"] != "2026-09-10"
        or p036["source_cutoff_session"] != "2026-10-09"
        or p036["missing_or_inconsistent_sessions"]
        or tuple(p036["all_original_five_company_ids_preserved"]) != EXPECTED_NAMES
        or p036["historical_source_reconstructed_after_stock_case_selection"] is not True
        or p036["investment_recommendations_created"] is not False
    ):
        raise ValueError("twenty-session original NSE source completeness changed")
    one = p035["cases"]
    twenty = p036["company_distribution"]
    if (
        tuple(x.get("symbol") for x in one) != EXPECTED_NAMES
        or tuple(x.get("symbol") for x in twenty) != EXPECTED_NAMES
    ):
        raise ValueError("liquidity study selected a different underlying company")
    enhanced = []
    for case, one_day, longer in zip(companies, one, twenty, strict=True):
        name = case["symbol"]
        if (
            one_day["symbol"] != name or longer["symbol"] != name
            or one_day["source_isin"] != longer["source_isin"]
        ):
            raise ValueError("historical source mismatched five-issuer NSE ISIN")
        one_day_crore = _require_positive(
            one_day.get("single_session_traded_value_inr_crore"), f"{name} P035 close"
        )
        p036_oct = _require_positive(
            longer.get("oct9_day_traded_value_inr_crore"), f"{name} P036 Oct9"
        )
        if not math.isclose(one_day_crore, p036_oct, abs_tol=1e-8):
            raise ValueError("original one-day NSE source diverges from 20-day same session")

        median = _require_positive(
            longer.get("twenty_session_traded_value_median_inr_crore"), f"{name} median"
        )
        p10 = _require_positive(
            longer.get("twenty_session_traded_value_p10_nearest_rank_inr_crore"), f"{name} P10"
        )
        p25 = _require_positive(
            longer.get("twenty_session_traded_value_p25_nearest_rank_inr_crore"), f"{name} P25"
        )
        maximum = _require_positive(
            longer.get("twenty_session_traded_value_max_inr_crore"), f"{name} maximum"
        )
        if not 0 < p10 <= p25 <= median <= maximum:
            raise ValueError("20-day lower-tail NSE traded value distribution invalid")
        if longer["session_count"] != 20:
            raise ValueError("company-specific 20-session trading coverage incomplete")
        quotient = TICKET_INR / (REFERENCE_PARTICIPATION_PERCENT / 100 * median * 1e7)
        if not math.isclose(
            quotient,
            longer["ten_lakh_ticket_divided_by_one_pct_of_historical_median"],
            abs_tol=1e-9,
        ):
            raise ValueError("20-day historical participation quotient altered")
        update = deepcopy(case)
        update["official_nse_historical_turnover_overlay"] = {
            "source_window_first_session": "2026-09-10",
            "source_window_last_session": "2026-10-09",
            "twenty_session_original_nse_source_complete": True,
            "source_eq_isin": longer["source_isin"],
            "median_daily_traded_value_inr_crore": median,
            "p10_nearest_rank_daily_traded_value_inr_crore": p10,
            "p25_nearest_rank_daily_traded_value_inr_crore": p25,
            "max_daily_traded_value_inr_crore": maximum,
            "oct9_traded_value_inr_crore": p036_oct,
            "highest_to_median_source_turnover_ratio": maximum / median,
            "oct9_to_trailing_20_median_source_turnover_ratio": (
                p036_oct / median
            ),
            "example_ticket_inr": TICKET_INR,
            "hypothetical_daily_participation_percent": REFERENCE_PARTICIPATION_PERCENT,
            "ticket_exceeds_one_pct_of_median_daily_turnover": quotient > 1,
            "ticket_divided_by_one_pct_of_median_source_turnover": quotient,
            "quotient_is_a_trading_days_or_fill_prediction": False,
            "bid_ask_spread_and_depth_independently_verified": False,
            "reliable_executable_position_size_verified": False,
            "multi_session_volume_assumed_representative_of_future": False,
            "source_reconstructed_after_case_selection_not_alpha": True,
        }
        update["cash_market_trading_and_liquidity_fully_verified"] = False
        update["company_specific_completion_probability_published"] = False
        update["current_fully_diluted_capital_and_ev_sufficient"] = False
        update["portfolio_eligibility_allowed"] = False
        update["live_capital_allowed"] = False
        enhanced.append(update)
    return {
        "schema_version": 1,
        "overlay_id": OVERLAY_ID,
        "classification": "SOURCE_PINNED_FIVE_CASE_TURNOVER_DIAGNOSTIC_NOT_INVESTABLE_CAPACITY",
        "assembled_as_of_ist": "2026-10-11",
        "source_provenance": receipts,
        "original_five_case_names_and_order_unchanged": True,
        "company_case_count": 5,
        "source_price_cutoff_session": "2026-10-09",
        "full_20_session_cash_market_source_verified": True,
        "original_economic_underwriting_or_rank_modified": False,
        "company_casework": enhanced,
        "orderbook_and_executable_liquidity_complete": False,
        "company_completion_probabilities_published": 0,
        "company_expected_returns_calculated": False,
        "company_market_impact_cost_forecast_published": False,
        "stock_recommendations_created": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
