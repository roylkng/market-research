from __future__ import annotations

import copy
import hashlib
import json
import math
from datetime import date, datetime
from zoneinfo import ZoneInfo

from marketlab.analyst import validate_decision

PF001_POLICY_ID = "PF001-v1"
BOOKS = {"DEVELOPMENT", "PROSPECTIVE_VALIDATION"}
INITIAL_NAV = 1_000_000.0
UNIT_WEIGHT = 0.05
SECTOR_CAP = 0.25
MAX_POSITIONS = 20
ROUND_TRIP_FRICTION = 0.005
ENTRY_FRICTION = ROUND_TRIP_FRICTION / 2.0
EXIT_FRICTION = ROUND_TRIP_FRICTION / 2.0
CHECKPOINT_SESSION = 20
MATURITY_SESSION = 60
INDIA_TZ = ZoneInfo("Asia/Kolkata")


def _parse_date(value: object) -> date:
    if not isinstance(value, str):
        raise TypeError("date must be ISO YYYY-MM-DD")
    return date.fromisoformat(value)


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("timestamp must be ISO string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be offset-aware")
    return parsed


def _event_id(payload: dict) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _append_event(state: dict, event_type: str, payload: dict) -> None:
    event = {
        "seq": len(state["events"]) + 1,
        "event_type": event_type,
        **payload,
    }
    event["event_id"] = _event_id(event)
    state["events"].append(event)


def _mutable_copy(state: dict) -> dict:
    updated = copy.deepcopy(state)
    updated.pop("state_sha256", None)
    return updated


def new_fund(*, book: str, policy_frozen_at: str) -> dict:
    if book not in BOOKS:
        raise ValueError(f"book must be one of {sorted(BOOKS)}")
    _parse_timestamp(policy_frozen_at)
    state = {
        "schema_version": 1,
        "fund_id": f"{PF001_POLICY_ID}-{book}",
        "policy_id": PF001_POLICY_ID,
        "book": book,
        "policy_frozen_at": policy_frozen_at,
        "live_capital_allowed": False,
        "initial_nav": INITIAL_NAV,
        "cash_gross": INITIAL_NAV,
        "cash_net": INITIAL_NAV,
        "last_session_date": None,
        "open_positions": {},
        "closed_positions": [],
        "rejected_entries": [],
        "events": [],
    }
    _append_event(
        state,
        "FUND_CREATED",
        {
            "book": book,
            "initial_nav": INITIAL_NAV,
            "policy_frozen_at": policy_frozen_at,
        },
    )
    return state


def gross_nav(state: dict) -> float:
    return float(state["cash_gross"]) + sum(
        float(position["shares"]) * float(position["current_price"])
        for position in state["open_positions"].values()
    )


def net_nav(state: dict) -> float:
    return float(state["cash_net"]) + sum(
        float(position["shares"]) * float(position["current_price"])
        for position in state["open_positions"].values()
    )


def sector_cost_basis(state: dict, sector: str) -> float:
    return sum(
        float(position["cost_basis"])
        for position in state["open_positions"].values()
        if position["sector"] == sector
    )


def _research_blocked(decision: dict) -> bool:
    for signal in decision["signal_states"].values():
        state = str(signal.get("state", "")).upper()
        if "BLOCKED" in state or state in {"REJECTED", "FAILED"}:
            return True
    return False


def _reject(state: dict, decision: dict, session_date: str, reason: str) -> None:
    rejection = {
        "decision_id": decision["decision_id"],
        "symbol": decision["symbol"],
        "sector": decision["sector"],
        "session_date": session_date,
        "reason": reason,
    }
    state["rejected_entries"].append(rejection)
    _append_event(state, "ENTRY_REJECTED", rejection)


