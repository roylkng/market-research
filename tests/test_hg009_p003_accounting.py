"""Account quality source flags cannot become stock alpha or fraud allegations."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_100 import load_hg001_router
from marketlab.hg009_p003_accounting import (
    COHORT,
    SOURCE,
    _flags,
    build_hg009_accounting_review,
    build_two_filing_pilots,
    validate_hg009_accounting_review,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/hg009/hg009-p003-accounting-quality-redteam-v1.json"


def _inputs() -> tuple[dict, dict]:
    return (
        load_hg001_router(ROOT / SOURCE),
        json.loads((ROOT / COHORT).read_text(encoding="utf-8")),
    )


def test_all_100_original_october5_rows_are_accounting_reviewed_without_returns():
    router, cohort = _inputs()
    report = build_hg009_accounting_review(router=router, cohort=cohort)
    assert report["selected_case_count"] == 100
    assert report["original_hg009_cohort_sha256"] == cohort["cohort_sha256"]
    assert report["original_screen_snapshot_date"] == "2026-10-05"
    assert report["method_review_date"] == "2026-10-14"
    assert report["cashflow_primary_source_manual_pilot_case_count"] == 2
    assert len(report["source_outcome_agnostic_company_rows"]) == 100
    assert [
        x["symbol"] for x in report["source_outcome_agnostic_company_rows"]
    ] == cohort["selected_symbols_sorted"]
    assert report["original_screen_had_no_future_return_labels"] is True
    assert report["future_returns_opened"] is False
    assert report["expected_returns_calculated"] is False
    assert report["investable_stocks_recommended"] is False
    assert report["live_capital_allowed"] is False
    for row in report["source_outcome_agnostic_company_rows"]:
        assert row["company_fair_value"] is None
        assert row["company_normalized_fcf"] is None
        assert row["company_expected_return"] is None
        assert not row["quarterly_cfo_capex_cash_conversion_verified"]
        assert not row["issuer_regime_and_accounting_basis_verified"]
    validate_hg009_accounting_review(report, router=router, cohort=cohort)


def test_flag_totals_are_deterministic_and_correspond_to_underwriting_needs():
    router, cohort = _inputs()
    report = build_hg009_accounting_review(router=router, cohort=cohort)
    assert report["screen_flags_count"] == {
        "EPS_REVENUE_DIVERGENCE_REVIEW": 34,
        "PBT_MARGIN_JUMP_REVIEW": 23,
        "TRIPLE_DIGIT_EPS_MODERATE_TOPLINE_REVIEW": 16,
        "NEGATIVE_PRETAX_MARGIN_NOT_CHEAP_EARNINGS": 6,
        "FINANCE_COST_SPIKE_REVIEW": 7,
        "INVESTMENT_ASSET_VS_OPERATING_EARNINGS_RECONCILE": 41,
        "GROWTH_DENOMINATOR_EPS_UNDEFINED": 10,
    }
    by = {
        row["symbol"]: row
        for row in report["source_outcome_agnostic_company_rows"]
    }
    assert "PBT_MARGIN_JUMP_REVIEW" in by["PIXTRANS"]["document_acquisition_flags"]
    assert "EPS_REVENUE_DIVERGENCE_REVIEW" in by[
        "PIXTRANS"
    ]["document_acquisition_flags"]
    assert "INVESTMENT_ASSET_VS_OPERATING_EARNINGS_RECONCILE" in by[
        "MAYURUNIQ"
    ]["document_acquisition_flags"]
    assert "EPS_REVENUE_DIVERGENCE_REVIEW" not in by[
        "MAYURUNIQ"
    ]["document_acquisition_flags"]
    assert by["MAYURUNIQ"]["source_filing_manual_review_case"] is True
    assert by["PIXTRANS"]["source_filing_manual_review_case"] is True
    assert sum(
        row["source_filing_manual_review_case"]
        for row in report["source_outcome_agnostic_company_rows"]
    ) == 2


def test_mayur_primary_consolidated_cashflow_versus_pretax_earnings():
    row = build_two_filing_pilots()["MAYURUNIQ"]
    assert row["source"]["source_reporting"] == "FY26_CONSOLIDATED_AUDITED"
    assert row["source"]["original_html_bytes_archived"] is False
    assert row["fy26_pbt_inr_crore"] == pytest.approx(258.9823)
    assert row["fy26_cfo_inr_crore"] == pytest.approx(133.1527)
    assert row["fy26_ppe_cash_purchase_inr_crore"] == pytest.approx(24.2071)
    assert row[
        "fy26_cfo_less_ppe_purchase_proxy_inr_crore_not_normalized_fcf"
    ] == pytest.approx(108.9456)
    assert row["fy26_cfo_over_pretax_profit_ratio_not_pat_conversion"] == pytest.approx(
        0.5141
    )
    assert row["fy26_cfo_less_ppe_proxy_over_pbt_ratio"] == pytest.approx(
        0.4207
    )
    assert row["selected_working_capital_component_movements_inr_crore"] == {
        "inventory": -47.5015,
        "trade_receivables": -22.6422,
        "other_current_assets": -17.7633,
        "trade_payables": 25.9716,
    }
    assert row["issuer_cfo_quality_reconciled_for_multiyear_cycle"] is False
    assert row["root_cause_proven"] is False


def test_pix_standalone_pbt_fvtpl_single_adjustment_not_earnings_normalization():
    row = build_two_filing_pilots()["PIXTRANS"]
    assert row["q1_reporting_basis"] == "STANDALONE_NOT_CONSOLIDATED"
    assert row["source"]["original_html_bytes_archived"] is False
    assert row["q1fy27_standalone_reported_pbt_inr_crore"] == pytest.approx(
        60.8168
    )
    assert row["q1fy26_standalone_reported_pbt_inr_crore"] == pytest.approx(
        30.9666
    )
    assert row["q1fy27_fvtpl_nonoperating_included_in_income_inr_crore"] == pytest.approx(
        25.2949
    )
    assert row[
        "q1fy27_pbt_excluding_only_investment_fvtpl_inr_crore"
    ] == pytest.approx(35.5219)
    assert row["fvtpl_share_of_reported_pbt_percent"] == pytest.approx(
        41.59
    )
    assert row["unadjusted_pbt_yoy_percent"] == pytest.approx(96.39)
    assert row[
        "single_item_excluded_pbt_yoy_percent_not_normalized_earnings"
    ] == pytest.approx(14.71)
    assert row["tax_effect_of_reclassification_applied"] is False
    assert row["prior_period_other_income_normalized"] is False
    assert row["company_fair_value_available"] is False


def test_source_mutation_fails_closed_and_same_source_recomputes():
    router, cohort = _inputs()
    report = build_hg009_accounting_review(router=router, cohort=cohort)
    modified = copy.deepcopy(report)
    modified["source_outcome_agnostic_company_rows"][0]["document_acquisition_flags"].append(
        "FAKE_ALPHA"
    )
    with pytest.raises(AlphaContractError, match="SHA mismatch"):
        validate_hg009_accounting_review(
            modified, router=router, cohort=cohort
        )
    modified = copy.deepcopy(report)
    modified["source_outcome_agnostic_company_rows"][0]["symbol"] = "FAKE_WINNER"
    unsigned = {k: v for k, v in modified.items() if k != "packet_sha256"}
    modified["packet_sha256"] = digest(unsigned)
    with pytest.raises(AlphaContractError, match="not reproducible"):
        validate_hg009_accounting_review(
            modified, router=router, cohort=cohort
        )
    broken_cohort = copy.deepcopy(cohort)
    broken_cohort["selected"][0]["symbol"] = "AFTER_THE_FACT_WINNER"
    with pytest.raises(AlphaContractError, match="cohort seal SHA"):
        build_hg009_accounting_review(
            router=router, cohort=broken_cohort
        )


def test_method_lacks_retrospective_return_signal_or_current_price_values():
    router, cohort = _inputs()
    result = build_hg009_accounting_review(router=router, cohort=cohort)
    for k in (
        "all_100_filing_cashflow_quality_verified",
        "two_pilot_original_html_bytes_retained_and_hashed",
        "latest_oct14_price_used",
        "expected_returns_calculated",
        "equity_value_or_current_fully_diluted_share_count_calculated",
        "investable_stocks_recommended",
        "live_capital_allowed",
    ):
        assert result[k] is False
    assert result["screens_are_not_misconduct_allegations"] is True
    assert result["finance_company_industry_specific_accounting_model_required"]


def test_packet_cli_is_exact_json_frozen_and_check_mode_read_only():
    router, cohort = _inputs()
    expected = build_hg009_accounting_review(router=router, cohort=cohort)
    observed = json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert observed == expected
    status = subprocess.run(
        [
            sys.executable, "scripts/materialize_hg009_accounting.py",
            "--output", str(OUTPUT.relative_to(ROOT)), "--check",
        ],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    result = json.loads(status.stdout)
    assert result["state"] == "VERIFIED"
    assert result["packet_sha256"] == expected["packet_sha256"]
    assert result["selected"] == 100
    assert result["live_capital_allowed"] is False


def test_no_flag_denial_is_derived_from_financial_fraud_inference():
    example = {
        "active_opportunity_lanes": ["EARNINGS_INFLECTION"],
        "asset_opportunity_flags": [],
        "earnings_metrics": {
            "basic_eps_yoy_pct": None,
            "revenue_yoy_pct": None,
            "pbt_margin_delta_pp": None,
            "current_pbt_margin_pct": None,
            "finance_cost_yoy_pct": None,
        },
    }
    assert _flags(example) == ["GROWTH_DENOMINATOR_EPS_UNDEFINED"]
