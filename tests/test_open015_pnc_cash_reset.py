"""OPEN015 PNC: mutation tests for issuer custody, period, source and cash."""
import copy
import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "scripts/open015_pnc_cash_reset.py"
SPEC = importlib.util.spec_from_file_location("open015_pnc",F)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SOURCE = ROOT / "research/broad-discovery/OPEN015_PNC_Q2_H1_ISSUER_CASH_INPUT_20261029.json"


@pytest.fixture
def packet():
    return json.loads(SOURCE.read_text(encoding="utf-8"),
                      parse_float=Decimal,parse_int=Decimal)


def test_signed_issuer_original_audit_replays_cfo_and_parent_cash(packet):
    out = MODULE.verify(packet)
    assert out["H1_after_tax_consolidated_CFO_crore"] == "-377.7677"
    assert out["H1_prior_consolidated_CFO_crore"] == "4189.0558"
    assert out["H1_after_tax_parent_CFO_crore"] == "-127.6028"
    assert out["H1_prior_parent_CFO_crore"] == "-404.3093"
    assert out["H1_consolidated_before_WC_crore"] == "810.7891"
    assert out["H1_consolidated_working_cap_drain_crore"] == "-1051.1262"
    assert out["H1_consolidated_cash_from_ops_before_tax_crore"] == "-240.3371"
    assert out["H1_one_time_settlement_revenue_crore"] == "217.6554"
    assert out["one_time_settlement_pct_of_H1_revenue"] == "7.23"
    assert out["Q2_consolidated_PAT_YoY_pct"] == "-46.83"


def test_dated_source_valuation_does_not_create_free_net_cash_or_buy(packet):
    out = MODULE.verify(packet)
    assert out["share_count_from_face_capital"] == 256539000
    assert out["quote_time_equity_cap_crore"] == "3437.1095"
    assert out["borrowings_crore"] == "5911.8252"
    assert out["cash_plus_other_banks_crore_restrictions_unverified"] == "1978.1177"
    assert out["borrowings_less_cash_and_bank_crore_not_true_net_debt"] == "3933.7075"
    assert out["current_investments_crore"] == "1114.5991"
    assert out["noncurrent_plus_current_trade_receivables_crore"] == "7132.3738"
    assert out["hypothetical_5pct_receivables_impairment_before_tax_crore"] == "356.62"
    assert out["hypothetical_5pct_impairment_as_pct_equity_cap"] == "10.38"
    assert out["normalized_annual_parent_owner_cash_crore"] is None
    assert out["HC_order_is_interim_stay_only"]
    assert out["next_price_is_a_quoted_observation_not_exchange_close"]
    assert out["investment_status"] == "INVESTIGATED_RISK_ONLY_NOT_BUY"


@pytest.mark.parametrize(("field","value"),[
    ("original_pdf_bytes_archived",True),
    ("original_pdf_sha256","fake-sha"),
    ("issuer_original_signed_date","2026-10-29"),
    ("financial_period_end","2026-03-31"),
    ("primary_url","https://example.com/another.pdf"),
    ("issuer_statement_scope","AUDITED"),
    ("research_observation_date","2026-10-27"),
])
def test_no_fabricated_primary_source_backdating_or_new_units(packet,field,value):
    altered = copy.deepcopy(packet)
    altered[field] = value
    with pytest.raises(ValueError):
        MODULE.verify(altered)


@pytest.mark.parametrize(("section","field","value"),[
    ("consolidated_cash_flow_H1_lakh","trade_receivables_change",Decimal(0)),
    ("consolidated_cash_flow_H1_lakh","net_after_tax_CFO",Decimal("459296.51")),
    ("consolidated_cash_flow_H1_lakh","before_working_capital",Decimal("459296.51")),
    ("consolidated_cash_flow_H1_lakh","direct_tax_paid",Decimal(0)),
    ("standalone_cash_flow_H1_lakh","net_after_tax_CFO",Decimal(60000)),
    ("consolidated_balance_20260930_lakh","current_investments",Decimal(0)),
    ("consolidated_balance_20260930_lakh","current_trade_receivables",Decimal(0)),
    ("consolidated_balance_20260930_lakh","paidup_equity_capital",Decimal("51307.8")),
    ("consolidated_income_lakh","Q2_reported_PAT",Decimal("33193.29")),
    ("consolidated_income_lakh","H1_one_time_Agra_Bypass_Vivad_se_Vishwas_III_settlement_revenue",Decimal(0)),
    ("as_of_quote","quote_inr",Decimal(300)),
])
def test_issuer_cash_face_denominator_and_nonrecurring_revenue_are_pinned(
        packet, section, field, value):
    altered = copy.deepcopy(packet)
    altered[section][field] = value
    with pytest.raises(ValueError):
        MODULE.verify(altered)


def test_interim_court_stay_cannot_be_called_final_exoneration(packet):
    altered = copy.deepcopy(packet)
    altered["governance"]["definitive_court_clearance"] = True
    with pytest.raises(ValueError):
        MODULE.verify(altered)


@pytest.mark.parametrize(("key","value"),[
    ("research_only",False),
    ("no_new_buy",False),
    ("no_owner_cash_proxy_from_CFO_less_PPE",False),
    ("prior_H1_after_tax_cash_is_repeated_asset_recycling_not_operating_baseline_verified",True),
    ("settlement_not_periodized_to_Q2",False),
    ("no_retroactive_H002_H003_HG009_changes",False),
    ("no_trading_or_capital_authorization",False),
])
def test_anti_hindsight_and_nobuy_guard(packet,key,value):
    altered = copy.deepcopy(packet)
    altered["controls"][key] = value
    with pytest.raises(ValueError):
        MODULE.verify(altered)


def test_unrestricted_cash_claim_must_be_proved(packet):
    altered = copy.deepcopy(packet)
    altered["consolidated_balance_20260930_lakh"]["bank_balances_fully_unrestricted_verified"] = True
    with pytest.raises(ValueError):
        MODULE.verify(altered)


def test_no_unverified_nse_close_stamp(packet):
    altered = copy.deepcopy(packet)
    altered["as_of_quote"]["exact_NSE_close_source_verified"] = True
    with pytest.raises(ValueError):
        MODULE.verify(altered)
