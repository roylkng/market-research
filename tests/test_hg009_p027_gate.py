"""Regression: H1 disappointment is recorded, not optimized away."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p027_gate import (
    build_decision_gate,
    load_p027_sources,
    materialize,
    verify_packet,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/hg009/hg009-p027-h1-no-alpha-next-cohort-gate-v1.json"


def test_frozen_h1_underperformed_both_controls_with_all_missing_sources_preserved():
    x = materialize(ROOT)
    counts = x["H1_arm_diagnostics"]
    assert x["source_companies_frozen"] == 300
    assert counts["SELECTED"]["source_priced_h1"] == 99
    assert counts["SELECTED"]["h1_missing_source"] == 1
    assert counts["ONE_LANE"]["source_priced_h1"] == 99
    assert counts["ONE_LANE"]["h1_missing_source"] == 1
    assert counts["ZERO_LANE"]["source_priced_h1"] == 100
    assert counts["ZERO_LANE"]["h1_missing_source"] == 0
    assert counts["SELECTED"]["observed_only_H1_mean_unadjusted_price_pct"] == (
        -1.410336
    )
    assert x["H1_selected_lags_both_source_controls"] is True
    gaps = x["H1_selected_minus_controls"]
    assert gaps["SELECTED_MINUS_ONE_LANE"][
        "observed_only_H1_mean_gap_pp"
    ] == -0.141339
    assert gaps["SELECTED_MINUS_ZERO_LANE"][
        "observed_only_H1_mean_gap_pp"
    ] == -0.334037
    assert gaps["SELECTED_MINUS_ONE_LANE"][
        "POSTHOC_growth_bucket_balanced_gap_pp"
    ] == -0.220359
    assert gaps["SELECTED_MINUS_ZERO_LANE"][
        "POSTHOC_growth_bucket_balanced_gap_pp"
    ] == -0.188974
    assert x["H1_growth_balancing_chosen_after_observing_H1"] is True
    assert x["H1_was_one_trade_date_not_100_independent_trials"] is True
    assert x["H1_not_proof_of_structurally_negative_future_alpha"] is True


def test_late_oct16_industry_subset_must_not_become_preentry_feature():
    report = materialize(ROOT)
    counts = report["H1_arm_diagnostics"]
    assert counts["SELECTED"]["later_Oct16_index_subset_industry_matches"] == 46
    assert counts["ONE_LANE"]["later_Oct16_index_subset_industry_matches"] == 43
    assert counts["ZERO_LANE"]["later_Oct16_index_subset_industry_matches"] == 53
    assert report["original_2026_10_16_index_subset_sector_matches"] == 142
    assert report["original_2026_10_16_index_subset_coverage_fraction"] == (
        0.473333
    )
    assert report["industry_date_is_after_first_cohort_entry"] is True
    assert report["pre_entry_retroactive_sector_source_admissible"] is False
    assert report["sector_coverage_complete_for_next_eligible_cohort"] is False
    assert report["minimum_next_trial_industry_coverage_total"] == 0.95
    assert report["minimum_next_trial_industry_coverage_per_arm"] == 0.9
    assert all(
        counts[arm]["sector_source_coverage_ratio"] < 0.9
        for arm in ("SELECTED", "ONE_LANE", "ZERO_LANE")
    )


def test_h5_not_independent_and_original_nov08_amendment_is_forward_only():
    x = materialize(ROOT)
    assert x["H5_original_close_session"] == "2026-10-22"
    assert x["H5_holding_period_contains_already_examined_H1"] is True
    assert x["H5_cannot_be_called_new_independent_validation"] is True
    assert x["H20_new_original_muhurat_session_2026_11_08_confirmed"] is True
    assert x["H20_source_safely_amended_exit"] == "2026-11-12"
    assert x["H60_official_2027_calendar_missing"] is True
    assert x["corporate_actions_and_dividends_adjusted"] is False


def test_no_investment_promotion_and_future_trial_must_be_independent():
    p = materialize(ROOT)
    assert p["issuer_original_ten_three_scenario_attributable_valuations_complete"] == 0
    assert p["four_independent_deep_value_cases_approved"] == 0
    assert p["result_state"] == (
        "NO_SUPPORTED_INVESTABLE_ALPHA_NOT_ALPHA_DISPROVEN"
    )
    assert p["live_capital_allowed"] is False
    assert p["investment_recommendations_generated"] is False
    new = p["next_experiment_protocol"]
    assert new["eligible_entered_after_method_and_source_freeze"]
    assert new["independent_new_cohort_selected_without_market_return_labels"]
    assert new["balance_required_before_any_new_entry"]
    assert new["frozen_horizons_trading_sessions"] == [60, 120, 252]
    assert new["multiple_independent_future_entry_dates_required"]
    assert new["no_retraining_on_first_cohort_H1_or_H5_results"]
    assert new["not_activated_until_all_evidence_gates_pass"] is True
    assert new["next_experiment_active"] is False


def test_prior_negative_result_or_sector_source_cannot_be_changed_in_memory():
    original, receipts = load_p027_sources(ROOT)
    modified = copy.deepcopy(original)
    modified["growth"]["gaps"]["SELECTED_MINUS_ONE_LANE"][
        "raw_observed_mean_gap_pp"
    ] = 2.0
    with pytest.raises(AlphaContractError, match="missing or positive-only"):
        build_decision_gate(modified, receipts)
    modified = copy.deepcopy(original)
    modified["industry"]["arm_observations"]["SELECTED"][
        "exact_source_matches"
    ] = 100
    with pytest.raises(AlphaContractError, match="retrospective sector"):
        build_decision_gate(modified, receipts)
    modified = copy.deepcopy(original)
    modified["underwriting"]["fully_underwritten_equity_valuations_count"] = 10
    with pytest.raises(AlphaContractError, match="capital-approved"):
        build_decision_gate(modified, receipts)
    modified = copy.deepcopy(original)
    modified["calendar_amendment"]["amended_H20_last_session"] = "2026-11-13"
    with pytest.raises(AlphaContractError, match="forward amendment"):
        build_decision_gate(modified, receipts)


def test_reproducible_signed_packet_and_check_only_cli():
    report = materialize(ROOT)
    assert json.loads(REPORT.read_text(encoding="utf-8")) == report
    assert report["report_sha256"] == digest({
        k: v for k, v in report.items() if k != "report_sha256"
    })
    verify_packet(report, ROOT)
    process = subprocess.run(
        [sys.executable, "scripts/materialize_hg009_p027.py", "--check"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    output = json.loads(process.stdout)
    assert output["state"] == "VERIFIED"
    assert output["H1_lagged_both_controls"] is True
    assert output["future_matched_cohort_activated"] is False
    assert output["live_capital_allowed"] is False


def test_tampered_signed_original_report_never_returns_alpha():
    packet = materialize(ROOT)
    packet["H1_selected_lags_both_source_controls"] = False
    with pytest.raises(AlphaContractError, match="tampered"):
        verify_packet(packet, ROOT)
