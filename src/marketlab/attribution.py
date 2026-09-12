from __future__ import annotations

import copy
import math
import statistics
from datetime import date
from typing import Any

from marketlab.paperfund import INITIAL_NAV, gross_nav, net_nav
from marketlab.paperfund_state import validate_fund_state

ATTRIBUTION_ID = "PF001-ATTR-v1"
PRIMARY_BENCHMARK_BASIS = "PRICE"


def _parse_date(value: object) -> date:
    if not isinstance(value, str):
        raise TypeError("session date must be ISO YYYY-MM-DD")
    return date.fromisoformat(value)


def _positive_number(value: object, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{field} must be numeric")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(f"{field} must be positive and finite")
    return parsed


def _benchmark_bar(bar: dict[str, Any]) -> tuple[float, float]:
    if not isinstance(bar, dict):
        raise TypeError("benchmark_bar must be an object")
    return (
        _positive_number(bar.get("open"), "benchmark open"),
        _positive_number(bar.get("close"), "benchmark close"),
    )


def _fund_errors(fund_state: dict) -> None:
    errors = validate_fund_state(fund_state)
    if errors:
        raise ValueError({"fund_state_errors": errors})


def new_attribution_state(
    fund_state: dict,
    *,
    benchmark_name: str,
    benchmark_basis: str,
    benchmark_source_ref: str,
) -> dict:
    _fund_errors(fund_state)
    if not isinstance(benchmark_name, str) or not benchmark_name.strip():
        raise ValueError("benchmark_name must be non-empty")
    if benchmark_basis != PRIMARY_BENCHMARK_BASIS:
        raise ValueError(
            "PF001 attribution-v1 requires PRICE basis because the official NIFTY 500 TRI "
            "series does not provide a genuine session-open TRI value"
        )
    if not isinstance(benchmark_source_ref, str) or not benchmark_source_ref.strip():
        raise ValueError("benchmark_source_ref must be non-empty")

    return {
        "schema_version": 1,
        "attribution_id": f"{ATTRIBUTION_ID}-{fund_state['book']}",
        "fund_id": fund_state["fund_id"],
        "policy_id": fund_state["policy_id"],
        "book": fund_state["book"],
        "live_capital_allowed": False,
        "benchmark": {
            "name": benchmark_name,
            "basis": benchmark_basis,
            "source_ref": benchmark_source_ref,
            "dividend_mismatch": True,
        },
        "first_session_date": None,
        "benchmark_start_open": None,
        "benchmark_current_close": None,
        "last_session_date": None,
        "last_fund_event_seq": 0,
        "position_benchmarks": {},
        "closed_position_attribution": [],
        "nav_history": [],
        "peak_gross_nav": INITIAL_NAV,
        "peak_net_nav": INITIAL_NAV,
        "max_gross_drawdown_pct": 0.0,
        "max_net_drawdown_pct": 0.0,
        "blocked_components": [
            "CF_A_TIMING:BLOCKED_BY_SELECTION_TIMESTAMP_CONTRACT",
            "CF_B_CONSTRAINTS:NOT_IMPLEMENTED_IN_ATTRIBUTION_V1",
        ],
    }


def _closed_position_for_event(
    fund_state: dict,
    *,
    symbol: str,
    session_date: str,
) -> dict:
    matches = [
        position
        for position in fund_state["closed_positions"]
        if position.get("symbol") == symbol
        and position.get("exit_session") == session_date
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one closed position for {symbol} on {session_date}, got {len(matches)}"
        )
    return matches[0]


def _open_position_for_symbol(fund_state: dict, symbol: str) -> dict:
    position = fund_state["open_positions"].get(symbol)
    if not isinstance(position, dict):
        raise ValueError(f"no open position for checkpoint symbol {symbol}")
    return position


def _event_session(event: dict) -> str | None:
    value = event.get("session_date")
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("fund event session_date must be ISO string")
    _parse_date(value)
    return value


def _record_entry(
    attribution: dict,
    event: dict,
    *,
    benchmark_open: float,
) -> None:
    decision_id = event.get("decision_id")
    if not isinstance(decision_id, str) or not decision_id:
        raise ValueError("ENTRY_FILLED event missing decision_id")
    if decision_id in attribution["position_benchmarks"]:
        raise ValueError(f"duplicate attribution entry for {decision_id}")
    attribution["position_benchmarks"][decision_id] = {
        "decision_id": decision_id,
        "symbol": event["symbol"],
        "entry_session": event["session_date"],
        "benchmark_entry_open": benchmark_open,
        "checkpoint_20": None,
        "exit": None,
    }


def _record_checkpoint(
    attribution: dict,
    fund_state: dict,
    event: dict,
    *,
    benchmark_close: float,
) -> None:
    symbol = str(event["symbol"])
    position = _open_position_for_symbol(fund_state, symbol)
    decision_id = str(position["analyst_decision_id"])
    link = attribution["position_benchmarks"].get(decision_id)
    if not isinstance(link, dict):
        raise ValueError(f"missing benchmark entry link for {decision_id}")
    if link["checkpoint_20"] is not None:
        raise ValueError(f"duplicate checkpoint attribution for {decision_id}")
    benchmark_return = benchmark_close / float(link["benchmark_entry_open"]) - 1.0
    stock_return = float(event["gross_return"])
    link["checkpoint_20"] = {
        "session_date": event["session_date"],
        "stock_gross_return": stock_return,
        "benchmark_return": benchmark_return,
        "gross_excess_pp": (stock_return - benchmark_return) * 100.0,
    }


def _record_exit(
    attribution: dict,
    fund_state: dict,
    event: dict,
    *,
    benchmark_close: float,
) -> None:
    symbol = str(event["symbol"])
    position = _closed_position_for_event(
        fund_state,
        symbol=symbol,
        session_date=str(event["session_date"]),
    )
    decision_id = str(position["analyst_decision_id"])
    link = attribution["position_benchmarks"].get(decision_id)
    if not isinstance(link, dict):
        raise ValueError(f"missing benchmark entry link for {decision_id}")
    if link["exit"] is not None:
        raise ValueError(f"duplicate exit attribution for {decision_id}")

    benchmark_return = benchmark_close / float(link["benchmark_entry_open"]) - 1.0
    gross_return = float(position["gross_return"])
    net_return = float(position["net_return"])
    row = {
        "decision_id": decision_id,
        "symbol": symbol,
        "entry_session": position["entry_session"],
        "exit_session": position["exit_session"],
        "exit_reason": position["exit_reason"],
        "stock_gross_return": gross_return,
        "stock_net_return": net_return,
        "benchmark_return": benchmark_return,
        "gross_excess_pp": (gross_return - benchmark_return) * 100.0,
        "net_excess_pp": (net_return - benchmark_return) * 100.0,
        "net_beat_benchmark": net_return > benchmark_return,
        "max_adverse_excursion_pct": position["max_adverse_excursion_pct"],
        "max_favourable_excursion_pct": position["max_favourable_excursion_pct"],
    }
    link["exit"] = {
        "session_date": position["exit_session"],
        "benchmark_exit_close": benchmark_close,
        "benchmark_return": benchmark_return,
    }
    attribution["closed_position_attribution"].append(row)


def _process_new_events(
    attribution: dict,
    fund_state: dict,
    *,
    session_date: str,
    benchmark_open: float,
    benchmark_close: float,
) -> None:
    events = fund_state["events"]
    last_seq = int(attribution["last_fund_event_seq"])
    if last_seq > len(events):
        raise ValueError("attribution event cursor is ahead of fund event ledger")

    current_date = _parse_date(session_date)
    new_events = events[last_seq:]
    for expected_seq, event in enumerate(new_events, last_seq + 1):
        if event.get("seq") != expected_seq:
            raise ValueError("fund event sequence changed under attribution")
        event_session = _event_session(event)
        event_date = _parse_date(event_session) if event_session is not None else None
        event_type = event.get("event_type")
        if event_date is not None and event_date > current_date:
            raise ValueError("fund event is future-dated relative to attribution session")
        if (
            event_date is not None
            and event_date < current_date
            and event_type in {"ENTRY_FILLED", "CHECKPOINT_20", "POSITION_CLOSED"}
        ):
            raise ValueError(
                f"attribution missed prior-session {event_type} event on {event_session}"
            )
        if event_session != session_date:
            continue
        if event_type == "ENTRY_FILLED":
            _record_entry(attribution, event, benchmark_open=benchmark_open)
        elif event_type == "CHECKPOINT_20":
            _record_checkpoint(
                attribution,
                fund_state,
                event,
                benchmark_close=benchmark_close,
            )
        elif event_type == "POSITION_CLOSED":
            _record_exit(
                attribution,
                fund_state,
                event,
                benchmark_close=benchmark_close,
            )

    attribution["last_fund_event_seq"] = len(events)


def advance_attribution(
    attribution_state: dict,
    fund_state: dict,
    *,
    session_date: str,
    benchmark_bar: dict[str, Any],
) -> dict:
    _fund_errors(fund_state)
    current_date = _parse_date(session_date)
    if fund_state["fund_id"] != attribution_state.get("fund_id"):
        raise ValueError("fund state does not match attribution fund_id")
    if fund_state.get("last_session_date") != session_date:
        raise ValueError("fund state must be marked through the attribution session")

    previous_session = attribution_state.get("last_session_date")
    if previous_session is not None and current_date <= _parse_date(previous_session):
        raise ValueError("attribution session must advance strictly")

    benchmark_open, benchmark_close = _benchmark_bar(benchmark_bar)
    updated = copy.deepcopy(attribution_state)
    if updated["first_session_date"] is None:
        updated["first_session_date"] = session_date
        updated["benchmark_start_open"] = benchmark_open

    _process_new_events(
        updated,
        fund_state,
        session_date=session_date,
        benchmark_open=benchmark_open,
        benchmark_close=benchmark_close,
    )

    fund_gross_nav = gross_nav(fund_state)
    fund_net_nav = net_nav(fund_state)
    start_open = float(updated["benchmark_start_open"])
    benchmark_return = benchmark_close / start_open - 1.0
    benchmark_nav = INITIAL_NAV * (1.0 + benchmark_return)
    fund_gross_return = fund_gross_nav / INITIAL_NAV - 1.0
    fund_net_return = fund_net_nav / INITIAL_NAV - 1.0

    if updated["nav_history"]:
        prior = updated["nav_history"][-1]
        daily_gross_return = fund_gross_nav / float(prior["gross_nav"]) - 1.0
        daily_net_return = fund_net_nav / float(prior["net_nav"]) - 1.0
        daily_benchmark_return = benchmark_close / float(prior["benchmark_close"]) - 1.0
    else:
        daily_gross_return = fund_gross_return
        daily_net_return = fund_net_return
        daily_benchmark_return = benchmark_return

    updated["peak_gross_nav"] = max(float(updated["peak_gross_nav"]), fund_gross_nav)
    updated["peak_net_nav"] = max(float(updated["peak_net_nav"]), fund_net_nav)
    gross_drawdown_pct = (
        fund_gross_nav / float(updated["peak_gross_nav"]) - 1.0
    ) * 100.0
    net_drawdown_pct = (
        fund_net_nav / float(updated["peak_net_nav"]) - 1.0
    ) * 100.0
    updated["max_gross_drawdown_pct"] = min(
        float(updated["max_gross_drawdown_pct"]), gross_drawdown_pct
    )
    updated["max_net_drawdown_pct"] = min(
        float(updated["max_net_drawdown_pct"]), net_drawdown_pct
    )

    cash_weight = float(fund_state["cash_net"]) / fund_net_nav
    updated["nav_history"].append(
        {
            "session_date": session_date,
            "gross_nav": fund_gross_nav,
            "net_nav": fund_net_nav,
            "benchmark_nav": benchmark_nav,
            "benchmark_close": benchmark_close,
            "gross_portfolio_return": fund_gross_return,
            "net_portfolio_return": fund_net_return,
            "benchmark_return": benchmark_return,
            "gross_active_pp": (fund_gross_return - benchmark_return) * 100.0,
            "net_active_pp": (fund_net_return - benchmark_return) * 100.0,
            "cost_drag_pp": (fund_gross_return - fund_net_return) * 100.0,
            "cash_weight": cash_weight,
            "gross_drawdown_pct": gross_drawdown_pct,
            "net_drawdown_pct": net_drawdown_pct,
            "daily_gross_return": daily_gross_return,
            "daily_net_return": daily_net_return,
            "daily_benchmark_return": daily_benchmark_return,
            "daily_net_active_return": daily_net_return - daily_benchmark_return,
        }
    )
    updated["benchmark_current_close"] = benchmark_close
    updated["last_session_date"] = session_date
    return updated


def summarize_attribution(attribution_state: dict) -> dict:
    history = attribution_state.get("nav_history")
    if not isinstance(history, list):
        raise TypeError("nav_history must be a list")
    closed = attribution_state.get("closed_position_attribution")
    if not isinstance(closed, list):
        raise TypeError("closed_position_attribution must be a list")

    summary: dict[str, Any] = {
        "attribution_id": attribution_state["attribution_id"],
        "fund_id": attribution_state["fund_id"],
        "sessions": len(history),
        "benchmark": copy.deepcopy(attribution_state["benchmark"]),
        "closed_positions": len(closed),
        "max_gross_drawdown_pct": attribution_state["max_gross_drawdown_pct"],
        "max_net_drawdown_pct": attribution_state["max_net_drawdown_pct"],
        "blocked_components": list(attribution_state["blocked_components"]),
        "information_ratio": None,
    }
    if not history:
        summary.update(
            {
                "gross_portfolio_return": None,
                "net_portfolio_return": None,
                "benchmark_return": None,
                "gross_active_pp": None,
                "net_active_pp": None,
                "cost_drag_pp": None,
                "current_cash_weight": None,
                "average_cash_weight": None,
                "mean_gross_excess_pp": None,
                "median_gross_excess_pp": None,
                "mean_net_excess_pp": None,
                "median_net_excess_pp": None,
                "net_benchmark_beat_rate": None,
            }
        )
        return summary

    latest = history[-1]
    summary.update(
        {
            "gross_portfolio_return": latest["gross_portfolio_return"],
            "net_portfolio_return": latest["net_portfolio_return"],
            "benchmark_return": latest["benchmark_return"],
            "gross_active_pp": latest["gross_active_pp"],
            "net_active_pp": latest["net_active_pp"],
            "cost_drag_pp": latest["cost_drag_pp"],
            "current_cash_weight": latest["cash_weight"],
            "average_cash_weight": statistics.fmean(row["cash_weight"] for row in history),
        }
    )

    if closed:
        gross_excess = [float(row["gross_excess_pp"]) for row in closed]
        net_excess = [float(row["net_excess_pp"]) for row in closed]
        summary.update(
            {
                "mean_gross_excess_pp": statistics.fmean(gross_excess),
                "median_gross_excess_pp": statistics.median(gross_excess),
                "mean_net_excess_pp": statistics.fmean(net_excess),
                "median_net_excess_pp": statistics.median(net_excess),
                "net_benchmark_beat_rate": statistics.fmean(
                    1.0 if row["net_beat_benchmark"] else 0.0 for row in closed
                ),
            }
        )
    else:
        summary.update(
            {
                "mean_gross_excess_pp": None,
                "median_gross_excess_pp": None,
                "mean_net_excess_pp": None,
                "median_net_excess_pp": None,
                "net_benchmark_beat_rate": None,
            }
        )

    if len(history) >= 20:
        active_returns = [float(row["daily_net_active_return"]) for row in history]
        active_std = statistics.stdev(active_returns)
        if active_std > 0:
            summary["information_ratio"] = (
                statistics.fmean(active_returns) / active_std * math.sqrt(252.0)
            )

    return summary
