"""Read-only cash-equity turnover sensitivity, not tradable liquidity or returns."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from pathlib import Path

from marketlab.alpha_market import parse_udiff_eq_panel
from marketlab.hg007_five_case_market_oct9 import EXPECTED_NAMES, validate_five_case_price_context

AUDIT_ID = "HG007-P035-FIVE-CASE-SINGLE-SESSION-LIQUIDITY-v1"
SOURCE_DIR = Path("research/hg007/oct09-five-case-market")
PRICE_FILE = SOURCE_DIR / "five-case-oct09-market-context-v1.json"
PRICE_BLOB = "3e124533915e4c9e12a7a41e445af71b915d10bd"
SOURCE_SHA = "8adbb3410c8cf4372290484a9b1798490ef279d30fc2439c93f082cc20ed198c"
ORIGINAL_ZIP = SOURCE_DIR / "original" / f"{SOURCE_SHA}.zip"
PARTICIPATION = (1, 5)
TICKETS_INR = (100_000, 1_000_000, 10_000_000)


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw, usedforsecurity=False).hexdigest()


def load_official_oct9(root: Path) -> tuple[dict, bytes, dict]:
    original_json = (root / PRICE_FILE).read_bytes()
    if _git_blob(original_json) != PRICE_BLOB:
        raise ValueError("frozen five-case market record has changed")
    packet = json.loads(original_json)
    validate_five_case_price_context(packet)
    original_zip = (root / ORIGINAL_ZIP).read_bytes()
    if hashlib.sha256(original_zip).hexdigest() != SOURCE_SHA:
        raise ValueError("original whole-market UDiFF hash changed")
    return packet, original_zip, {
        "market_context_git_blob_sha": PRICE_BLOB,
        "market_context_original_sha256": hashlib.sha256(original_json).hexdigest(),
        "market_context_source_path": str(PRICE_FILE),
        "original_udiff_zip_sha256": SOURCE_SHA,
        "original_udiff_zip_path": str(ORIGINAL_ZIP),
    }


def build_one_session_liquidity(packet: dict, original_zip: bytes, provenance: dict) -> dict:
    """Arithmetic illustrations only. No forecast of execution, price impact or volume."""
    validate_five_case_price_context(packet)
    if hashlib.sha256(original_zip).hexdigest() != SOURCE_SHA:
        raise ValueError("original raw NSE file changed")
    panel = parse_udiff_eq_panel(original_zip, session_date=date(2026, 10, 9))
    by_symbol = {}
    for item in panel:
        if item.symbol in EXPECTED_NAMES:
            if item.symbol in by_symbol:
                raise ValueError("ambiguous official EQ records")
            by_symbol[item.symbol] = item
    if set(by_symbol) != set(EXPECTED_NAMES):
        raise ValueError("official EQ record missing for selected issuer")

    cases = []
    for row in packet["price_context_rows"]:
        symbol = row["symbol"]
        bar = by_symbol[symbol]
        amount = row["official_oct9_total_traded_value_inr"]
        volume = row["official_oct9_total_traded_shares"]
        close = row["official_oct9_close_inr"]
        low = row["official_oct9_low_inr"]
        high = row["official_oct9_high_inr"]
        count = row["official_oct9_number_of_executed_transactions"]
        if (
            any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0
                for x in (amount, volume, close, low, high))
            or type(count) is not int or count <= 0
        ):
            raise ValueError("official volume, trading value or price invalid")
        vwap = amount / volume
        if not low <= close <= high or not low <= vwap <= high:
            raise ValueError("official source reported an invalid intraday price range")
        comparisons = {
            "close": (close, bar.close_price),
            "high": (high, bar.high_price),
            "low": (low, bar.low_price),
            "volume": (volume, bar.volume),
            "turnover": (amount, bar.turnover_inr),
            "trades": (count, bar.trade_count),
        }
        if row["official_nse_eq_isin_observed"] != bar.isin or any(
            not math.isclose(float(lhs), float(rhs), abs_tol=1e-7)
            for lhs, rhs in comparisons.values()
        ):
            raise ValueError("five-case price record does not match original NSE UDiFF")
        scenarios = [
            {
                "single_day_participation_percent": pct,
                "illustrative_ticket_inr": ticket,
                "same_day_turnover_fraction_inr": amount * pct / 100,
                "ticket_divided_by_same_day_fraction": ticket / (amount * pct / 100),
                "predicted_elapsed_trading_days": None,
                "executable_order_capacity_verified": False,
            }
            for pct in PARTICIPATION for ticket in TICKETS_INR
        ]
        cases.append({
            "symbol": symbol,
            "source_isin": bar.isin,
            "original_oct9_close_inr": close,
            "single_session_traded_value_inr_crore": amount / 10_000_000,
            "single_session_total_traded_shares": volume,
            "single_session_reported_trade_count": count,
            "single_session_vwap_arithmetic_inr": vwap,
            "single_session_high_low_range_over_close_percent": 100 * (high - low) / close,
            "illustrative_participation_scenarios": scenarios,
            "verified_bid_ask_spread": False,
            "verified_orderbook_depth": False,
            "multi_session_liquidity_distribution_measured": False,
            "actual_ticket_execution_claimed": False,
            "live_capital_allowed": False,
        })

    return {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "SINGLE_VERIFIED_OCT9_NSE_DAY_NOT_EXECUTABLE_LIQUIDITY_CAPACITY",
        "source_session": "2026-10-09",
        "original_five_company_count": 5,
        "source_provenance": provenance,
        "participation_percent_scenarios": list(PARTICIPATION),
        "illustrative_ticket_sizes_inr": list(TICKETS_INR),
        "cases": cases,
        "original_selection_changed": False,
        "daily_volumes_assumed_stable": False,
        "spread_slippage_and_impact_modeled": False,
        "expected_returns_calculated": False,
        "investment_recommendations_created": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
