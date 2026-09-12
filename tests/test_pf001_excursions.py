from __future__ import annotations

from copy import deepcopy

import pytest

from marketlab.paperfund import mark_session, new_fund, process_entry_batch
from marketlab.paperfund_state import validate_fund_state
from tests.test_paperfund import POLICY_FROZEN_AT, make_decision


def _entered_state() -> dict:
    state = new_fund(
        book="PROSPECTIVE_VALIDATION",
        policy_frozen_at=POLICY_FROZEN_AT,
    )
    decision = make_decision("EXC")
    return process_entry_batch(
        state,
        [decision],
        session_date="2026-09-14",
        open_prices={"EXC": 100.0},
    )


def test_close_only_mark_does_not_invent_mae_mfe() -> None:
    state = _entered_state()
    state = mark_session(
        state,
        session_date="2026-09-14",
        bars={"EXC": {"close": 105.0}},
    )
    position = state["open_positions"]["EXC"]
    assert position["max_adverse_excursion_pct"] is None
    assert position["max_favourable_excursion_pct"] is None
    assert position["excursion_observed_sessions"] == 0
    assert position["excursion_missing_sessions"] == 1
    assert validate_fund_state(state) == []


def test_real_high_low_populates_excursions_and_coverage() -> None:
    state = _entered_state()
    state = mark_session(
        state,
        session_date="2026-09-14",
        bars={"EXC": {"close": 102.0}},
    )
    state = mark_session(
        state,
        session_date="2026-09-15",
        bars={"EXC": {"close": 104.0, "high": 110.0, "low": 90.0}},
    )
    position = state["open_positions"]["EXC"]
    assert position["max_adverse_excursion_pct"] == pytest.approx(-10.0)
    assert position["max_favourable_excursion_pct"] == pytest.approx(10.0)
    assert position["excursion_observed_sessions"] == 1
    assert position["excursion_missing_sessions"] == 1
    assert validate_fund_state(state) == []


def test_partial_high_low_is_rejected() -> None:
    state = _entered_state()
    with pytest.raises(ValueError, match="high and low must be provided together"):
        mark_session(
            state,
            session_date="2026-09-14",
            bars={"EXC": {"close": 102.0, "high": 110.0}},
        )


def test_inconsistent_high_low_close_is_rejected() -> None:
    state = _entered_state()
    with pytest.raises(ValueError, match="inconsistent high/low/close"):
        mark_session(
            state,
            session_date="2026-09-14",
            bars={"EXC": {"close": 112.0, "high": 110.0, "low": 90.0}},
        )


def test_state_validator_detects_forged_excursion_without_observation() -> None:
    state = _entered_state()
    forged = deepcopy(state)
    position = forged["open_positions"]["EXC"]
    position["max_adverse_excursion_pct"] = -5.0
    errors = validate_fund_state(forged)
    assert any("require observed high/low sessions" in error for error in errors)
