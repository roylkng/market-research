"""HG009 P002: source-linked NSE EQ daily observations for all 300 frozen identities.

Reuse ORIGINAL whole-market UDiFF and Nifty500 source bytes already anchored
by independent H021. A source-missing or non-EQ case remains missing. This is
not a trade, return, adjusted price series, or posthoc stock selection.
"""

from __future__ import annotations

import copy
import hashlib
import math
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_market import parse_udiff_eq_panel
from marketlab.calendar_snapshot import CalendarSnapshot
from marketlab.h021_daily_prices import official_market_transport_ready
from marketlab.hg009_100 import validate_hg009_100
from marketlab.hg009_controls import verify_hg009_controls
from marketlab.marketdata import parse_index_snapshot

RECORD_ID = "HG009-P002-300-FROZEN-NSE-OFFICIAL-EQ-DAILY-v1"
FIRST_SESSION = "2026-10-15"
ORIGINAL_2026_CALENDAR_SHA = (
    "2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce"
)
HG009_SELECTED_SHA = (
    "e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5"
)
HG009_CONTROL_SHA = (
    "8c8d9781adf7900addd28a1a60f1cfb33bed9a1e4985e6c410a010d2c819eef8"
)
ARMS = ("SELECTED", "ONE_LANE", "ZERO_LANE")
H021_SOURCE_DIR = Path("research/prospective/h021/daily-prices")
MISSING = frozenset({
    "MISSING_EQ_IDENTITY_NO_SUBSTITUTION",
    "SYMBOL_CHANGED_REQUIRES_ORIGINAL_ACTION",
    "ISIN_CHANGED_REQUIRES_ORIGINAL_ACTION",
    "MULTIPLE_EQ_ROWS_FAIL_CLOSED",
})


