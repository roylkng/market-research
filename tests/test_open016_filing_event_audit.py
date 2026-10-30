"""OPEN016 signed-filing arithmetic and provenance/anti-promotion gates."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location(
    "open016_audit",ROOT/"scripts/open016_filing_event_audit.py")
AUDIT=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
INPUT=ROOT/"research/broad-discovery/OPEN016_Q2_DISCOVERY_INPUT_20261030.json"


@pytest.fixture
def evidence():
    return json.loads(INPUT.read_text(encoding="utf-8"))


def test_crizac_q2_decline_earnings_and_tax_cross_checks(evidence):
    r=AUDIT.replay(evidence)
    x=r["Crizac"]
    assert r["capital_authorized"] is False
    assert r["historical_cohorts_untouched"] is True
    assert x["q2_revenue_yoy_pct"] == -36.72
    assert x["q2_revenue_qoq_pct"] == -48.98
    assert x["q2_PBT_yoy_pct"] == -38.08
    assert x["q2_PAT_yoy_pct"] == -25.04
    assert x["h1_revenue_yoy_pct"] == -18.48
    assert x["h1_PAT_yoy_pct"] == -12.48
    assert x["h1_CFO_crore_not_owner_FCFE"] == 126.9221
    assert x["h1_UK_deferred_tax_asset_crore"] == 12.701
    assert x["h1_UK_DTA_as_pct_H1_PAT"] == 15.41
    assert x["q2_effective_tax_rate_pct"] == 9.72
    assert x["prior_q2_effective_tax_rate_pct"] == 25.43
    assert x["reference_shares"] == 174982500
    assert x["reference_close_market_cap_crore"] == 2414.9335
    assert x["reference_trailing_PAT_crore"] == 207.431
    assert x["reference_P_E_x"] == 11.64
    assert x["mechanical_P_E_ex_H1_DTA_x_NOT_FORECAST"] == 12.4
    assert x["interim_dividend_total_crore"] == 69.993
    assert x["new_dividend_pct_of_H1_CFO"] == 55.15
    assert x["price_preceded_disclosure"] is True
    assert x["opportunity_status"] == "THESIS_NEGATIVE_RESEARCH_ONLY"


def test_oswal_award_scale_cash_risk_and_parent_standalone_receivables(evidence):
    r=AUDIT.replay(evidence)
    x=r["OswalPumps"]
    assert x["award_gross_including_GST_crore"] == 235.92
    assert x["award_gross_pct_prior_equity_cap"] == 9.86
    assert x["FY26_group_PAT_crore"] == 376.278
    assert x["FY26_group_CFO_crore"] == -77.076
    assert x["FY26_group_PPE_cash_outflow_crore"] == 134.889
    assert x["FY26_selected_CFO_after_PPE_crore_NOT_FCFE"] == -211.965
    assert x["FY26_standalone_trade_receivables_crore"] == 1101.929
    assert x["FY25_standalone_trade_receivables_crore"] == 615.094
    assert x["FY26_standalone_trade_receivables_growth_pct"] == 79.15
    assert x["FY26_group_CFO_over_PAT_pct"] == -20.48
    assert x["FY26_unspent_IPO_cash_earmarked_crore"] == 271.34
    assert x["Q1FY27_PAT_yoy_pct"] == -42.82
    assert x["Q1FY27_margin_vs_yearago_pp"] == -11.69
    assert x["FY26_historical_E_P_multiple"] == 6.36
    assert x["Q1_annualised_PAT_multiple_HYPOTHETICAL_NOT_ESTIMATE"] == 11.05
    assert x["ten_pct_recovery_impairment_pretax_crore"] == 110.1929
    assert x["ten_pct_recovery_impairment_pct_cap"] == 4.61
    assert x["order_recognized_as_revenue"] is False
    assert x["real_earned_order_margin_and_parent_owner_cash"] is False
    assert x["opportunity_status"] == "NEW_ORDER_BUT_CASH_TRAP_RESEARCH_ONLY"


@pytest.mark.parametrize(("field","invalid"),[
    ("raw_issuer_pdf_bytes_archived",True),
    ("original_issuer_pdf_visually_inspected",True),
    ("future_prediction_or_live_capital",True),
    ("observed_local","2026-10-29T19:09:24+05:30"),
    ("study_type","RETROFIT_HG009_PROSPECTIVE"),
])
def test_cannot_upgrade_source_or_retrofit_study(evidence,field,invalid):
    altered=copy.deepcopy(evidence)
    altered[field]=invalid
    with pytest.raises(ValueError):
        AUDIT.replay(altered)


@pytest.mark.parametrize(("field","invalid"),[
    ("q2_PAT_lakh",float("nan")),
    ("source_released_time","2026-10-30T15:00:00+05:30"),
    ("share_count_from_dividend_consistency",180000000),
    ("source_NSE_named_attachment","fiction.pdf"),
    ("ownership_and_acquisition_dilution_full_verified",True),
    ("value_ready",True),
    ("interim_dividend_per_share_inr",100),
])
def test_crizac_decline_cannot_turn_into_admitted_owner_catalyst(
    evidence,field,invalid
):
    altered=copy.deepcopy(evidence)
    altered["studies"]["CRIZAC"][field]=invalid
    with pytest.raises((ValueError,TypeError)):
        AUDIT.replay(altered)


@pytest.mark.parametrize(("field","invalid"),[
    ("FY26_CONSOLIDATED_after_tax_CFO_million",770.76),
    ("price_close_date","2026-10-30"),
    ("FY26_standalone_trade_receivables_million",100),
    ("order_solar_pumps",20000),
    ("source_exchange_pdf_uuid","different.pdf"),
    ("owner_parent_cash_verified",True),
    ("cash_collected_on_new_order",True),
    ("award_GST_exclusion_verified",True),
    ("value_ready",True),
])
def test_oswal_order_and_accounting_non_promotion(evidence,field,invalid):
    altered=copy.deepcopy(evidence)
    altered["studies"]["OSWALPUMPS"][field]=invalid
    with pytest.raises((ValueError,TypeError)):
        AUDIT.replay(altered)


def test_no_post_announcement_quote_inference(evidence):
    altered=copy.deepcopy(evidence)
    altered["safety_gates"]["no_quote_after_issuer_release_claimed_for_CRIZAC"]=False
    with pytest.raises(ValueError):
        AUDIT.replay(altered)
