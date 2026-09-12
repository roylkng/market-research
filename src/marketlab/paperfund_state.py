from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime

from marketlab.paperfund import BOOKS, INITIAL_NAV, PF001_POLICY_ID

REQUIRED_STATE_KEYS = {
    "schema_version",
    "fund_id",
    "policy_id",
    "book",
    "policy_frozen_at",
    "live_capital_allowed",
    "initial_nav",
    "cash_gross",
    "cash_net",
    "last_session_date",
    "open_positions",
    "closed_positions",
    "rejected_entries",
    "events",
}


def _event_id(event: dict) -> str:
    payload = dict(event)
    payload.pop("event_id", None)
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _state_digest_payload(state: dict) -> dict:
    payload = dict(state)
    payload.pop("state_sha256", None)
    return payload


def _raw_state_sha256(state: dict) -> str:
    raw = json.dumps(
        _state_digest_payload(state),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _validate_excursions(position: dict, label: str, errors: list[str]) -> None:
    observed = position.get("excursion_observed_sessions")
    missing = position.get("excursion_missing_sessions")
    for field, value in (
        ("excursion_observed_sessions", observed),
        ("excursion_missing_sessions", missing),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{label} {field} must be a non-negative integer")

    adverse = position.get("max_adverse_excursion_pct")
    favourable = position.get("max_favourable_excursion_pct")
    for field, value in (
        ("max_adverse_excursion_pct", adverse),
        ("max_favourable_excursion_pct", favourable),
    ):
        if value is not None and not _is_finite_number(value):
            errors.append(f"{label} {field} must be finite or null")

    if isinstance(observed, int) and observed == 0 and (
        adverse is not None or favourable is not None
    ):
        errors.append(f"{label} excursion values require observed high/low sessions")
    elif (
        isinstance(observed, int)
        and observed > 0
        and (adverse is None or favourable is None)
    ):
        errors.append(f"{label} observed excursions require both MAE and MFE")


def validate_fund_state(state: dict) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_STATE_KEYS - state.keys()
    if missing:
        errors.append(f"missing state fields: {sorted(missing)}")
        return errors

    if state.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if state.get("policy_id") != PF001_POLICY_ID:
        errors.append(f"policy_id must equal {PF001_POLICY_ID}")
    book = state.get("book")
    if book not in BOOKS:
        errors.append(f"book must be one of {sorted(BOOKS)}")
    if state.get("fund_id") != f"{PF001_POLICY_ID}-{book}":
        errors.append("fund_id does not match policy/book")
    if state.get("live_capital_allowed") is not False:
        errors.append("live_capital_allowed must be false")
    if state.get("initial_nav") != INITIAL_NAV:
        errors.append(f"initial_nav must equal {INITIAL_NAV}")

    try:
        frozen_at = datetime.fromisoformat(state["policy_frozen_at"])
    except (TypeError, ValueError):
        errors.append("policy_frozen_at must be an ISO timestamp")
    else:
        if frozen_at.tzinfo is None:
            errors.append("policy_frozen_at must be offset-aware")

    for field in ("cash_gross", "cash_net"):
        value = state.get(field)
        if not _is_finite_number(value) or float(value) < -1e-6:
            errors.append(f"{field} must be finite and non-negative")

    last_session = state.get("last_session_date")
    if last_session is not None:
        try:
            date.fromisoformat(last_session)
        except (TypeError, ValueError):
            errors.append("last_session_date must be null or ISO date")

    open_positions = state.get("open_positions")
    if not isinstance(open_positions, dict):
        errors.append("open_positions must be an object")
    else:
        for symbol, position in open_positions.items():
            if not isinstance(symbol, str) or not isinstance(position, dict):
                errors.append("open_positions must map symbols to objects")
                continue
            if position.get("symbol") != symbol:
                errors.append(f"open position key mismatch for {symbol}")
            shares = position.get("shares")
            if not isinstance(shares, int) or isinstance(shares, bool) or shares <= 0:
                errors.append(f"open position {symbol} shares must be positive integer")
            for field in ("entry_price", "cost_basis", "current_price"):
                value = position.get(field)
                if not _is_finite_number(value) or float(value) <= 0:
                    errors.append(f"open position {symbol} {field} must be positive")
            holding = position.get("holding_sessions")
            if not isinstance(holding, int) or isinstance(holding, bool) or holding < 1:
                errors.append(f"open position {symbol} holding_sessions invalid")
            if position.get("status") != "OPEN":
                errors.append(f"open position {symbol} status must equal OPEN")
            if not isinstance(position.get("analyst_decision_id"), str):
                errors.append(f"open position {symbol} analyst_decision_id missing")
            _validate_excursions(position, f"open position {symbol}", errors)

    closed = state.get("closed_positions")
    if not isinstance(closed, list):
        errors.append("closed_positions must be a list")
    else:
        for index, position in enumerate(closed):
            if not isinstance(position, dict) or position.get("status") != "CLOSED":
                errors.append(f"closed_positions[{index}] must have CLOSED status")
                continue
            _validate_excursions(position, f"closed_positions[{index}]", errors)

    rejected = state.get("rejected_entries")
    if not isinstance(rejected, list):
        errors.append("rejected_entries must be a list")

    events = state.get("events")
    if not isinstance(events, list) or not events:
        errors.append("events must be a non-empty list")
    else:
        seen_ids: set[str] = set()
        for expected_seq, event in enumerate(events, 1):
            if not isinstance(event, dict):
                errors.append(f"events[{expected_seq - 1}] must be an object")
                continue
            if event.get("seq") != expected_seq:
                errors.append(f"event sequence broken at {expected_seq}")
            event_id = event.get("event_id")
            if event_id != _event_id(event):
                errors.append(f"event hash mismatch at sequence {expected_seq}")
            if event_id in seen_ids:
                errors.append(f"duplicate event_id at sequence {expected_seq}")
            if isinstance(event_id, str):
                seen_ids.add(event_id)

    stored_sha = state.get("state_sha256")
    if stored_sha is not None and (
        not isinstance(stored_sha, str) or stored_sha != _raw_state_sha256(state)
    ):
        errors.append("state_sha256 does not match canonical fund state")

    return errors


def state_sha256(state: dict) -> str:
    errors = validate_fund_state(
        {key: value for key, value in state.items() if key != "state_sha256"}
    )
    if errors:
        raise ValueError(errors)
    return _raw_state_sha256(state)
