from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from datetime import time as dt_time
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
from scipy import stats

from marketlab.h022_outcomes import (
    BLOCKED_ACTION_TOKENS,
    HOLIDAYS,
    MARKET_DATA_CUTOFF,
    SPECIAL_SESSION_TIMES,
    HistoricalSession,
)

IST = ZoneInfo("Asia/Kolkata")
DIAGNOSTIC_ID = "H022-D001"
HYPOTHESIS_ID = "H022"
OUTCOME_REPORT_SHA256 = "4298bfce4227e4c27d1edcf19b0651def6e8980356a6a9de2493d09a81bee6c5"
CONTROL_LOOKBACK_SESSIONS = 60
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 22_023
ADDITIONAL_PRECHALLENGE_HOLIDAYS = frozenset({date(2025, 8, 15), date(2025, 8, 27)})
DIAGNOSTIC_START = date(2025, 6, 15)


class H022MomentumDiagnosticError(ValueError):
    """Raised when H022 momentum independence cannot be tested without guessing."""


def _canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise H022MomentumDiagnosticError(
            "H022 momentum diagnostic payload must contain finite JSON values"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def validate_outcome_report(report: dict[str, Any]) -> None:
    if report.get("hypothesis_id") != HYPOTHESIS_ID:
        raise H022MomentumDiagnosticError("unexpected H022 outcome hypothesis id")
    if report.get("execution_rule_id") != "H022-X001":
        raise H022MomentumDiagnosticError("unexpected H022 execution rule")
    if report.get("report_sha256") != OUTCOME_REPORT_SHA256:
        raise H022MomentumDiagnosticError("H022 outcome report digest changed")
    unsigned = dict(report)
    unsigned.pop("report_sha256", None)
    if _canonical_hash(unsigned) != OUTCOME_REPORT_SHA256:
        raise H022MomentumDiagnosticError("H022 outcome report hash mismatch")
    records = report.get("records")
    if not isinstance(records, list):
        raise H022MomentumDiagnosticError("H022 outcome report records must be a list")


def _session(day: date, opened: dt_time, closed: dt_time, *, special: bool) -> HistoricalSession:
    start = datetime.combine(day, opened, tzinfo=IST).astimezone(UTC)
    end = datetime.combine(day, closed, tzinfo=IST).astimezone(UTC)
    if start >= end:
        raise H022MomentumDiagnosticError(f"invalid session interval: {day}")
    return HistoricalSession(
        session_date=day.isoformat(),
        open_timestamp_utc=start.isoformat().replace("+00:00", "Z"),
        close_timestamp_utc=end.isoformat().replace("+00:00", "Z"),
        special=special,
    )


def build_diagnostic_sessions(
    *,
    start_date: date = DIAGNOSTIC_START,
    end_date: date = MARKET_DATA_CUTOFF,
) -> tuple[HistoricalSession, ...]:
    if start_date > end_date:
        raise H022MomentumDiagnosticError("diagnostic calendar start exceeds end")
    holidays = HOLIDAYS | ADDITIONAL_PRECHALLENGE_HOLIDAYS
    sessions: list[HistoricalSession] = []
    cursor = start_date
    while cursor <= end_date:
        special = SPECIAL_SESSION_TIMES.get(cursor)
        if special is not None:
            sessions.append(_session(cursor, special[0], special[1], special=True))
        elif cursor.weekday() < 5 and cursor not in holidays:
            sessions.append(_session(cursor, dt_time(9, 15), dt_time(15, 30), special=False))
        cursor += timedelta(days=1)
    return tuple(sessions)


def control_window(
    sessions: tuple[HistoricalSession, ...], entry_session_date: str
) -> tuple[HistoricalSession, HistoricalSession] | None:
    by_date = {row.session_date: index for index, row in enumerate(sessions)}
    entry_index = by_date.get(entry_session_date)
    if entry_index is None:
        raise H022MomentumDiagnosticError(
            f"H022 entry session not present in diagnostic calendar: {entry_session_date}"
        )
    start_index = entry_index - CONTROL_LOOKBACK_SESSIONS
    end_index = entry_index - 1
    if start_index < 0 or end_index < 0:
        return None
    return sessions[start_index], sessions[end_index]


def _parse_action_date(value: object) -> date:
    import time

    if not isinstance(value, str):
        raise H022MomentumDiagnosticError("corporate action ex-date is missing")
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y"):
        try:
            parsed = time.strptime(value.strip(), fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
        except ValueError:
            continue
    raise H022MomentumDiagnosticError(f"unsupported corporate action ex-date: {value}")


def parse_control_action_audit(payload: object, *, symbol: str) -> dict[str, Any]:
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        candidate = payload.get("data") or payload.get("records") or []
        rows = [row for row in candidate if isinstance(row, dict)] if isinstance(candidate, list) else []
    else:
        rows = []
    wanted = symbol.strip().upper()
    actions: list[dict[str, str]] = []
    unresolved: list[str] = []
    for row in rows:
        observed_symbol = str(row.get("symbol") or "").strip().upper()
        if observed_symbol and observed_symbol != wanted:
            continue
        subject = str(row.get("subject") or row.get("purpose") or "").strip()
        if not subject or not any(token in subject.casefold() for token in BLOCKED_ACTION_TOKENS):
            continue
        raw_date = row.get("exDate") or row.get("ex_date")
        try:
            action_date = _parse_action_date(raw_date)
        except H022MomentumDiagnosticError:
            unresolved.append(subject)
            continue
        actions.append({"ex_date": action_date.isoformat(), "subject": subject})
    actions.sort(key=lambda row: (row["ex_date"], row["subject"]))
    return {
        "status": "UNRESOLVED" if unresolved else "READY",
        "actions": actions,
        "unresolved_subjects": sorted(set(unresolved)),
    }


def control_window_blocked(
    audit: dict[str, Any], *, start_date: str, end_date: str
) -> tuple[dict[str, str], ...]:
    if audit.get("status") != "READY":
        raise H022MomentumDiagnosticError("momentum corporate-action audit unresolved")
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    blocked: list[dict[str, str]] = []
    for action in audit.get("actions", []):
        if not isinstance(action, dict):
            raise H022MomentumDiagnosticError("corporate-action row must be an object")
        ex_date = date.fromisoformat(str(action["ex_date"]))
        if start < ex_date <= end:
            blocked.append({"ex_date": ex_date.isoformat(), "subject": str(action["subject"])})
    return tuple(blocked)


def required_control_windows(
    outcome_report: dict[str, Any], sessions: tuple[HistoricalSession, ...]
) -> list[dict[str, str]]:
    validate_outcome_report(outcome_report)
    windows: list[dict[str, str]] = []
    for row in outcome_report["records"]:
        horizon = row.get("horizons", {}).get("60")
        if not isinstance(horizon, dict) or horizon.get("status") != "COMPLETE":
            continue
        entry = row.get("entry_session")
        if not isinstance(entry, dict) or not isinstance(entry.get("session_date"), str):
            raise H022MomentumDiagnosticError("complete H022 row is missing entry session")
        window = control_window(sessions, entry["session_date"])
        if window is None:
            windows.append(
                {
                    "source_id": str(row["source_id"]),
                    "symbol": str(row["symbol"]),
                    "status": "NO_CONTROL_INSUFFICIENT_HISTORY",
                    "entry_session_date": entry["session_date"],
                    "start_session_date": "",
                    "end_session_date": "",
                }
            )
            continue
        start, end = window
        windows.append(
            {
                "source_id": str(row["source_id"]),
                "symbol": str(row["symbol"]),
                "status": "REQUIRED",
                "entry_session_date": entry["session_date"],
                "start_session_date": start.session_date,
                "end_session_date": end.session_date,
            }
        )
    return windows


def _return_pct(start: float, end: float) -> float:
    result = (end / start - 1.0) * 100.0
    if not math.isfinite(result):
        raise H022MomentumDiagnosticError("non-finite return")
    return result


def build_control_panel(
    outcome_report: dict[str, Any],
    *,
    sessions: tuple[HistoricalSession, ...],
    stock_closes: dict[tuple[str, str], float | None],
    benchmark_closes: dict[str, float | None],
    corporate_actions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    validate_outcome_report(outcome_report)
    future_by_source = {
        str(row["source_id"]): row
        for row in outcome_report["records"]
        if isinstance(row.get("horizons", {}).get("60"), dict)
        and row["horizons"]["60"].get("status") == "COMPLETE"
    }
    records: list[dict[str, Any]] = []
    for window in required_control_windows(outcome_report, sessions):
        source_id = window["source_id"]
        future = future_by_source[source_id]
        base = {
            "source_id": source_id,
            "symbol": window["symbol"],
            "entry_session_date": window["entry_session_date"],
            "start_session_date": window["start_session_date"] or None,
            "end_session_date": window["end_session_date"] or None,
            "h022_signal": float(future["primary_signal"]),
            "future_60d_excess_pp": float(future["horizons"]["60"]["gross_excess_pp"]),
            "control_status": None,
            "prior_60d_stock_return_pct": None,
            "prior_60d_benchmark_return_pct": None,
            "prior_60d_relative_return_pp": None,
            "blocked_actions": [],
        }
        if window["status"] != "REQUIRED":
            base["control_status"] = window["status"]
            records.append(base)
            continue
        audit = corporate_actions.get(window["symbol"])
        if audit is None or audit.get("status") != "READY":
            base["control_status"] = "CONTROL_ACTION_AUDIT_UNRESOLVED"
            records.append(base)
            continue
        blocked = control_window_blocked(
            audit,
            start_date=window["start_session_date"],
            end_date=window["end_session_date"],
        )
        if blocked:
            base["control_status"] = "CONTROL_BLOCKED"
            base["blocked_actions"] = list(blocked)
            records.append(base)
            continue
        symbol = window["symbol"]
        stock_start = stock_closes.get((window["start_session_date"], symbol))
        stock_end = stock_closes.get((window["end_session_date"], symbol))
        bench_start = benchmark_closes.get(window["start_session_date"])
        bench_end = benchmark_closes.get(window["end_session_date"])
        if None in (stock_start, stock_end):
            base["control_status"] = "NO_CONTROL_MISSING_STOCK_BAR"
            records.append(base)
            continue
        if None in (bench_start, bench_end):
            base["control_status"] = "NO_CONTROL_MISSING_BENCHMARK_BAR"
            records.append(base)
            continue
        assert stock_start is not None and stock_end is not None
        assert bench_start is not None and bench_end is not None
        stock_return = _return_pct(float(stock_start), float(stock_end))
        benchmark_return = _return_pct(float(bench_start), float(bench_end))
        base.update(
            {
                "control_status": "READY",
                "prior_60d_stock_return_pct": stock_return,
                "prior_60d_benchmark_return_pct": benchmark_return,
                "prior_60d_relative_return_pp": stock_return - benchmark_return,
            }
        )
        records.append(base)
    panel: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": DIAGNOSTIC_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "outcome_report_sha256": OUTCOME_REPORT_SHA256,
        "record_count": len(records),
        "ready_count": sum(row["control_status"] == "READY" for row in records),
        "records": records,
    }
    panel["panel_sha256"] = _canonical_hash(panel)
    return panel


def _zscore(values: np.ndarray) -> np.ndarray:
    std = float(np.std(values, ddof=0))
    if not math.isfinite(std) or std <= 0:
        raise H022MomentumDiagnosticError("diagnostic variable has zero/non-finite dispersion")
    return (values - float(np.mean(values))) / std


def _ols_h022_coefficient(rows: list[dict[str, Any]]) -> tuple[float, float, np.ndarray]:
    signal = np.asarray([float(row["h022_signal"]) for row in rows], dtype=float)
    momentum = np.asarray([float(row["prior_60d_relative_return_pp"]) for row in rows], dtype=float)
    future = np.asarray([float(row["future_60d_excess_pp"]) for row in rows], dtype=float)
    z_signal = _zscore(signal)
    z_momentum = _zscore(momentum)
    design = np.column_stack([np.ones(len(rows)), z_signal, z_momentum])
    coefficients, *_ = np.linalg.lstsq(design, future, rcond=None)
    return float(coefficients[1]), float(coefficients[2]), z_signal


def _residualized_signal(rows: list[dict[str, Any]]) -> np.ndarray:
    signal = np.asarray([float(row["h022_signal"]) for row in rows], dtype=float)
    momentum = np.asarray([float(row["prior_60d_relative_return_pp"]) for row in rows], dtype=float)
    z_signal = _zscore(signal)
    z_momentum = _zscore(momentum)
    design = np.column_stack([np.ones(len(rows)), z_momentum])
    coefficients, *_ = np.linalg.lstsq(design, z_signal, rcond=None)
    return z_signal - design @ coefficients


def _quintile_spread(rows: list[dict[str, Any]]) -> float | None:
    if len(rows) < 10:
        return None
    ordered = sorted(rows, key=lambda row: (float(row["h022_signal"]), str(row["source_id"])))
    tagged: list[tuple[int, dict[str, Any]]] = [
        (min(4, index * 5 // len(ordered)), row) for index, row in enumerate(ordered)
    ]
    bottom = [float(row["future_60d_excess_pp"]) for quintile, row in tagged if quintile == 0]
    top = [float(row["future_60d_excess_pp"]) for quintile, row in tagged if quintile == 4]
    if not top or not bottom:
        return None
    return statistics.fmean(top) - statistics.fmean(bottom)


def _cluster_bootstrap_h022_coefficient(rows: list[dict[str, Any]]) -> tuple[float | None, float | None, int]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_symbol[str(row["symbol"])].append(row)
    symbols = sorted(by_symbol)
    if len(symbols) < 2:
        return None, None, 0
    rng = random.Random(BOOTSTRAP_SEED)
    coefficients: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sample: list[dict[str, Any]] = []
        for _symbol in symbols:
            sample.extend(by_symbol[rng.choice(symbols)])
        try:
            coefficient, _, _ = _ols_h022_coefficient(sample)
        except H022MomentumDiagnosticError:
            continue
        coefficients.append(coefficient)
    if not coefficients:
        return None, None, 0
    low, high = np.quantile(np.asarray(coefficients, dtype=float), [0.025, 0.975])
    return float(low), float(high), len(coefficients)


def summarize_independence(control_panel: dict[str, Any]) -> dict[str, Any]:
    stored = control_panel.get("panel_sha256")
    unsigned = dict(control_panel)
    unsigned.pop("panel_sha256", None)
    if stored != _canonical_hash(unsigned):
        raise H022MomentumDiagnosticError("control panel hash mismatch")
    ready = [row for row in control_panel["records"] if row["control_status"] == "READY"]
    if len(ready) < 50:
        classification = "NOT_ESTABLISHED"
        metrics: dict[str, Any] = {"reason": "insufficient_ready_rows"}
    else:
        h022_values = [float(row["h022_signal"]) for row in ready]
        momentum_values = [float(row["prior_60d_relative_return_pp"]) for row in ready]
        future_values = [float(row["future_60d_excess_pp"]) for row in ready]
        rho_signal_momentum, p_signal_momentum = stats.spearmanr(h022_values, momentum_values)
        rho_momentum_future, p_momentum_future = stats.spearmanr(momentum_values, future_values)
        h022_coef, momentum_coef, _ = _ols_h022_coefficient(ready)
        residual = _residualized_signal(ready)
        residual_rho, residual_p = stats.spearmanr(residual, future_values)
        ci_low, ci_high, valid_bootstrap = _cluster_bootstrap_h022_coefficient(ready)

        median_momentum = float(np.median(np.asarray(momentum_values, dtype=float)))
        low_momentum = [row for row in ready if float(row["prior_60d_relative_return_pp"]) <= median_momentum]
        high_momentum = [row for row in ready if float(row["prior_60d_relative_return_pp"]) > median_momentum]
        low_spread = _quintile_spread(low_momentum)
        high_spread = _quintile_spread(high_momentum)
        metrics = {
            "ready_count": len(ready),
            "spearman_h022_vs_prior_momentum": float(rho_signal_momentum),
            "spearman_h022_vs_prior_momentum_p_value": float(p_signal_momentum),
            "spearman_prior_momentum_vs_future_excess": float(rho_momentum_future),
            "spearman_prior_momentum_vs_future_excess_p_value": float(p_momentum_future),
            "standardized_h022_ols_coefficient_pp": h022_coef,
            "standardized_prior_momentum_ols_coefficient_pp": momentum_coef,
            "cluster_bootstrap_h022_coefficient_ci_95_low_pp": ci_low,
            "cluster_bootstrap_h022_coefficient_ci_95_high_pp": ci_high,
            "cluster_bootstrap_valid_iterations": valid_bootstrap,
            "residualized_h022_spearman_vs_future_excess": float(residual_rho),
            "residualized_h022_spearman_p_value": float(residual_p),
            "prior_momentum_median_pp": median_momentum,
            "low_prior_momentum_count": len(low_momentum),
            "high_prior_momentum_count": len(high_momentum),
            "h022_top_minus_bottom_spread_low_prior_momentum_pp": low_spread,
            "h022_top_minus_bottom_spread_high_prior_momentum_pp": high_spread,
        }
        if h022_coef > 0 and ci_low is not None and ci_low > 0 and residual_rho > 0:
            classification = "SUPPORTIVE_INDEPENDENCE"
        elif h022_coef > 0 and residual_rho > 0:
            classification = "PARTIAL_INDEPENDENCE"
        else:
            classification = "NOT_ESTABLISHED"

    status_counts: dict[str, int] = defaultdict(int)
    for row in control_panel["records"]:
        status_counts[str(row["control_status"])] += 1
    summary: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": DIAGNOSTIC_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "evidence_class": "POST_OUTCOME_DIAGNOSTIC",
        "control_panel_sha256": control_panel["panel_sha256"],
        "record_count": control_panel["record_count"],
        "ready_count": control_panel["ready_count"],
        "control_status_counts": dict(sorted(status_counts.items())),
        "classification": classification,
        "metrics": metrics,
        "can_upgrade_h022_validation": False,
        "live_capital_allowed": False,
    }
    summary["summary_sha256"] = _canonical_hash(summary)
    return summary
