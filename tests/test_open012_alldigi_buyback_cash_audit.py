"""OPEN012: original issuer terms, H1 cash and no premature buyback arbitrage."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/open012_alldigi_buyback_cash_audit.py"
SPEC = importlib.util.spec_from_file_location("open012_alldigi_audit", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
DATA = ROOT / "research/broad-discovery/OPEN012_ALLDIGI_BUYBACK_CASH_INPUT_20261029.json"


@pytest.fixture
def packet():
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_issuer_reported_official_buyback_not_tender_execution(packet):
    x = MODULE.verify(packet)
    assert x["issuer_exact_shares"] == 15238326
    assert x["promoter_percentage"] == 73.3867
    assert x["board_buyback_max_gross_crore"] == 48
    assert x["maximum_buyback_fraction_pct"] == 3.15
    assert x["market_equity_at_preannouncement_quote_crore"] == 1234.4568
    assert x["buyback_size_to_earlier_market_cap_pct"] == 3.89
    assert x["nominal_offer_premium_to_earlier_quote_pct"] == 23.44
    assert x["shareholder_approval_pending"] is True
    assert x["record_date_unpublished"] is True
    assert x["approved_investments"] == 0


def test_cannot_buy_prior_session_quote_after_evening_board_filing(packet):
    x = MODULE.verify(packet)
    assert (
        x["new_approved_board_price_available_for_executable_trade_at_prior_quote"]
        is False
    )
    for case in x["hypothetical_gross_tender_sensitivities"]:
        assert case["afterclose_buy_available_at_observed_quote"] is False
        assert case["is_total_portfolio_return"] is False
        assert case["probability"] is None


def test_actual_group_cash_and_dividend_are_not_a_guaranteed_yield(packet):
    x = MODULE.verify(packet)
    assert x["H1_FY27_consolidated_after_tax_CFO_crore"] == 70.2
    assert x["H1_FY26_consolidated_after_tax_CFO_crore"] == 53.46
    assert x["H1_CFO_growth_pct"] == 31.31
    assert x["H1_FY27_cash_after_selected_PPE_lease_crore"] == 23.71
    assert x["H1_FY26_cash_after_selected_PPE_lease_crore"] == 15.9
    assert x["H1_FY27_cash_dividend_paid_crore"] == 45.66
    assert x["H1_cash_after_selected_PPE_lease_less_dividends_crore"] == -21.95
    assert x["annualized_H1_selected_cash_yield_at_preannouncement_market_cap_pct"] == 3.84
    assert x["consolidated_current_investments_cash_and_other_bank_crore"] == 127.23
    assert x["consolidated_current_and_noncurrent_lease_liabilities_crore"] == 153.33
    assert x["financial_asset_marks_less_lease_claims_crore"] == -26.1
    assert x["parent_owner_cash_verified"] is False


def test_q2_sales_vs_pat_and_historical_premia_are_distinct(packet):
    x = MODULE.verify(packet)
    assert x["H1_group_net_PAT_crore"] == 44.7
    assert x["Q2_revenue_yoy_pct"] == 4.0
    assert x["Q2_group_PAT_yoy_pct"] == 50.85
    cases = x["hypothetical_gross_tender_sensitivities"]
    assert [c["hypothetical_share_acceptance_pct"] for c in cases] == [
        0, 1, 3.15, 5, 10
    ]
    assert cases[2]["gross_accepted_share_offer_premium_effect_pct"] == 0.7384
    assert cases[4]["gross_accepted_share_offer_premium_effect_pct"] == 2.3442


@pytest.mark.parametrize(("outer", "value"), [
    ("schema", "ALTERED"),
    ("scope", "PROSPECTIVE_HG009_BUY"),
])
def test_investment_ranking_source_boundaries(packet, outer, value):
    altered = copy.deepcopy(packet)
    altered[outer] = value
    with pytest.raises(ValueError):
        MODULE.verify(altered)


@pytest.mark.parametrize(("field", "value"), [
    ("issuer_existing_shares_at_2026_09_30", 12000000),
    ("issuer_pre_buyback_promoter_shares", 11000000),
    ("max_shares", 500000),
    ("price_inr", 1050),
    ("max_gross_crore", 100),
    ("record_date_set", True),
    ("shareholder_special_resolution_approved", True),
    ("allocation_results_known", True),
    ("promoter_explicit_intention_to_participate", False),
])
def test_cannot_invent_buyback_terms_fulfillment_or_share_counts(packet, field, value):
    altered = copy.deepcopy(packet)
    altered["buyback"][field] = value
    with pytest.raises((ValueError, TypeError)):
        MODULE.verify(altered)


def test_postclose_market_execution_and_publication_times_are_not_fabricated(packet):
    altered = copy.deepcopy(packet)
    altered["observation"]["quote_observation_IST"] = "2026-10-29T18:00:00+05:30"
    with pytest.raises(ValueError, match="before disclosure"):
        MODULE.verify(altered)
    altered = copy.deepcopy(packet)
    altered["observation"]["official_NSE_postdisclosure_tradable_quote"] = 810.10
    with pytest.raises(ValueError, match="postdisclosure"):
        MODULE.verify(altered)


def test_must_not_double_count_sub_dividend_or_original_custody(packet):
    altered = copy.deepcopy(packet)
    altered["h1_group"]["FY27H1_standalone_parent_dividend_from_Philippines_sub_lakh"] = 0
    with pytest.raises(ValueError, match="standalone subsidiary"):
        MODULE.verify(altered)
    altered = copy.deepcopy(packet)
    altered["evidence_custody"]["pdf_sha256_archive"] = "a" * 64
    with pytest.raises(ValueError, match="custody"):
        MODULE.verify(altered)


def test_live_capital_remains_forbidden_and_sensitivity_is_not_forecast(packet):
    altered = copy.deepcopy(packet)
    altered["controls"]["company_eligible_for_live_investment"] = True
    with pytest.raises(ValueError, match="trade"):
        MODULE.verify(altered)
    altered = copy.deepcopy(packet)
    altered["scenarios"]["postdisclosure_share_price_unknown"] = False
    with pytest.raises(ValueError, match="acceptance"):
        MODULE.verify(altered)


def test_cash_and_capex_wrong_sign_or_nonfinite_rejected(packet):
    altered = copy.deepcopy(packet)
    altered["h1_group"]["CFO_2026_lakh"] = float("nan")
    with pytest.raises(ValueError, match="invalid amount"):
        MODULE.verify(altered)
    altered = copy.deepcopy(packet)
    altered["h1_group"]["lease_principal_paid_2026_lakh"] = -1322
    with pytest.raises(ValueError, match="invalid amount"):
        MODULE.verify(altered)
