"""HG009 P004: no fabricated market horizon through unresolved NSE sessions."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p004_clock import (
    build_hg009_outcome_clock,
    load_p004_inputs,
    planned_horizon,
    validate_hg009_outcome_clock,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/hg009/hg009-p004-2026-outcome-clock-v1.json"


def _inputs() -> dict:
    calendar, original, selected, controls = load_p004_inputs(ROOT)
    return {
        "calendar": calendar,
        "original": original,
        "selected": selected,
        "controls": controls,
    }


def test_official_horizon_from_oct15_2026_h5_and_h20_special_session_block():
    inp = _inputs()
    report = build_hg009_outcome_clock(**inp)
    clock = report["planned_horizon_status"]
    assert report["first_eligible_entry_session"] == "2026-10-15"
    assert report["primary_descriptive_horizon_sessions"] == 20
    assert report["declared_arm_sizes"] == {
        "SELECTED": 100, "ONE_LANE": 100, "ZERO_LANE": 100
    }
    assert clock["1"]["official_exit_session"] == "2026-10-15"
    assert clock["5"]["official_exit_session"] == "2026-10-22"
    assert clock["5"]["date_scoped_holding_sessions"] == [
        "2026-10-15", "2026-10-16", "2026-10-19",
        "2026-10-21", "2026-10-22",
    ]
    assert clock["20"]["state"] == (
        "UNRESOLVED_EXCHANGE_SPECIAL_SESSION_BLOCKS_RESULT"
    )
    assert clock["20"]["provisional_exit_if_unresolved"] == "2026-11-13"
    assert clock["20"]["official_exit_session"] is None
    assert clock["20"]["date_scoped_holding_sessions"] is None
    assert clock["20"]["unresolved_special_dates_in_window"] == ["2026-11-08"]
    assert clock["60"]["state"] == "REQUIRES_NEW_OFFICIAL_FORWARD_CALENDAR"
    assert clock["60"]["frozen_calendar_available_sessions"] == 52
    assert clock["60"]["official_exit_session"] is None
    assert clock["60"]["date_scoped_holding_sessions"] is None
    assert all(row["outcome_eligible"] is False for row in clock.values())
    validate_hg009_outcome_clock(report, **inp)


def test_stock_returns_are_not_claimed_before_source_price_or_action_adjustment():
    inp = _inputs()
    report = build_hg009_outcome_clock(**inp)
    assert report["dividend_adjusted_equity_total_return_available"] is False
    assert report["source_return_labels_opened"] is False
    assert report["significance_or_causal_alpha_claim_authorized"] is False
    assert report["future_market_benchmark_return_calculated"] is False
    assert report["investable_order_or_fill_execution_verified"] is False
    assert report["portfolio_eligibility_allowed"] is False
    assert report["live_capital_allowed"] is False
    assert report["corporate_action_and_dividend_adjustment_required_for_total_returns"]
    assert report["missing_source_identity_slots_must_remain_in_denominator"]
    assert report["no_survivor_only_exclusion"]


def test_calendar_drift_retrospective_start_or_unapproved_horizon_blocked():
    inp = _inputs()
    bad_calendar = replace(inp["calendar"], sha256="e" * 64)
    with pytest.raises(AlphaContractError, match="calendar changed"):
        planned_horizon(
            bad_calendar, first_entry="2026-10-15", holding_sessions=5
        )
    with pytest.raises(AlphaContractError, match="first entry or frozen horizon"):
        planned_horizon(
            inp["calendar"], first_entry="2026-10-14", holding_sessions=5
        )
    with pytest.raises(AlphaContractError, match="first entry or frozen horizon"):
        planned_horizon(
            inp["calendar"], first_entry="2026-10-15", holding_sessions=30
        )


def test_source_cohort_change_not_retroactively_permitted():
    inp = _inputs()
    bad = copy.deepcopy(inp["selected"])
    bad["selected"][0]["symbol"] = "KNOWN_WINNER_FROM_FUTURE"
    with pytest.raises(AlphaContractError, match="cohort seal SHA"):
        build_hg009_outcome_clock(**{**inp, "selected": bad})


def test_original_protocol_packet_replays_bit_for_bit():
    inp = _inputs()
    expected = build_hg009_outcome_clock(**inp)
    observed = json.loads(REPORT.read_text(encoding="utf-8"))
    assert expected == observed
    assert expected["protocol_sha256"] == digest({
        key: value
        for key, value in expected.items() if key != "protocol_sha256"
    })
    proc = subprocess.run(
        [sys.executable, "scripts/materialize_hg009_p004_clock.py", "--check"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    summary = json.loads(proc.stdout)
    assert summary["state"] == "VERIFIED"
    assert summary["sha256"] == expected["protocol_sha256"]
