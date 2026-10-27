"""OPEN010: exact post-buyback denominator, promoter cash and value tests."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/open010_owner_cash_buyback_audit.py"
SPEC = importlib.util.spec_from_file_location("open010_buyback_audit", FILE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SOURCE = (
    ROOT / "research/broad-discovery/OPEN010_REALIZED_CAPITAL_RETURN_INPUT_20261027.json"
)


@pytest.fixture
def packet():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def test_gandhi_sebi_completed_buyback_and_denominator(packet):
    x = MODULE.verify(packet)["GANDHITUBE"]
    assert x["latest_source_verified_shares"] == 11283900
    assert x["post_buyback_mcap_crore"] == 941.2465
    assert x["stale_old_share_mcap_crore"] == 1013.6591
    assert x["old_share_denominator_mcap_error_crore"] == 72.4126
    assert x["buyback_gross_paid_crore"] == 78.129
    assert x["promoter_group_shares_accepted"] == 844704
    assert x["nonpromoter_shares_accepted"] == 23396
    assert x["promoter_share_of_repurchases_pct"] == 97.3049
    assert x["gross_cash_paid_to_promoters_crore"] == 76.02336
    assert x["gross_cash_paid_to_nonpromoters_crore"] == 2.10564
    assert x["fy26_proforma_earnings_per_new_share_inr"] == 60.5857
    assert x["fy27_Q1_mtm_in_other_income_crore"] == 9.3212
    assert x["fy27_Q1_mtm_gain_as_pct_of_PBT"] == 25.81
    assert x["fy27_Q1_PBT_ex_only_FVTPL_gain_crore"] == 26.7996
    assert x["historical_earnings_to_new_cap_multiple"] == 13.77


def test_gandhi_real_cashflow_is_not_owner_FCF(packet):
    x = MODULE.verify(packet)["GANDHITUBE"]
    assert x["fy26_CFO_crore"] == 55.1951
    assert x["fy25_CFO_crore"] == 47.0465
    assert x["fy26_CFO_less_selected_PPE_lease_interest_crore"] == 53.0902
    assert x["historic_cash_proxy_yield_pct"] == 5.64
    assert x["March2026_investments_bank_cash_pre_buyback_crore"] == 220.1264
    assert x["must_not_subtract_historic_buyback_from_March_assets_to_claim_Oct_cash"]
    assert x["company_dividend_repetition_guaranteed"] is False
    assert x["next_shareholder_buyback_open"] is False
    assert x["parent_cash_rights_and_normalized_FCFE_confirmed"] is False


def test_nucleus_original_audited_financial_cash_and_recent_profit(packet):
    x = MODULE.verify(packet)["NUCLEUS"]
    assert x["reference_FY26_shares_not_new_Q2_verified"] == 26325306
    assert x["reference_equity_cap_crore"] == 1724.7024
    assert x["fy26_after_tax_CFO_crore"] == 117.46
    assert x["fy25_after_tax_CFO_crore"] == 150.94
    assert x["fy26_CFO_change_pct"] == -22.18
    assert x["fy26_CFO_less_PPE_and_lease_crore"] == 85.5
    assert x["historic_cash_proxy_yield_pct"] == 4.96
    assert x["march2026_current_cash_investments_crore"] == 414.14
    assert x["march2026_noncurrent_financial_assets_not_assumed_liquid_crore"] == 575.59
    assert x["all_book_liabilities_crore"] == 358.68
    assert x["q1_FY27_PAT_change_pct"] == -32.19
    assert x["FY25_buyback_paid_currently_actionable"] is False
    assert x["owner_cash_verified"] is False


def test_research_only_and_prospective_freeze(packet):
    result = MODULE.verify(packet)
    assert result["capital_authorized"] is False
    assert result["original_portfolios_unchanged"] is True
    assert all(x["investment_recommendation"] == "WATCH_NOT_BUY"
               for k,x in result.items() if k in ("GANDHITUBE","NUCLEUS"))


@pytest.mark.parametrize(("outer_key","value"),[
    ("research_date","2026-10-15"),
    ("quote_session","2026-10-27"),
    ("purpose","RETRO_HG009_ALPHA"),
    ("original_raw_bytes_in_repo",True),
    ("no_capital_authorized",False),
])
def test_cannot_mutate_time_source_claims_or_buy_state(packet,outer_key,value):
    changed = copy.deepcopy(packet)
    changed[outer_key] = value
    with pytest.raises(ValueError):
        MODULE.verify(changed)


@pytest.mark.parametrize(("field","value"),[
    ("post_buyback_shares",12152000),
    ("buyback_completed_accepted_shares",100),
    ("pre_buyback_promoter_shares",8000000),
    ("post_buyback_promoter_shares",8500000),
    ("price_inr",float("nan")),
    ("buyback_price_inr",834.15),
    ("sustaining_normalized_owner_cash_crore",53.09),
    ("capital_distribution_fairness_verified",True),
    ("fy27_Q1_FVTPL_gain_lakh",4500),
])
def test_promoter_buyback_no_false_cash_recommendation(packet,field,value):
    changed = copy.deepcopy(packet)
    changed["candidate_studies"][0][field] = value
    with pytest.raises((ValueError,TypeError)):
        MODULE.verify(changed)


@pytest.mark.parametrize(("field","value"),[
    ("shares_original_FY26",30000000),
    ("fy26_source_scope","AUDITED_STANDALONE_INR_LAKH"),
    ("FY27_Q2_results_board_date","2026-10-27"),
    ("noncurrent_investments_accessible_cash_verified",True),
    ("latest_legal_current_shares_after_FY26_verified",True),
    ("normalized_parent_owner_cash_crore",100),
    ("FY25_buyback_at_price_inr",650),
])
def test_nucleus_no_fabricated_quarter_or_current_liquidity(packet,field,value):
    changed = copy.deepcopy(packet)
    changed["candidate_studies"][1][field] = value
    with pytest.raises(ValueError):
        MODULE.verify(changed)


def test_denominator_never_uses_pre_buyback_shares(packet):
    changed = copy.deepcopy(packet)
    changed["controls"]["buyback_old_shares_for_marketcap_forbidden"] = False
    with pytest.raises(ValueError,match="guard"):
        MODULE.verify(changed)
