"""Independent original NSE Oct-12 H021 opening-source replay.

Reconstruct the exact original ten company OHLC bars and Nifty 500 price
index from immutable raw exchange bytes, never from a supplied summary
alone. No order fills, dividends, share adjustments or future returns.
"""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, date, datetime
from typing import Any

from marketlab.h021_entry_observation import (
    ENTRY_CLOSE_UTC,
    ENTRY_DAY,
    EXPECTED_SELECTION,
    INTENT_ID,
    RECORD_ID,
    _canonical_hash,
    _validate_intent,
    validate_entry_observation,
)
from marketlab.marketdata import index_snapshot_url, udiff_url
from marketlab.pf001_marketdata import (
    parse_pf001_nifty500_index,
    parse_pf001_udiff_equity,
)

REPLAY_ID = "H021-P015-2026-10-12-INDEPENDENT-OFFICIAL-RAW-REPLAY-v1"


def _parse_utc(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{label} requires an ISO timestamp")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} has an invalid UTC capture timestamp") from exc
    if result.tzinfo is None:
        raise ValueError(f"{label} capture timestamp has no timezone")
    return result.astimezone(UTC)


def _check_source_receipt(
    packet: dict[str, Any],
    *,
    name: str,
    raw: bytes,
    url: str,
    suffix: str,
) -> dict[str, Any]:
    source = packet.get("source_receipts", {}).get(name)
    if not isinstance(source, dict):
        raise TypeError(f"{name}: missing original official source receipt")
    if not isinstance(raw, bytes) or not raw:
        raise ValueError(f"{name}: missing original NSE source bytes")
    raw_sha = hashlib.sha256(raw).hexdigest()
    if (
        source.get("status") != "OK"
        or source.get("http_status") != 200
        or source.get("error") is not None
        or source.get("official_source_url") != url
        or source.get("raw_filename_extension") != suffix
        or source.get("raw_byte_count") != len(raw)
        or source.get("raw_sha256") != raw_sha
    ):
        raise ValueError(f"{name}: exchange raw bytes/URL/receipt identity mismatch")
    time = _parse_utc(source.get("captured_at_utc"), f"{name} source")
    if not _parse_utc(ENTRY_CLOSE_UTC, "session close") <= time <= _parse_utc(
        packet.get("recorded_at_utc"), "original record"
    ):
        raise ValueError(f"{name}: original source capture occurs outside completed session")
    return {
        "raw_sha256": raw_sha,
        "raw_byte_count": len(raw),
        "original_url": url,
        "original_captured_at_utc": source["captured_at_utc"],
    }


def _same_numeric(original: object, parsed: float, label: str) -> None:
    if (
        type(original) not in (float, int)
        or not math.isfinite(float(original))
        or float(original) != parsed
    ):
        raise ValueError(f"{label} differs from independently reparsed NSE original")


