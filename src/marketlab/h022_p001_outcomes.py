from __future__ import annotations

import copy
import math
from collections import Counter
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.h022_outcomes import (
    HORIZONS,
    MIN_COMPLETE_SHARE,
    MIN_PRIMARY_OBSERVATIONS,
    PRIMARY_HORIZON,
    ROUND_TRIP_COST_PP,
    HistoricalSession,
    blocked_actions,
    classify_primary,
    evaluate_horizon,
    first_entry_session,
    horizon_session,
)
from marketlab.h022_p001_acquisition import canonical_hash, capture_latency_status
from marketlab.h022_prospective import validate_signal_ledger, validate_signal_record
from marketlab.h022_p001_stream import validate_stream_consistency

IST = ZoneInfo("Asia/Kolkata")
OUTCOME_CONTRACT_ID = "H022-P001-OUTCOMES-V1"
EXECUTION_RULE_ID = "H022-X001"
BENCHMARK_ID = "NIFTY500"
PENDING_STATUSES = frozenset(
    {
        "NOT_MATURE",
        "CALENDAR_COVERAGE_INSUFFICIENT",
        "CALENDAR_UNRESOLVED_SPECIAL_SESSION",
    }
)


class H022P001OutcomeError(ValueError):
    """Raised when prospective P001 outcomes cannot be evaluated without guessing."""


def _timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise H022P001OutcomeError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H022P001OutcomeError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _iso_date(value: object, *, field: str) -> date:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be ISO YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise H022P001OutcomeError(f"invalid {field}: {value}") from exc
    if parsed.isoformat() != value:
        raise H022P001OutcomeError(f"{field} must be canonical ISO YYYY-MM-DD")
    return parsed


def _positive_number(value: object, *, field: str) -> float:
    if isinstance(value, bool):
        raise H022P001OutcomeError(f"{field} must be a positive finite number")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise H022P001OutcomeError(f"invalid {field}: {value}") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise H022P001OutcomeError(f"{field} must be a positive finite number")
    return parsed


