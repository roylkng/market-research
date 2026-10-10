"""Outcome-blind NSE official daily source plane for the immutable U001 universe.

Preserves raw EQ OHLC, volume, traded value and Nifty 500 price-index OHLC
for later *separately authorized* H021 20/60-session evaluation.
An official price observation is not an executable trade or return label.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time
from typing import Any

from marketlab.alpha import AlphaContractError
from marketlab.alpha_market import parse_udiff_eq_panel
from marketlab.calendar_snapshot import CalendarSnapshot, _canonical_hash
from marketlab.marketdata import index_snapshot_url, udiff_url
from marketlab.pf001_marketdata import (
    PF001MarketDataError,
    parse_pf001_nifty500_index,
)

DAILY_ID = "H021-P008-U001-DAILY-OFFICIAL-SOURCE-v1"
ORIGINAL_U001_GIT_BLOB = "8026e81faee3e913d2fba1dba72d60603b69fa07"
ORIGINAL_CALENDAR_SHA = "2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce"
FIRST_DAILY_DATE = "2026-10-13"
LAST_CALENDAR_DATE = "2026-12-31"
ALLOWED_SOURCE_STATES = frozenset({"OK", "NOT_PUBLISHED", "ACCESS_BLOCKED", "FETCH_FAILED"})


def _utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError("official capture timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid official capture timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("official capture timestamp must be offset-aware")
    return parsed.astimezone(UTC)


def _sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def validate_calendar_day(session_date: str, calendar: CalendarSnapshot) -> str:
    day = date.fromisoformat(session_date)
    if not FIRST_DAILY_DATE <= day.isoformat() <= LAST_CALENDAR_DATE:
        raise ValueError("H021 P008 limited to the frozen 2026 daily research window")
    original = calendar.to_dict()
    declared_sha = original.pop("sha256")
    if _canonical_hash(original) != declared_sha or declared_sha != ORIGINAL_CALENDAR_SHA:
        raise ValueError("original official NSE calendar SHA mismatch")
    if calendar.version != "NSE-CM-FY27Q2-v1":
        raise ValueError("official NSE 2026 calendar version mismatch")
    regular_sessions = {item.session_date for item in calendar.sessions}
    if session_date in regular_sessions:
        return "FROZEN_REGULAR_NSE_SESSION"
    if session_date in calendar.unresolved_special_dates:
        return "POTENTIAL_SPECIAL_SESSION_OFFICIAL_SCHEDULE_UNVERIFIED"
    raise ValueError("not a recognized regular or pending NSE special session")


def _identity(universe: dict[str, Any]) -> list[dict[str, str | int]]:
    if (
        universe.get("schema_version") != 2
        or universe.get("cohort_id") != "FY27-Q2-2026-09-06"
        or universe.get("rule_version") != "U001-nifty200-top100-nonfinancial-ffmc-v2"
    ):
        raise ValueError("wrong original frozen H021-U001 universe identity")
    members = universe.get("members")
    if not isinstance(members, list) or len(members) != 100:
        raise ValueError("H021 P008 needs exactly 100 frozen U001 members")
    seen: set[str] = set()
    identities: list[dict[str, str | int]] = []
    for item in members:
        if not isinstance(item, dict):
            raise TypeError("frozen U001 member must be object")
        symbol, isin, rank = item.get("symbol"), item.get("isin"), item.get("rank")
        if (
            not isinstance(symbol, str) or not symbol or symbol in seen
            or not isinstance(isin, str) or len(isin) != 12
            or type(rank) is not int or not 1 <= rank <= 100
        ):
            raise ValueError("duplicate or malformed frozen U001 symbol/ISIN/rank")
        seen.add(symbol)
        identities.append({"symbol": symbol, "isin": isin, "universe_rank": rank})
    if sorted(int(item["universe_rank"]) for item in identities) != list(range(1, 101)):
        raise ValueError("frozen U001 rank identity changed")
    return sorted(identities, key=lambda item: int(item["universe_rank"]))


def _source(
    source: dict[str, Any],
    *,
    name: str,
    official_url: str,
    session_date: str,
    recorded_at: datetime,
) -> tuple[bytes | None, dict[str, Any]]:
    if not isinstance(source, dict):
        raise TypeError("official NSE source must be an object")
    if source.get("status") not in ALLOWED_SOURCE_STATES:
        raise ValueError("unexpected original source acquisition state")
    if source.get("url") != official_url:
        raise ValueError(f"{name}: not the pinned official NSE URL")
    captured = _utc(source.get("captured_at_utc"))
    # Ordinary NSE cash session closes at 10:00 UTC. For pending Muhurat
    # schedules this is ONLY a source capture floor, not a verified close.
    minimum = datetime.combine(date.fromisoformat(session_date), time(10), tzinfo=UTC)
    if captured < minimum:
        raise ValueError(f"{name}: source captured before standard close proxy")
    if captured > recorded_at:
        raise ValueError(f"{name}: recorded evidence precedes source acquisition")
    http = source.get("http_status")
    if http is not None and (type(http) is not int or not 100 <= http <= 599):
        raise ValueError(f"{name}: invalid HTTP status")
    status = source["status"]
    raw = source.get("raw")
    error = source.get("error")
    if status == "OK":
        if http != 200 or not isinstance(raw, bytes) or not raw or error is not None:
            raise ValueError(f"{name}: successful official fetch must retain original bytes")
    else:
        if raw is not None or not isinstance(error, str) or not error:
            raise ValueError(f"{name}: failed fetch may contain no source bytes")
        if status == "NOT_PUBLISHED" and http != 404:
            raise ValueError(f"{name}: NOT_PUBLISHED requires HTTP 404")
        if status == "ACCESS_BLOCKED" and http not in (401, 403, 429):
            raise ValueError(f"{name}: access blocking requires HTTP 401/403/429")
    receipt = {
        "status": status,
        "official_url": official_url,
        "captured_at_utc": captured.isoformat().replace("+00:00", "Z"),
        "http_status": http,
        "raw_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
        "raw_byte_count": len(raw) if raw is not None else None,
        "error": error,
    }
    return raw, receipt


def build_daily_u001_source(
    universe: dict[str, Any],
    calendar: CalendarSnapshot,
    *,
    session_date: str,
    udiff_source: dict[str, Any],
    index_source: dict[str, Any],
    recorded_at_utc: str,
) -> dict[str, Any]:
    calendar_state = validate_calendar_day(session_date, calendar)
    members = _identity(universe)
    recorded = _utc(recorded_at_utc)
    stock_bytes, stock_receipt = _source(
        udiff_source, name="udiff", session_date=session_date, recorded_at=recorded,
        official_url=udiff_url(date.fromisoformat(session_date)),
    )
    index_bytes, index_receipt = _source(
        index_source, name="index", session_date=session_date, recorded_at=recorded,
        official_url=index_snapshot_url(date.fromisoformat(session_date)),
    )

    official_by_symbol: dict[str, list] = {}
    official_parsing_error: str | None = None
    if stock_bytes is not None:
        try:
            parsed = parse_udiff_eq_panel(
                stock_bytes, session_date=date.fromisoformat(session_date)
            )
        except (AlphaContractError, ValueError, TypeError) as exc:
            official_parsing_error = f"{type(exc).__name__}:{exc}"
        else:
            for item in parsed:
                official_by_symbol.setdefault(item.symbol, []).append(item)

    observations: list[dict[str, Any]] = []
    for item in members:
        symbol = str(item["symbol"])
        isin = str(item["isin"])
        rows = official_by_symbol.get(symbol, [])
        base: dict[str, Any] = {
            "symbol": symbol,
            "isin": isin,
            "universe_rank": item["universe_rank"],
            "series": "EQ",
            "session_date": session_date,
            "open_price": None,
            "high_price": None,
            "low_price": None,
            "close_price": None,
            "previous_close": None,
            "volume": None,
            "turnover_inr": None,
            "trade_count": None,
            "status": None,
            "issue": None,
            "source_raw_sha256": stock_receipt["raw_sha256"],
            "liquidity_or_tradability_verified": False,
            "market_trade_fill_verified": False,
        }
        if stock_bytes is None:
            base["status"] = "OFFICIAL_SOURCE_UNAVAILABLE"
            base["issue"] = f"UDIFF_{stock_receipt['status']}"
        elif official_parsing_error is not None:
            base["status"] = "ORIGINAL_UDIFF_PARSER_ERROR"
            base["issue"] = official_parsing_error
        elif not rows:
            base["status"] = "NO_ORIGINAL_EQ_ROW"
            base["issue"] = "NO_OFFICIAL_SYMBOL_EVIDENCE_DO_NOT_FILL"
        elif len(rows) != 1 or rows[0].isin != isin:
            base["status"] = "ISIN_OR_SYMBOL_IDENTITY_UNRESOLVED"
            base["issue"] = "AMBIGUOUS_OR_CHANGED_EQ_IDENTITY"
        else:
            data = rows[0]
            base.update({
                "status": "OFFICIAL_EQ_OHLC_OBSERVED_UNADJUSTED",
                "open_price": data.open_price,
                "high_price": data.high_price,
                "low_price": data.low_price,
                "close_price": data.close_price,
                "previous_close": data.previous_close,
                "volume": data.volume,
                "turnover_inr": data.turnover_inr,
                "trade_count": data.trade_count,
            })
        observations.append(base)

    benchmark: dict[str, Any] = {
        "benchmark_id": "nifty_500",
        "session_date": session_date,
        "index_price_basis": "NIFTY500_PRICE_INDEX_NOT_TOTAL_RETURN",
        "source_raw_sha256": index_receipt["raw_sha256"],
        "open_index_value": None,
        "close_index_value": None,
        "status": None,
        "issue": None,
    }
    if index_bytes is None:
        benchmark["status"] = "OFFICIAL_INDEX_SOURCE_UNAVAILABLE"
        benchmark["issue"] = f"INDEX_{index_receipt['status']}"
    else:
        try:
            value = parse_pf001_nifty500_index(
                index_bytes, session_date=date.fromisoformat(session_date)
            )
        except PF001MarketDataError as exc:
            benchmark["status"] = "OFFICIAL_INDEX_PARSE_FAILURE"
            benchmark["issue"] = str(exc)
        else:
            benchmark["status"] = "OFFICIAL_NIFTY500_PRICE_INDEX_OBSERVED"
            benchmark["open_index_value"] = value.open_price
            benchmark["close_index_value"] = value.close_price

    price_count = sum(
        row["status"] == "OFFICIAL_EQ_OHLC_OBSERVED_UNADJUSTED" for row in observations
    )
    complete = (
        price_count == 100
        and benchmark["status"] == "OFFICIAL_NIFTY500_PRICE_INDEX_OBSERVED"
    )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "record_id": DAILY_ID,
        "classification": "ORIGINAL_NSE_DAILY_SOURCE_OBSERVATIONS_NOT_RETURN_OR_PORTFOLIO",
        "session_date_ist": session_date,
        "recorded_at_utc": recorded.isoformat().replace("+00:00", "Z"),
        "original_universe_git_blob_sha": ORIGINAL_U001_GIT_BLOB,
        "original_calendar_sha256": ORIGINAL_CALENDAR_SHA,
        "calendar_session_state": calendar_state,
        "possible_special_session_verified": False,
        "source_receipts": {"udiff": stock_receipt, "index": index_receipt},
        "universe_count": 100,
        "official_eq_ohlc_observed_count": price_count,
        "stock_rows": observations,
        "benchmark_row": benchmark,
        "source_observation_state": (
            "COMPLETE_UNADJUSTED_U001_PLUS_PRICE_INDEX_SOURCE"
            if complete
            else "PARTIAL_MISSING_OR_CORRUPTED_OFFICIAL_SOURCE"
        ),
        "corporate_actions_verified": False,
        "dividends_and_total_return_verified": False,
        "future_holding_session_outcomes_opened": False,
        "return_or_alpha_statistics_calculated": False,
        "trade_fills_verified": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    payload["packet_sha256"] = _sha(payload)
    return payload


def validate_daily_source_packet(packet: dict[str, Any]) -> None:
    value = packet.get("packet_sha256")
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError("H021 daily source packet SHA missing")
    if _sha({k: v for k, v in packet.items() if k != "packet_sha256"}) != value:
        raise ValueError("H021 daily source packet content tampered")
    if (
        packet.get("schema_version") != 1
        or packet.get("record_id") != DAILY_ID
        or packet.get("universe_count") != 100
    ):
        raise ValueError("daily source/identity schema mismatch")
    rows = packet.get("stock_rows")
    if not isinstance(rows, list) or len(rows) != 100:
        raise ValueError("daily source must preserve all 100 symbols")
    if len({row.get("symbol") for row in rows if isinstance(row, dict)}) != 100:
        raise ValueError("daily source symbol identity duplicated or missing")
    for field in (
        "corporate_actions_verified", "dividends_and_total_return_verified",
        "future_holding_session_outcomes_opened", "return_or_alpha_statistics_calculated",
        "trade_fills_verified", "portfolio_eligibility_allowed", "live_capital_allowed",
    ):
        if packet.get(field) is not False:
            raise ValueError(f"daily source must not elevate {field}")