def process_entry_batch(
    state: dict,
    decisions: list[dict],
    *,
    session_date: str,
    open_prices: dict[str, float],
) -> dict:
    updated = _mutable_copy(state)
    trade_date = _parse_date(session_date)
    if updated["last_session_date"] is not None:
        last_date = _parse_date(updated["last_session_date"])
        if trade_date <= last_date:
            raise ValueError("entry session must be later than last processed session")

    valid_decisions: list[dict] = []
    for decision in decisions:
        errors = validate_decision(decision)
        if errors:
            raise ValueError({"decision_id": decision.get("decision_id"), "errors": errors})
        valid_decisions.append(decision)

    valid_decisions.sort(key=lambda row: (row["decision_timestamp"], row["symbol"]))
    batch_nav = net_nav(updated)
    target_notional = batch_nav * UNIT_WEIGHT

    for decision in valid_decisions:
        symbol = str(decision["symbol"])
        decision_date = _parse_timestamp(decision["decision_timestamp"]).astimezone(INDIA_TZ).date()
        if decision["analyst_action"] != "PORTFOLIO_ELIGIBLE":
            _reject(updated, decision, session_date, "ANALYST_NOT_PORTFOLIO_ELIGIBLE")
            continue
        if decision["validation_role"] != updated["book"]:
            _reject(updated, decision, session_date, "BOOK_ROLE_MISMATCH")
            continue
        if (
            updated["book"] == "PROSPECTIVE_VALIDATION"
            and _parse_timestamp(decision["decision_timestamp"])
            <= _parse_timestamp(updated["policy_frozen_at"])
        ):
            _reject(updated, decision, session_date, "PRE_FREEZE_DECISION")
            continue
        if decision_date >= trade_date:
            _reject(updated, decision, session_date, "DECISION_NOT_BEFORE_ENTRY_SESSION")
            continue
        if _research_blocked(decision):
            _reject(updated, decision, session_date, "RESEARCH_INTEGRITY_BLOCK")
            continue
        if symbol in updated["open_positions"]:
            _reject(updated, decision, session_date, "NO_PYRAMIDING")
            continue
        if len(updated["open_positions"]) >= MAX_POSITIONS:
            _reject(updated, decision, session_date, "RISK_REJECTED_CAPACITY")
            continue

        price = open_prices.get(symbol)
        if price is None or not math.isfinite(float(price)) or float(price) <= 0:
            _reject(updated, decision, session_date, "MISSED_NO_EXECUTABLE_OPEN")
            continue
        price = float(price)
        shares = math.floor(target_notional / price)
        if shares < 1:
            _reject(updated, decision, session_date, "MISSED_INSUFFICIENT_UNIT_CAPITAL")
            continue

        cost_basis = shares * price
        sector_after = sector_cost_basis(updated, decision["sector"]) + cost_basis
        if sector_after > batch_nav * SECTOR_CAP + 1e-9:
            _reject(updated, decision, session_date, "RISK_REJECTED_SECTOR_CAP")
            continue

        entry_fee = cost_basis * ENTRY_FRICTION
        if cost_basis > float(updated["cash_gross"]) + 1e-9:
            _reject(updated, decision, session_date, "RISK_REJECTED_GROSS_CASH")
            continue
        if cost_basis + entry_fee > float(updated["cash_net"]) + 1e-9:
            _reject(updated, decision, session_date, "RISK_REJECTED_NET_CASH")
            continue

        updated["cash_gross"] -= cost_basis
        updated["cash_net"] -= cost_basis + entry_fee
        position = {
            "symbol": symbol,
            "isin": decision["isin"],
            "sector": decision["sector"],
            "analyst_decision_id": decision["decision_id"],
            "entry_decision_timestamp": decision["decision_timestamp"],
            "entry_session": session_date,
            "entry_price": price,
            "shares": shares,
            "target_notional": target_notional,
            "cost_basis": cost_basis,
            "entry_friction": entry_fee,
            "exit_friction": None,
            "current_price": price,
            "holding_sessions": 1,
            "last_mark_session": session_date,
            "checkpoint_20": None,
            "maturity_pending": False,
            "max_adverse_excursion_pct": 0.0,
            "max_favourable_excursion_pct": 0.0,
            "missing_mark_count": 0,
            "status": "OPEN",
        }
        updated["open_positions"][symbol] = position
        _append_event(
            updated,
            "ENTRY_FILLED",
            {
                "decision_id": decision["decision_id"],
                "symbol": symbol,
                "session_date": session_date,
                "price": price,
                "shares": shares,
                "cost_basis": cost_basis,
                "entry_friction": entry_fee,
                "target_notional": target_notional,
            },
        )

    return updated


