from __future__ import annotations

import pytest

from marketlab.dr001_post_h021 import build_post_h021_evidence_pack


SYMBOLS = ["COFORGE", "AUROPHARMA", "MOTHERSON", "HINDALCO", "PERSISTENT"]


def _pre() -> dict:
    values = {
        "COFORGE": 26.2,
        "AUROPHARMA": 32.1,
        "MOTHERSON": 45.1,
        "HINDALCO": 87.4,
        "PERSISTENT": 20.6,
    }
    return {
        "pack_id": "DR001-PRE-H021-EVIDENCE-2026-10-04-v1",
        "companies": [
            {
                "symbol": symbol,
                "rr001": {"forward_pe": 20.0},
                "fq001": {"quality_score": 50.0},
                "nv001": {"normalized_valuation_score": 50.0},
                "forward_eps_uplift_vs_fy26_trailing_pct": values[symbol],
            }
            for symbol in SYMBOLS
        ],
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _comparison() -> dict:
    revisions = {
        "COFORGE": 4.0,
        "AUROPHARMA": 1.0,
        "MOTHERSON": 0.0,
        "HINDALCO": -2.0,
        "PERSISTENT": None,
    }
    return {
        "hypothesis_id": "H021",
        "prior_capture_date_ist": "2026-09-11",
        "current_capture_date_ist": "2026-10-09",
        "revision_observations": [
            {
                "symbol": symbol,
                "prior_capture_date": "2026-09-11",
                "current_capture_date": "2026-10-09",
                "eps_revision_pct": revisions[symbol],
                "primary_signal_available": revisions[symbol] is not None,
                "primary_signal_reason": (
                    "ELIGIBLE" if revisions[symbol] is not None else "PERIOD_END_MISMATCH"
                ),
            }
            for symbol in SYMBOLS
        ],
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }


def _gate() -> dict:
    states = {
        "COFORGE": ("STRONG_POSITIVE_PRIMARY", "ADVANCE_TO_VALUATION_AND_RED_TEAM", True, True),
        "AUROPHARMA": ("POSITIVE_NOT_PRIMARY", "REMAIN_WATCH_POSITIVE_NOT_PRIMARY", False, False),
        "MOTHERSON": ("FLAT", "THESIS_CHALLENGE_REMAIN_WATCH", False, False),
        "HINDALCO": ("NEGATIVE", "THESIS_CHALLENGE_REMAIN_WATCH", False, False),
        "PERSISTENT": ("NO_PRIMARY_SIGNAL", "REMAIN_WATCH_DATA_INCOMPATIBLE", False, False),
    }
    return {
        "gate_id": "DR001-H021-TIER-A-GATE-v1",
        "companies": [
            {
                "symbol": symbol,
                "gate_state": states[symbol][0],
                "research_action": states[symbol][1],
                "valuation_red_team_allowed": states[symbol][2],
                "primary_top_decile": states[symbol][3],
            }
            for symbol in SYMBOLS
        ],
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_pack_joins_frozen_evidence_without_new_decision_rule() -> None:
    result = build_post_h021_evidence_pack(_pre(), _comparison(), _gate())
    rows = {row["symbol"]: row for row in result["companies"]}

    assert rows["COFORGE"]["h021"]["revision_sign"] == "POSITIVE"
    assert rows["COFORGE"]["dr001_gate"]["research_action"] == (
        "ADVANCE_TO_VALUATION_AND_RED_TEAM"
    )
    assert rows["MOTHERSON"]["forward_earnings_dependency_state"] == (
        "FORWARD_EARNINGS_DEPENDENCY_HIGH"
    )
    assert rows["HINDALCO"]["h021"]["revision_sign"] == "NEGATIVE"
    assert rows["PERSISTENT"]["h021"]["revision_sign"] == "UNAVAILABLE"
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False


def test_dependency_thresholds_are_frozen_and_descriptive() -> None:
    result = build_post_h021_evidence_pack(_pre(), _comparison(), _gate())
    rows = {row["symbol"]: row for row in result["companies"]}
    assert rows["PERSISTENT"]["forward_earnings_dependency_state"] == (
        "FORWARD_EARNINGS_DEPENDENCY_MODERATE"
    )
    assert rows["HINDALCO"]["forward_earnings_dependency_state"] == (
        "FORWARD_EARNINGS_DEPENDENCY_HIGH"
    )


def test_pack_fails_closed_if_tier_a_symbol_set_changes() -> None:
    pre = _pre()
    pre["companies"].pop()
    with pytest.raises(ValueError, match="pre-H021 symbols changed"):
        build_post_h021_evidence_pack(pre, _comparison(), _gate())
