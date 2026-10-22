"""Exact Sunday 8-Nov-2026 H021 *source observation*, not H20 returns.

P024 is a special-session extension to the existing P008 weekday-only
collector. It cannot modify frozen original NSE calendar, position, H021
entry date, 20/60 holding period or trade execution assumptions.
An official circular published after Oct9 but before Nov8 authorizes only
a new source acquisition clock, not a retrospective price prediction.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from typing import Any

from marketlab.h021_daily_prices import _source
from marketlab.h021_entry_observation import (
    _canonical_hash,
    _utc,
    _validate_intent,
)
from marketlab.h021_muhurat_amendment import (
    AMENDMENT_ID,
    NEW_H20_EXIT,
    SAFE_ORIGINAL_MARKET_DATA_AFTER_UTC,
    validate_h021_muhurat_amendment,
)
from marketlab.marketdata import index_snapshot_url, udiff_url
from marketlab.pf001_marketdata import (
    PF001MarketDataError,
    PF001MarketDataMissingRow,
    parse_pf001_nifty500_index,
    parse_pf001_udiff_equity,
)

PACKET_ID = "H021-P024-NOV08-SPECIAL-NSE-ORIGINAL-OHLC-SOURCE-v1"
SUNDAY = date.fromisoformat(NEW_H20_EXIT)
SOURCE_RELEASE_NOT_BEFORE = _utc(SAFE_ORIGINAL_MARKET_DATA_AFTER_UTC)


def build_h021_muhurat_source(
    intent: dict[str, Any],
    universe: dict[str, Any],
    verified_clock: dict[str, Any],
    *,
    udiff_source: dict[str, Any],
    index_source: dict[str, Any],
    recorded_at_utc: str,
) -> dict[str, Any]:
    """Strict no-fill Sunday source capture, including missing/blocked receipts."""
    selected = _validate_intent(intent, universe)
    validate_h021_muhurat_amendment(verified_clock)
    if (
        verified_clock.get("amendment_id") != AMENDMENT_ID
        or verified_clock.get("H021_20_completed_sessions_calendar_exit_ist")
        != SUNDAY.isoformat()
        or verified_clock.get("H021_20_market_session_completed_as_of_circular")
        is not False
        or verified_clock.get("H021_20_stock_and_Nifty500_original_price_source_verified")
        is not False
    ):
        raise ValueError("immutable H021 November 8 source calendar changed")
    recorded = _utc(recorded_at_utc)
    if recorded < SOURCE_RELEASE_NOT_BEFORE:
        raise ValueError("Muhurat observation cannot precede all exchange trading cutoffs")
    udiff_bytes, udiff_receipt = _source(
        udiff_source, url=udiff_url(SUNDAY), minimum_time=SOURCE_RELEASE_NOT_BEFORE
    )
    index_bytes, index_receipt = _source(
        index_source, url=index_snapshot_url(SUNDAY), minimum_time=SOURCE_RELEASE_NOT_BEFORE
    )
    if recorded < _utc(udiff_receipt["captured_at_utc"]) or recorded < _utc(
        index_receipt["captured_at_utc"]
    ):
        raise ValueError("Muhurat packet cannot predate original NSE source capture")

    observed = 0
    stock_rows = []
    for symbol, isin in selected.items():
        ohlc = {
            "open_inr": None, "high_inr": None,
            "low_inr": None, "close_inr": None,
        }
        state = "OFFICIAL_SOURCE_NOT_YET_AVAILABLE"
        missing_reason = "UDIFF_" + udiff_receipt["status"]
        if udiff_bytes is not None:
            try:
                row = parse_pf001_udiff_equity(
                    udiff_bytes, symbol=symbol, session_date=SUNDAY, expected_isin=isin
                )
            except PF001MarketDataMissingRow:
                state = "OFFICIAL_EQ_IDENTITY_ABSENT"
                missing_reason = "NSE_EQ_ROW_MISSING_NOT_REPLACED_OR_ZERO_FILLED"
            except PF001MarketDataError as exc:
                state = "OFFICIAL_EQ_IDENTITY_OR_PRICE_INVALID"
                missing_reason = type(exc).__name__
            else:
                prices = (row.open_price, row.high_price, row.low_price, row.close_price)
                if not all(math.isfinite(price) and price > 0 for price in prices):
                    raise ValueError("original NSE Sunday OHLC contains invalid price")
                ohlc = dict(zip(
                    ("open_inr", "high_inr", "low_inr", "close_inr"),
                    prices, strict=True
                ))
                observed += 1
                state = "OFFICIAL_UNADJUSTED_SOURCE_OHLC_ONLY"
                missing_reason = None
        stock_rows.append({
            "symbol": symbol,
            "isin": isin,
            "series": "EQ",
            "original_source_sha256": udiff_receipt["sha256"],
            "state": state,
            "missing_reason": missing_reason,
            "original_unadjusted_ohlc_inr": ohlc,
            "closing_auction_instrument_eligibility_confirmed": False,
            "h021_exit_trade_executed": False,
            "split_bonus_and_dividend_basis_cleared": False,
        })

    index = {
        "index": "Nifty 500",
        "basis": "ORIGINAL_NSE_PRICE_INDEX_NOT_TRI",
        "original_source_sha256": index_receipt["sha256"],
        "open": None,
        "close": None,
        "state": "OFFICIAL_NSE_INDEX_SOURCE_NOT_YET_AVAILABLE",
    }
    if index_bytes is not None:
        try:
            parsed_index = parse_pf001_nifty500_index(
                index_bytes, session_date=SUNDAY
            )
        except PF001MarketDataError as exc:
            index["state"] = "ORIGINAL_NSE_NIFTY500_INDEX_INVALID_" + type(exc).__name__
        else:
            index.update(
                open=parsed_index.open_price,
                close=parsed_index.close_price,
                state="ORIGINAL_UNADJUSTED_NIFTY500_INDEX_ONLY",
            )
    complete = (
        observed == len(selected) == 10
        and index["state"] == "ORIGINAL_UNADJUSTED_NIFTY500_INDEX_ONLY"
    )
    result = {
        "schema_version": 1,
        "packet_id": PACKET_ID,
        "classification": "OFFICIAL_MUHURAT_NSE_SOURCE_ONLY_NO_BENCHMARK_EXCESS_OR_RETURN",
        "original_first_cohort_intent_id": intent["intent_id"],
        "special_session_date_ist": SUNDAY.isoformat(),
        "original_clock_amendment_id": AMENDMENT_ID,
        "original_clock_amendment_sha256": verified_clock["amendment_sha256"],
        "nse_special_trading_open_ist": "14:20",
        "nse_non_CAS_close_ist": "15:30",
        "nse_CAS_matching_end_ist": "15:35",
        "source_minimum_capture_time_utc": SAFE_ORIGINAL_MARKET_DATA_AFTER_UTC,
        "recorded_at_utc": recorded.isoformat().replace("+00:00", "Z"),
        "original_udiff_source_receipt": udiff_receipt,
        "original_index_source_receipt": index_receipt,
        "selected_original_stocks": len(selected),
        "observed_issuer_stock_ohlc_count": observed,
        "stocks": stock_rows,
        "benchmark": index,
        "capture_state": (
            "SOURCE_COMPLETE_NOT_ECONOMIC_RETURN" if complete
            else "SOURCE_INCOMPLETE_NO_FABRICATED_PRICE"
        ),
        "official_Sunday_market_index_price_basis_verified": complete,
        "H021_H20_trading_return_or_index_excess_calculated": False,
        "actual_execution_and_fees_verified": False,
        "CAS_nonCAS_security_specific_close_basis_verified": False,
        "corporate_action_and_dividend_total_return_verified": False,
        "H021_60_official_2027_calendar_verified": False,
        "equity_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["packet_sha256"] = _canonical_hash(result)
    return result


def validate_h021_muhurat_source(packet: dict[str, Any]) -> None:
    source = {k: v for k, v in packet.items() if k != "packet_sha256"}
    if packet.get("packet_sha256") != _canonical_hash(source):
        raise ValueError("Sunday original NSE source packet hash changed")
    if (
        packet.get("packet_id") != PACKET_ID
        or packet.get("special_session_date_ist") != SUNDAY.isoformat()
        or packet.get("original_clock_amendment_id") != AMENDMENT_ID
        or packet.get("selected_original_stocks") != 10
        or not isinstance(packet.get("stocks"), list)
        or len(packet["stocks"]) != 10
    ):
        raise ValueError("unrecognized Sunday original stock-source identity")
    for flag in (
        "H021_H20_trading_return_or_index_excess_calculated",
        "actual_execution_and_fees_verified",
        "CAS_nonCAS_security_specific_close_basis_verified",
        "corporate_action_and_dividend_total_return_verified",
        "H021_60_official_2027_calendar_verified",
        "equity_expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if packet.get(flag) is not False:
            raise ValueError(f"Sunday source packet cannot promote {flag}")