def _finite_number(value: object, *, field: str) -> float:
    if isinstance(value, bool):
        raise H022P001OutcomeError(f"{field} must be finite numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise H022P001OutcomeError(f"invalid {field}: {value}") from exc
    if not math.isfinite(parsed):
        raise H022P001OutcomeError(f"{field} must be finite numeric")
    return parsed


def load_reviewed_sessions(
    calendar: dict[str, Any],
) -> tuple[tuple[HistoricalSession, ...], tuple[date, ...]]:
    if not isinstance(calendar, dict):
        raise TypeError("NSE calendar must be an object")
    start = _iso_date(calendar.get("start_date"), field="calendar.start_date")
    end = _iso_date(calendar.get("end_date"), field="calendar.end_date")
    if start > end:
        raise H022P001OutcomeError("calendar start date exceeds end date")
    raw_sessions = calendar.get("sessions")
    if not isinstance(raw_sessions, list) or not raw_sessions:
        raise H022P001OutcomeError("calendar sessions must be a non-empty list")
    sessions: list[HistoricalSession] = []
    seen_dates: set[str] = set()
    prior_open: datetime | None = None
    for index, row in enumerate(raw_sessions):
        if not isinstance(row, dict):
            raise TypeError(f"calendar session[{index}] must be an object")
        session_date = _iso_date(row.get("session_date"), field=f"session[{index}].date")
        opened = _timestamp(row.get("open_timestamp_utc"), field=f"session[{index}].open")
        closed = _timestamp(row.get("close_timestamp_utc"), field=f"session[{index}].close")
        if not start <= session_date <= end:
            raise H022P001OutcomeError(f"session {session_date} outside calendar coverage")
        if opened >= closed:
            raise H022P001OutcomeError(f"session {session_date} open is not before close")
        if opened.astimezone(IST).date() != session_date or closed.astimezone(IST).date() != session_date:
            raise H022P001OutcomeError(f"session {session_date} timestamps do not map to India date")
        if session_date.isoformat() in seen_dates:
            raise H022P001OutcomeError(f"duplicate calendar session date: {session_date}")
        if prior_open is not None and opened <= prior_open:
            raise H022P001OutcomeError("calendar sessions are not strictly chronological")
        seen_dates.add(session_date.isoformat())
        prior_open = opened
        sessions.append(
            HistoricalSession(
                session_date=session_date.isoformat(),
                open_timestamp_utc=opened.isoformat().replace("+00:00", "Z"),
                close_timestamp_utc=closed.isoformat().replace("+00:00", "Z"),
                special=bool(row.get("special", False)),
            )
        )
    unresolved_raw = calendar.get("unresolved_special_dates", [])
    if not isinstance(unresolved_raw, list):
        raise H022P001OutcomeError("calendar unresolved_special_dates must be a list")
    unresolved = tuple(
        sorted(
            {
                _iso_date(value, field="calendar.unresolved_special_date")
                for value in unresolved_raw
            }
        )
    )
    return tuple(sessions), unresolved


def _unresolved_between(
    unresolved: tuple[date, ...],
    *,
    start_date: date,
    end_date: date,
) -> tuple[str, ...]:
    if end_date < start_date:
        return ()
    return tuple(
        item.isoformat() for item in unresolved if start_date <= item <= end_date
    )


def _gross_return_pct(entry: float, exit_value: float) -> float:
    result = (exit_value / entry - 1.0) * 100.0
    if not math.isfinite(result):
        raise H022P001OutcomeError("computed return is non-finite")
    return result


def _validate_stock_bar(
    bar: dict[str, Any],
    *,
    symbol: str,
    expected_isin: str,
    series: str,
    session_date: str,
) -> tuple[float, float]:
    if not isinstance(bar, dict):
        raise TypeError("stock bar must be an object")
    if bar.get("session_date") != session_date:
        raise H022P001OutcomeError(f"{symbol}: stock bar session mismatch")
    if str(bar.get("symbol_requested") or "").strip().upper() != symbol:
        raise H022P001OutcomeError(f"{symbol}: stock bar requested symbol mismatch")
    if str(bar.get("isin_requested") or "").strip() != expected_isin:
        raise H022P001OutcomeError(f"{symbol}: stock bar requested ISIN mismatch")
    if str(bar.get("series") or "").strip().upper() != series:
        raise H022P001OutcomeError(f"{symbol}: stock bar series mismatch")
    identity_mode = bar.get("identity_mode")
    if identity_mode not in {"EXACT_CURRENT_U001_ISIN", "CURRENT_SYMBOL_EQ_FALLBACK"}:
        raise H022P001OutcomeError(f"{symbol}: unsupported stock-bar identity mode")
    source_url = str(bar.get("source_url") or "")
    if not source_url.startswith("https://"):
        raise H022P001OutcomeError(f"{symbol}: stock bar source URL is not HTTPS")
    return (
        _positive_number(bar.get("open"), field=f"{symbol}.stock_open"),
        _positive_number(bar.get("close"), field=f"{symbol}.stock_close"),
    )


def _validate_benchmark_bar(
    bar: dict[str, Any], *, session_date: str
) -> tuple[float, float]:
    if not isinstance(bar, dict):
        raise TypeError("benchmark bar must be an object")
    observed_date = bar.get("session_date") or bar.get("date")
    if observed_date != session_date:
        raise H022P001OutcomeError("Nifty 500 bar session mismatch")
    source_url = str(bar.get("source_url") or "")
    if not source_url.startswith("https://"):
        raise H022P001OutcomeError("Nifty 500 bar source URL is not HTTPS")
    return (
        _positive_number(bar.get("open"), field="nifty500.open"),
        _positive_number(bar.get("close"), field="nifty500.close"),
    )


def _member_map(universe_snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    members = universe_snapshot.get("members")
    if not isinstance(members, list) or len(members) != 100:
        raise H022P001OutcomeError("prospective H022 outcomes require frozen 100-name U001")
    result: dict[str, dict[str, Any]] = {}
    for row in members:
        if not isinstance(row, dict):
            raise TypeError("U001 member must be an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        isin = str(row.get("isin") or "").strip()
        series = str(row.get("series") or "EQ").strip().upper()
        if not symbol or not isin or not series or symbol in result:
            raise H022P001OutcomeError(f"invalid/duplicate U001 member: {symbol}")
        result[symbol] = {"symbol": symbol, "isin": isin, "series": series}
    return result


def build_prospective_outcome_report(
    signal_ledger: dict[str, Any],
    *,
    universe_snapshot: dict[str, Any],
    calendar: dict[str, Any],
    market_data_cutoff_session: str,
    stock_bars: dict[tuple[str, str], dict[str, Any] | None],
    benchmark_bars: dict[str, dict[str, Any] | None],
    corporate_actions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    validate_signal_ledger(signal_ledger)
    members = _member_map(universe_snapshot)
    sessions, unresolved_special_dates = load_reviewed_sessions(calendar)
    cutoff = _iso_date(market_data_cutoff_session, field="market_data_cutoff_session")
    if cutoff > date.today():
        raise H022P001OutcomeError("market-data cutoff cannot be in the future")
    calendar_end = _iso_date(calendar.get("end_date"), field="calendar.end_date")
    if cutoff > calendar_end:
        raise H022P001OutcomeError("market-data cutoff exceeds reviewed calendar coverage")

    signal_records = [
        row for row in signal_ledger["records"] if row.get("signal_status") == "SIGNAL"
    ]
    records: list[dict[str, Any]] = []
    for signal in signal_records:
        validate_signal_record(signal)
        symbol = str(signal["symbol"]).strip().upper()
        member = members.get(symbol)
        if member is None:
            raise H022P001OutcomeError(f"signal symbol is outside frozen U001: {symbol}")
        primary_signal = _finite_number(signal.get("primary_signal"), field="primary_signal")
        publication = _timestamp(
            signal.get("exchange_published_at_utc"), field="exchange_published_at_utc"
        )
        entry_result = first_entry_session(str(signal["exchange_published_at_utc"]), sessions)
        row: dict[str, Any] = {
            "source_id": signal["source_id"],
            "source_record_id": signal["source_record_id"],
            "symbol": symbol,
            "exchange_published_at_utc": signal["exchange_published_at_utc"],
            "signal_frozen_at_utc": signal["signal_frozen_at_utc"],
            "primary_signal": primary_signal,
            "execution_status": None,
            "entry_session": None,
            "entry_stock_bar": None,
            "entry_benchmark_bar": None,
            "horizons": {},
        }
        if entry_result is None:
            row["execution_status"] = "CALENDAR_COVERAGE_INSUFFICIENT"
            for horizon in HORIZONS:
                row["horizons"][str(horizon)] = {
                    "status": "CALENDAR_COVERAGE_INSUFFICIENT"
                }
            records.append(row)
            continue
        entry_index, entry_session = entry_result
        entry_date = date.fromisoformat(entry_session.session_date)
        unresolved_entry = _unresolved_between(
            unresolved_special_dates,
            start_date=publication.astimezone(IST).date(),
            end_date=entry_date,
        )
        if unresolved_entry:
            row["execution_status"] = "CALENDAR_UNRESOLVED_SPECIAL_SESSION"
            for horizon in HORIZONS:
                row["horizons"][str(horizon)] = {
                    "status": "CALENDAR_UNRESOLVED_SPECIAL_SESSION",
                    "unresolved_special_dates": list(unresolved_entry),
                }
            records.append(row)
            continue
        row["entry_session"] = entry_session.to_dict()
        execution_status = capture_latency_status(
            signal_frozen_at_utc=str(signal["signal_frozen_at_utc"]),
            nominal_entry_open_utc=entry_session.open_timestamp_utc,
        )
        row["execution_status"] = execution_status
        if execution_status != "EXECUTABLE_AT_H022_X001_ENTRY":
            for horizon in HORIZONS:
                row["horizons"][str(horizon)] = {"status": "LATE_SIGNAL_FREEZE"}
            records.append(row)
            continue

        entry_stock = stock_bars.get((entry_session.session_date, symbol))
        entry_benchmark = benchmark_bars.get(entry_session.session_date)
        if entry_date <= cutoff:
            row["entry_stock_bar"] = entry_stock
            row["entry_benchmark_bar"] = entry_benchmark

        for horizon in HORIZONS:
            key = str(horizon)
            exit_session = horizon_session(sessions, entry_index=entry_index, horizon=horizon)
            if exit_session is None:
                row["horizons"][key] = {"status": "CALENDAR_COVERAGE_INSUFFICIENT"}
                continue
            exit_date = date.fromisoformat(exit_session.session_date)
            unresolved_horizon = _unresolved_between(
                unresolved_special_dates,
                start_date=entry_date,
                end_date=exit_date,
            )
            if unresolved_horizon:
                row["horizons"][key] = {
                    "status": "CALENDAR_UNRESOLVED_SPECIAL_SESSION",
                    "unresolved_special_dates": list(unresolved_horizon),
                }
                continue
            if exit_date > cutoff:
                row["horizons"][key] = {
                    "status": "NOT_MATURE",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            if entry_date > cutoff:
                row["horizons"][key] = {"status": "NOT_MATURE"}
                continue
            if entry_stock is None:
                row["horizons"][key] = {
                    "status": "MISSING_ENTRY_STOCK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            if entry_benchmark is None:
                row["horizons"][key] = {
                    "status": "MISSING_ENTRY_BENCHMARK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            action_audit = corporate_actions.get(symbol)
            if action_audit is None or action_audit.get("status") != "READY":
                row["horizons"][key] = {
                    "status": "CORPORATE_ACTION_AUDIT_UNRESOLVED",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            actions = blocked_actions(
                action_audit,
                entry_date=entry_session.session_date,
                exit_date=exit_session.session_date,
            )
            if actions:
                row["horizons"][key] = {
                    "status": "CORPORATE_ACTION_BLOCKED",
                    "exit_session": exit_session.to_dict(),
                    "blocked_actions": list(actions),
                }
                continue
            exit_stock = stock_bars.get((exit_session.session_date, symbol))
            exit_benchmark = benchmark_bars.get(exit_session.session_date)
            if exit_stock is None:
                row["horizons"][key] = {
                    "status": "MISSING_EXIT_STOCK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            if exit_benchmark is None:
                row["horizons"][key] = {
                    "status": "MISSING_EXIT_BENCHMARK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            entry_stock_open, _ = _validate_stock_bar(
                entry_stock,
                symbol=symbol,
                expected_isin=member["isin"],
                series=member["series"],
                session_date=entry_session.session_date,
            )
            _, exit_stock_close = _validate_stock_bar(
                exit_stock,
                symbol=symbol,
                expected_isin=member["isin"],
                series=member["series"],
                session_date=exit_session.session_date,
            )
            entry_benchmark_open, _ = _validate_benchmark_bar(
                entry_benchmark, session_date=entry_session.session_date
            )
            _, exit_benchmark_close = _validate_benchmark_bar(
                exit_benchmark, session_date=exit_session.session_date
            )
            stock_return = _gross_return_pct(entry_stock_open, exit_stock_close)
            benchmark_return = _gross_return_pct(
                entry_benchmark_open, exit_benchmark_close
            )
            excess = stock_return - benchmark_return
            row["horizons"][key] = {
                "status": "COMPLETE",
                "exit_session": exit_session.to_dict(),
                "exit_stock_bar": exit_stock,
                "exit_benchmark_bar": exit_benchmark,
                "stock_return_pct": stock_return,
                "benchmark_return_pct": benchmark_return,
                "gross_excess_pp": excess,
                "cost_adjusted_excess_pp": excess - ROUND_TRIP_COST_PP,
                "beat_benchmark": excess > 0,
            }
        records.append(row)

    report: dict[str, Any] = {
        "schema_version": 1,
        "hypothesis_id": "H022",
        "protocol_id": "H022-P001",
        "outcome_contract_id": OUTCOME_CONTRACT_ID,
        "execution_rule_id": EXECUTION_RULE_ID,
        "benchmark_id": BENCHMARK_ID,
        "signal_ledger_sha256": signal_ledger["ledger_sha256"],
        "signal_ledger_record_count": signal_ledger["record_count"],
        "eligible_signal_count": len(records),
        "market_data_cutoff_session": cutoff.isoformat(),
        "calendar_version": calendar.get("version"),
        "calendar_start_date": calendar.get("start_date"),
        "calendar_end_date": calendar.get("end_date"),
        "calendar_unresolved_special_dates": [
            item.isoformat() for item in unresolved_special_dates
        ],
        "primary_horizon_sessions": PRIMARY_HORIZON,
        "horizons_sessions": list(HORIZONS),
        "round_trip_cost_pp": ROUND_TRIP_COST_PP,
        "records": records,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = canonical_hash(report)
    return report


def _evaluation_view(report: dict[str, Any]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for row in report["records"]:
        if row.get("execution_status") != "EXECUTABLE_AT_H022_X001_ENTRY":
            continue
        copied = copy.deepcopy(row)
        for horizon in HORIZONS:
            horizon_row = copied["horizons"][str(horizon)]
            if horizon_row.get("status") in PENDING_STATUSES:
                copied["horizons"][str(horizon)] = {"status": "NOT_MATURE"}
        records.append(copied)
    return {"records": records}


def summarize_prospective_outcomes(report: dict[str, Any]) -> dict[str, Any]:
    stored = report.get("report_sha256")
    unsigned = dict(report)
    unsigned.pop("report_sha256", None)
    if stored != canonical_hash(unsigned):
        raise H022P001OutcomeError("prospective H022 outcome report digest mismatch")
    if report.get("outcome_contract_id") != OUTCOME_CONTRACT_ID:
        raise H022P001OutcomeError("prospective H022 outcome contract identity changed")
    if report.get("primary_horizon_sessions") != PRIMARY_HORIZON:
        raise H022P001OutcomeError("prospective H022 primary horizon changed")
    if report.get("round_trip_cost_pp") != ROUND_TRIP_COST_PP:
        raise H022P001OutcomeError("prospective H022 cost assumption changed")

    view = _evaluation_view(report)
    horizons: dict[str, dict[str, Any]] = {}
    for horizon in HORIZONS:
        result = evaluate_horizon(view, horizon=horizon)
        raw_counts = Counter(
            str(row["horizons"][str(horizon)]["status"])
            for row in report["records"]
        )
        result["raw_status_counts"] = dict(sorted(raw_counts.items()))
        result["late_signal_freeze_count"] = raw_counts.get("LATE_SIGNAL_FREEZE", 0)
        result["calendar_pending_count"] = sum(
            raw_counts.get(status, 0)
            for status in (
                "CALENDAR_COVERAGE_INSUFFICIENT",
                "CALENDAR_UNRESOLVED_SPECIAL_SESSION",
            )
        )
        horizons[str(horizon)] = result
    primary = horizons[str(PRIMARY_HORIZON)]
    classification = classify_primary(primary)
    summary: dict[str, Any] = {
        "schema_version": 1,
        "hypothesis_id": "H022",
        "protocol_id": "H022-P001",
        "outcome_contract_id": OUTCOME_CONTRACT_ID,
        "execution_rule_id": EXECUTION_RULE_ID,
        "benchmark_id": BENCHMARK_ID,
        "signal_ledger_sha256": report["signal_ledger_sha256"],
        "outcome_report_sha256": stored,
        "market_data_cutoff_session": report["market_data_cutoff_session"],
        "primary_horizon_sessions": PRIMARY_HORIZON,
        "minimum_primary_complete_observations": MIN_PRIMARY_OBSERVATIONS,
        "minimum_complete_share": MIN_COMPLETE_SHARE,
        "primary_classification": classification,
        "horizons": horizons,
        "live_capital_allowed": False,
    }
    summary["summary_sha256"] = canonical_hash(summary)
    return summary
