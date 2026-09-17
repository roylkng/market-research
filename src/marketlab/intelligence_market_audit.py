"""Post-close broad-market audit for the company-intelligence v2 research engine.

This module deliberately evaluates *coverage*, not trading skill. The official NSE
EQ bhavcopy is the denominator. News that was public before a move is kept separate
from news that MarketLab had actually observed before the move, so a post-close
backfill cannot be counted as a prospective hit.
"""
from __future__ import annotations

import csv
import io
import math
import zipfile
from collections import Counter
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from marketlab.intelligence_core import EvidenceError
from marketlab.intelligence_store import ResearchStore, digest, sha256, timestamp
from marketlab.marketdata import udiff_url

IST = ZoneInfo("Asia/Kolkata")
OPEN_TIME = time(9, 15)
CLOSE_TIME = time(15, 30)
DEFAULT_LIQUIDITY_FLOOR_INR = 20_000_000.0
DEFAULT_MOVE_THRESHOLD_PCT = 5.0
DEFAULT_TOP_ABS_MOVERS = 25


class MarketAuditError(EvidenceError):
    """Raised when official market evidence cannot be interpreted without guessing."""


def _finite_number(value: object, field: str, *, positive: bool = False) -> float:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise MarketAuditError(f"invalid {field}: {value}") from exc
    if not math.isfinite(number) or (positive and number <= 0):
        raise MarketAuditError(f"invalid {field}: {value}")
    return number


def _read_udiff_rows(raw_zip: bytes, session_date: date) -> list[dict]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            names = archive.namelist()
            if len(names) != 1 or not names[0].lower().endswith(".csv"):
                raise MarketAuditError("UDiFF archive must contain exactly one CSV")
            raw_csv = archive.read(names[0])
    except (zipfile.BadZipFile, KeyError) as exc:
        raise MarketAuditError(f"invalid UDiFF archive: {exc}") from exc
    try:
        reader = csv.DictReader(io.StringIO(raw_csv.decode("utf-8-sig")))
    except UnicodeDecodeError as exc:
        raise MarketAuditError("UDiFF CSV is not UTF-8") from exc
    required = {
        "TradDt",
        "Sgmt",
        "Src",
        "FinInstrmTp",
        "ISIN",
        "TckrSymb",
        "SctySrs",
        "OpnPric",
        "ClsPric",
        "PrvsClsgPric",
        "TtlTradgVol",
        "TtlTrfVal",
    }
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise MarketAuditError("UDiFF header lacks the market-audit contract")
    wanted_day = session_date.isoformat()
    parsed: list[dict] = []
    symbols: set[str] = set()
    for row in reader:
        if (
            str(row.get("TradDt") or "").strip() != wanted_day
            or str(row.get("Sgmt") or "").strip().upper() != "CM"
            or str(row.get("Src") or "").strip().upper() != "NSE"
            or str(row.get("FinInstrmTp") or "").strip().upper() != "STK"
            or str(row.get("SctySrs") or "").strip().upper() != "EQ"
        ):
            continue
        symbol = str(row.get("TckrSymb") or "").strip().upper()
        isin = str(row.get("ISIN") or "").strip()
        if not symbol or not isin:
            raise MarketAuditError("EQ row lacks symbol or ISIN")
        if symbol in symbols:
            raise MarketAuditError(f"duplicate EQ symbol in UDiFF: {symbol}")
        symbols.add(symbol)
        open_price = _finite_number(row.get("OpnPric"), "open price", positive=True)
        close_price = _finite_number(row.get("ClsPric"), "close price", positive=True)
        previous_close = _finite_number(row.get("PrvsClsgPric"), "previous close", positive=True)
        volume = _finite_number(row.get("TtlTradgVol"), "traded volume")
        turnover = _finite_number(row.get("TtlTrfVal"), "traded value")
        if volume < 0 or turnover < 0:
            raise MarketAuditError("UDiFF volume and traded value cannot be negative")
        parsed.append(
            {
                "symbol": symbol,
                "isin": isin,
                "open": open_price,
                "close": close_price,
                "previous_close": previous_close,
                "volume": volume,
                "turnover_inr": turnover,
                "close_return_pct": 100.0 * (close_price / previous_close - 1.0),
                "open_gap_pct": 100.0 * (open_price / previous_close - 1.0),
                "open_to_close_pct": 100.0 * (close_price / open_price - 1.0),
            }
        )
    if not parsed:
        raise MarketAuditError(f"no NSE EQ rows for {wanted_day}")
    return sorted(parsed, key=lambda row: row["symbol"])


