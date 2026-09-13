from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from scipy.stats import rankdata, spearmanr

from marketlab.h022 import validate_feature_panel

HYPOTHESIS_ID = "H022"
OUTCOME_RULE_ID = "H022-O001"
FEATURE_PANEL_SHA256 = "dd992523238aebce5e9f6ee8535951fd869bf9d8615705d4fb5f420e8f85bee3"
CUTOFF_SESSION = date(2026, 9, 11)
HORIZONS = (20, 60, 120)
PRIMARY_HORIZON = 60
IST = ZoneInfo("Asia/Kolkata")
NSE_OPEN = time(9, 15)
SHARE_CHANGE_TOKENS = (
    "bonus",
    "split",
    "sub-division",
    "subdivision",
    "consolidation",
    "rights",
    "scheme of arrangement",
    "demerger",
    "merger",
    "amalgamation",
)


class H022OutcomeError(ValueError):
    """Raised when the frozen H022 historical replay cannot be evaluated safely."""


@dataclass(frozen=True)
class IndexSession:
    session_date: date
    open_price: float
    close_price: float


def _positive_float(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise H022OutcomeError(f"{field} must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise H022OutcomeError(f"{field} must be numeric") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise H022OutcomeError(f"{field} must be positive and finite")
    return parsed


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise H022OutcomeError("event timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise H022OutcomeError(f"invalid event timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise H022OutcomeError("event timestamp must be offset-aware")
    return parsed.astimezone(UTC)


def parse_index_sessions(rows: list[dict[str, Any]]) -> list[IndexSession]:
    sessions: list[IndexSession] = []
    seen: set[date] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise H022OutcomeError("index session row must be an object")
        try:
            session_date = date.fromisoformat(str(row["session_date"]))
        except (KeyError, ValueError) as exc:
            raise H022OutcomeError("invalid index session date") from exc
        if session_date in seen:
            raise H022OutcomeError(f"duplicate index session: {session_date}")
        if session_date > CUTOFF_SESSION:
            raise H022OutcomeError("index calendar contains a session after frozen cutoff")
        seen.add(session_date)
        sessions.append(
            IndexSession(
                session_date=session_date,
                open_price=_positive_float(row.get("open"), "index open"),
                close_price=_positive_float(row.get("close"), "index close"),
            )
        )
    sessions.sort(key=lambda row: row.session_date)
    if not sessions:
        raise H022OutcomeError("index calendar is empty")
    return sessions


def parse_universe(universe: dict[str, Any]) -> dict[str, dict[str, str]]:
    members = universe.get("members")
    if not isinstance(members, list):
        raise H022OutcomeError("U001 universe members missing")
    result: dict[str, dict[str, str]] = {}
    for row in members:
        if not isinstance(row, dict):
            raise H022OutcomeError("universe member must be an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        isin = str(row.get("isin") or "").strip()
        series = str(row.get("series") or "").strip().upper()
        if not symbol or not isin or series != "EQ":
            raise H022OutcomeError(f"invalid U001 identity row for {symbol!r}")
        if symbol in result:
            raise H022OutcomeError(f"duplicate U001 symbol: {symbol}")
        result[symbol] = {"isin": isin, "series": series}
    if len(result) != 100:
        raise H022OutcomeError(f"expected 100 frozen U001 identities, observed {len(result)}")
    return result


def _entry_session_index(published_at: datetime, sessions: list[IndexSession]) -> int | None:
    for index, session in enumerate(sessions):
        local_open = datetime.combine(session.session_date, NSE_OPEN, tzinfo=IST).astimezone(UTC)
        if local_open > published_at:
            return index
    return None


def _share_action_between(
    actions: list[dict[str, Any]], symbol: str, start: date, end: date
) -> list[dict[str, str]]:
    blocked: list[dict[str, str]] = []
    for action in actions:
        if str(action.get("symbol") or "").strip().upper() != symbol:
            continue
        raw_date = action.get("ex_date")
        if not isinstance(raw_date, str):
            continue
        try:
            ex_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        if not start <= ex_date <= end:
            continue
        subject = str(action.get("subject") or "").strip()
        if any(token in subject.casefold() for token in SHARE_CHANGE_TOKENS):
            blocked.append({"ex_date": ex_date.isoformat(), "subject": subject})
    blocked.sort(key=lambda row: (row["ex_date"], row["subject"]))
    return blocked


def build_outcome_panel(
    feature_panel: dict[str, Any],
    universe: dict[str, Any],
    index_rows: list[dict[str, Any]],
    stock_prices: dict[str, dict[str, dict[str, Any]]],
    corporate_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    validate_feature_panel(feature_panel)
    if feature_panel.get("panel_sha256") != FEATURE_PANEL_SHA256:
        raise H022OutcomeError("H022 feature panel digest changed")
    identities = parse_universe(universe)
    sessions = parse_index_sessions(index_rows)

    rows: list[dict[str, Any]] = []
    for feature in feature_panel["records"]:
        symbol = str(feature["symbol"]).upper()
        if symbol not in identities:
            raise H022OutcomeError(f"H022 symbol missing from frozen U001: {symbol}")
        row: dict[str, Any] = {
            "schema_version": 1,
            "hypothesis_id": HYPOTHESIS_ID,
            "outcome_rule_id": OUTCOME_RULE_ID,
            "symbol": symbol,
            "source_id": feature["source_id"],
            "exchange_published_at_utc": feature["exchange_published_at_utc"],
            "historical_split": feature["historical_split"],
            "feature_status": feature["feature_status"],
            "primary_signal": feature["primary_signal"],
            "entry_session": None,
            "entry_price": None,
            "benchmark_entry_open": None,
            "horizons": {},
        }
        if feature["feature_status"] != "SIGNAL":
            row["outcome_status"] = "NO_FEATURE_SIGNAL"
            rows.append(row)
            continue

        published = _timestamp(feature["exchange_published_at_utc"])
        entry_index = _entry_session_index(published, sessions)
        if entry_index is None:
            row["outcome_status"] = "PENDING_ENTRY_AFTER_CUTOFF"
            rows.append(row)
            continue
        entry_session = sessions[entry_index]
        row["entry_session"] = entry_session.session_date.isoformat()
        row["benchmark_entry_open"] = entry_session.open_price

        day_prices = stock_prices.get(entry_session.session_date.isoformat(), {})
        entry_security = day_prices.get(symbol)
        if not isinstance(entry_security, dict):
            row["outcome_status"] = "MISSING_ENTRY_PRICE"
            rows.append(row)
            continue
        if entry_security.get("isin") != identities[symbol]["isin"]:
            raise H022OutcomeError(f"{symbol}: entry ISIN mismatch")
        if str(entry_security.get("series") or "").upper() != "EQ":
            raise H022OutcomeError(f"{symbol}: entry series mismatch")
        entry_price = _positive_float(entry_security.get("open"), f"{symbol} entry open")
        row["entry_price"] = entry_price

        for horizon in HORIZONS:
            exit_index = entry_index + horizon - 1
            horizon_key = str(horizon)
            if exit_index >= len(sessions):
                row["horizons"][horizon_key] = {"status": "PENDING_NOT_MATURED"}
                continue
            exit_session = sessions[exit_index]
            exit_day = stock_prices.get(exit_session.session_date.isoformat(), {})
            exit_security = exit_day.get(symbol)
            if not isinstance(exit_security, dict):
                row["horizons"][horizon_key] = {
                    "status": "MISSING_EXIT_PRICE",
                    "exit_session": exit_session.session_date.isoformat(),
                }
                continue
            if exit_security.get("isin") != identities[symbol]["isin"]:
                raise H022OutcomeError(f"{symbol}: exit ISIN mismatch")
            if str(exit_security.get("series") or "").upper() != "EQ":
                raise H022OutcomeError(f"{symbol}: exit series mismatch")
            exit_price = _positive_float(exit_security.get("close"), f"{symbol} exit close")
            blocked_actions = _share_action_between(
                corporate_actions,
                symbol,
                entry_session.session_date,
                exit_session.session_date,
            )
            stock_return = exit_price / entry_price - 1.0
            benchmark_return = exit_session.close_price / entry_session.open_price - 1.0
            horizon_row = {
                "status": "COMPLETE",
                "exit_session": exit_session.session_date.isoformat(),
                "exit_price": exit_price,
                "benchmark_exit_close": exit_session.close_price,
                "stock_return": stock_return,
                "benchmark_return": benchmark_return,
                "excess_return": stock_return - benchmark_return,
                "cost_adjusted_stock_return": stock_return - 0.005,
                "cost_adjusted_excess_return": stock_return - 0.005 - benchmark_return,
                "corporate_action_status": "BLOCKED" if blocked_actions else "CLEAR",
                "blocked_corporate_actions": blocked_actions,
            }
            row["horizons"][horizon_key] = horizon_row
        primary = row["horizons"].get(str(PRIMARY_HORIZON), {})
        if primary.get("status") == "PENDING_NOT_MATURED":
            row["outcome_status"] = "PENDING_PRIMARY_HORIZON"
        elif primary.get("status") != "COMPLETE":
            row["outcome_status"] = "INCOMPLETE_PRIMARY_SOURCE"
        elif primary.get("corporate_action_status") == "BLOCKED":
            row["outcome_status"] = "BLOCKED_PRIMARY_CORPORATE_ACTION"
        else:
            row["outcome_status"] = "COMPLETE_PRIMARY"
        rows.append(row)

    return {
        "schema_version": 1,
        "hypothesis_id": HYPOTHESIS_ID,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "feature_panel_sha256": FEATURE_PANEL_SHA256,
        "availability_cutoff_session": CUTOFF_SESSION.isoformat(),
        "survivor_panel_bias": True,
        "records": rows,
    }


def _mean(values: list[float]) -> float:
    if not values:
        raise H022OutcomeError("cannot compute mean of empty sample")
    return statistics.fmean(values)


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise H022OutcomeError("cannot compute percentile of empty sample")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return sorted_values[low]
    weight = position - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


def _spread(rows: list[dict[str, Any]]) -> float | None:
    top = [float(row["excess_return"]) for row in rows if row["quintile"] == "TOP"]
    bottom = [float(row["excess_return"]) for row in rows if row["quintile"] == "BOTTOM"]
    if not top or not bottom:
        return None
    return _mean(top) - _mean(bottom)


def summarize_challenge(outcome_panel: dict[str, Any]) -> dict[str, Any]:
    sample: list[dict[str, Any]] = []
    pending = 0
    blocked_actions = 0
    incomplete_source = 0
    for row in outcome_panel["records"]:
        if row.get("historical_split") != "CHALLENGE" or row.get("feature_status") != "SIGNAL":
            continue
        status = row.get("outcome_status")
        if status == "PENDING_PRIMARY_HORIZON":
            pending += 1
            continue
        if status == "BLOCKED_PRIMARY_CORPORATE_ACTION":
            blocked_actions += 1
            continue
        if status != "COMPLETE_PRIMARY":
            incomplete_source += 1
            continue
        primary = row["horizons"][str(PRIMARY_HORIZON)]
        sample.append(
            {
                "symbol": row["symbol"],
                "source_id": row["source_id"],
                "entry_session": row["entry_session"],
                "exit_session": primary["exit_session"],
                "signal": float(row["primary_signal"]),
                "excess_return": float(primary["excess_return"]),
            }
        )

    n = len(sample)
    if n < 10:
        return {
            "status": "INCONCLUSIVE",
            "complete_primary_count": n,
            "pending_primary_count": pending,
            "blocked_corporate_action_count": blocked_actions,
            "incomplete_source_count": incomplete_source,
            "reason": "fewer than 10 complete primary challenge outcomes",
        }

    ranks = rankdata([row["signal"] for row in sample], method="average")
    for row, rank in zip(sample, ranks, strict=True):
        pct = (float(rank) - 1.0) / (n - 1.0)
        row["percentile_rank"] = pct
        row["quintile"] = "TOP" if pct >= 0.80 else "BOTTOM" if pct <= 0.20 else "MIDDLE"

    top = [row for row in sample if row["quintile"] == "TOP"]
    bottom = [row for row in sample if row["quintile"] == "BOTTOM"]
    if not top or not bottom:
        raise H022OutcomeError("frozen percentile rule produced an empty extreme quintile")

    signal_values = [row["signal"] for row in sample]
    excess_values = [row["excess_return"] for row in sample]
    spearman = spearmanr(signal_values, excess_values)
    spread = _mean([row["excess_return"] for row in top]) - _mean(
        [row["excess_return"] for row in bottom]
    )

    groups: dict[str, list[dict[str, Any]]] = {}
    for row in sample:
        groups.setdefault(row["symbol"], []).append(row)
    symbols = sorted(groups)
    rng = random.Random(20260913)
    bootstrap_spreads: list[float] = []
    for _ in range(5000):
        replicate: list[dict[str, Any]] = []
        for _cluster in symbols:
            sampled_symbol = rng.choice(symbols)
            replicate.extend(groups[sampled_symbol])
        replicate_spread = _spread(replicate)
        if replicate_spread is not None:
            bootstrap_spreads.append(replicate_spread)
    bootstrap_spreads.sort()
    bootstrap_ci = (
        [_percentile(bootstrap_spreads, 0.025), _percentile(bootstrap_spreads, 0.975)]
        if bootstrap_spreads
        else [None, None]
    )

    loo: list[dict[str, Any]] = []
    for excluded in symbols:
        value = _spread([row for row in sample if row["symbol"] != excluded])
        if value is not None:
            loo.append({"excluded_symbol": excluded, "spread": value})
    loo.sort(key=lambda row: row["spread"])

    overlap_count = 0
    for symbol in symbols:
        company_rows = sorted(groups[symbol], key=lambda row: row["entry_session"])
        prior_exit: date | None = None
        for row in company_rows:
            entry = date.fromisoformat(row["entry_session"])
            exit_date = date.fromisoformat(row["exit_session"])
            if prior_exit is not None and entry <= prior_exit:
                overlap_count += 1
            prior_exit = max(prior_exit, exit_date) if prior_exit else exit_date

    top_mean = _mean([row["excess_return"] for row in top])
    top_median = statistics.median(row["excess_return"] for row in top)
    bottom_mean = _mean([row["excess_return"] for row in bottom])
    top_beat = _mean([1.0 if row["excess_return"] > 0 else 0.0 for row in top])
    spread_pp = spread * 100.0
    top_mean_pp = top_mean * 100.0
    top_median_pp = top_median * 100.0
    ci_lower_pp = bootstrap_ci[0] * 100.0 if bootstrap_ci[0] is not None else None

    if spread_pp <= 0 or top_mean_pp <= 0:
        interpretation = "REJECTED"
    elif (
        spread_pp >= 4.0
        and ci_lower_pp is not None
        and ci_lower_pp > 0
        and top_beat >= 0.55
    ):
        interpretation = "STRONG"
    elif spread_pp >= 2.0 and top_median_pp > 0 and top_beat >= 0.55:
        interpretation = "PROMISING"
    else:
        interpretation = "INCONCLUSIVE"

    return {
        "status": interpretation,
        "survivor_panel_bias": True,
        "complete_primary_count": n,
        "pending_primary_count": pending,
        "blocked_corporate_action_count": blocked_actions,
        "incomplete_source_count": incomplete_source,
        "top_count": len(top),
        "bottom_count": len(bottom),
        "spearman_rho": float(spearman.statistic),
        "spearman_p_value": float(spearman.pvalue),
        "top_mean_excess_pp": top_mean_pp,
        "top_median_excess_pp": top_median_pp,
        "bottom_mean_excess_pp": bottom_mean * 100.0,
        "top_minus_bottom_mean_excess_pp": spread_pp,
        "top_quintile_beat_rate": top_beat,
        "company_cluster_bootstrap_95ci_spread_pp": [
            value * 100.0 if value is not None else None for value in bootstrap_ci
        ],
        "leave_one_company_out_min_spread_pp": loo[0]["spread"] * 100.0 if loo else None,
        "leave_one_company_out_min_excluded_symbol": loo[0]["excluded_symbol"] if loo else None,
        "leave_one_company_out_max_spread_pp": loo[-1]["spread"] * 100.0 if loo else None,
        "overlapping_60_session_positions_within_symbol": overlap_count,
        "primary_rows": sample,
    }