def _close_position(
    state: dict,
    *,
    symbol: str,
    session_date: str,
    exit_price: float,
    reason: str,
) -> None:
    position = state["open_positions"].pop(symbol)
    proceeds = float(position["shares"]) * exit_price
    exit_fee = proceeds * EXIT_FRICTION
    state["cash_gross"] += proceeds
    state["cash_net"] += proceeds - exit_fee
    gross_return = exit_price / float(position["entry_price"]) - 1.0
    net_pnl = (
        proceeds
        - exit_fee
        - float(position["cost_basis"])
        - float(position["entry_friction"])
    )
    net_return = net_pnl / float(position["cost_basis"])
    closed = {
        **position,
        "status": "CLOSED",
        "exit_session": session_date,
        "exit_price": exit_price,
        "exit_friction": exit_fee,
        "exit_reason": reason,
        "gross_return": gross_return,
        "net_return": net_return,
    }
    state["closed_positions"].append(closed)
    _append_event(
        state,
        "POSITION_CLOSED",
        {
            "symbol": symbol,
            "session_date": session_date,
            "exit_price": exit_price,
            "reason": reason,
            "gross_return": gross_return,
            "net_return": net_return,
        },
    )


def mark_session(
    state: dict,
    *,
    session_date: str,
    bars: dict[str, dict[str, float]],
) -> dict:
    updated = _mutable_copy(state)
    market_date = _parse_date(session_date)
    if updated["last_session_date"] is not None:
        last_date = _parse_date(updated["last_session_date"])
        if market_date <= last_date:
            raise ValueError("mark session must be strictly later than prior marked session")

    to_close: list[tuple[str, float, str]] = []
    for symbol in sorted(updated["open_positions"]):
        position = updated["open_positions"][symbol]
        entry_date = _parse_date(position["entry_session"])
        if market_date < entry_date:
            raise ValueError("cannot mark a position before its entry session")

        bar = bars.get(symbol)
        if bar is None:
            position["missing_mark_count"] += 1
        else:
            close = float(bar["close"])
            if not math.isfinite(close) or close <= 0:
                raise ValueError(f"invalid close for {symbol}")
            position["current_price"] = close
            high = float(bar.get("high", close))
            low = float(bar.get("low", close))
            entry = float(position["entry_price"])
            adverse = low / entry - 1.0
            favourable = high / entry - 1.0
            position["max_adverse_excursion_pct"] = min(
                float(position["max_adverse_excursion_pct"]), adverse * 100.0
            )
            position["max_favourable_excursion_pct"] = max(
                float(position["max_favourable_excursion_pct"]), favourable * 100.0
            )

        if market_date > _parse_date(position["last_mark_session"]):
            position["holding_sessions"] += 1
            position["last_mark_session"] = session_date

        if (
            position["holding_sessions"] >= CHECKPOINT_SESSION
            and position["checkpoint_20"] is None
        ):
            current_price = float(position["current_price"])
            position["checkpoint_20"] = {
                "session_date": session_date,
                "holding_sessions": position["holding_sessions"],
                "gross_return": current_price / float(position["entry_price"]) - 1.0,
            }
            _append_event(
                updated,
                "CHECKPOINT_20",
                {
                    "symbol": symbol,
                    **position["checkpoint_20"],
                },
            )

        if position["holding_sessions"] >= MATURITY_SESSION:
            if bar is None:
                position["maturity_pending"] = True
            else:
                to_close.append((symbol, float(position["current_price"]), "MATURED_60"))

    for symbol, exit_price, reason in to_close:
        _close_position(
            updated,
            symbol=symbol,
            session_date=session_date,
            exit_price=exit_price,
            reason=reason,
        )

    updated["last_session_date"] = session_date
    _append_event(
        updated,
        "SESSION_MARKED",
        {
            "session_date": session_date,
            "gross_nav": gross_nav(updated),
            "net_nav": net_nav(updated),
            "open_positions": len(updated["open_positions"]),
        },
    )
    return updated


def hard_invalidation_exit(
    state: dict,
    *,
    decision: dict,
    session_date: str,
    exit_price: float,
    condition: str,
) -> dict:
    errors = validate_decision(decision)
    if errors:
        raise ValueError(errors)
    hard_conditions = {
        item["condition"]
        for item in decision["invalidations"]
        if item["severity"] == "HARD"
    }
    if condition not in hard_conditions:
        raise ValueError("condition was not frozen as a HARD invalidation")

    updated = _mutable_copy(state)
    symbol = decision["symbol"]
    position = updated["open_positions"].get(symbol)
    if position is None:
        raise ValueError("no open position for decision symbol")
    if position["analyst_decision_id"] != decision["decision_id"]:
        raise ValueError("decision does not match open position")
    if exit_price <= 0 or not math.isfinite(float(exit_price)):
        raise ValueError("exit_price must be positive and finite")

    _close_position(
        updated,
        symbol=symbol,
        session_date=session_date,
        exit_price=float(exit_price),
        reason=f"HARD_INVALIDATION:{condition}",
    )
    return updated
