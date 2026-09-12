from __future__ import annotations

from datetime import date, timedelta

import pytest

from marketlab.analyst import seal_decision
from marketlab.paperfund import (
    CHECKPOINT_SESSION,
    MATURITY_SESSION,
    gross_nav,
    hard_invalidation_exit,
    mark_session,
    net_nav,
    new_fund,
    process_entry_batch,
)

POLICY_FROZEN_AT = "2026-09-11T18:46:13Z"


def make_decision(
    symbol: str,
    *,
    sector: str = "Industrials",
    role: str = "PROSPECTIVE_VALIDATION",
    timestamp: str = "2026-09-12T16:00:00+05:30",
    evidence_timestamp: str = "2026-09-12T15:00:00+05:30",
    h020_state: str = "PAPER_ENTRY_ELIGIBLE_TREND",
) -> dict:
    return seal_decision(
        {
            "schema_version": 1,
            "object_type": "ANALYST_DECISION",
            "live_capital_allowed": False,
            "decision_timestamp": timestamp,
            "symbol": symbol,
            "isin": f"INE{symbol[:3]:0<3}A01001",
            "company_name": f"{symbol} Ltd",
            "sector": sector,
            "benchmark": "NIFTY 500",
            "horizon_sessions": 60,
            "validation_role": role,
            "business_thesis": "Frozen thesis.",
            "thesis_evidence": [
                {
                    "source_ref": f"repo://research/{symbol}.json",
                    "available_at": evidence_timestamp,
                }
            ],
            "valuation_assumptions": {"status": "ACCEPTABLE"},
            "signal_states": {
                "h019": {"state": "MISSING", "evidence_ref": None},
                "h021": {"state": "MISSING_EXPECTATION_SIGNAL", "evidence_ref": None},
                "h013": {"state": "NOT_DUE", "evidence_ref": None},
                "h020": {"state": h020_state, "evidence_ref": "repo://h020.json"},
            },
            "market_regime": "BEARISH",
            "sector_regime": "NEUTRAL",
            "catalysts": [],
            "invalidations": [
                {"condition": "guidance withdrawn", "severity": "HARD"}
            ],
            "scenarios": {
                "bear": {"narrative": "Bear.", "benchmark_relative_return_pct": None},
                "base": {"narrative": "Base.", "benchmark_relative_return_pct": None},
                "bull": {"narrative": "Bull.", "benchmark_relative_return_pct": None},
            },
            "forecast": {
                "expected_benchmark_relative_return_pct": None,
                "p10_benchmark_relative_return_pct": None,
                "p50_benchmark_relative_return_pct": None,
                "p90_benchmark_relative_return_pct": None,
                "probability_beat_benchmark": None,
                "expected_mae_pct": None,
                "calibration_status": "UNAVAILABLE",
            },
            "missing_information": [],
            "analyst_action": "PORTFOLIO_ELIGIBLE",
        }
    )


def test_new_fund_starts_with_separate_gross_and_net_cash() -> None:
    state = new_fund(book="PROSPECTIVE_VALIDATION", policy_frozen_at=POLICY_FROZEN_AT)
    assert gross_nav(state) == 1_000_000.0
    assert net_nav(state) == 1_000_000.0
    assert state["open_positions"] == {}


def test_entry_uses_five_percent_unit_whole_shares_and_half_friction() -> None:
    state = new_fund(book="PROSPECTIVE_VALIDATION", policy_frozen_at=POLICY_FROZEN_AT)
    decision = make_decision("AAA")
    state = process_entry_batch(
        state,
        [decision],
        session_date="2026-09-14",
        open_prices={"AAA": 120.0},
    )
    position = state["open_positions"]["AAA"]
    assert position["target_notional"] == 50_000.0
    assert position["shares"] == 416
    assert position["cost_basis"] == 49_920.0
    assert position["entry_friction"] == pytest.approx(124.8)
    assert state["cash_gross"] == 950_080.0
    assert state["cash_net"] == pytest.approx(949_955.2)


def test_validation_book_rejects_pre_freeze_and_development_decisions() -> None:
    state = new_fund(book="PROSPECTIVE_VALIDATION", policy_frozen_at=POLICY_FROZEN_AT)
    old = make_decision(
        "OLD",
        timestamp="2026-09-11T16:00:00+05:30",
        evidence_timestamp="2026-09-11T15:00:00+05:30",
    )
    dev = make_decision("DEV", role="DEVELOPMENT")
    state = process_entry_batch(
        state,
        [old, dev],
        session_date="2026-09-14",
        open_prices={"OLD": 100.0, "DEV": 100.0},
    )
    reasons = {row["symbol"]: row["reason"] for row in state["rejected_entries"]}
    assert reasons == {
        "DEV": "BOOK_ROLE_MISMATCH",
        "OLD": "PRE_FREEZE_DECISION",
    }


def test_same_session_decision_cannot_get_open_fill() -> None:
    state = new_fund(book="PROSPECTIVE_VALIDATION", policy_frozen_at=POLICY_FROZEN_AT)
    decision = make_decision(
        "SAME",
        timestamp="2026-09-14T10:00:00+05:30",
        evidence_timestamp="2026-09-14T09:30:00+05:30",
    )
    state = process_entry_batch(
        state,
        [decision],
        session_date="2026-09-14",
        open_prices={"SAME": 100.0},
    )
    assert not state["open_positions"]
    assert state["rejected_entries"][0]["reason"] == "DECISION_NOT_BEFORE_ENTRY_SESSION"


