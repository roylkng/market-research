"""Twenty completed official NSE sessions of five-company *turnover*, not fills.

HG007-P035 showed one day's traded value, including DEVX's ~INR 0.61cr.
P036 fixes the 20 exchange sessions ending 2026-10-09 from an immutable
calendar and records their daily whole-market NSE UDiFF original bytes.

This is a *historical liquidity diagnostic assembled after selection*, not
an alpha test or evidence an investor could trade a specified fraction.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha_market import DailyEquityObservation, parse_udiff_eq_panel
from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.hg007_five_case_market_oct9 import EXPECTED_NAMES
from marketlab.hg007_liquidity_friction import (
    ORIGINAL_ZIP,
    PRICE_FILE,
    SOURCE_SHA,
    build_one_session_liquidity,
    load_official_oct9,
    validate_one_session_liquidity,
)
from marketlab.marketdata import udiff_url

HISTORY_ID = "HG007-P036-FIVE-CASE-TWENTY-SESSION-EXCHANGE-TURNOVER-v1"
ROOT = Path("research/hg007/twenty-session-liquidity")
CALENDAR_PATH = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json"
)
CALENDAR_GIT_BLOB = "9ac614820a67b0f7b20d8170d15b84df3c996b62"
CALENDAR_CONTENT_SHA = "2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce"
P035_FILE = Path("research/hg007/hg007-p035-five-case-liquidity-friction-v1.json")
P035_BLOB = "7f39738d0210f43965dedfe48c5c382caffa4b90"
LAST_SESSION = "2026-10-09"
FIRST_SESSION = "2026-09-10"
REQUIRED_SESSIONS = 20
PARTICIPATION_PERCENT = (1, 5)
ILLUSTRATIVE_TICKET_INR = 1_000_000


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _digest(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def _utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("source receipt captured timestamp must be string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("source timestamp invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("source timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def pinned_window_and_context(root: Path) -> tuple[list[dict], dict, dict, bytes, dict]:
    """All source/candidate identities frozen, before reading additional sessions."""
    raw_calendar = (root / CALENDAR_PATH).read_bytes()
    if _git_blob(raw_calendar) != CALENDAR_GIT_BLOB:
        raise ValueError("official calendar original Git blob changed")
    calendar = load_calendar_snapshot(root / CALENDAR_PATH)
    if calendar.sha256 != CALENDAR_CONTENT_SHA:
        raise ValueError("official calendar SHA changed")

    sessions = [
        {"date": row.session_date, "close_utc": row.close_timestamp_utc}
        for row in calendar.sessions if row.session_date <= LAST_SESSION
    ][-REQUIRED_SESSIONS:]
    if (
        len(sessions) != REQUIRED_SESSIONS
        or sessions[0]["date"] != FIRST_SESSION
        or sessions[-1]["date"] != LAST_SESSION
        or len({s["date"] for s in sessions}) != REQUIRED_SESSIONS
    ):
        raise ValueError("twenty original NSE sessions do not match frozen window")
    if any(
        date.fromisoformat(s["date"]).isoformat() != s["date"]
        for s in sessions
    ):
        raise ValueError("invalid NSE session date")

    raw_p035 = (root / P035_FILE).read_bytes()
    if _git_blob(raw_p035) != P035_BLOB:
        raise ValueError("original 9 October P035 evidence source changed")
    p035 = json.loads(raw_p035)
    validate_one_session_liquidity(p035)
    old_packet, original_oct9, old_receipts = load_official_oct9(root)
    original_p035 = build_one_session_liquidity(old_packet, original_oct9, old_receipts)
    if original_p035 != p035:
        raise ValueError("P035 cannot be reproduced from pinned official original ZIP")
    cases = p035["cases"]
    ids = {r["symbol"]: r["source_isin"] for r in cases}
    if tuple(ids) != EXPECTED_NAMES or len(ids) != 5:
        raise ValueError("five original issuer identities changed")
    if hashlib.sha256(original_oct9).hexdigest() != SOURCE_SHA:
        raise ValueError("original Oct9 official source SHA mismatch")
    provenance = {
        "official_calendar_git_blob": CALENDAR_GIT_BLOB,
        "official_calendar_content_sha256": CALENDAR_CONTENT_SHA,
        "p035_research_record_git_blob": P035_BLOB,
        "p034_market_record_path": str(PRICE_FILE),
        "oct9_original_udiff_source_path": str(ORIGINAL_ZIP),
        "oct9_original_udiff_sha256": SOURCE_SHA,
    }
    return sessions, ids, p035, original_oct9, provenance


def _receipt_path(root: Path, day: str) -> Path:
    return root / ROOT / "receipts" / f"{day}.json"


def _original_path(root: Path, sha: str) -> Path:
    return root / ROOT / "raw" / "sha256" / f"{sha}.zip"


def validated_historical_source(
    root: Path, day: str, close_utc: str
) -> tuple[bytes | None, dict[str, Any]]:
    if day == LAST_SESSION:
        raise ValueError("October 9 original has separate frozen P035 source identity")
    receipt_path = _receipt_path(root, day)
    if not receipt_path.exists():
        return None, {"date": day, "state": "ORIGINAL_SOURCE_MISSING"}
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    expected_url = udiff_url(date.fromisoformat(day))
    if (
        not isinstance(receipt, dict)
        or receipt.get("session_date") != day
        or receipt.get("original_source_url") != expected_url
        or receipt.get("http_status") != 200
        or receipt.get("state") != "ORIGINAL_NSE_EQ_ZIP_RETAINED"
        or receipt.get("source_sha256") is None
    ):
        raise ValueError(f"{day}: invalid exact official original source receipt")
    sha = receipt["source_sha256"]
    if not isinstance(sha, str) or len(sha) != 64:
        raise ValueError(f"{day}: source SHA-256 invalid")
    if _utc(receipt.get("captured_at_utc")) < _utc(close_utc):
        raise ValueError(f"{day}: source captured before exchange session completed")
    raw = _original_path(root, sha).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha or receipt.get("raw_bytes") != len(raw):
        raise ValueError(f"{day}: original exchange source ZIP bytes changed")
    return raw, {
        "date": day,
        "state": "ORIGINAL_NSE_EQ_ZIP_RETAINED",
        "source_sha256": sha,
        "captured_at_utc": receipt["captured_at_utc"],
        "source_url": expected_url,
        "raw_bytes": len(raw),
    }


def _five_bars(
    raw: bytes, day: str, expected_isins: dict[str, str]
) -> dict[str, DailyEquityObservation]:
    all_bars = parse_udiff_eq_panel(raw, session_date=date.fromisoformat(day))
    named: dict[str, DailyEquityObservation] = {}
    for bar in all_bars:
        if bar.symbol not in expected_isins:
            continue
        if bar.symbol in named:
            raise ValueError(f"{day}: multiple official EQ/ISIN rows for {bar.symbol}")
        if bar.isin != expected_isins[bar.symbol]:
            raise ValueError(f"{day}: {bar.symbol} source ISIN changed; review identity")
        if any(
            not math.isfinite(value) or value <= 0
            for value in (
                bar.volume, bar.turnover_inr, bar.trade_count,
                bar.open_price, bar.close_price, bar.high_price, bar.low_price,
            )
        ):
            raise ValueError(f"{day}: {bar.symbol} zero/nonpositive official trading fields")
        if (
            not float(bar.volume).is_integer()
            or not float(bar.trade_count).is_integer()
            or not bar.low_price <= bar.turnover_inr / bar.volume <= bar.high_price
        ):
            raise ValueError(f"{day}: {bar.symbol} invalid official traded value or trade counts")
        named[bar.symbol] = bar
    if set(named) != set(expected_isins):
        missing = sorted(set(expected_isins) - set(named))
        raise ValueError(f"{day}: original NSE EQ rows missing for {missing}")
    return named


def _nearest_rank(values: list[float], pct: int) -> float:
    if not values or not 1 <= pct <= 100:
        raise ValueError("nearest-rank liquidity quantile invalid")
    ordered = sorted(values)
    return ordered[math.ceil(len(values) * pct / 100) - 1]


def build_twenty_session_liquidity(root: Path) -> dict[str, Any]:
    sessions, ids, p035, last_raw, provenance = pinned_window_and_context(root)
    per_day = []
    missing = []
    for session in sessions:
        day = session["date"]
        try:
            if day == LAST_SESSION:
                raw = last_raw
                evidence = {
                    "date": day, "source_sha256": SOURCE_SHA,
                    "source_url": udiff_url(date.fromisoformat(day)),
                    "state": "PINNED_ORIGINAL_OCT09_ALREADY_REVIEWED",
                }
            else:
                raw, evidence = validated_historical_source(
                    root, day, session["close_utc"]
                )
                if raw is None:
                    missing.append(evidence)
                    continue
            matched = _five_bars(raw, day, ids)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            missing.append({
                "date": day, "state": "UNVERIFIED_ORIGINAL_EQUITY_SOURCE",
                "reason": f"{type(exc).__name__}: {exc}",
            })
            continue
        per_day.append({
            "session_date": day,
            "original_source": evidence,
            "five_equity_rows": [
                {
                    "symbol": symbol, "isin": bar.isin,
                    "close_inr": bar.close_price,
                    "open_inr": bar.open_price,
                    "high_inr": bar.high_price,
                    "low_inr": bar.low_price,
                    "traded_value_inr": bar.turnover_inr,
                    "traded_shares": int(bar.volume),
                    "reported_executed_trade_count": int(bar.trade_count),
                }
                for symbol, bar in matched.items()
            ],
        })
    complete = (
        len(missing) == 0
        and len(per_day) == REQUIRED_SESSIONS
        and [x["session_date"] for x in per_day] == [x["date"] for x in sessions]
    )
    cases = []
    if complete:
        for original in p035["cases"]:
            symbol = original["symbol"]
            measures = [
                next(item for item in row["five_equity_rows"] if item["symbol"] == symbol)[
                    "traded_value_inr"
                ]
                for row in per_day
            ]
            oct9_amount = measures[-1]
            if not math.isclose(
                oct9_amount / 10_000_000,
                original["single_session_traded_value_inr_crore"],
                rel_tol=0, abs_tol=1e-7,
            ):
                raise ValueError("twenty-session Oct9 day diverges from frozen P035")
            median = statistics.median(measures)
            p10 = _nearest_rank(measures, 10)
            p25 = _nearest_rank(measures, 25)
            if not 0 < p10 <= p25 <= median <= max(measures):
                raise ValueError("source liquidity quantile arithmetic invalid")
            cases.append({
                "symbol": symbol,
                "source_isin": ids[symbol],
                "session_count": REQUIRED_SESSIONS,
                "twenty_session_traded_value_median_inr_crore": median / 10_000_000,
                "twenty_session_traded_value_p10_nearest_rank_inr_crore": p10 / 10_000_000,
                "twenty_session_traded_value_p25_nearest_rank_inr_crore": p25 / 10_000_000,
                "twenty_session_traded_value_min_inr_crore": min(measures) / 10_000_000,
                "twenty_session_traded_value_max_inr_crore": max(measures) / 10_000_000,
                "oct9_day_traded_value_inr_crore": oct9_amount / 10_000_000,
                "oct9_to_trailing_20_session_median_turnover_ratio": oct9_amount / median,
                "ten_lakh_ticket_divided_by_one_pct_of_historical_median": (
                    ILLUSTRATIVE_TICKET_INR / (0.01 * median)
                ),
                "one_pct_median_quotient_predicts_execution_time": False,
                "bid_ask_and_market_depth_verified": False,
                "order_execution_or_cost_validated": False,
                "capital_allocation_authorized": False,
            })
    packet = {
        "schema_version": 1,
        "audit_id": HISTORY_ID,
        "classification": "ORIGINAL_NSE_HISTORICAL_TURNOVER_DISTRIBUTION_NOT_EXECUTABLE_LIQUIDITY",
        "source_cutoff_session": LAST_SESSION,
        "source_window_first_session": FIRST_SESSION,
        "requested_completed_exchange_sessions": REQUIRED_SESSIONS,
        "observed_complete_session_count": len(per_day),
        "source_status": (
            "COMPLETE_ORIGINAL_20_SESSION_EQUITY_EVIDENCE" if complete
            else "INCOMPLETE_ORIGINAL_HISTORICAL_MARKET_EVIDENCE"
        ),
        "missing_or_inconsistent_sessions": missing,
        "source_receipts": provenance,
        "source_session_rows": per_day if complete else [],
        "all_original_five_company_ids_preserved": list(EXPECTED_NAMES),
        "company_distribution": cases,
        "session_distribution_matured": complete,
        "historical_source_reconstructed_after_stock_case_selection": True,
        "equity_total_return_calculated": False,
        "future_daily_turnover_assumed_repeatable": False,
        "execution_days_or_fill_probability_estimated": False,
        "orderbook_bid_ask_depth_verified": False,
        "market_impact_slippage_model_verified": False,
        "research_hypothesis_or_company_ranking_changed": False,
        "investment_recommendations_created": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    packet["packet_sha256"] = _digest(packet)
    return packet


def validate_twenty_session_liquidity(packet: dict[str, Any]) -> None:
    if packet.get("audit_id") != HISTORY_ID or packet.get("source_cutoff_session") != LAST_SESSION:
        raise ValueError("unexpected historical NSE liquidity-window contract")
    expected_hash = packet.get("packet_sha256")
    if not isinstance(expected_hash, str) or expected_hash != _digest(
        {k: v for k, v in packet.items() if k != "packet_sha256"}
    ):
        raise ValueError("twenty-session research packet content was altered")
    count = packet.get("observed_complete_session_count")
    status = packet.get("source_status")
    if (
        type(count) is not int
        or not 0 <= count <= REQUIRED_SESSIONS
        or status not in {
            "COMPLETE_ORIGINAL_20_SESSION_EQUITY_EVIDENCE",
            "INCOMPLETE_ORIGINAL_HISTORICAL_MARKET_EVIDENCE",
        }
    ):
        raise ValueError("historical source count/status inconsistent")
    completed = status == "COMPLETE_ORIGINAL_20_SESSION_EQUITY_EVIDENCE"
    if completed != (count == REQUIRED_SESSIONS):
        raise ValueError("historical liquidity source completeness misrepresented")
    if not completed and (
        packet.get("session_distribution_matured") is not False
        or packet.get("company_distribution") != []
        or packet.get("source_session_rows") != []
    ):
        raise ValueError("incomplete original source may not publish partial medians")
    if completed and (
        len(packet.get("company_distribution", [])) != len(EXPECTED_NAMES)
        or len(packet.get("source_session_rows", [])) != REQUIRED_SESSIONS
    ):
        raise ValueError("complete historical source lost issuer/day accounting")
    for flag in (
        "equity_total_return_calculated", "future_daily_turnover_assumed_repeatable",
        "execution_days_or_fill_probability_estimated", "orderbook_bid_ask_depth_verified",
        "market_impact_slippage_model_verified", "research_hypothesis_or_company_ranking_changed",
        "investment_recommendations_created", "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if packet.get(flag) is not False:
            raise ValueError(f"historical liquidity cannot authorize {flag}")