def replay_first_h021_entry(
    *,
    original_packet: dict[str, Any],
    frozen_intent: dict[str, Any],
    frozen_universe: dict[str, Any],
    stock_udiff_zip: bytes,
    nifty500_index_csv: bytes,
) -> dict[str, Any]:
    """Construct a non-investable replay from original source after close."""
    validate_entry_observation(original_packet)
    frozen = _validate_intent(frozen_intent, frozen_universe)
    if tuple(frozen) != EXPECTED_SELECTION:
        raise ValueError("original H021 ten-company selection/order changed")
    if (
        original_packet.get("record_id") != RECORD_ID
        or original_packet.get("source_intent_id") != INTENT_ID
        or original_packet.get("source_observation_status")
        != "FULL_OFFICIAL_OHLC_SOURCE_OBSERVED"
        or original_packet.get("observed_official_stock_open_count") != 10
        or original_packet.get("selected_symbol_count") != 10
        or original_packet.get("classification")
        != "OFFICIAL_SOURCE_OBSERVATION_NOT_EXECUTION_OR_RETURN"
    ):
        raise ValueError("first H021 original source packet is incomplete or replaced")
    for blocked in (
        "entry_trades_executed",
        "expected_returns_calculated",
        "return_outcomes_opened",
        "execution_and_liquidity_verified",
        "corporate_action_adjustments_verified",
        "dividends_and_total_return_basis_verified",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if original_packet.get(blocked) is not False:
            raise ValueError(f"original source cannot authorize {blocked}")
    if set(original_packet.get("source_receipts", {})) != {"udiff", "index"}:
        raise ValueError("first source packet does not have the exact two official sources")
    day = date.fromisoformat(ENTRY_DAY)
    udiff = _check_source_receipt(
        original_packet, name="udiff", raw=stock_udiff_zip,
        url=udiff_url(day), suffix=".zip",
    )
    index = _check_source_receipt(
        original_packet, name="index", raw=nifty500_index_csv,
        url=index_snapshot_url(day), suffix=".csv",
    )
    reported = original_packet.get("stock_observations")
    if not isinstance(reported, list) or len(reported) != 10:
        raise ValueError("original H021 full stock rows missing")
    stock_bars = []
    for symbol, row in zip(EXPECTED_SELECTION, reported, strict=True):
        if not isinstance(row, dict):
            raise TypeError("original first-entry OHLC row must be object")
        isin = frozen[symbol]
        if (
            row.get("symbol") != symbol or row.get("isin") != isin
            or row.get("session_date") != ENTRY_DAY
            or row.get("series") != "EQ"
            or row.get("source_sha256") != udiff["raw_sha256"]
            or row.get("status") != "OFFICIAL_OHLC_OBSERVED_NOT_EXECUTABLE_FILL"
            or row.get("issue") is not None
            or row.get("tradability_confirmed") is not False
            or row.get("actual_trade_fill_confirmed") is not False
        ):
            raise ValueError(f"{symbol}: first-entry reported row is not original EQ/ISIN")
        parsed = parse_pf001_udiff_equity(
            stock_udiff_zip, symbol=symbol, expected_isin=isin, session_date=day,
        )
        for key, number in (
            ("open_price_inr", parsed.open_price),
            ("high_price_inr", parsed.high_price),
            ("low_price_inr", parsed.low_price),
            ("close_price_inr", parsed.close_price),
        ):
            _same_numeric(row.get(key), number, f"{symbol}:{key}")
        stock_bars.append({
            "symbol": symbol,
            "isin": isin,
            "date_ist": ENTRY_DAY,
            "open_price_inr": parsed.open_price,
            "close_price_inr": parsed.close_price,
            "high_price_inr": parsed.high_price,
            "low_price_inr": parsed.low_price,
            "original_udiff_sha256": udiff["raw_sha256"],
            "entry_trade_filled": False,
            "raw_price_is_corporate_action_adjusted": False,
        })

    benchmark = original_packet.get("benchmark_observation")
    if not isinstance(benchmark, dict):
        raise TypeError("original H021 index observation must be object")
    if (
        benchmark.get("benchmark_id") != "nifty_500"
        or benchmark.get("index_name") != "Nifty 500"
        or benchmark.get("basis") != "PRICE_INDEX_NOT_TRI"
        or benchmark.get("session_date") != ENTRY_DAY
        or benchmark.get("source_sha256") != index["raw_sha256"]
        or benchmark.get("status") != "OFFICIAL_PRICE_INDEX_OHLC_OBSERVED"
        or benchmark.get("issue") is not None
    ):
        raise ValueError("index source basis or identity differs from original packet")
    parsed_index = parse_pf001_nifty500_index(
        nifty500_index_csv, session_date=day,
    )
    _same_numeric(benchmark.get("open_index_value"), parsed_index.open_price, "NIFTY500:open")
    _same_numeric(benchmark.get("close_index_value"), parsed_index.close_price, "NIFTY500:close")

    result = {
        "schema_version": 1,
        "replay_id": REPLAY_ID,
        "classification": "RAW_NSE_H021_ENTRY_SOURCE_INDEPENDENT_REPLAY_NOT_TRADING",
        "source_entry_session_date_ist": ENTRY_DAY,
        "source_entry_record_sha256": original_packet["packet_sha256"],
        "source_entry_recorded_at_utc": original_packet["recorded_at_utc"],
        "source_original_intent_id": INTENT_ID,
        "source_receipts": {"stock_udiff": udiff, "index_csv": index},
        "selected_stock_source_count": len(stock_bars),
        "selected_stock_bars": stock_bars,
        "benchmark_price_index_bar": {
            "name": "Nifty 500",
            "price_index_not_tri": True,
            "open": parsed_index.open_price,
            "close": parsed_index.close_price,
            "original_source_sha256": index["raw_sha256"],
        },
        "raw_official_post_close_market_source_replayed": True,
        "proves_first_open_was_executable_fill": False,
        "current_market_depth_and_slippage_verified": False,
        "vedl_pre_entry_dividend_entitlement_verified": False,
        "all_ten_dividend_and_corporate_actions_verified": False,
        "benchmark_and_equity_dividend_total_return_bases_reconciled": False,
        "twenty_session_holding_outcome_opened": False,
        "sixty_session_holding_outcome_opened": False,
        "expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["replay_sha256"] = _canonical_hash(result)
    return result


def validate_first_h021_replay(packet: dict[str, Any]) -> None:
    digest = packet.get("replay_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("entry raw replay digest missing")
    if _canonical_hash({k: v for k, v in packet.items() if k != "replay_sha256"}) != digest:
        raise ValueError("entry raw source replay packet SHA is invalid")
    if (
        packet.get("replay_id") != REPLAY_ID
        or packet.get("selected_stock_source_count") != 10
        or packet.get("source_entry_session_date_ist") != ENTRY_DAY
        or packet.get("raw_official_post_close_market_source_replayed") is not True
    ):
        raise ValueError("unrecognized/partial original official NSE replay")
    for blocked in (
        "proves_first_open_was_executable_fill",
        "current_market_depth_and_slippage_verified",
        "vedl_pre_entry_dividend_entitlement_verified",
        "all_ten_dividend_and_corporate_actions_verified",
        "benchmark_and_equity_dividend_total_return_bases_reconciled",
        "twenty_session_holding_outcome_opened",
        "sixty_session_holding_outcome_opened",
        "expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if packet.get(blocked) is not False:
            raise ValueError(f"entry source replay cannot authorize {blocked}")