def _utc(value: object, *, label: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise AlphaContractError(f"HG009 P002 invalid timestamp: {label}") from exc
    if stamp.tzinfo is None:
        raise AlphaContractError(f"HG009 P002 missing UTC offset: {label}")
    return stamp.astimezone(UTC)


def _source_path(source_sha: str, *, suffix: str) -> str:
    if (
        not isinstance(source_sha, str)
        or len(source_sha) != 64
        or any(char not in "0123456789abcdef" for char in source_sha)
    ):
        raise AlphaContractError("HG009 P002 invalid original NSE SHA")
    return str(H021_SOURCE_DIR / "raw" / "sha256" / f"{source_sha}{suffix}")


def _observed_company(
    *,
    arm: str,
    symbol: str,
    isin: str,
    by_symbol: dict[str, list[Any]],
    by_isin: dict[str, list[Any]],
    raw_sha: str,
) -> dict[str, Any]:
    source_rows = by_symbol.get(symbol, [])
    matched = [
        bar for bar in source_rows if bar.isin == isin
    ]
    status: str
    evidence = None
    if len(source_rows) > 1 or len(matched) > 1:
        status = "MULTIPLE_EQ_ROWS_FAIL_CLOSED"
    elif len(matched) == 1:
        bar = matched[0]
        if (
            not all(
                math.isfinite(v) and v > 0
                for v in (
                    bar.open_price,
                    bar.high_price,
                    bar.low_price,
                    bar.close_price,
                )
            )
            or bar.low_price > min(bar.open_price, bar.close_price)
            or bar.high_price < max(bar.open_price, bar.close_price)
        ):
            raise AlphaContractError(
                f"HG009 P002 inconsistent official EQ OHLC {symbol}"
            )
        status = "ORIGINAL_NSE_EQ_OHLC_OBSERVED_NOT_FILL"
        evidence = {
            "open_inr": bar.open_price,
            "high_inr": bar.high_price,
            "low_inr": bar.low_price,
            "close_inr": bar.close_price,
            "traded_value_inr": bar.turnover_inr,
            "traded_volume": bar.volume,
            "trade_count": bar.trade_count,
        }
    elif source_rows:
        status = "ISIN_CHANGED_REQUIRES_ORIGINAL_ACTION"
    elif by_isin.get(isin):
        status = "SYMBOL_CHANGED_REQUIRES_ORIGINAL_ACTION"
    else:
        status = "MISSING_EQ_IDENTITY_NO_SUBSTITUTION"
    return {
        "arm": arm,
        "symbol": symbol,
        "frozen_isin": isin,
        "exchange_series": "EQ",
        "source_original_udiff_sha256": raw_sha,
        "state": status,
        "ohlcv": evidence,
        "corporate_action_adjusted": False,
        "dividend_adjusted": False,
        "actual_trade_fill": False,
        "current_order_capacity_verified": False,
    }


def build_hg009_daily_source_observation(
    *,
    h021_observation: dict[str, Any],
    original_udiff_zip: bytes,
    original_index_csv: bytes,
    selected_manifest: dict[str, Any],
    controls_manifest: dict[str, Any],
    original_router: dict[str, Any],
    calendar: CalendarSnapshot,
    recorded_at_utc: str,
) -> dict[str, Any]:
    """Replay original market bytes for 300 frozen NSE symbol+ISIN identities."""
    validate_hg009_100(selected_manifest, source=original_router)
    verify_hg009_controls(
        controls_manifest,
        source=original_router,
        selected=selected_manifest,
    )
    if (
        calendar.sha256 != ORIGINAL_2026_CALENDAR_SHA
        or selected_manifest.get("cohort_sha256") != HG009_SELECTED_SHA
        or controls_manifest.get("manifest_sha256") != HG009_CONTROL_SHA
        or not official_market_transport_ready(h021_observation)
    ):
        raise AlphaContractError("HG009 P002 frozen source or transport invalid")
    day_text = h021_observation.get("session_date_ist")
    if not isinstance(day_text, str) or day_text < FIRST_SESSION:
        raise AlphaContractError("HG009 P002 cannot observe pre-freeze sessions")
    matching_sessions = [
        s for s in calendar.sessions if s.session_date == day_text
    ]
    if len(matching_sessions) != 1:
        raise AlphaContractError("HG009 P002 missing exact frozen NSE trading date")
    session = matching_sessions[0]
    recorded = _utc(recorded_at_utc, label="source-derived record")
    exchange_close = _utc(session.close_timestamp_utc, label="market close")
    sources = (
        ("stock_source", original_udiff_zip, ".zip"),
        ("index_source", original_index_csv, ".csv"),
    )
    for name, raw, _ in sources:
        receipt = h021_observation[name]
        captured = _utc(receipt["captured_at_utc"], label=f"{name} capture")
        if captured < exchange_close or recorded < captured:
            raise AlphaContractError(
                "HG009 P002 future/post-source timestamp chronology violated"
            )
        if (
            hashlib.sha256(raw).hexdigest() != receipt["sha256"]
            or len(raw) != receipt["byte_count"]
        ):
            raise AlphaContractError(
                f"HG009 P002 {name} original NSE source bytes changed"
            )
    if recorded < _utc(
        h021_observation["recorded_at_utc"], label="H021 source recorded"
    ):
        raise AlphaContractError("HG009 P002 derived observation predates source")

    day = date.fromisoformat(day_text)
    original_eq = parse_udiff_eq_panel(
        original_udiff_zip, session_date=day
    )
    if len(original_eq) < 300:
        # A full NSE CM market archive typically has thousands of EQ rows.
        # A tiny fabricated subset must not pass as official whole-market data.
        raise AlphaContractError("HG009 P002 original full-market NSE EQ rows missing")
    index = parse_index_snapshot(
        original_index_csv, benchmark_id="nifty_500", session_date=day
    )
    h021_index = h021_observation["benchmark"]
    if (
        index.benchmark_id != "nifty_500"
        or index.session_date != day_text
        or index.open_price != h021_index["open"]
        or index.close_price != h021_index["close"]
    ):
        raise AlphaContractError("HG009 P002 independent Nifty500 price source differs")

    by_symbol: dict[str, list[Any]] = {}
    by_isin: dict[str, list[Any]] = {}
    for bar in original_eq:
        by_symbol.setdefault(bar.symbol, []).append(bar)
        by_isin.setdefault(bar.isin, []).append(bar)

    arms = {
        "SELECTED": selected_manifest["selected"],
        "ONE_LANE": controls_manifest["controls"]["ONE_LANE"],
        "ZERO_LANE": controls_manifest["controls"]["ZERO_LANE"],
    }
    rows = []
    coverage = {}
    for arm in ARMS:
        group = arms[arm]
        if len(group) != 100:
            raise AlphaContractError("HG009 P002 frozen group not 100 identities")
        observed = []
        for item in group:
            record = _observed_company(
                arm=arm,
                symbol=item["symbol"],
                isin=item.get("isin", item.get("frozen_isin")),
                by_symbol=by_symbol,
                by_isin=by_isin,
                raw_sha=h021_observation["stock_source"]["sha256"],
            )
            observed.append(record)
        observed.sort(key=lambda x: (x["symbol"], x["frozen_isin"]))
        counts = Counter(x["state"] for x in observed)
        coverage[arm] = {
            "declared": 100,
            "observed_official_eq": counts.get(
                "ORIGINAL_NSE_EQ_OHLC_OBSERVED_NOT_FILL", 0
            ),
            "missing_or_changed_identity": sum(
                value for key, value in counts.items() if key in MISSING
            ),
            "state_counts": dict(sorted(counts.items())),
        }
        rows.extend(observed)
    if (
        len(rows) != 300
        or len({(x["symbol"], x["frozen_isin"]) for x in rows}) != 300
        or any(
            record["actual_trade_fill"] is not False
            for record in rows
        )
    ):
        raise AlphaContractError("HG009 P002 frozen market identity collision")

    packet: dict[str, Any] = {
        "schema_version": 1,
        "record_id": RECORD_ID,
        "classification": (
            "ORIGINAL_NSE_EQ_DAILY_OBSERVATION_NOT_PREDICTION_OR_PNL"
        ),
        "date_ist": day_text,
        "observed_recorded_at_utc": recorded.isoformat(),
        "calendar_sha256": calendar.sha256,
        "exchange_session_close_utc": exchange_close.isoformat(),
        "first_declared_entry_market_session": FIRST_SESSION,
        "selected_manifest_sha256": HG009_SELECTED_SHA,
        "controls_manifest_sha256": HG009_CONTROL_SHA,
        "h021_original_daily_packet_sha256": h021_observation["packet_sha256"],
        "h021_original_daily_packet_path": str(
            H021_SOURCE_DIR / f"{day_text}-v1.json"
        ),
        "original_market_source_sha256": h021_observation[
            "stock_source"
        ]["sha256"],
        "original_index_source_sha256": h021_observation[
            "index_source"
        ]["sha256"],
        "original_market_raw_path": _source_path(
            h021_observation["stock_source"]["sha256"], suffix=".zip"
        ),
        "original_index_raw_path": _source_path(
            h021_observation["index_source"]["sha256"], suffix=".csv"
        ),
        "original_source_market_captured_at_utc": h021_observation[
            "stock_source"
        ]["captured_at_utc"],
        "original_source_index_captured_at_utc": h021_observation[
            "index_source"
        ]["captured_at_utc"],
        "benchmark": {
            "id": "nifty_500",
            "basis": "PRICE_INDEX_NOT_TOTAL_RETURN",
            "open": index.open_price,
            "close": index.close_price,
            "source_sha256": h021_observation["index_source"]["sha256"],
        },
        "original_EQ_market_universe_row_count": len(original_eq),
        "arm_coverage": coverage,
        "source_identity_rows": rows,
        "source_complete_for_all_300": all(
            x["observed_official_eq"] == 100 for x in coverage.values()
        ),
        "unresolved_special_calendar_sessions_to_date": [
            value for value in calendar.unresolved_special_dates
            if FIRST_SESSION <= value <= day_text
        ],
        "no_future_prices_used_in_cohort_selection": True,
        "no_backdated_market_source_timestamps": True,
        "market_data_is_not_executable_fill_or_order_capacity": True,
        "corporate_actions_resolved": False,
        "dividends_adjusted": False,
        "gross_holding_period_returns_calculated": False,
        "benchmark_excess_returns_calculated": False,
        "live_capital_allowed": False,
        "portfolio_eligibility_allowed": False,
    }
    packet["packet_sha256"] = digest(packet)
    return packet


def validate_hg009_daily_snapshot(packet: dict[str, Any]) -> None:
    if packet.get("record_id") != RECORD_ID:
        raise AlphaContractError("HG009 P002 wrong source record ID")
    unsigned = copy.deepcopy(packet)
    sha = unsigned.pop("packet_sha256", None)
    if sha != digest(unsigned):
        raise AlphaContractError("HG009 P002 tampered source packet SHA")
    if (
        packet.get("selected_manifest_sha256") != HG009_SELECTED_SHA
        or packet.get("controls_manifest_sha256") != HG009_CONTROL_SHA
        or packet.get("date_ist", "") < FIRST_SESSION
        or len(packet.get("source_identity_rows", [])) != 300
    ):
        raise AlphaContractError("HG009 P002 invalid frozen cohort/date/cardinality")
    for name in (
        "corporate_actions_resolved",
        "dividends_adjusted",
        "gross_holding_period_returns_calculated",
        "benchmark_excess_returns_calculated",
        "live_capital_allowed",
        "portfolio_eligibility_allowed",
    ):
        if packet.get(name) is not False:
            raise AlphaContractError(f"HG009 P002 may not authorize {name}")
    if sum(
        item["observed_official_eq"]
        for item in packet["arm_coverage"].values()
    ) > 300:
        raise AlphaContractError("HG009 P002 impossible source coverage")
    ids = [
        (item["symbol"], item["frozen_isin"])
        for item in packet["source_identity_rows"]
    ]
    if len(set(ids)) != 300:
        raise AlphaContractError("HG009 P002 duplicate original cohort identity")
    for item in packet["source_identity_rows"]:
        if (
            item["actual_trade_fill"] is not False
            or item["corporate_action_adjusted"] is not False
            or item["dividend_adjusted"] is not False
            or item["current_order_capacity_verified"] is not False
        ):
            raise AlphaContractError("HG009 P002 cannot invent adjustments or trades")
