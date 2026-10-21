"""PF001 cash-only benchmark avoidance is not stock-selection alpha."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.pf001_a001_skill_guard import (
    PINNED,
    build_pf001_a001,
    load_source_receipts,
    materialize_pf001_a001,
    validate_pf001_a001,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / (
    "research/paper-funds/PF001/audits/pf001-a001-stock-selection-skill-v1.json"
)


def test_original_six_state_snapshot_files_replay_with_exact_git_blob_hashes():
    original, receipts = load_source_receipts(ROOT)
    assert set(receipts) == set(PINNED)
    assert len(original["VALIDATION_ATTRIBUTION"]["nav_history"]) == 23
    assert len(original["DEVELOPMENT_ATTRIBUTION"]["nav_history"]) == 23
    assert original["VALIDATION_FUND"]["last_session_date"] == "2026-10-19"
    assert original["VALIDATION_FUND"]["open_positions"] == {}
    assert original["VALIDATION_FUND"]["closed_positions"] == []
    assert original["VALIDATION_ATTRIBUTION"]["position_benchmarks"] == {}
    assert len(original["DEVELOPMENT_FUND"]["open_positions"]) == 1
    assert set(original["DEVELOPMENT_FUND"]["open_positions"]) == {"ARVIND"}
    assert original["VALIDATION_SUMMARY"]["closed_positions"] == 0
    for row in receipts.values():
        assert len(row["original_raw_bytes_sha256"]) == 64
        assert len(row["original_git_blob_sha"]) == 40
    report = build_pf001_a001(original, receipts)
    assert report["original_snapshots_copied_byte_for_byte"] is True


def test_validation_cash_vs_benchmark_performance_never_stock_picking_skill():
    report = materialize_pf001_a001(ROOT)
    validation = report["validation"]
    assert validation["observed_session_count"] == 23
    assert validation["entry_filled_event_count"] == 0
    assert validation["open_paper_stock_positions"] == 0
    assert validation["closed_paper_stock_positions"] == 0
    assert validation["average_cash_weight"] == pytest.approx(1.0)
    assert validation["estimated_average_paper_stock_exposure_fraction"] == 0
    assert validation["source_net_fund_return_fraction"] == 0
    assert validation["source_benchmark_price_index_return_fraction"] == pytest.approx(
        -0.04160497772675997
    )
    assert validation["legacy_benchmark_relative_active_pp"] == pytest.approx(
        4.160497772675997
    )
    assert validation["legacy_information_ratio_NOT_stock_selection"] == pytest.approx(
        2.665000784125277
    )
    assert validation["cash_avoidance_active_pp_if_all_cash"] == pytest.approx(
        4.160497772675997
    )
    assert validation["realized_stock_selection_excess_return_pp"] is None
    assert validation["stock_selection_skill_information_ratio"] is None
    assert validation["stock_selection_skill_win_rate"] is None
    assert validation["interpretation_state"] == (
        "NO_STOCK_SELECTION_OBSERVATIONS_CASH_ONLY"
    )


def test_development_one_unmatured_position_not_a_23_day_stock_skill_sample():
    report = materialize_pf001_a001(ROOT)
    dev = report["development"]
    assert dev["observed_session_count"] == 23
    assert dev["entry_filled_event_count"] == 1
    assert dev["open_paper_stock_positions"] == 1
    assert dev["closed_paper_stock_positions"] == 0
    assert dev["average_cash_weight"] == pytest.approx(0.9539452049888163)
    assert dev["legacy_benchmark_relative_active_pp"] == pytest.approx(
        3.5486335726759966
    )
    assert dev["legacy_information_ratio_NOT_stock_selection"] == pytest.approx(
        2.343576695608886
    )
    assert dev["cash_avoidance_active_pp_if_all_cash"] is None
    assert dev["stock_selection_skill_information_ratio"] is None
    assert dev["realized_stock_selection_excess_return_pp"] is None
    assert dev["interpretation_state"] == (
        "UNMATURED_SINGLE_PAPER_POSITION_NO_REALIZED_SELECTION_SKILL"
    )
    assert report["v1_information_ratio_is_not_invalid_math"] is True
    assert report["v1_information_ratio_does_not_measure_stock_selection_skill"]
    assert report["positive_stock_selection_alpha_evidence"] is False
    assert report["live_capital_allowed"] is False


def test_original_legacy_summary_and_fund_state_mismatches_fail_closed():
    original, receipts = load_source_receipts(ROOT)
    changed = copy.deepcopy(original)
    changed["VALIDATION_SUMMARY"]["information_ratio"] = 1000
    with pytest.raises(AlphaContractError, match="not reproducible"):
        build_pf001_a001(changed, receipts)
    changed = copy.deepcopy(original)
    changed["VALIDATION_FUND"]["cash_net"] -= 100000
    with pytest.raises(AlphaContractError, match="fund state corrupt"):
        build_pf001_a001(changed, receipts)
    changed = copy.deepcopy(original)
    changed["DEVELOPMENT_ATTRIBUTION"]["nav_history"][0][
        "cash_weight"
    ] = 0
    with pytest.raises(AlphaContractError, match="not reproducible"):
        build_pf001_a001(changed, receipts)


def test_signed_audit_report_reproduces_exactly_and_cli_does_not_change_fund():
    report = materialize_pf001_a001(ROOT)
    assert report["audit_sha256"] == digest({
        k: v for k, v in report.items() if k != "audit_sha256"
    })
    assert report == json.loads(REPORT.read_text(encoding="utf-8"))
    check = subprocess.run(
        [sys.executable, "scripts/materialize_pf001_a001.py", "--check"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    status = json.loads(check.stdout)
    assert status["stock_selection_alpha_supported"] is False
    assert status["live_capital_allowed"] is False
    assert status["state"] == "VERIFIED"
    invalid = copy.deepcopy(report)
    invalid["validation"]["stock_selection_skill_information_ratio"] = 2.665
    with pytest.raises(AlphaContractError, match="audit SHA changed"):
        validate_pf001_a001(invalid, ROOT)
