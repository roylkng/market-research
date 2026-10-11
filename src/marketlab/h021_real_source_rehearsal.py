"""Before 12 Oct H021 open, rehearse actual prior-session NSE source parsers.

The archived 9 Oct NSE UDiFF is already source-pinned from the independent
HG007/SS002 capture. This rehearsal checks all original ten *unchanged*
H021 symbol/ISIN/EQ identities and Nifty 500 source schema without
opening return outcomes, publishing historical prices or making trades.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Any

from marketlab.h021_entry_observation import (
    ENTRY_DAY,
    EXPECTED_SELECTION,
    _canonical_hash,
    _validate_intent,
)
from marketlab.marketdata import index_snapshot_url, udiff_url
from marketlab.pf001_marketdata import (
    PF001MarketDataError,
    parse_pf001_nifty500_index,
    parse_pf001_udiff_equity,
)

REHEARSAL_ID = "H021-P011-2026-10-09-REAL-SOURCE-REHEARSAL-v1"
ORIGINAL_TRADING_DAY = date(2026, 10, 9)
SOURCE_ZIP_PATH = (
    "research/hg007/oct09-five-case-market/original/"
    "8adbb3410c8cf4372290484a9b1798490ef279d30fc2439c93f082cc20ed198c.zip"
)
SOURCE_ZIP_SHA256 = "8adbb3410c8cf4372290484a9b1798490ef279d30fc2439c93f082cc20ed198c"
SOURCE_ZIP_SIZE = 206_974
FIRST_OPEN_UTC = datetime(2026, 10, 12, 3, 45, tzinfo=UTC)
LAST_CLOSE_UTC = datetime(2026, 10, 9, 10, 0, tzinfo=UTC)
SOURCE_STATES = frozenset({
    "OK", "ACCESS_BLOCKED", "NOT_PUBLISHED", "FETCH_FAILED",
})


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be an ISO timestamp")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} timestamp invalid") from exc
    if result.tzinfo is None:
        raise ValueError(f"{label} timestamp must be timezone-aware")
    return result.astimezone(UTC)


def rehearse_original_official_files(
    intent: dict[str, Any],
    universe: dict[str, Any],
    *,
    original_oct9_zip: bytes,
    index_source: dict[str, Any],
    rehearsal_at_utc: str,
) -> dict[str, Any]:
    selected = _validate_intent(intent, universe)
    if tuple(selected) != EXPECTED_SELECTION or len(selected) != 10:
        raise ValueError("pre-entry original ten H021 identities changed")
    if intent.get("outcome_plan", {}).get("return_outcomes_opened") is not False:
        raise ValueError("original H021 outcomes unexpectedly opened")
    if intent.get("live_capital_allowed") is not False:
        raise ValueError("H021 cannot authorize capital")
    now = _utc(rehearsal_at_utc, "pre-entry rehearsal")
    if not LAST_CLOSE_UTC <= now < FIRST_OPEN_UTC:
        raise ValueError("pre-entry rehearsal must be after Oct9 close and before Oct12 open")
    if (
        not isinstance(original_oct9_zip, bytes)
        or len(original_oct9_zip) != SOURCE_ZIP_SIZE
        or hashlib.sha256(original_oct9_zip).hexdigest() != SOURCE_ZIP_SHA256
    ):
        raise ValueError("exact 9 October NSE UDiFF original source bytes changed")
    stock_rows: list[dict[str, Any]] = []
    for symbol, isin in selected.items():
        row: dict[str, Any] = {
            "symbol": symbol,
            "expected_isin": isin,
            "session_date": ORIGINAL_TRADING_DAY.isoformat(),
            "source_sha256": SOURCE_ZIP_SHA256,
            "source_url": udiff_url(ORIGINAL_TRADING_DAY),
            "status": "MISSING_OR_INVALID_OFFICIAL_EQ_RECORD",
            "issue": None,
            "market_price_values_disclosed_in_rehearsal": False,
            "actual_next_open_trade_executed": False,
        }
        try:
            parsed = parse_pf001_udiff_equity(
                original_oct9_zip,
                symbol=symbol,
                expected_isin=isin,
                session_date=ORIGINAL_TRADING_DAY,
            )
        except PF001MarketDataError as exc:
            row["issue"] = f"{type(exc).__name__}:{exc}"
        else:
            if (
                parsed.symbol != symbol or parsed.isin != isin
                or parsed.series != "EQ"
                or parsed.session_date != ORIGINAL_TRADING_DAY.isoformat()
            ):
                raise ValueError("NSE parser returned mismatched source identity")
            row["status"] = "ORIGINAL_OCT9_EQ_OHLC_SCHEMA_VALIDATED_NO_PRICES_RELEASED"
        stock_rows.append(row)
    valid = sum(
        item["status"] == "ORIGINAL_OCT9_EQ_OHLC_SCHEMA_VALIDATED_NO_PRICES_RELEASED"
        for item in stock_rows
    )

    if not isinstance(index_source, dict):
        raise TypeError("NSE index source requires a receipt")
    official_url = index_snapshot_url(ORIGINAL_TRADING_DAY)
    if index_source.get("url") != official_url:
        raise ValueError("index source URL cannot be changed")
    state = index_source.get("status")
    if state not in SOURCE_STATES:
        raise ValueError("official index source status missing/unknown")
    capture = _utc(index_source.get("captured_at_utc"), "index capture")
    if not LAST_CLOSE_UTC <= capture <= now:
        raise ValueError("Nifty500 index source capture outside pre-entry time boundary")
    http_status = index_source.get("http_status")
    raw = index_source.get("raw")
    error = index_source.get("error")
    if state == "OK":
        if http_status != 200 or not isinstance(raw, bytes) or not raw or error is not None:
            raise ValueError("successful index source must preserve exact HTTP 200 original bytes")
    else:
        if raw is not None or not isinstance(error, str) or not error:
            raise ValueError("unavailable index source must preserve reason without invented bytes")
        if state == "ACCESS_BLOCKED" and http_status not in (401, 403, 429):
            raise ValueError("blocked original source needs actual 401/403/429")
        if state == "NOT_PUBLISHED" and http_status != 404:
            raise ValueError("not published requires actual HTTP 404")
    index_sha = hashlib.sha256(raw).hexdigest() if raw is not None else None
    index_usable = False
    index_issue = error
    if raw is not None:
        try:
            observed = parse_pf001_nifty500_index(
                raw, session_date=ORIGINAL_TRADING_DAY
            )
        except PF001MarketDataError as exc:
            index_issue = f"{type(exc).__name__}:{exc}"
        else:
            index_usable = (
                observed.benchmark_id == "nifty_500"
                and observed.index_name == "Nifty 500"
                and observed.session_date == ORIGINAL_TRADING_DAY.isoformat()
            )
            if not index_usable:
                index_issue = "NIFTY500_SOURCE_IDENTITY_INVALID"
    if index_usable:
        index_issue = None
    complete = valid == len(EXPECTED_SELECTION) and index_usable
    packet: dict[str, Any] = {
        "schema_version": 1,
        "rehearsal_id": REHEARSAL_ID,
        "classification": "REAL_PRIOR_SESSION_SOURCE_FORMAT_PREFLIGHT_NO_OUTCOME_OR_TRADE",
        "recorded_at_utc": now.isoformat().replace("+00:00", "Z"),
        "source_session": ORIGINAL_TRADING_DAY.isoformat(),
        "planned_future_entry_session": ENTRY_DAY,
        "pre_future_entry_intent_unchanged": True,
        "original_oct9_udiff_source_sha256": SOURCE_ZIP_SHA256,
        "original_oct9_udiff_source_bytes": len(original_oct9_zip),
        "original_oct9_udiff_source_url": udiff_url(ORIGINAL_TRADING_DAY),
        "selected_stock_identity_count": len(EXPECTED_SELECTION),
        "real_stock_row_valid_count": valid,
        "stock_parser_receipts": stock_rows,
        "index_source_receipt": {
            "url": official_url,
            "status": state,
            "http_status": http_status,
            "captured_at_utc": capture.isoformat().replace("+00:00", "Z"),
            "raw_sha256": index_sha,
            "raw_bytes": len(raw) if raw is not None else None,
            "parser_identity_ready": index_usable,
            "error_or_parser_issue": index_issue,
            "basis": "NIFTY500_PRICE_INDEX_NOT_TRI",
        },
        "rehearsal_state": (
            "VALIDATED_REAL_OCT9_STOCK_AND_INDEX_SOURCE_FORMATS"
            if complete else "SOURCE_FORMAT_OR_ACCESS_BLOCKED_EXPLICITLY"
        ),
        "actual_oct12_price_rows_observed": False,
        "index_and_stock_return_observed": False,
        "entry_trade_filled": False,
        "selection_changed": False,
        "corporate_actions_verified": False,
        "dividends_adjusted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    packet["packet_sha256"] = _canonical_hash(packet)
    return packet


def validate_pre_entry_rehearsal(packet: dict[str, Any]) -> None:
    if packet.get("rehearsal_id") != REHEARSAL_ID:
        raise ValueError("unrecognized real-source H021 rehearsal")
    digest = packet.get("packet_sha256")
    if (
        not isinstance(digest, str) or len(digest) != 64
        or _canonical_hash({k: v for k, v in packet.items() if k != "packet_sha256"})
        != digest
    ):
        raise ValueError("original source rehearsal packet was modified")
    if (
        packet.get("selected_stock_identity_count") != 10
        or packet.get("real_stock_row_valid_count", 0) > 10
        or packet.get("source_session") != "2026-10-09"
    ):
        raise ValueError("H021 pre-entry source rehearsal identity mismatch")
    for flag in (
        "actual_oct12_price_rows_observed",
        "index_and_stock_return_observed",
        "entry_trade_filled",
        "selection_changed",
        "corporate_actions_verified",
        "dividends_adjusted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if packet.get(flag) is not False:
            raise ValueError(f"source preflight cannot authorize {flag}")