def _session_boundaries(session_date: date) -> tuple[datetime, datetime]:
    open_at = datetime.combine(session_date, OPEN_TIME, IST).astimezone(UTC)
    close_at = datetime.combine(session_date, CLOSE_TIME, IST).astimezone(UTC)
    return open_at, close_at


def _timing(value: str | None, open_at: datetime, close_at: datetime) -> str:
    if not value:
        return "UNRESOLVED"
    observed = timestamp(value).astimezone(UTC)
    if observed <= open_at:
        return "PRE_OPEN"
    if observed <= close_at:
        return "INTRADAY"
    return "POST_CLOSE"


def _publication_value(item: dict) -> str | None:
    publication = item.get("publication")
    if not isinstance(publication, dict):
        return None
    return publication.get("value")


def _symbol_matches(item: dict, symbol: str) -> bool:
    mentions = item.get("mentions") or {}
    for key in ("panel_symbols", "unverified_nse_symbols"):
        if symbol in (mentions.get(key) or []):
            return True
    return False


def _news_audit_for_symbol(
    symbol: str,
    items: list[dict],
    *,
    open_at: datetime,
    close_at: datetime,
) -> dict:
    matched = [item for item in items if _symbol_matches(item, symbol)]
    if not matched:
        return {
            "coverage_class": "NOT_DISCOVERED",
            "matched_item_ids": [],
            "earliest_publication_at": None,
            "earliest_system_seen_at": None,
            "public_timing": "UNRESOLVED",
            "system_timing": "UNRESOLVED",
            "topic_cues": [],
        }
    public_values = [value for item in matched if (value := _publication_value(item))]
    seen_values = [item.get("first_seen_at") for item in matched if item.get("first_seen_at")]
    earliest_public = min(public_values, key=timestamp) if public_values else None
    earliest_seen = min(seen_values, key=timestamp) if seen_values else None
    public_timing = _timing(earliest_public, open_at, close_at)
    system_timing = _timing(earliest_seen, open_at, close_at)
    if system_timing == "PRE_OPEN":
        coverage_class = "SYSTEM_PREOPEN_HIT"
    elif system_timing == "INTRADAY":
        coverage_class = "SYSTEM_INTRADAY_HIT"
    elif public_timing == "PRE_OPEN":
        coverage_class = "PUBLIC_PREOPEN_NOT_OBSERVED_IN_TIME"
    elif public_timing == "INTRADAY":
        coverage_class = "PUBLIC_INTRADAY_NOT_OBSERVED_IN_TIME"
    elif public_timing == "POST_CLOSE":
        coverage_class = "POST_CLOSE_DISCOVERY"
    else:
        coverage_class = "DISCOVERED_TIME_UNRESOLVED"
    topics = sorted(
        {
            topic.get("topic")
            for item in matched
            for topic in (item.get("topics") or [])
            if isinstance(topic, dict) and topic.get("topic")
        }
    )
    return {
        "coverage_class": coverage_class,
        "matched_item_ids": sorted(item["item_id"] for item in matched),
        "earliest_publication_at": earliest_public,
        "earliest_system_seen_at": earliest_seen,
        "public_timing": public_timing,
        "system_timing": system_timing,
        "topic_cues": topics,
    }


