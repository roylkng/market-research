from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021_first_entry_intent import CALENDAR_PATH
from marketlab.h021_horizon_readiness import first_cohort_horizon_readiness
from marketlab.h021_muhurat_amendment import (
    NEW_H20_EXIT,
    build_h021_muhurat_calendar_amendment,
    validate_h021_muhurat_amendment,
    verified_h021_20_calendar_date_only,
)
from marketlab.hg009_p004_a1_muhurat import AMENDMENT_PATH
from scripts.check_h021_horizon_readiness import load_first_intent
from scripts.seal_h021_muhurat_clock import load_h021_source_clock


def _sources() -> tuple[dict, object, dict]:
    original = load_first_intent()
    calendar = load_calendar_snapshot(CALENDAR_PATH)
    hg009 = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
    return original, calendar, hg009


def test_actual_original_nse_circular_resolves_h021_20_calendar_only() -> None:
    result = load_h021_source_clock()
    assert result["frozen_h021_p003_intent_id"] == (
        "H021-P003-2026-10-09-FIRST-COHORT-v1"
    )
    assert result["first_entry_session_date_ist"] == "2026-10-12"
    assert result["original_unverified_weekday_only_20_session_exit"] == (
        "2026-11-09"
    )
    assert result["official_source_circular"] == "NSE/CMTR/76941"
    assert result["official_source_published_date"] == "2026-10-19"
    assert result["newly_verified_special_trading_session_date_ist"] == "2026-11-08"
    assert result["normal_market_first_trade_ist"] == "14:20"
    assert result["CAS_price_discovery_final_match_time_ist"] == "15:35"
    assert result["last_trade_modification_deadline_ist"] == "16:15"
    assert result["safest_original_source_capture_not_before_utc"] == (
        "2026-11-08T10:45:00+00:00"
    )
    assert result["H021_20_completed_sessions_calendar_exit_ist"] == NEW_H20_EXIT
    assert verified_h021_20_calendar_date_only(result) == NEW_H20_EXIT
    holding = result["H021_20_completed_sessions_count_entry_as_one"]
    assert len(holding) == len(set(holding)) == 20
    assert holding[0] == "2026-10-12"
    assert holding[-2] == "2026-11-06"
    assert holding[-1] == "2026-11-08"
    assert result["H021_20_calendar_date_source_verified"] is True
    assert result["H021_20_market_session_completed_as_of_circular"] is False
    assert result["H021_20_stock_and_Nifty500_original_price_source_verified"] is False
    assert result["H021_20_corporate_actions_dividend_and_cost_basis_verified"] is False
    assert result["H021_20_CAS_security_eligibility_and_price_method_verified"] is False
    validate_h021_muhurat_amendment(result)


def test_missing_2027_calendar_still_blocks_sixty_sessions_and_returns() -> None:
    result = load_h021_source_clock()
    assert result["H021_60_verified_2026_sessions_available_from_entry"] == 56
    assert result["H021_60_minimum_2027_additional_sessions"] == 4
    assert result["H021_60_exit_date_ist"] is None
    assert result["H021_60_official_2027_calendar_verified"] is False
    for flag in (
        "h021_forward_return_outcomes_opened",
        "h021_original_stock_selection_or_entry_date_changed",
        "h021_holding_horizon_or_benchmark_family_changed",
        "h021_expected_alpha_claim_published",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert result[flag] is False
    assert result["original_2026_calendar_immutably_retained"] is True


def test_original_frozen_h021_and_hg009_research_not_modified() -> None:
    original, calendar, hg009 = _sources()
    before = deepcopy((original, calendar.to_dict(), hg009))
    still_blocked = first_cohort_horizon_readiness(original, calendar)
    assert still_blocked["horizons"]["20"]["state"] == "BLOCKED"
    assert still_blocked["horizons"]["20"]["verified_exit_session_date"] is None
    amendment = build_h021_muhurat_calendar_amendment(
        original, calendar, hg009
    )
    assert amendment["H021_20_completed_sessions_calendar_exit_ist"] == (
        "2026-11-08"
    )
    assert (original, calendar.to_dict(), hg009) == before
    # The separate original HG009 decision has a different first entry.
    assert hg009["amended_H20_last_session"] == "2026-11-12"
    assert hg009["H20_new_outcomes_observed_or_calculated"] is False


def test_rejects_fake_special_session_and_posthoc_experiment_changes() -> None:
    intent, calendar, original_hg009 = _sources()
    fake = deepcopy(original_hg009)
    fake["prospective_special_session"]["regular_trading_open_ist"] = "09:15"
    with pytest.raises(ValueError, match="hash or contents"):
        build_h021_muhurat_calendar_amendment(intent, calendar, fake)

    fake = deepcopy(original_hg009)
    fake["amended_H20_last_session"] = "2026-11-13"
    with pytest.raises(ValueError, match="hash or contents"):
        build_h021_muhurat_calendar_amendment(intent, calendar, fake)

    forged_intent = deepcopy(intent)
    forged_intent["entry_plan"]["session_date_ist"] = "2026-10-13"
    with pytest.raises(ValueError, match="frozen first H021 entry date"):
        build_h021_muhurat_calendar_amendment(
            forged_intent, calendar, original_hg009
        )

    amended_calendar = replace(calendar, unresolved_special_dates=())
    with pytest.raises(ValueError, match="contents changed"):
        build_h021_muhurat_calendar_amendment(
            intent, amended_calendar, original_hg009
        )


def test_sealed_amendment_cannot_become_a_fake_outcome_or_trade() -> None:
    original = load_h021_source_clock()
    for field in (
        "H021_20_market_session_completed_as_of_circular",
        "H021_20_stock_and_Nifty500_original_price_source_verified",
        "h021_forward_return_outcomes_opened",
        "H021_60_official_2027_calendar_verified",
        "live_capital_allowed",
    ):
        counterfeit = deepcopy(original)
        counterfeit[field] = True
        with pytest.raises(ValueError, match="digest mismatch"):
            validate_h021_muhurat_amendment(counterfeit)


def test_cli_deterministic_seal_and_tamper_detection(tmp_path: Path) -> None:
    out = tmp_path / "verified-special-session-clock.json"
    command = [
        sys.executable, "scripts/seal_h021_muhurat_clock.py",
        "--out", str(out),
        "--require-20-calendar-date",
    ]
    completed = subprocess.run(
        command, check=True, capture_output=True, text=True,
    )
    response = json.loads(completed.stdout)
    assert response["verified_H021_H20_date"] == "2026-11-08"
    assert response["H021_H60_calendar_verified"] is False
    assert response["minimum_verified_2027_sessions_still_required"] == 4
    assert response["live_capital_allowed"] is False
    assert json.loads(out.read_text(encoding="utf-8")) == load_h021_source_clock()
    subprocess.run(
        command + ["--verify-existing"],
        check=True, capture_output=True, text=True,
    )
    out.write_text(out.read_text(encoding="utf-8") + "tampered", encoding="utf-8")
    failed = subprocess.run(
        command + ["--verify-existing"],
        check=False, capture_output=True, text=True,
    )
    assert failed.returncode != 0
    assert "packet differs" in failed.stderr
