"""OPEN017: November FY27 H1 source and no-investment-inference regression tests."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/open017_fy27h1_reality_audit.py"
SPEC = importlib.util.spec_from_file_location("open017_fy27h1_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
EVIDENCE = (
    ROOT
    / "research/broad-discovery/OPEN017_FY27H1_EARNINGS_CASH_REALITY_20261106.json"
)


@pytest.fixture
def packet():
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def test_fy27_h1_bls_attributable_cash_and_trailing_earnings(packet):
    result = MODULE.evaluate(packet)
    b = result["BLS"]
    assert result["capital_approved"] is False
    assert result["prospective_alpha_validated"] is False
    assert result["owner_cash_verified_cases"] == 0
    assert b["FY27_Q2_revenue_growth_yoy_pct"] == 32.05
    assert b["Q2_EBITDA_margin_change_pp"] == -3.4
    assert b["H1_group_CFO_growth_pct"] == 5.77
    assert b["H1_cash_after_selected_capex_leases_interest_cr"] == 335.094
    assert b["H1_prior_cash_after_selected_capex_leases_interest_cr"] == 444.4589
    assert b["H1_selected_cash_change_pct"] == -24.61
    assert b["H1_cash_after_additional_acquisitions_cr"] == 182.8017
    assert b["standalone_parent_cash_after_selected_including_sub_dividends_cr"] == 101.7407
    assert b["trailing_parent_PAT_cr"] == 716.8436
    assert b["price_to_trailing_parent_PAT_x"] == 13.03
    assert b["standalone_dividend_eliminated_on_group_consolidation"] is True
    assert b["source_underwritten_owner_FCFE_cr"] is None


def test_indiamart_subscriber_churn_and_cash_evidence(packet):
    r = MODULE.evaluate(packet)["INDIAMART"]
    assert r["current_approx_paying_suppliers"] == 217000
    assert r["management_reported_net_supplier_change"] == -615
    assert r["Q2_cash_vs_Q1_change_pct"] == -17.18
    assert r["cash_investments_QoQ_change_cr"] == -319
    assert r["reported_cash_investments_not_owner_cash"] is True
    assert r["Q2_reported_group_PAT_cr"] == 91
    assert r["shareholder_cash_discount_model_verified"] is False
    assert r["investment_decision"] == "SUBSCRIBER_CHURN_BLOCKED"


def test_century_enka_negative_cash_despite_stale_book_discount(packet):
    r = MODULE.evaluate(packet)["CENTENKA"]
    assert r["H1_operating_cash_cr"] == -14.17
    assert r["H1_PPE_cash_cr"] == 45.28
    assert r["H1_CFO_less_selected_PPE_cr"] == -59.45
    assert r["Q2_PAT_cr"] == 18.49
    assert r["Q1_PAT_implied_cr"] == 61.7
    assert r["price_to_PRIOR_YEAR_book_x"] == 0.659
    assert r["book_discount_not_equivalent_to_equity_valuation"] is True
    assert r["investment_decision"] == "NEGATIVE_H1_CASH"


def test_acutaas_shareholder_claim_and_valuation_hurdle(packet):
    r = MODULE.evaluate(packet)["ACUTAAS"]
    assert r["H1_parent_PAT_cr"] == 199.4293
    assert r["H1_group_CFO_cr"] == 215.919
    assert r["H1_PPE_cash_cr"] == 123.9204
    assert r["H1_CFO_less_PPE_cr_not_FCFE"] == 91.9986
    assert r["H1_cash_after_PPE_as_pct_current_cap"] == 0.3
    assert r["annualized_H1_parent_PAT_cr_NOT_FORECAST"] == 398.8586
    assert r["implied_quasi_PE_using_annualized_H1_parent_PAT"] == 77.4
    assert r["earnings_CAGR_3yr_for_flat_share_value_at_35x_exit_pct"] == 30.28
    assert r["earnings_CAGR_3yr_for_15pct_price_CAGR_at_35x_exit_pct"] == 49.83
    assert r["scenario_probability"] is None
    assert r["investment_decision"] == "GROWTH_PRICED_IN_NOT_BUY"


@pytest.mark.parametrize(("key", "value"), [
    ("observed_as_of", "2026-10-26"),
    ("latest_completed_NSE_session", "2026-11-06"),
    ("study_type", "POST_OUTCOME_PROMOTED_ALPHA"),
    ("original_source_bytes_archived_in_this_change", True),
    ("source_first_retrieved_utc", "2026-10-15T00:00:00Z"),
])
def test_cannot_backdate_original_sources_or_alpha(packet, key, value):
    altered = copy.deepcopy(packet)
    altered[key] = value
    with pytest.raises(ValueError):
        MODULE.evaluate(altered)


@pytest.mark.parametrize(("guard_key", "value"), [
    ("original_H002_H003_HG009_signal_identity_and_outcomes_unchanged", False),
    ("prospective_alpha_validated", True),
    ("independently_underwritten_parent_owner_cash_cases", 1),
    ("investments_authorized", 1),
    ("unconditional_price_targets_permitted", True),
])
def test_cannot_promote_unverified_cases_to_investments(packet, guard_key, value):
    altered = copy.deepcopy(packet)
    altered["guard"][guard_key] = value
    with pytest.raises(ValueError):
        MODULE.evaluate(altered)


def test_no_nci_profit_misclassified_as_bls_parent(packet):
    altered = copy.deepcopy(packet)
    altered["BLS"]["H1_FY27_parent_PAT_crore"] += 27.0042
    with pytest.raises(ValueError, match="noncontrolling"):
        MODULE.evaluate(altered)


def test_acutaas_negative_nci_and_share_denominator_not_forged(packet):
    altered = copy.deepcopy(packet)
    altered["ACUTAAS"]["H1_FY27_noncontrolling_PAT_lakh"] = 0
    with pytest.raises(ValueError, match="attribution"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(packet)
    altered["ACUTAAS"]["share_face_value_INR"] = 10
    with pytest.raises(ValueError, match="share count"):
        MODULE.evaluate(altered)


def test_no_fabricated_exact_indiamart_subscriber_recovery(packet):
    altered = copy.deepcopy(packet)
    altered["INDIAMART"]["Q2_exact_net_paying_supplier_change_from_concall"] = 800
    with pytest.raises(ValueError, match="supplier"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(packet)
    altered["INDIAMART"]["supplier_net_change_method"] = "OFFICIAL_NSE_RAW_AUDITED"
    with pytest.raises(ValueError, match="subscriber"):
        MODULE.evaluate(altered)


def test_original_source_scope_and_financial_year_cannot_change(packet):
    altered = copy.deepcopy(packet)
    altered["CENTENKA"]["NSE_official_consolidated_xbrl"] = "https://example.org"
    with pytest.raises(ValueError, match="original NSE"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(packet)
    altered["ACUTAAS"]["unit"] = "INR_MILLIONS"
    with pytest.raises(ValueError, match="unit"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(packet)
    altered["BLS"]["H1_FY27_after_tax_group_CFO_crore"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        MODULE.evaluate(altered)