def build_market_audit(
    raw_udiff: bytes,
    *,
    session_date: date,
    store: ResearchStore,
    captured_at: str,
    liquidity_floor_inr: float = DEFAULT_LIQUIDITY_FLOOR_INR,
    move_threshold_pct: float = DEFAULT_MOVE_THRESHOLD_PCT,
    top_abs_movers: int = DEFAULT_TOP_ABS_MOVERS,
) -> dict:
    """Build a diagnostic mover audit from official NSE data and prospective news state."""
    timestamp(captured_at)
    if liquidity_floor_inr < 0 or move_threshold_pct <= 0:
        raise MarketAuditError("invalid audit thresholds")
    if type(top_abs_movers) is not int or not 1 <= top_abs_movers <= 100:
        raise MarketAuditError("top_abs_movers must be an integer in [1, 100]")
    rows = _read_udiff_rows(raw_udiff, session_date)
    liquid = [row for row in rows if row["turnover_inr"] >= liquidity_floor_inr]
    ranked = sorted(liquid, key=lambda row: (-abs(row["close_return_pct"]), row["symbol"]))
    threshold_symbols = {
        row["symbol"] for row in liquid if abs(row["close_return_pct"]) >= move_threshold_pct
    }
    top_symbols = {row["symbol"] for row in ranked[:top_abs_movers]}
    audit_symbols = threshold_symbols | top_symbols
    items = [
        row
        for row in store.records("news_item")
        if row.get("processed_at") and timestamp(row["processed_at"]) <= timestamp(captured_at)
    ]
    panel_symbols = {
        member["symbol"]
        for panel in store.records("panel")
        for member in panel.get("members", [])
    }
    open_at, close_at = _session_boundaries(session_date)
    movers = []
    for row in ranked:
        if row["symbol"] not in audit_symbols:
            continue
        news = _news_audit_for_symbol(
            row["symbol"], items, open_at=open_at, close_at=close_at
        )
        movers.append(
            {
                **row,
                "in_deep_panel": row["symbol"] in panel_symbols,
                "audit_reasons": sorted(
                    reason
                    for reason, condition in (
                        ("ABS_MOVE_THRESHOLD", row["symbol"] in threshold_symbols),
                        ("TOP_ABS_MOVER", row["symbol"] in top_symbols),
                    )
                    if condition
                ),
                "news_audit": news,
                "diagnostic_only": True,
            }
        )
    classes = Counter(row["news_audit"]["coverage_class"] for row in movers)
    advancing = sum(row["close_return_pct"] > 0 for row in liquid)
    declining = sum(row["close_return_pct"] < 0 for row in liquid)
    unchanged = len(liquid) - advancing - declining
    threshold_count = len(threshold_symbols)
    report = {
        "schema_version": 1,
        "engine": "MARKETLAB_V2_DAILY_MOVER_MISS_AUDIT",
        "session_date": session_date.isoformat(),
        "captured_at": captured_at,
        "market_source": {
            "url": udiff_url(session_date),
            "raw_sha256": sha256(raw_udiff),
            "source_kind": "OFFICIAL_NSE_UDIFF_EQ_BHAVCOPY",
        },
        "parameters": {
            "liquidity_floor_inr": liquidity_floor_inr,
            "move_threshold_pct": move_threshold_pct,
            "top_abs_movers": top_abs_movers,
        },
        "universe": {
            "eq_count": len(rows),
            "liquid_eq_count": len(liquid),
            "advancing": advancing,
            "declining": declining,
            "unchanged": unchanged,
            "threshold_mover_count": threshold_count,
            "audited_mover_count": len(movers),
        },
        "coverage_class_counts": dict(sorted(classes.items())),
        "movers": movers,
        "interpretation_contract": {
            "SYSTEM_PREOPEN_HIT": "MarketLab observed a linked item no later than 09:15 IST.",
            "SYSTEM_INTRADAY_HIT": "MarketLab first observed a linked item after open but by close.",
            "PUBLIC_PREOPEN_NOT_OBSERVED_IN_TIME": (
                "A linked item appears publicly timestamped pre-open, but MarketLab first saw it later."
            ),
            "PUBLIC_INTRADAY_NOT_OBSERVED_IN_TIME": (
                "A linked item appears publicly timestamped intraday, but MarketLab first saw it later."
            ),
            "NOT_DISCOVERED": "No current news item linked to the NSE symbol in retained state.",
        },
        "research_use": "COVERAGE_AND_MISS_DIAGNOSTIC_NOT_A_TRADING_SIGNAL",
        "forecast": None,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
