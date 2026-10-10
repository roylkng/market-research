"""Prospective daily source evidence for the original H021 ten-stock paper cohort.

Capture stock and index OHLC after each completed NSE session. Do not compute
horizon returns, P&L, target prices, trade fills, or modify frozen stock selection.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from typing import Any

from marketlab.calendar_snapshot import CalendarSnapshot
from marketlab.h021_entry_observation import (
    ENTRY_DAY,
    _canonical_hash,
    _utc,
    _validate_intent,
)
from marketlab.marketdata import index_snapshot_url, udiff_url
from marketlab.pf001_marketdata import (
    PF001MarketDataError,
    PF001MarketDataMissingRow,
    parse_pf001_nifty500_index,
    parse_pf001_udiff_equity,
)

RECORD_ID = "H021-P008-DAILY-OFFICIAL-PATH-v1"
CALENDAR_SHA256 = "2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce"
ALLOWED_SOURCE_STATES = frozenset({"OK", "NOT_PUBLISHED", "ACCESS_BLOCKED", "FETCH_FAILED"})


def _verified_session(calendar: CalendarSnapshot, session_date: str) -> tuple[datetime, date]:
    if calendar.version != "NSE-CM-FY27Q2-v1" or calendar.sha256 != CALENDAR_SHA256:
        raise ValueError("unverified original NSE 2026 source calendar")
    day = date.fromisoformat(session_date)
    if not (date.fromisoformat(ENTRY_DAY) < day <= date.fromisoformat(calendar.end_date)):
        raise ValueError("H021 P008 requires completed post-entry 2026 sessions only")
    matching = [x for x in calendar.sessions if x.session_date == session_date]
    if len(matching) != 1:
        raise ValueError("unverified or duplicate NSE completed session")
    close = _utc(matching[0].close_timestamp_utc)
    return close, day


def _source(
    value: dict[str, Any], *,
    url: str,
    minimum_time: datetime,
) -> tuple[bytes | None, dict[str, Any]]:
    if not isinstance(value, dict):
        raise TypeError("source evidence must be a mapping")
    if value.get("url") != url:
        raise ValueError("unexpected NSE source URL")
    status = value.get("status")
    if status not in ALLOWED_SOURCE_STATES:
        raise ValueError("unrecognized NSE source receipt state")
    timestamp = _utc(value.get("captured_at_utc"))
    if timestamp < minimum_time:
        raise ValueError("source retrieved before official session close")
    http_status = value.get("http_status")
    if http_status is not None and (type(http_status) is not int or not 100 <= http_status <= 599):
        raise ValueError("invalid NSE source HTTP code")
    raw = value.get("raw")
    error = value.get("error")
    if status == "OK":
        if http_status != 200 or not isinstance(raw, bytes) or not raw or error is not None:
            raise ValueError("successful NSE source requires original unmodified bytes")
    else:
        if raw is not None or not isinstance(error, str) or not error:
            raise ValueError("blocked NSE source must preserve status and reason")
        if status == "NOT_PUBLISHED" and http_status != 404:
            raise ValueError("not-published NSE source must be HTTP 404")
        if status == "ACCESS_BLOCKED" and http_status not in (401, 403, 429):
            raise ValueError("access blocked must be 401, 403 or 429")
    receipt = {
        "url": url,
        "captured_at_utc": timestamp.isoformat().replace("+00:00", "Z"),
        "status": status,
        "http_status": http_status,
        "sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
        "byte_count": len(raw) if raw is not None else None,
        "error": error,
    }
    return raw, receipt


def build_daily_source_observation(
    intent: dict[str, Any],
    universe: dict[str, Any],
    calendar: CalendarSnapshot,
    *,
    session_date: str,
    udiff_source: dict[str, Any],
    index_source: dict[str, Any],
    recorded_at_utc: str,
) -> dict[str, Any]:
    """Exact source observation only; any missing row remains explicitly missing."""
    by_symbol = _validate_intent(intent, universe)
    close, day = _verified_session(calendar, session_date)
    recorded = _utc(recorded_at_utc)
    if recorded < close:
        raise ValueError("daily H021 packet cannot be recorded before session close")
    stock_raw, stock_receipt = _source(
        udiff_source, url=udiff_url(day), minimum_time=close
    )
    index_raw, index_receipt = _source(
        index_source, url=index_snapshot_url(day), minimum_time=close
    )
    if any(recorded < _utc(receipt["captured_at_utc"]) for receipt in (stock_receipt,index_receipt)):
        raise ValueError("daily packet was recorded before its original source capture")

    observed_stock_count = 0
    stock_rows: list[dict[str, Any]] = []
    for symbol, isin in by_symbol.items():
        status = "SOURCE_MISSING"
        reason = "UDIFF_" + stock_receipt["status"]
        ohlc: dict[str, float | None] = {
            "open_inr": None,
            "high_inr": None,
            "low_inr": None,
            "close_inr": None,
        }
        if stock_raw is not None:
            try:
                row = parse_pf001_udiff_equity(
                    stock_raw, symbol=symbol, session_date=day, expected_isin=isin
                )
            except PF001MarketDataMissingRow:
                status, reason = "OFFICIAL_EQ_ROW_MISSING", "ROW_ABSENT_NO_FILL"
            except PF001MarketDataError as exc:
                status, reason = "INVALID_OFFICIAL_EQ_SOURCE", type(exc).__name__
            else:
                prices = (row.open_price, row.high_price, row.low_price, row.close_price)
                if not all(math.isfinite(x) and x > 0 for x in prices):
                    raise ValueError("official OHLC row contains nonfinite or nonpositive price")
                ohlc = dict(zip(("open_inr","high_inr","low_inr","close_inr"),prices,strict=True))
                observed_stock_count += 1
                status, reason = "OFFICIAL_OHLC_NOT_EXECUTABLE_FILL", None
        stock_rows.append({
            "symbol": symbol,
            "isin": isin,
            "series": "EQ",
            "source_sha256": stock_receipt["sha256"],
            "status": status,
            "reason": reason,
            "ohlc": ohlc,
            "trade_filled": False,
            "corporate_action_adjusted": False,
        })

    benchmark = {
        "benchmark_id": "nifty_500",
        "basis": "PRICE_INDEX_NOT_TRI",
        "source_sha256": index_receipt["sha256"],
        "status": "SOURCE_MISSING",
        "open": None,
        "close": None,
        "reason": "INDEX_" + index_receipt["status"],
    }
    if index_raw is not None:
        try:
            v = parse_pf001_nifty500_index(index_raw, session_date=day)
        except PF001MarketDataError as exc:
            benchmark["status"] = "INVALID_OFFICIAL_INDEX_SOURCE"
            benchmark["reason"] = type(exc).__name__
        else:
            benchmark.update(status="OFFICIAL_INDEX_OHLC", open=v.open_price, close=v.close_price, reason=None)

    complete = observed_stock_count == 10 and benchmark["status"] == "OFFICIAL_INDEX_OHLC"
    result = {
        "schema_version": 1,
        "record_id": RECORD_ID,
        "classification": "FUTURE_NSE_PRICE_SOURCE_CAPTURE_NOT_H021_OUTCOME",
        "source_intent_id": intent["intent_id"],
        "session_date_ist": session_date,
        "recorded_at_utc": recorded.isoformat().replace("+00:00", "Z"),
        "calendar_version": calendar.version,
        "calendar_sha256": calendar.sha256,
        "stock_source": stock_receipt,
        "index_source": index_receipt,
        "selected_company_count": 10,
        "observed_stock_count": observed_stock_count,
        "stock_rows": stock_rows,
        "benchmark": benchmark,
        "capture_state": "SOURCE_COMPLETE" if complete else "SOURCE_INCOMPLETE",
        "unresolved_special_sessions_not_claimed_complete": [
            d for d in calendar.unresolved_special_dates if ENTRY_DAY < d <= session_date
        ],
        "horizon_return_calculated": False,
        "benchmark_excess_calculated": False,
        "corporate_actions_resolved": False,
        "dividends_adjusted": False,
        "trades_filled": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["packet_sha256"] = _canonical_hash(result)
    return result


def validate_daily_source_observation(packet: dict[str, Any]) -> None:
    digest = packet.get("packet_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("daily source packet digest missing")
    if _canonical_hash({k:v for k,v in packet.items() if k != "packet_sha256"}) != digest:
        raise ValueError("daily source packet was modified after sealing")
    if packet.get("record_id") != RECORD_ID:
        raise ValueError("not an H021 P008 daily source observation")
    for flag in (
        "horizon_return_calculated",
        "benchmark_excess_calculated",
        "corporate_actions_resolved",
        "dividends_adjusted",
        "trades_filled",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if packet.get(flag) is not False:
            raise ValueError(f"daily observation cannot enable {flag}")
