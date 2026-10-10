"""Fail-closed NSE next-open price *observation*, never a trade fill or return.

Only the ten symbols of the precommitted H021-P003 first cohort are
observable here. No selection logic, portfolio weights, ex-post substitution,
total-return adjustment, or 20/60-session outcome is produced.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from typing import Any

from marketlab.marketdata import index_snapshot_url, udiff_url
from marketlab.pf001_marketdata import (
    PF001MarketDataError,
    PF001MarketDataMissingRow,
    parse_pf001_nifty500_index,
    parse_pf001_udiff_equity,
)

ENTRY_DAY = "2026-10-12"
ENTRY_CLOSE_UTC = "2026-10-12T10:00:00Z"
INTENT_ID = "H021-P003-2026-10-09-FIRST-COHORT-v1"
RECORD_ID = "H021-P004-2026-10-12-OFFICIAL-ENTRY-OBSERVATION-v1"
EXPECTED_SELECTION = (
    "VEDL",
    "ETERNAL",
    "DMART",
    "IDEA",
    "ADANIENSOL",
    "JSWSTEEL",
    "COALINDIA",
    "INFY",
    "GAIL",
    "POWERGRID",
)
SOURCE_STATES = frozenset({"OK", "NOT_PUBLISHED", "ACCESS_BLOCKED", "FETCH_FAILED"})


def _utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError("capture timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid capture timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("capture timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _canonical_hash(value: dict[str, Any]) -> str:
    data = json.dumps(
        value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _validate_intent(intent: dict[str, Any], universe: dict[str, Any]) -> dict[str, str]:
    if intent.get("intent_id") != INTENT_ID or intent.get("schema_version") != 1:
        raise ValueError("unexpected frozen first H021 entry intent")
    if intent.get("classification") != (
        "PRE_ENTRY_OUTCOME_BLIND_H021_RESEARCH_ONLY_NOT_PORTFOLIO"
    ):
        raise ValueError("H021 entry intent classification changed")
    if intent.get("portfolio_eligibility_allowed") is not False:
        raise ValueError("portfolio eligibility must be disabled")
    if intent.get("live_capital_allowed") is not False:
        raise ValueError("live capital must be disabled")
    if intent.get("frozen_primary_selection_unchanged") is not True:
        raise ValueError("primary H021 cohort not frozen")
    if intent.get("no_position_orders_created") is not True:
        raise ValueError("entry intent must contain no orders")

    planned = intent.get("entry_plan")
    if not isinstance(planned, dict):
        raise TypeError("entry plan missing")
    if planned.get("session_date_ist") != ENTRY_DAY:
        raise ValueError("entry session was modified")
    if planned.get("calendar_open_timestamp_utc") != "2026-10-12T03:45:00Z":
        raise ValueError("entry open timestamp modified")
    if planned.get("price_proxy") != "NEXT_COMPLETED_SESSION_FIRST_EXECUTABLE_OPEN":
        raise ValueError("entry proxy changed")

    outcome = intent.get("outcome_plan")
    if not isinstance(outcome, dict):
        raise TypeError("H021 outcome plan missing")
    if (
        outcome.get("return_outcomes_opened") is not False
        or outcome.get("entry_and_exit_prices_observed") is not False
        or outcome.get("primary_horizon_completed_sessions") != 60
        or outcome.get("secondary_horizon_completed_sessions") != 20
        or outcome.get("benchmark_family") != "NIFTY_500"
    ):
        raise ValueError("frozen H021 return or benchmark boundary changed")

    selected = intent.get("selected_observations")
    if not isinstance(selected, list) or len(selected) != 10:
        raise ValueError("ten frozen H021 selected observations required")
    symbols = tuple(row.get("symbol") for row in selected if isinstance(row, dict))
    if symbols != EXPECTED_SELECTION:
        raise ValueError("frozen H021 selection was altered")
    if any(
        row.get("entry_price") is not None
        or row.get("capital_allocation") is not None
        or row.get("entry_execution_status") != "UNOBSERVED_NEXT_OPEN"
        for row in selected
    ):
        raise ValueError("entry intent already contains fills or capital")

    members = universe.get("members")
    if not isinstance(members, list) or len(members) != 100:
        raise ValueError("frozen U001 must have 100 members")
    if universe.get("cohort_id") != "FY27-Q2-2026-09-06":
        raise ValueError("unexpected frozen U001 cohort")
    by_symbol: dict[str, str] = {}
    for member in members:
        if not isinstance(member, dict):
            raise TypeError("U001 member must be object")
        symbol = member.get("symbol")
        isin = member.get("isin")
        if (
            not isinstance(symbol, str)
            or not symbol
            or symbol in by_symbol
            or not isinstance(isin, str)
            or len(isin) != 12
        ):
            raise ValueError("U001 has duplicate/invalid symbol or ISIN")
        by_symbol[symbol] = isin
    if not set(symbols).issubset(by_symbol):
        raise ValueError("frozen selected H021 name absent from U001")
    return {symbol: by_symbol[symbol] for symbol in symbols}


def _validate_source(
    name: str, raw_source: dict[str, Any], expected_url: str
) -> tuple[bytes | None, dict[str, Any]]:
    if not isinstance(raw_source, dict):
        raise TypeError(f"{name} must be a source record")
    status = raw_source.get("status")
    if status not in SOURCE_STATES:
        raise ValueError(f"{name}: invalid source status")
    if raw_source.get("url") != expected_url:
        raise ValueError(f"{name}: wrong official NSE source URL")
    captured = _utc(raw_source.get("captured_at_utc"))
    if captured < _utc(ENTRY_CLOSE_UTC):
        raise ValueError(f"{name}: source was captured before completed session close")
    http_status = raw_source.get("http_status")
    if http_status is not None and (
        type(http_status) is not int or not 100 <= http_status <= 599
    ):
        raise ValueError(f"{name}: invalid HTTP status")
    raw = raw_source.get("raw")
    error = raw_source.get("error")
    if status == "OK":
        if http_status != 200 or not isinstance(raw, bytes) or not raw:
            raise ValueError(f"{name}: successful source requires original nonempty bytes")
        if error is not None:
            raise ValueError(f"{name}: successful source may not have an error")
    else:
        if raw is not None or not isinstance(error, str) or not error:
            raise ValueError(f"{name}: unavailable source must preserve reason without bytes")
        if status == "NOT_PUBLISHED" and http_status != 404:
            raise ValueError(f"{name}: not-published state needs HTTP 404")
        if status == "ACCESS_BLOCKED" and http_status not in (401, 403, 429):
            raise ValueError(f"{name}: blocked status needs HTTP 401/403/429")
    receipt = {
        "status": status,
        "official_source_url": expected_url,
        "captured_at_utc": captured.isoformat().replace("+00:00", "Z"),
        "http_status": http_status,
        "raw_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
        "raw_byte_count": len(raw) if raw is not None else None,
        "raw_filename_extension": ".zip" if name == "udiff" else ".csv",
        "error": error,
    }
    return raw, receipt


def build_entry_observation(
    intent: dict[str, Any],
    universe: dict[str, Any],
    *,
    udiff_source: dict[str, Any],
    index_source: dict[str, Any],
    recorded_at_utc: str,
) -> dict[str, Any]:
    """Preserve source/data failures; never infer a trade or fill a price."""
    selected_isins = _validate_intent(intent, universe)
    recorded_at = _utc(recorded_at_utc)
    if recorded_at < _utc(ENTRY_CLOSE_UTC):
        raise ValueError("entry observation cannot exist before exchange session closes")
    session = date.fromisoformat(ENTRY_DAY)
    udiff_bytes, udiff_receipt = _validate_source(
        "udiff", udiff_source, udiff_url(session)
    )
    index_bytes, index_receipt = _validate_source(
        "index", index_source, index_snapshot_url(session)
    )
    if recorded_at < _utc(udiff_receipt["captured_at_utc"]) or recorded_at < _utc(
        index_receipt["captured_at_utc"]
    ):
        raise ValueError("observation timestamp cannot precede source capture")

    stocks = []
    for symbol, isin in selected_isins.items():
        row: dict[str, Any] = {
            "symbol": symbol,
            "isin": isin,
            "series": "EQ",
            "session_date": ENTRY_DAY,
            "open_price_inr": None,
            "high_price_inr": None,
            "low_price_inr": None,
            "close_price_inr": None,
            "source_sha256": udiff_receipt["raw_sha256"],
            "status": None,
            "issue": None,
            "tradability_confirmed": False,
            "actual_trade_fill_confirmed": False,
        }
        if udiff_bytes is None:
            row["status"] = "SOURCE_UNAVAILABLE"
            row["issue"] = f"UDIFF_{udiff_receipt['status']}"
        else:
            try:
                parsed = parse_pf001_udiff_equity(
                    udiff_bytes,
                    symbol=symbol,
                    session_date=session,
                    expected_isin=isin,
                )
            except PF001MarketDataMissingRow:
                row["status"] = "NO_OFFICIAL_EQ_ROW"
                row["issue"] = "ROW_ABSENT_DO_NOT_ASSUME_SUSPENDED_OR_FILL"
            except PF001MarketDataError as exc:
                row["status"] = "PARSER_OR_IDENTITY_ERROR"
                row["issue"] = str(exc)
            else:
                numbers = (
                    parsed.open_price,
                    parsed.high_price,
                    parsed.low_price,
                    parsed.close_price,
                )
                if not all(math.isfinite(x) and x > 0 for x in numbers):
                    raise ValueError(f"{symbol}: parser returned invalid price")
                row.update(
                    status="OFFICIAL_OHLC_OBSERVED_NOT_EXECUTABLE_FILL",
                    open_price_inr=parsed.open_price,
                    high_price_inr=parsed.high_price,
                    low_price_inr=parsed.low_price,
                    close_price_inr=parsed.close_price,
                )
        stocks.append(row)

    benchmark: dict[str, Any] = {
        "benchmark_id": "nifty_500",
        "index_name": "Nifty 500",
        "basis": "PRICE_INDEX_NOT_TRI",
        "session_date": ENTRY_DAY,
        "open_index_value": None,
        "close_index_value": None,
        "source_sha256": index_receipt["raw_sha256"],
        "status": "SOURCE_UNAVAILABLE",
        "issue": None,
    }
    if index_bytes is None:
        benchmark["issue"] = f"INDEX_{index_receipt['status']}"
    else:
        try:
            parsed_index = parse_pf001_nifty500_index(
                index_bytes, session_date=session
            )
        except PF001MarketDataError as exc:
            benchmark["status"] = "PARSER_OR_BENCHMARK_ERROR"
            benchmark["issue"] = str(exc)
        else:
            benchmark.update(
                open_index_value=parsed_index.open_price,
                close_index_value=parsed_index.close_price,
                status="OFFICIAL_PRICE_INDEX_OHLC_OBSERVED",
            )

    ready_count = sum(
        row["status"] == "OFFICIAL_OHLC_OBSERVED_NOT_EXECUTABLE_FILL"
        for row in stocks
    )
    is_complete = ready_count == 10 and benchmark["status"] == (
        "OFFICIAL_PRICE_INDEX_OHLC_OBSERVED"
    )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "record_id": RECORD_ID,
        "classification": "OFFICIAL_SOURCE_OBSERVATION_NOT_EXECUTION_OR_RETURN",
        "source_intent_id": INTENT_ID,
        "session_date_ist": ENTRY_DAY,
        "recorded_at_utc": recorded_at.isoformat().replace("+00:00", "Z"),
        "source_receipts": {"udiff": udiff_receipt, "index": index_receipt},
        "selected_symbol_count": 10,
        "observed_official_stock_open_count": ready_count,
        "stock_observations": stocks,
        "benchmark_observation": benchmark,
        "source_observation_status": (
            "FULL_OFFICIAL_OHLC_SOURCE_OBSERVED"
            if is_complete
            else "PARTIAL_OR_BLOCKED_SOURCE_OBSERVATION"
        ),
        "stock_price_basis": "RAW_NSE_UNADJUSTED",
        "corporate_action_adjustments_verified": False,
        "dividends_and_total_return_basis_verified": False,
        "execution_and_liquidity_verified": False,
        "return_outcomes_opened": False,
        "expected_returns_calculated": False,
        "entry_trades_executed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    payload["packet_sha256"] = _canonical_hash(payload)
    return payload


def validate_entry_observation(packet: dict[str, Any]) -> None:
    digest = packet.get("packet_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("entry packet SHA missing or invalid")
    if _canonical_hash({k: v for k, v in packet.items() if k != "packet_sha256"}) != digest:
        raise ValueError("entry packet content hash mismatch")
    if (
        packet.get("record_id") != RECORD_ID
        or packet.get("source_intent_id") != INTENT_ID
        or packet.get("session_date_ist") != ENTRY_DAY
    ):
        raise ValueError("entry packet identity mismatch")
    if (
        packet.get("return_outcomes_opened") is not False
        or packet.get("entry_trades_executed") is not False
        or packet.get("live_capital_allowed") is not False
        or packet.get("portfolio_eligibility_allowed") is not False
        or packet.get("execution_and_liquidity_verified") is not False
    ):
        raise ValueError("entry packet violates research-only boundary")