def test_research_block_is_fail_closed() -> None:
    state = new_fund(book="PROSPECTIVE_VALIDATION", policy_frozen_at=POLICY_FROZEN_AT)
    decision = make_decision("BAD", h020_state="BLOCKED_DATA")
    state = process_entry_batch(
        state,
        [decision],
        session_date="2026-09-14",
        open_prices={"BAD": 100.0},
    )
    assert not state["open_positions"]
    assert state["rejected_entries"][0]["reason"] == "RESEARCH_INTEGRITY_BLOCK"


def test_sector_cap_accepts_five_units_and_rejects_sixth() -> None:
    state = new_fund(book="PROSPECTIVE_VALIDATION", policy_frozen_at=POLICY_FROZEN_AT)
    decisions = [make_decision(f"S{i}", sector="Power") for i in range(6)]
    prices = {decision["symbol"]: 100.0 for decision in decisions}
    state = process_entry_batch(
        state,
        decisions,
        session_date="2026-09-14",
        open_prices=prices,
    )
    assert len(state["open_positions"]) == 5
    assert state["rejected_entries"][0]["reason"] == "RISK_REJECTED_SECTOR_CAP"


def test_checkpoint_and_maturity_use_entry_session_as_holding_session_one() -> None:
    state = new_fund(book="PROSPECTIVE_VALIDATION", policy_frozen_at=POLICY_FROZEN_AT)
    decision = make_decision("HOLD")
    state = process_entry_batch(
        state,
        [decision],
        session_date="2026-09-14",
        open_prices={"HOLD": 100.0},
    )

    start = date(2026, 9, 14)
    state = mark_session(
        state,
        session_date=start.isoformat(),
        bars={"HOLD": {"close": 101.0, "high": 102.0, "low": 99.0}},
    )
    assert state["open_positions"]["HOLD"]["holding_sessions"] == 1

    for offset in range(1, CHECKPOINT_SESSION):
        session = start + timedelta(days=offset)
        state = mark_session(
            state,
            session_date=session.isoformat(),
            bars={"HOLD": {"close": 105.0, "high": 106.0, "low": 98.0}},
        )
    assert state["open_positions"]["HOLD"]["holding_sessions"] == CHECKPOINT_SESSION
    assert state["open_positions"]["HOLD"]["checkpoint_20"] is not None

    for offset in range(CHECKPOINT_SESSION, MATURITY_SESSION):
        session = start + timedelta(days=offset)
        state = mark_session(
            state,
            session_date=session.isoformat(),
            bars={"HOLD": {"close": 110.0, "high": 112.0, "low": 97.0}},
        )
    assert "HOLD" not in state["open_positions"]
    closed = state["closed_positions"][0]
    assert closed["holding_sessions"] == MATURITY_SESSION
    assert closed["exit_reason"] == "MATURED_60"
    assert closed["gross_return"] == pytest.approx(0.10)
    assert closed["net_return"] < closed["gross_return"]


def test_missing_bar_at_maturity_defers_exit_until_executable_mark() -> None:
    state = new_fund(book="PROSPECTIVE_VALIDATION", policy_frozen_at=POLICY_FROZEN_AT)
    decision = make_decision("SUSP")
    state = process_entry_batch(
        state,
        [decision],
        session_date="2026-09-14",
        open_prices={"SUSP": 100.0},
    )
    start = date(2026, 9, 14)
    state = mark_session(
        state,
        session_date=start.isoformat(),
        bars={"SUSP": {"close": 100.0}},
    )
    for offset in range(1, MATURITY_SESSION):
        session = start + timedelta(days=offset)
        bars = {} if offset == MATURITY_SESSION - 1 else {"SUSP": {"close": 100.0}}
        state = mark_session(state, session_date=session.isoformat(), bars=bars)
    assert state["open_positions"]["SUSP"]["maturity_pending"] is True

    next_session = start + timedelta(days=MATURITY_SESSION)
    state = mark_session(
        state,
        session_date=next_session.isoformat(),
        bars={"SUSP": {"close": 99.0}},
    )
    assert state["closed_positions"][0]["exit_reason"] == "MATURED_60"


def test_hard_invalidation_must_have_been_frozen_at_entry() -> None:
    state = new_fund(book="PROSPECTIVE_VALIDATION", policy_frozen_at=POLICY_FROZEN_AT)
    decision = make_decision("INV")
    state = process_entry_batch(
        state,
        [decision],
        session_date="2026-09-14",
        open_prices={"INV": 100.0},
    )
    with pytest.raises(ValueError, match="not frozen"):
        hard_invalidation_exit(
            state,
            decision=decision,
            session_date="2026-09-15",
            exit_price=95.0,
            condition="price fell",
        )

    state = hard_invalidation_exit(
        state,
        decision=decision,
        session_date="2026-09-15",
        exit_price=95.0,
        condition="guidance withdrawn",
    )
    assert state["closed_positions"][0]["exit_reason"].startswith("HARD_INVALIDATION")
