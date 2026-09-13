from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
import statistics
import time
import zipfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time as dt_time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
from scipy import stats

from marketlab.h022 import validate_feature_panel
from marketlab.marketdata import index_snapshot_url, udiff_url

IST = ZoneInfo("Asia/Kolkata")
HYPOTHESIS_ID = "H022"
EXECUTION_RULE_ID = "H022-X001"
FEATURE_PANEL_SHA256 = "dd992523238aebce5e9f6ee8535951fd869bf9d8615705d4fb5f420e8f85bee3"
CHALLENGE_SIGNAL_COUNT = 398
MARKET_DATA_CUTOFF = date(2026, 9, 11)
HORIZONS = (20, 60, 120)
PRIMARY_HORIZON = 60
ROUND_TRIP_COST_PP = 0.50
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 22_022
MIN_PRIMARY_OBSERVATIONS = 200
MIN_COMPLETE_SHARE = 0.80

HOLIDAYS = frozenset(
    {
        date(2025, 10, 2),
        date(2025, 10, 22),
        date(2025, 11, 5),
        date(2025, 12, 25),
        date(2026, 1, 15),
        date(2026, 1, 26),
        date(2026, 3, 3),
        date(2026, 3, 26),
        date(2026, 3, 31),
        date(2026, 4, 3),
        date(2026, 4, 14),
        date(2026, 5, 1),
        date(2026, 5, 28),
        date(2026, 6, 26),
    }
)
SPECIAL_SESSION_TIMES = {
    date(2025, 10, 21): (dt_time(13, 45), dt_time(14, 45)),
}
BLOCKED_ACTION_TOKENS = (
    "bonus",
    "split",
    "sub-division",
    "subdivision",
    "consolidation",
    "rights",
    "demerger",
    "spin-off",
    "spin off",
    "reduction of capital",
    "scheme of arrangement",
    "merger",
    "amalgamation",
)


class H022OutcomeError(ValueError):
    """Raised when H022 historical outcomes cannot be reconstructed without guessing."""


