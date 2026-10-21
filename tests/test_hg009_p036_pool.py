"""P036 must not reuse the original 300 after their H1 was observed."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p036_independent_pool import (
    ARMS,
    INDEX_SHA,
    _arm,
    build_feasibility,
    validate_feasibility,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/hg009/hg009-p036-next-cohort-industry-feasibility-v1.json"


def test_source_is_original_archived_nse_index_not_legacy_return():
    r = build_feasibility(ROOT)
    assert r["original_nse_index_sha256"] == INDEX_SHA
    assert r["original_index_valid_EQ_industry_count"] == 741
    assert r["original_full_market_identities"] == 2319
    assert r["original_development_identity_count"] == 300
    assert r["original_development_identities_seen"] == 300
    assert r["source_first_observed_at_utc"] == (
        "2026-10-21T10:33:05.207160+00:00"
    )
    assert r["old_300_development_identities_excluded"] is True
    assert r["old_H1_H5_returns_NOT_used_for_candidate_selection"] is True
    assert r["new_independent_prospective_trial_activated"] is False
    assert r["four_tier_and_financial_regime_verified"] is False
    assert r["size_float_beta_profitability_balanced"] is False
    assert r["live_capital_allowed"] is False


def test_each_industry_liquidity_stratum_has_equal_three_arm_potential():
    r = build_feasibility(ROOT)
    n = r["maximum_industry_liquidity_matched_triplets"]
    assert sum(
        s["maximum_exact_industry_and_band_triplets"]
        for s in r["exact_one_level_industry_and_liquidity_strata"]
    ) == n
    assert r["maximum_new_company_count_at_these_two_dimensions"] == n * 3
    for arm in ARMS:
        assert len(r["possible_identity_queue_NOT_a_registered_trial"][arm]) == n
    ids = [
        (row["symbol"], row["isin"])
        for arm in ARMS
        for row in r["possible_identity_queue_NOT_a_registered_trial"][arm]
    ]
    assert len(ids) == len(set(ids))
    for row in (
        entry for arm in ARMS
        for entry in r["possible_identity_queue_NOT_a_registered_trial"][arm]
    ):
        assert row["original_median_traded_inr_not_order_capacity"] >= 10_000_000
        assert len(row["original_HG001_row_sha256"]) == 64
        assert len(row["source_selection_hash"]) == 64
    assert sum(r["new_eligible_source_rows_by_arm"].values()) >= len(ids)


def test_hypothesis_is_untested_and_original_classification_only():
    r = build_feasibility(ROOT)
    assert r["source_is_index_subset_not_all_Indian_equities"] is True
    assert r["registered_2026_10_21_after_legacy_H1_observed"] is True
    assert r["CAS_spread_action_total_return_and_cost_verified"] is False
    assert r["return_prediction_or_investment_recommendation_created"] is False
    assert _arm({
        "active_opportunity_lane_count": 0,
        "in_existing_u001": True,
    }) is None


def test_signed_report_and_separate_source_are_reproducible():
    r = build_feasibility(ROOT)
    assert r["report_sha256"] == digest({
        key: value for key, value in r.items() if key != "report_sha256"
    })
    assert json.loads(REPORT.read_text("utf-8")) == r
    validate_feasibility(ROOT, r)
    observed = subprocess.run(
        [sys.executable, "scripts/materialize_hg009_p036.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    result = json.loads(observed.stdout)
    assert result["state"] == "VERIFIED"
    assert result["new_trial_activated"] is False


def test_tampering_with_source_eligibility_fails():
    r = build_feasibility(ROOT)
    tampered = copy.deepcopy(r)
    tampered["live_capital_allowed"] = True
    with pytest.raises(AlphaContractError, match="SHA mismatch"):
        validate_feasibility(ROOT, tampered)
    tampered = copy.deepcopy(r)
    tampered["old_H1_H5_returns_NOT_used_for_candidate_selection"] = False
    tampered["report_sha256"] = digest({
        key: value for key, value in tampered.items() if key != "report_sha256"
    })
    with pytest.raises(AlphaContractError, match="not reproducible"):
        validate_feasibility(ROOT, tampered)
