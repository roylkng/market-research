"""P026 prevents fictitious 300-company sector-matched causal alpha."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_controls import load_hg009_inputs
from marketlab.hg009_p026_sector_coverage import (
    REQUIRED_PER_ARM_COVERAGE_FRACTION,
    REQUIRED_SOURCE_COVERAGE_FRACTION,
    SOURCE_PATH,
    build_sector_identifiability_report,
    materialize,
    validate_report,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/hg009/hg009-p026-postentry-sector-coverage-v1.json"


def _inputs() -> dict:
    original, selected = load_hg009_inputs(ROOT)
    controls = json.loads((
        ROOT / "research/hg009/hg009-p001-matched-300-company-controls-v1.json"
    ).read_text(encoding="utf-8"))
    return {
        "source_csv": (ROOT / SOURCE_PATH).read_bytes(),
        "router": original,
        "selected": selected,
        "controls": controls,
    }


def test_original_full_300_source_coverage_and_missing_are_not_imputed():
    report = build_sector_identifiability_report(**_inputs())
    assert report["source_original_NSE_report_date"] == "2026-10-16"
    assert report["original_first_entry_session"] == "2026-10-15"
    assert report["source_original_index_member_count"] == 755
    assert report["source_original_exact_EQ_row_count"] == 744
    assert report["frozen_300_total"] == 300
    assert report["source_exact_match_count"] == 142
    assert report["source_exact_nonmatch_count"] == 158
    assert report["source_exact_match_fraction"] == pytest.approx(142 / 300, abs=1e-6)
    assert len(report["all_source_identity_rows"]) == 300
    assert report["arm_observations"]["SELECTED"]["exact_source_matches"] == 46
    assert report["arm_observations"]["ONE_LANE"]["exact_source_matches"] == 43
    assert report["arm_observations"]["ZERO_LANE"]["exact_source_matches"] == 53
    assert report["arm_observations"]["SELECTED"][
        "not_covered_by_original_index_subset"
    ] == 54
    assert report["arm_observations"]["ONE_LANE"][
        "not_covered_by_original_index_subset"
    ] == 57
    assert report["arm_observations"]["ZERO_LANE"][
        "not_covered_by_original_index_subset"
    ] == 47
    assert all(
        (row["provisional_oct16_index_industry"] is None)
        == row["source_missing_not_imputed"]
        for row in report["all_source_identity_rows"]
    )
    assert report["source_report_session_is_after_original_entry"] is True
    assert report["sector_size_risk_conditioned_model_admissible"] is False


def test_financial_services_and_common_sector_coverage_disqualify_naive_controls():
    result = build_sector_identifiability_report(**_inputs())
    assert [
        result["arm_observations"][arm]["financial_services_exact_matches"]
        for arm in ("SELECTED", "ONE_LANE", "ZERO_LANE")
    ] == [4, 13, 17]
    assert result["sector_triplet_upper_bound_complete_count"] == 20
    assert sum(
        item["maximum_complete_industry_triplets_without_replacement"]
        for item in result["industry_strata_overlap"]
    ) == 20
    assert all(
        x["maximum_complete_industry_triplets_without_replacement"]
        <= min(x["selected_exact"], x["one_lane_exact"], x["zero_lane_exact"])
        for x in result["industry_strata_overlap"]
    )
    assert result["source_95pct_total_coverage_gate"] is False
    assert result["source_90pct_each_arm_coverage_gate"] is False
    assert REQUIRED_SOURCE_COVERAGE_FRACTION == 0.95
    assert REQUIRED_PER_ARM_COVERAGE_FRACTION == 0.90


def test_future_only_timeliness_rule_and_no_false_stock_returns():
    result = build_sector_identifiability_report(**_inputs())
    for name in (
        "original_oct15_preentry_source_gate",
        "sector_size_risk_conditioned_model_admissible",
        "sector_matched_three_arm_causal_inference_available",
        "size_float_exposure_source_independently_complete",
        "credit_regime_split_source_independently_complete",
        "outcome_prices_or_share_returns_read_by_this_method",
        "stock_pick_model_trained_on_market_outcomes",
        "industry_membership_imputed_for_missing_issuers",
        "expected_return_forecast_produced",
        "live_capital_allowed",
    ):
        assert result[name] is False
    assert result["future_cohort_must_use_independent_preentry_sector_size_source"]
    assert result["posthoc_source_reconstruction_must_not_change_h1_h5"]


def test_original_nse_sector_bytes_and_cohort_seals_cannot_be_rewritten():
    data = _inputs()
    data["source_csv"] += b"ALTERED"
    with pytest.raises(AlphaContractError, match="CSV SHA changed"):
        build_sector_identifiability_report(**data)

    data = _inputs()
    altered = copy.deepcopy(data["selected"])
    altered["selected"][0]["symbol"] = "RETROSPECTIVE_BEST_STOCK"
    data["selected"] = altered
    with pytest.raises(AlphaContractError, match="cohort seal SHA"):
        build_sector_identifiability_report(**data)

    result = build_sector_identifiability_report(**_inputs())
    result["all_source_identity_rows"][0]["provisional_oct16_index_industry"] = (
        "FUTURE_WINNING_INDUSTRY"
    )
    with pytest.raises(AlphaContractError, match="report tampered"):
        validate_report(result, ROOT)


def test_original_replay_and_direct_cli_check_are_read_only():
    report = materialize(ROOT)
    assert report == json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert report["report_sha256"] == digest({
        k: v for k, v in report.items() if k != "report_sha256"
    })
    done = subprocess.run(
        [
            sys.executable, "scripts/materialize_hg009_p026_sector.py",
            "--check",
        ],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    data = json.loads(done.stdout)
    assert data["source_exact_match_count"] == 142
    assert data["max_complete_industry_triplets"] == 20
    assert data["industry_coverage_gate_passed"] is False
    assert data["live_capital_allowed"] is False