def _canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise H022OutcomeError("H022 outcome payload must contain finite JSON values") from exc
    return hashlib.sha256(raw).hexdigest()


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise H022OutcomeError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise H022OutcomeError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H022OutcomeError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _positive_float(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise H022OutcomeError(f"{field} must be a finite positive number")
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise H022OutcomeError(f"invalid {field}: {value}") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise H022OutcomeError(f"{field} must be a finite positive number")
    return parsed


@dataclass(frozen=True)
class HistoricalSession:
    session_date: str
    open_timestamp_utc: str
    close_timestamp_utc: str
    special: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShareAction:
    ex_date: str
    subject: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _session(day: date, opened: dt_time, closed: dt_time, *, special: bool) -> HistoricalSession:
    open_dt = datetime.combine(day, opened, tzinfo=IST).astimezone(UTC)
    close_dt = datetime.combine(day, closed, tzinfo=IST).astimezone(UTC)
    if open_dt >= close_dt:
        raise H022OutcomeError(f"invalid session interval: {day}")
    return HistoricalSession(
        session_date=day.isoformat(),
        open_timestamp_utc=open_dt.isoformat().replace("+00:00", "Z"),
        close_timestamp_utc=close_dt.isoformat().replace("+00:00", "Z"),
        special=special,
    )


def build_frozen_sessions(
    *,
    start_date: date = date(2025, 10, 1),
    end_date: date = MARKET_DATA_CUTOFF,
) -> tuple[HistoricalSession, ...]:
    if start_date > end_date:
        raise H022OutcomeError("calendar start date exceeds end date")
    sessions: list[HistoricalSession] = []
    cursor = start_date
    while cursor <= end_date:
        special = SPECIAL_SESSION_TIMES.get(cursor)
        if special is not None:
            sessions.append(_session(cursor, special[0], special[1], special=True))
        elif cursor.weekday() < 5 and cursor not in HOLIDAYS:
            sessions.append(_session(cursor, dt_time(9, 15), dt_time(15, 30), special=False))
        cursor += timedelta(days=1)
    if not sessions:
        raise H022OutcomeError("frozen calendar produced zero sessions")
    return tuple(sessions)


def first_entry_session(
    exchange_published_at_utc: str,
    sessions: tuple[HistoricalSession, ...],
) -> tuple[int, HistoricalSession] | None:
    publication = _parse_timestamp(exchange_published_at_utc, "exchange_published_at_utc")
    for index, session in enumerate(sessions):
        opened = _parse_timestamp(session.open_timestamp_utc, "session open")
        if opened > publication:
            return index, session
    return None


def horizon_session(
    sessions: tuple[HistoricalSession, ...],
    *,
    entry_index: int,
    horizon: int,
) -> HistoricalSession | None:
    if entry_index < 0:
        raise H022OutcomeError("entry_index must be non-negative")
    if horizon not in HORIZONS:
        raise H022OutcomeError(f"unsupported H022 horizon: {horizon}")
    target = entry_index + horizon - 1
    if target >= len(sessions):
        return None
    return sessions[target]


def _parse_action_date(value: object) -> date:
    if not isinstance(value, str):
        raise H022OutcomeError("corporate action ex-date is missing")
    raw = value.strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y"):
        try:
            parsed = time.strptime(raw, fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
        except ValueError:
            continue
    raise H022OutcomeError(f"unsupported corporate action ex-date: {value}")


def parse_share_action_audit(payload: object, *, symbol: str) -> dict[str, Any]:
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        candidate = payload.get("data") or payload.get("records") or []
        rows = [row for row in candidate if isinstance(row, dict)] if isinstance(candidate, list) else []
    else:
        rows = []

    actions: list[ShareAction] = []
    unresolved: list[str] = []
    wanted = symbol.strip().upper()
    for row in rows:
        observed_symbol = str(row.get("symbol") or "").strip().upper()
        if observed_symbol and observed_symbol != wanted:
            continue
        subject = str(row.get("subject") or row.get("purpose") or "").strip()
        if not subject:
            continue
        lowered = subject.casefold()
        if not any(token in lowered for token in BLOCKED_ACTION_TOKENS):
            continue
        raw_date = row.get("exDate") or row.get("ex_date")
        try:
            action_date = _parse_action_date(raw_date)
        except H022OutcomeError:
            unresolved.append(subject)
            continue
        actions.append(ShareAction(action_date.isoformat(), subject))

    actions.sort(key=lambda item: (item.ex_date, item.subject))
    unresolved = sorted(set(unresolved))
    return {
        "status": "UNRESOLVED" if unresolved else "READY",
        "actions": [action.to_dict() for action in actions],
        "unresolved_subjects": unresolved,
    }


def blocked_actions(
    audit: dict[str, Any],
    *,
    entry_date: str,
    exit_date: str,
) -> tuple[dict[str, str], ...]:
    if audit.get("status") != "READY":
        raise H022OutcomeError("corporate action audit is unresolved")
    entry = date.fromisoformat(entry_date)
    exit_day = date.fromisoformat(exit_date)
    if exit_day < entry:
        raise H022OutcomeError("exit date precedes entry date")
    relevant = []
    for row in audit.get("actions", []):
        if not isinstance(row, dict):
            raise H022OutcomeError("corporate action row must be an object")
        ex_day = date.fromisoformat(str(row["ex_date"]))
        if entry < ex_day <= exit_day:
            relevant.append({"ex_date": ex_day.isoformat(), "subject": str(row["subject"])})
    return tuple(relevant)


def parse_udiff_identity_bar(
    raw_zip: bytes,
    *,
    session_date: date,
    symbol: str,
    expected_isin: str,
    series: str = "EQ",
) -> dict[str, Any] | None:
    try:
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            names = archive.namelist()
            if len(names) != 1 or not names[0].lower().endswith(".csv"):
                raise H022OutcomeError("UDiFF archive must contain exactly one CSV")
            raw_csv = archive.read(names[0])
    except (zipfile.BadZipFile, KeyError) as exc:
        raise H022OutcomeError(f"invalid UDiFF ZIP: {exc}") from exc

    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise H022OutcomeError("UDiFF CSV is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
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
    }
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise H022OutcomeError("UDiFF header does not match H022 contract")

    day = session_date.isoformat()
    wanted_symbol = symbol.strip().upper()
    wanted_series = series.strip().upper()
    eligible: list[dict[str, str]] = []
    for row in reader:
        if (
            str(row.get("TradDt") or "").strip() == day
            and str(row.get("Sgmt") or "").strip().upper() == "CM"
            and str(row.get("Src") or "").strip().upper() == "NSE"
            and str(row.get("FinInstrmTp") or "").strip().upper() == "STK"
            and str(row.get("SctySrs") or "").strip().upper() == wanted_series
        ):
            eligible.append(row)

    isin_matches = [row for row in eligible if str(row.get("ISIN") or "").strip() == expected_isin]
    if len(isin_matches) > 1:
        raise H022OutcomeError(f"multiple UDiFF EQ rows match ISIN {expected_isin} on {day}")
    if isin_matches:
        row = isin_matches[0]
        identity_mode = "EXACT_CURRENT_U001_ISIN"
    else:
        symbol_matches = [
            row
            for row in eligible
            if str(row.get("TckrSymb") or "").strip().upper() == wanted_symbol
        ]
        if len(symbol_matches) > 1:
            raise H022OutcomeError(f"multiple UDiFF EQ rows match symbol {wanted_symbol} on {day}")
        if not symbol_matches:
            return None
        row = symbol_matches[0]
        identity_mode = "CURRENT_SYMBOL_EQ_FALLBACK"

    observed_symbol = str(row.get("TckrSymb") or "").strip().upper()
    observed_isin = str(row.get("ISIN") or "").strip()
    if not observed_symbol or not observed_isin:
        raise H022OutcomeError("UDiFF identity fields are missing")
    return {
        "session_date": day,
        "symbol_requested": wanted_symbol,
        "symbol_observed": observed_symbol,
        "isin_requested": expected_isin,
        "isin_observed": observed_isin,
        "series": wanted_series,
        "identity_mode": identity_mode,
        "open": _positive_float(row.get("OpnPric"), "UDiFF open"),
        "close": _positive_float(row.get("ClsPric"), "UDiFF close"),
        "source_url": udiff_url(session_date),
    }


def _gross_return_pct(entry: float, exit_value: float) -> float:
    result = (exit_value / entry - 1.0) * 100.0
    if not math.isfinite(result):
        raise H022OutcomeError("computed return is non-finite")
    return result


def build_outcome_report(
    feature_panel: dict[str, Any],
    *,
    sessions: tuple[HistoricalSession, ...],
    stock_bars: dict[tuple[str, str], dict[str, Any] | None],
    benchmark_bars: dict[str, dict[str, Any]],
    corporate_actions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    validate_feature_panel(feature_panel)
    if feature_panel.get("panel_sha256") != FEATURE_PANEL_SHA256:
        raise H022OutcomeError("H022 feature panel digest changed")

    challenge = [
        row
        for row in feature_panel["records"]
        if row.get("historical_split") == "CHALLENGE" and row.get("feature_status") == "SIGNAL"
    ]
    if len(challenge) != CHALLENGE_SIGNAL_COUNT:
        raise H022OutcomeError(
            f"expected {CHALLENGE_SIGNAL_COUNT} challenge signals, found {len(challenge)}"
        )

    session_index = {row.session_date: index for index, row in enumerate(sessions)}
    records: list[dict[str, Any]] = []
    for feature in challenge:
        symbol = str(feature["symbol"])
        entry_result = first_entry_session(str(feature["exchange_published_at_utc"]), sessions)
        row: dict[str, Any] = {
            "source_id": feature["source_id"],
            "symbol": symbol,
            "exchange_published_at_utc": feature["exchange_published_at_utc"],
            "primary_signal": feature["primary_signal"],
            "entry_session": None,
            "entry_stock_bar": None,
            "entry_benchmark_bar": None,
            "horizons": {},
        }
        if entry_result is None:
            for horizon in HORIZONS:
                row["horizons"][str(horizon)] = {"status": "NOT_MATURE"}
            records.append(row)
            continue

        entry_idx, entry_session = entry_result
        row["entry_session"] = entry_session.to_dict()
        entry_stock = stock_bars.get((entry_session.session_date, symbol))
        entry_benchmark = benchmark_bars.get(entry_session.session_date)
        row["entry_stock_bar"] = entry_stock
        row["entry_benchmark_bar"] = entry_benchmark
        action_audit = corporate_actions.get(symbol)

        for horizon in HORIZONS:
            exit_session = horizon_session(sessions, entry_index=entry_idx, horizon=horizon)
            if exit_session is None:
                row["horizons"][str(horizon)] = {"status": "NOT_MATURE"}
                continue
            if exit_session.session_date not in session_index:
                raise H022OutcomeError("horizon exit session is not in frozen calendar")
            if entry_stock is None:
                row["horizons"][str(horizon)] = {
                    "status": "MISSING_ENTRY_STOCK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            if entry_benchmark is None:
                row["horizons"][str(horizon)] = {
                    "status": "MISSING_ENTRY_BENCHMARK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            if action_audit is None or action_audit.get("status") != "READY":
                row["horizons"][str(horizon)] = {
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
                row["horizons"][str(horizon)] = {
                    "status": "CORPORATE_ACTION_BLOCKED",
                    "exit_session": exit_session.to_dict(),
                    "blocked_actions": list(actions),
                }
                continue

            exit_stock = stock_bars.get((exit_session.session_date, symbol))
            exit_benchmark = benchmark_bars.get(exit_session.session_date)
            if exit_stock is None:
                row["horizons"][str(horizon)] = {
                    "status": "MISSING_EXIT_STOCK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            if exit_benchmark is None:
                row["horizons"][str(horizon)] = {
                    "status": "MISSING_EXIT_BENCHMARK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue

            stock_return = _gross_return_pct(float(entry_stock["open"]), float(exit_stock["close"]))
            benchmark_return = _gross_return_pct(
                float(entry_benchmark["open"]), float(exit_benchmark["close"])
            )
            excess = stock_return - benchmark_return
            row["horizons"][str(horizon)] = {
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

    report = {
        "schema_version": 1,
        "hypothesis_id": HYPOTHESIS_ID,
        "execution_rule_id": EXECUTION_RULE_ID,
        "feature_panel_sha256": FEATURE_PANEL_SHA256,
        "evidence_class": "HISTORICAL_SURVIVOR_PANEL_DEVELOPMENT",
        "market_data_cutoff_session": MARKET_DATA_CUTOFF.isoformat(),
        "challenge_signal_count": len(records),
        "records": records,
    }
    report["report_sha256"] = _canonical_hash(report)
    return report


def _assign_quintiles(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: (float(row["primary_signal"]), str(row["source_id"])))
    count = len(ordered)
    assigned: list[dict[str, Any]] = []
    for index, row in enumerate(ordered):
        tagged = dict(row)
        tagged["quintile"] = min(4, index * 5 // count)
        assigned.append(tagged)
    return assigned


def _cluster_bootstrap_spread(rows: list[dict[str, Any]]) -> tuple[float | None, float | None, int]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_symbol[str(row["symbol"])].append(row)
    symbols = sorted(by_symbol)
    if len(symbols) < 2:
        return None, None, 0

    rng = random.Random(BOOTSTRAP_SEED)
    spreads: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sample_rows: list[dict[str, Any]] = []
        for _cluster in symbols:
            chosen = rng.choice(symbols)
            sample_rows.extend(by_symbol[chosen])
        top = [float(row["gross_excess_pp"]) for row in sample_rows if row["quintile"] == 4]
        bottom = [float(row["gross_excess_pp"]) for row in sample_rows if row["quintile"] == 0]
        if top and bottom:
            spreads.append(statistics.fmean(top) - statistics.fmean(bottom))
    if not spreads:
        return None, None, 0
    low, high = np.quantile(np.asarray(spreads, dtype=float), [0.025, 0.975])
    return float(low), float(high), len(spreads)


def evaluate_horizon(report: dict[str, Any], *, horizon: int) -> dict[str, Any]:
    if horizon not in HORIZONS:
        raise H022OutcomeError(f"unsupported evaluation horizon: {horizon}")
    key = str(horizon)
    mature = [row for row in report["records"] if row["horizons"][key]["status"] != "NOT_MATURE"]
    complete_base = [
        {
            "source_id": row["source_id"],
            "symbol": row["symbol"],
            "primary_signal": row["primary_signal"],
            "gross_excess_pp": row["horizons"][key]["gross_excess_pp"],
            "cost_adjusted_excess_pp": row["horizons"][key]["cost_adjusted_excess_pp"],
            "beat_benchmark": row["horizons"][key]["beat_benchmark"],
        }
        for row in mature
        if row["horizons"][key]["status"] == "COMPLETE"
    ]
    status_counts: dict[str, int] = defaultdict(int)
    for row in report["records"]:
        status_counts[str(row["horizons"][key]["status"])] += 1

    result: dict[str, Any] = {
        "horizon_sessions": horizon,
        "challenge_signal_count": len(report["records"]),
        "mature_signal_count": len(mature),
        "complete_count": len(complete_base),
        "complete_share_of_mature": len(complete_base) / len(mature) if mature else None,
        "status_counts": dict(sorted(status_counts.items())),
        "spearman_signal_vs_excess": None,
        "spearman_p_value": None,
        "top_quintile_count": 0,
        "bottom_quintile_count": 0,
        "top_quintile_mean_excess_pp": None,
        "bottom_quintile_mean_excess_pp": None,
        "top_minus_bottom_mean_excess_pp": None,
        "top_quintile_median_excess_pp": None,
        "top_quintile_mean_cost_adjusted_excess_pp": None,
        "top_quintile_benchmark_beat_rate": None,
        "cluster_bootstrap_ci_95_low_pp": None,
        "cluster_bootstrap_ci_95_high_pp": None,
        "cluster_bootstrap_valid_iterations": 0,
    }
    if len(complete_base) < 2:
        return result

    assigned = _assign_quintiles(complete_base)
    signals = [float(row["primary_signal"]) for row in assigned]
    excess = [float(row["gross_excess_pp"]) for row in assigned]
    correlation = stats.spearmanr(signals, excess)
    rho = float(correlation.statistic)
    p_value = float(correlation.pvalue)
    if math.isfinite(rho):
        result["spearman_signal_vs_excess"] = rho
    if math.isfinite(p_value):
        result["spearman_p_value"] = p_value

    top = [row for row in assigned if row["quintile"] == 4]
    bottom = [row for row in assigned if row["quintile"] == 0]
    result["top_quintile_count"] = len(top)
    result["bottom_quintile_count"] = len(bottom)
    if top and bottom:
        top_excess = [float(row["gross_excess_pp"]) for row in top]
        bottom_excess = [float(row["gross_excess_pp"]) for row in bottom]
        result["top_quintile_mean_excess_pp"] = statistics.fmean(top_excess)
        result["bottom_quintile_mean_excess_pp"] = statistics.fmean(bottom_excess)
        result["top_minus_bottom_mean_excess_pp"] = (
            result["top_quintile_mean_excess_pp"] - result["bottom_quintile_mean_excess_pp"]
        )
        result["top_quintile_median_excess_pp"] = statistics.median(top_excess)
        result["top_quintile_mean_cost_adjusted_excess_pp"] = statistics.fmean(
            float(row["cost_adjusted_excess_pp"]) for row in top
        )
        result["top_quintile_benchmark_beat_rate"] = statistics.fmean(
            1.0 if row["beat_benchmark"] else 0.0 for row in top
        )
        low, high, valid_iterations = _cluster_bootstrap_spread(assigned)
        result["cluster_bootstrap_ci_95_low_pp"] = low
        result["cluster_bootstrap_ci_95_high_pp"] = high
        result["cluster_bootstrap_valid_iterations"] = valid_iterations
    return result


def classify_primary(primary: dict[str, Any]) -> str:
    mature = int(primary["mature_signal_count"])
    complete = int(primary["complete_count"])
    share = primary["complete_share_of_mature"]
    if (
        complete < MIN_PRIMARY_OBSERVATIONS
        or mature == 0
        or share is None
        or float(share) < MIN_COMPLETE_SHARE
    ):
        return "INSUFFICIENT_COVERAGE"

    top_mean = float(primary["top_quintile_mean_excess_pp"])
    spread = float(primary["top_minus_bottom_mean_excess_pp"])
    top_median = float(primary["top_quintile_median_excess_pp"])
    beat_rate = float(primary["top_quintile_benchmark_beat_rate"])
    ci_low = primary["cluster_bootstrap_ci_95_low_pp"]

    if spread <= 0.0 or top_mean <= 0.0:
        return "REJECTED"
    if spread >= 4.0 and ci_low is not None and float(ci_low) > 0.0 and beat_rate >= 0.55:
        return "STRONG"
    if spread >= 2.0 and top_median > 0.0 and beat_rate >= 0.55:
        return "PROMISING"
    return "INCONCLUSIVE"


def summarize_outcomes(report: dict[str, Any]) -> dict[str, Any]:
    stored = report.get("report_sha256")
    unsigned = dict(report)
    unsigned.pop("report_sha256", None)
    if stored != _canonical_hash(unsigned):
        raise H022OutcomeError("H022 outcome report hash mismatch")
    horizons = {str(horizon): evaluate_horizon(report, horizon=horizon) for horizon in HORIZONS}
    classification = classify_primary(horizons[str(PRIMARY_HORIZON)])
    summary = {
        "schema_version": 1,
        "hypothesis_id": HYPOTHESIS_ID,
        "execution_rule_id": EXECUTION_RULE_ID,
        "feature_panel_sha256": FEATURE_PANEL_SHA256,
        "outcome_report_sha256": stored,
        "evidence_class": report["evidence_class"],
        "market_data_cutoff_session": report["market_data_cutoff_session"],
        "challenge_signal_count": report["challenge_signal_count"],
        "primary_horizon_sessions": PRIMARY_HORIZON,
        "primary_classification": classification,
        "horizons": horizons,
        "live_capital_allowed": False,
    }
    summary["summary_sha256"] = _canonical_hash(summary)
    return summary


def benchmark_bar_from_index(raw_csv: bytes, *, session_date: date) -> dict[str, Any]:
    from marketlab.pf001_marketdata import parse_pf001_nifty500_index

    parsed = parse_pf001_nifty500_index(raw_csv, session_date=session_date)
    return {
        **parsed.to_dict(),
        "source_url": index_snapshot_url(session_date),
    }
