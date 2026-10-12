"""Recover official *12 Oct 2026* Nifty 500 source without backdating H021.

The first official UDiFF already has ten valid original equity open observations,
but its separately captured official Nifty 500 index source returned HTTP 404.
Never substitute third-party indices, alternate dates, inferred TRI or fills.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from marketlab.h021_entry_observation import (
    ENTRY_CLOSE_UTC,
    ENTRY_DAY,
    EXPECTED_SELECTION,
    _canonical_hash,
    _validate_intent,
    validate_entry_observation,
)
from marketlab.h021_first_entry_intent import (
    build_first_entry_intent,
    git_blob_sha,
    load_pinned_inputs,
)
from marketlab.marketdata import index_snapshot_url
from marketlab.pf001_marketdata import (
    PF001MarketDataError,
    parse_pf001_nifty500_index,
    parse_pf001_udiff_equity,
)

RECOVERY_ID = "H021-P018-2026-10-12-OFFICIAL-INDEX-SOURCE-RECOVERY-v1"
ORIGINAL_FIRST_PACKET = Path(
    "research/prospective/h021/entry-observations/"
    "reconstructed-attempts/38246531921-1.json"
)
ORIGINAL_PACKET_BLOB = "4c85a6a053ffcdb6d28456163464e63a463f9511"
ORIGINAL_PACKET_SHA = "c314c0f001476f9ff221ca5055fb6b185702f862d4a455c5f0bb0e2f151dacbd"
ORIGINAL_STOCK_SHA = "818f673b3cdb96ae8ec4e466c7c4fd3a28d035482173a675dd24f9437a3ecd99"
ORIGINAL_STOCK_PATH = Path(
    "research/prospective/h021/entry-observations/raw/sha256/"
    + ORIGINAL_STOCK_SHA + ".zip"
)
ORIGINAL_INTENT = Path(
    "research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json"
)
ORIGINAL_INTENT_BLOB = "e25f77e1c845456473e624899d4748e306b1225b"
ORIGINAL_UNIVERSE = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")
ORIGINAL_UNIVERSE_BLOB = "8026e81faee3e913d2fba1dba72d60603b69fa07"
PRIMARY_URL = index_snapshot_url(date.fromisoformat(ENTRY_DAY))
NSE_ARCHIVE_MIRROR_URL = (
    "https://nsearchives.nseindia.com/content/indices/ind_close_all_12102026.csv"
)
SOURCE_URLS = {"primary": PRIMARY_URL, "nse_archive_mirror": NSE_ARCHIVE_MIRROR_URL}
CAPTURE_STATES = frozenset({"OK", "NOT_PUBLISHED", "ACCESS_BLOCKED", "FETCH_FAILED"})
SEALABLE_STATES = frozenset({"OFFICIAL_PRIMARY_INDEX_VERIFIED", "OFFICIAL_DUAL_HOSTS_AGREE"})


def _utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("source/packet captured-at must be a timezone-aware string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid ISO capture timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("capture timestamps require timezone")
    return parsed.astimezone(UTC)


def read_originals(root: Path) -> dict[str, Any]:
    """Reparse all ten original equity bars. Never trust a pasted price table."""
    comp, cal = load_pinned_inputs(
        root / "research/prospective/h021/comparisons/2026-10-09-primary-revision-v1.json",
        root / "research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json",
    )
    raw_intent = (root / ORIGINAL_INTENT).read_bytes()
    raw_universe = (root / ORIGINAL_UNIVERSE).read_bytes()
    raw_first = (root / ORIGINAL_FIRST_PACKET).read_bytes()
    raw_equity = (root / ORIGINAL_STOCK_PATH).read_bytes()
    if (
        git_blob_sha(raw_intent) != ORIGINAL_INTENT_BLOB
        or git_blob_sha(raw_universe) != ORIGINAL_UNIVERSE_BLOB
        or git_blob_sha(raw_first) != ORIGINAL_PACKET_BLOB
        or hashlib.sha256(raw_equity).hexdigest() != ORIGINAL_STOCK_SHA
    ):
        raise ValueError("original prospective source Git blob or NSE ZIP SHA changed")
    intent = json.loads(raw_intent)
    universe = json.loads(raw_universe)
    first = json.loads(raw_first)
    if intent != build_first_entry_intent(comp, cal):
        raise ValueError("original first H021 intent is not reproducible")
    selected = _validate_intent(intent, universe)
    validate_entry_observation(first)
    if (
        first.get("packet_sha256") != ORIGINAL_PACKET_SHA
        or first.get("observed_official_stock_open_count") != 10
        or first.get("source_observation_status") != "PARTIAL_OR_BLOCKED_SOURCE_OBSERVATION"
        or first.get("session_date_ist") != ENTRY_DAY
        or first.get("benchmark_observation", {}).get("status") != "SOURCE_UNAVAILABLE"
        or first.get("source_receipts", {}).get("index", {}).get("status") != "NOT_PUBLISHED"
        or first.get("source_receipts", {}).get("udiff", {}).get("raw_sha256")
        != ORIGINAL_STOCK_SHA
    ):
        raise ValueError("first official NSE original packet missing 10 EQ/404 index boundary")
    expected = first.get("stock_observations")
    if not isinstance(expected, list) or len(expected) != 10:
        raise ValueError("original ten stock OHLC rows missing")
    for symbol, row in zip(EXPECTED_SELECTION, expected, strict=True):
        if (
            row.get("symbol") != symbol or row.get("isin") != selected[symbol]
            or row.get("source_sha256") != ORIGINAL_STOCK_SHA
            or row.get("status") != "OFFICIAL_OHLC_OBSERVED_NOT_EXECUTABLE_FILL"
            or row.get("actual_trade_fill_confirmed") is not False
        ):
            raise ValueError("original first equity source row identity changed")
        parsed = parse_pf001_udiff_equity(
            raw_equity, symbol=symbol, expected_isin=selected[symbol],
            session_date=date.fromisoformat(ENTRY_DAY)
        )
        if (
            row.get("open_price_inr") != parsed.open_price
            or row.get("close_price_inr") != parsed.close_price
            or row.get("high_price_inr") != parsed.high_price
            or row.get("low_price_inr") != parsed.low_price
        ):
            raise ValueError(f"{symbol}: original actual NSE opening/closing price drifted")
    return {"original_packet_sha256": first["packet_sha256"],
            "original_equity_sha256": ORIGINAL_STOCK_SHA,
            "original_stock_open_count": 10,
            "frozen_selection_symbols": list(EXPECTED_SELECTION),
            "entry_session": ENTRY_DAY,
            "original_first_index_status": "NOT_PUBLISHED"}


def _parse_source(name: str, source: dict[str, Any]) -> tuple[dict[str, Any], bytes | None]:
    """Validate one exact official NSE endpoint and parse only Oct12 Nifty500."""
    if name not in SOURCE_URLS or not isinstance(source, dict):
        raise TypeError("only declared official source candidate records are accepted")
    if source.get("url") != SOURCE_URLS[name]:
        raise ValueError("source URL must be exact declared official NSE endpoint")
    captured = _utc(source.get("captured_at_utc"))
    if captured < _utc(ENTRY_CLOSE_UTC):
        raise ValueError("NSE index source capture cannot predate Oct12 session close")
    status = source.get("status")
    if status not in CAPTURE_STATES:
        raise ValueError("unknown official NSE fetch status")
    code = source.get("http_status")
    raw = source.get("raw")
    error = source.get("error")
    if status == "OK":
        if code != 200 or not isinstance(raw, bytes) or not raw or error is not None:
            raise ValueError("successful NSE index source requires unmodified HTTP 200 bytes")
    else:
        if raw is not None or not isinstance(error, str) or not error:
            raise ValueError("unavailable source must preserve reason and no bytes")
        if status == "NOT_PUBLISHED" and code != 404:
            raise ValueError("not-published official index source requires HTTP 404")
        if status == "ACCESS_BLOCKED" and code not in (401, 403, 429):
            raise ValueError("access-blocked NSE source requires explicit 401/403/429")
    out = {"endpoint_id": name, "url": source["url"],
           "captured_at_utc": captured.isoformat().replace("+00:00", "Z"),
           "fetch_status": status, "http_status": code,
           "raw_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
           "raw_byte_count": len(raw) if raw is not None else None,
           "fetch_error": error,
           "parse_status": "UNAVAILABLE", "open_index_value": None,
           "close_index_value": None}
    if raw is not None:
        try:
            parsed = parse_pf001_nifty500_index(
                raw, session_date=date.fromisoformat(ENTRY_DAY)
            )
        except PF001MarketDataError as exc:
            out["parse_status"] = "INVALID_OFFICIAL_INDEX_CSV"
            out["parse_error"] = str(exc)
        else:
            out["parse_status"] = "EXACT_OCT12_NIFTY500_PRICE_INDEX_ROW"
            out["open_index_value"] = parsed.open_price
            out["close_index_value"] = parsed.close_price
    return out, raw


def build_recovery(
    original: dict[str, Any],
    *,
    source_candidates: dict[str, dict[str, Any]],
    recorded_at_utc: str,
) -> dict[str, Any]:
    if (
        original.get("original_packet_sha256") != ORIGINAL_PACKET_SHA
        or original.get("original_equity_sha256") != ORIGINAL_STOCK_SHA
        or original.get("original_stock_open_count") != 10
        or original.get("frozen_selection_symbols") != list(EXPECTED_SELECTION)
        or original.get("original_first_index_status") != "NOT_PUBLISHED"
    ):
        raise ValueError("P018 cannot substitute original H021 ten-equity source")
    if set(source_candidates) != set(SOURCE_URLS):
        raise ValueError("official recovery must check exactly both declared NSE hosts")
    recorded = _utc(recorded_at_utc)
    parsed_receipts, saved = {}, {}
    for name in SOURCE_URLS:
        evidence, raw = _parse_source(name, source_candidates[name])
        if _utc(evidence["captured_at_utc"]) > recorded:
            raise ValueError("official source packet cannot predate its original fetch")
        parsed_receipts[name] = evidence
        if raw is not None:
            saved[name] = raw
    primary = parsed_receipts["primary"]
    mirror = parsed_receipts["nse_archive_mirror"]
    primary_ok = primary["parse_status"] == "EXACT_OCT12_NIFTY500_PRICE_INDEX_ROW"
    mirror_ok = mirror["parse_status"] == "EXACT_OCT12_NIFTY500_PRICE_INDEX_ROW"
    if primary_ok and mirror_ok and (
        primary["open_index_value"] != mirror["open_index_value"]
        or primary["close_index_value"] != mirror["close_index_value"]
    ):
        state = "CONFLICT_BETWEEN_OFFICIAL_NSE_ARCHIVE_HOSTS"
    elif primary["parse_status"] == "INVALID_OFFICIAL_INDEX_CSV" or (
        mirror["parse_status"] == "INVALID_OFFICIAL_INDEX_CSV"
    ):
        state = "BLOCKED_UNPARSEABLE_NSE_INDEX_SOURCE"
    elif primary_ok and mirror_ok:
        state = "OFFICIAL_DUAL_HOSTS_AGREE"
    elif primary_ok:
        state = "OFFICIAL_PRIMARY_INDEX_VERIFIED"
    elif mirror_ok:
        state = "SECONDARY_NSE_ARCHIVE_ONLY_PENDING_CORROBORATION"
    else:
        state = "OFFICIAL_OCT12_INDEX_NOT_YET_AVAILABLE"
    sealed = state in SEALABLE_STATES
    benchmark = {
        "index_name": "Nifty 500",
        "session_date_ist": ENTRY_DAY,
        "basis": "NSE_PRICE_INDEX_NOT_TOTAL_RETURN_INDEX",
        "original_oct12_primary_was_not_published_at_first_capture": True,
        "first_source_packet_sha256": ORIGINAL_PACKET_SHA,
        "first_source_stock_raw_sha256": ORIGINAL_STOCK_SHA,
        "observed_primary_open": primary["open_index_value"],
        "observed_primary_close": primary["close_index_value"],
        "observed_secondary_open": mirror["open_index_value"],
        "observed_secondary_close": mirror["close_index_value"],
        "corroborated_recovery_open": primary["open_index_value"] if sealed else None,
        "corroborated_recovery_close": primary["close_index_value"] if sealed else None,
        "source_state": state,
    }
    packet = {
        "schema_version": 1,
        "recovery_id": RECOVERY_ID,
        "classification": "POST_ENTRY_OFFICIAL_INDEX_SOURCE_SUPPLEMENT_NOT_BACKDATED_ENTRY",
        "session_date_ist": ENTRY_DAY,
        "created_at_utc": recorded.isoformat().replace("+00:00", "Z"),
        "first_original_equity_source": original,
        "source_receipts": parsed_receipts,
        "source_state": state,
        "verified_primary_or_agreed_dual_index_source": sealed,
        "benchmark": benchmark,
        "raw_source_byte_counts_retained": {
            k: len(v) for k, v in sorted(saved.items())
        },
        "first_original_source_attempt_unmodified": True,
        "nifty500_price_index_not_tri": True,
        "external_third_party_index_values_used": False,
        "index_from_other_sessions_inserted": False,
        "stock_price_source_substituted": False,
        "equity_dividends_and_corporate_actions_verified": False,
        "calendar_20_60_horizon_verified": False,
        "stock_and_index_total_return_bases_reconciled": False,
        "actual_executable_open_trade_confirmed": False,
        "benchmark_excess_return_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    packet["packet_sha256"] = _canonical_hash(packet)
    return packet


def validate_recovery(packet: dict[str, Any]) -> None:
    if packet.get("recovery_id") != RECOVERY_ID or packet.get("session_date_ist") != ENTRY_DAY:
        raise ValueError("not original Oct12 NSE index supplement")
    digest = packet.get("packet_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or (
        _canonical_hash({k: v for k, v in packet.items() if k != "packet_sha256"})
        != digest
    ):
        raise ValueError("official Nifty 500 source supplement hash mismatch")
    if (
        packet.get("source_state") not in SEALABLE_STATES
        and packet.get("verified_primary_or_agreed_dual_index_source") is not False
    ):
        raise ValueError("unconfirmed official index source cannot be marked verified")
    for field in (
        "external_third_party_index_values_used",
        "index_from_other_sessions_inserted",
        "stock_price_source_substituted",
        "equity_dividends_and_corporate_actions_verified",
        "calendar_20_60_horizon_verified",
        "stock_and_index_total_return_bases_reconciled",
        "actual_executable_open_trade_confirmed",
        "benchmark_excess_return_calculated",
        "return_outcomes_opened",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if packet.get(field) is not False:
            raise ValueError(f"unreviewed official index cannot authorize {field}")
