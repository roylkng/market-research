"""Immutable Oct 9 INOXGREEN turnover and disclosure-timing diagnostic.

The original NSE EQ UDiFF and original Sep29 (broadcast Oct8) pledge
filing are independently source-hashed and remain authoritative. A very
high share-turnover day is NOT evidence of economic accumulation, net
buyer demand, delivery, institutional ownership changes or stock alpha.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha_market import parse_udiff_eq_panel

AUDIT_ID = "HG007-P035-INOXGREEN-OCT09-NSE-TURNOVER-DISCLOSURE-TIMING-v1"
UDIFF_SHA = "8adbb3410c8cf4372290484a9b1798490ef279d30fc2439c93f082cc20ed198c"
SOURCES = {
    "P034": (
        "research/hg007/oct09-five-case-market/five-case-oct09-market-context-v1.json",
        "3e124533915e4c9e12a7a41e445af71b915d10bd",
    ),
    "P034_RECEIPT": (
        "research/hg007/oct09-five-case-market/source-acquisition-v1.json",
        "6426f5d4330be1a82701848e35d4beb9853ffd28",
    ),
    "P012": (
        "research/hg007/inoxgreen-post-qip-special/original-promoter-pledge-v1.json",
        "8a7d9efc1975b0790726663953ac2dd8ee5e67f0",
    ),
}
ZIP_PATH = Path(
    "research/hg007/oct09-five-case-market/original/" + UDIFF_SHA + ".zip"
)
SYMBOL = "INOXGREEN"
ISIN = "INE510W01014"
SOURCE_TRADING_DAY = "2026-10-09"
OCT8_NSE_CM_SESSION_CLOSE = "2026-10-08T10:00:00Z"
OCT9_NSE_CM_SESSION_OPEN = "2026-10-09T03:45:00Z"
PLEDGE_FIRST_BROADCAST = "2026-10-08T13:24:47Z"


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("source time must be ISO UTC string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("source timestamp must have timezone")
    return parsed.astimezone(UTC)


def _read_original_json(root: Path, key: str) -> tuple[dict[str, Any], dict[str, str]]:
    path, expected_git = SOURCES[key]
    raw = (root / path).read_bytes()
    git_sha = _git_blob(raw)
    if git_sha != expected_git:
        raise ValueError(f"{key}: original disclosure/market source Git blob changed")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise TypeError(f"{key}: original source is not JSON object")
    return parsed, {
        "path": path,
        "git_blob_sha": git_sha,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }


def load_immutable_inputs(root: Path) -> tuple[dict, dict, dict, bytes, dict]:
    source = {}
    provenance = {}
    for name in SOURCES:
        source[name], provenance[name] = _read_original_json(root, name)
    raw = (root / ZIP_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != UDIFF_SHA:
        raise ValueError("original Oct9 NSE UDiFF raw bytes do not match frozen SHA")
    provenance["ORIGINAL_UDIFF"] = {
        "path": str(ZIP_PATH),
        "source_sha256": UDIFF_SHA,
        "byte_count": len(raw),
    }
    return source["P034"], source["P034_RECEIPT"], source["P012"], raw, provenance


def build_oct9_volatility_custody(
    p034: dict[str, Any],
    acquisition: dict[str, Any],
    original_pledge: dict[str, Any],
    raw_udiff: bytes,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    if (
        p034.get("price_context_id")
        != "HG007-P034-2026-10-09-FIVE-CASE-OFFICIAL-EQ-PRICE-CONTEXT-v1"
        or p034.get("source_original_zip_sha256") != UDIFF_SHA
        or p034.get("five_case_count") != 5
        or p034.get("live_capital_allowed") is not False
    ):
        raise ValueError("previous market source or 5-stock research boundary changed")
    if (
        acquisition.get("status") != "ORIGINAL_OCT9_UDIFF_BYTES_VERIFIED"
        or acquisition.get("source_sha256") != UDIFF_SHA
        or acquisition.get("source_recovery_route")
        != "PRIOR_OFFICIAL_SS002_P007_GITHUB_ACTIONS_ORIGINAL_RAW_ARTIFACT"
        or acquisition.get("research_price_context_published") is not True
        or acquisition.get("live_capital_allowed") is not False
    ):
        raise ValueError("original source receipt provenance changed")
    if (
        original_pledge.get("audit_id") != "HG007-P012-INOXGREEN-EXACT-SEPT29-PLEDGE-AND-FD-v1"
        or original_pledge.get("issuer_asof_date") != "2026-09-29"
        or original_pledge.get("original_filing_public_broadcast_utc") != PLEDGE_FIRST_BROADCAST
        or original_pledge.get("listed_company_total_basic_shares") != 419602518
        or original_pledge.get("named_promoter_pledged_shares") != 4900000
        or original_pledge.get("listed_company_total_fully_diluted_shares") != 422070138
        or original_pledge.get("live_capital_allowed") is not False
    ):
        raise ValueError("29 Sep official pledge/capital facts or disclosure chronology drifted")
    cutoff = _timestamp(PLEDGE_FIRST_BROADCAST)
    if not (
        _timestamp(OCT8_NSE_CM_SESSION_CLOSE)
        < cutoff
        < _timestamp(OCT9_NSE_CM_SESSION_OPEN)
    ):
        raise ValueError("NSE pledge disclosure was not observed between two trading sessions")
    if not isinstance(raw_udiff, bytes) or hashlib.sha256(raw_udiff).hexdigest() != UDIFF_SHA:
        raise ValueError("Oct9 original NSE UDiFF fails raw SHA")
    rows = parse_udiff_eq_panel(raw_udiff, session_date=datetime.fromisoformat(SOURCE_TRADING_DAY).date())
    matches = [item for item in rows if item.symbol == SYMBOL]
    if len(matches) != 1 or matches[0].isin != ISIN:
        raise ValueError("Oct9 official NSE EQ row not uniquely bound to INOXGREEN ISIN")
    bar = matches[0]
    p034rows = p034.get("price_context_rows")
    if not isinstance(p034rows, list) or len(p034rows) != 5:
        raise ValueError("five-case source row accounting changed")
    previous = [r for r in p034rows if r.get("symbol") == SYMBOL]
    if len(previous) != 1 or previous[0].get("official_nse_eq_isin_observed") != ISIN:
        raise ValueError("INOXGREEN original P034 source ISIN changed")
    p034row = previous[0]
    for original_name, fresh in (
        ("official_oct9_open_inr", bar.open_price),
        ("official_oct9_high_inr", bar.high_price),
        ("official_oct9_low_inr", bar.low_price),
        ("official_oct9_close_inr", bar.close_price),
        ("official_oct9_total_traded_shares", bar.volume),
        ("official_oct9_total_traded_value_inr", bar.turnover_inr),
        ("official_oct9_number_of_executed_transactions", bar.trade_count),
    ):
        observed = p034row.get(original_name)
        if type(observed) not in (int, float) or not math.isclose(
            float(observed), float(fresh), rel_tol=0.0, abs_tol=1e-7
        ):
            raise ValueError(f"Oct9 source and prior five-case census disagree: {original_name}")
    if not all(
        math.isfinite(x) and x > 0 for x in (
            bar.previous_close, bar.open_price, bar.high_price,
            bar.low_price, bar.close_price, bar.volume, bar.turnover_inr
        )
    ):
        raise ValueError("official prior-close or stock activity is invalid")

    basic = original_pledge["listed_company_total_basic_shares"]
    # Daily volume counts transactions of shares, not unique shareholders.
    # Do not interpret volume/issued shares as % of company acquired.
    return {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "OCT9_ORIGINAL_NSE_VOLATILITY_AND_SOURCE_TIMING_NO_ALPHA",
        "symbol": SYMBOL,
        "isin": ISIN,
        "source_observation_session": SOURCE_TRADING_DAY,
        "source_provenance": provenance,
        "source_original_nse_zip_sha256": UDIFF_SHA,
        "source_ino_green_9oct": {
            "previous_nse_session_official_close_inr": bar.previous_close,
            "9oct_official_open_inr": bar.open_price,
            "9oct_official_high_inr": bar.high_price,
            "9oct_official_low_inr": bar.low_price,
            "9oct_official_close_inr": bar.close_price,
            "9oct_change_vs_previous_session_close_pct": (
                100 * (bar.close_price / bar.previous_close - 1)
            ),
            "9oct_official_traded_shares": bar.volume,
            "9oct_official_traded_value_inr": bar.turnover_inr,
            "9oct_official_traded_value_inr_crore": bar.turnover_inr / 10_000_000,
            "9oct_reported_number_of_transactions": bar.trade_count,
            "9oct_traded_volume_to_29sep_issued_basic_shares_pct": (
                100 * bar.volume / basic
            ),
            "oct1_to_oct9_unadjusted_price_reference_change_pct": (
                p034row["oct1_to_oct9_unadjusted_price_reference_change_pct"]
            ),
        },
        "disclosure_timing_control": {
            "official_pledge_source_asof_date": "2026-09-29",
            "official_pledge_source_first_broadcast_utc": PLEDGE_FIRST_BROADCAST,
            "oct8_cash_market_session_close_utc": OCT8_NSE_CM_SESSION_CLOSE,
            "oct9_cash_market_session_open_utc": OCT9_NSE_CM_SESSION_OPEN,
            "first_original_nse_pledge_broadcast_after_oct8_close": True,
            "first_original_nse_pledge_broadcast_before_oct9_open": True,
            "pledge_disclosure_publicly_available_during_oct8_cash_trading": False,
            "verified_pledged_promoter_shares_asof_29sep": 4900000,
            "actual_pledge_creation_instant_verified": False,
            "subsequent_pledge_changes_verified": False,
            "correlation_explains_intraday_price_move": False,
        },
        "interpretation_safeguards": {
            "high_daily_volume_proves_net_accumulation": False,
            "volume_proves_unique_shareholders_or_deliverable_quantity": False,
            "issuer_received_9oct_secondary_market_turnover_inr": False,
            "observed_9oct_close_is_broker_executable_fill": False,
            "specific_8oct_or_9oct_price_causation_verified": False,
            "oct9_overnight_pledge_information_was_a_possible_public_input": True,
        },
        "current_fully_diluted_share_count_verified_asof_oct11": False,
        "corporate_actions_and_dividend_adjusted_returns_verified": False,
        "prospective_holding_period_outcomes_opened": False,
        "stock_expected_returns_calculated": False,
        "current_equity_valuation_authorized": False,
        "investment_recommendation_authorized": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
