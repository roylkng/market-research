"""OPEN011 source arithmetic, business-quality reversals and anti-hindsight gates."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/open011_q2fy27_cash_valuation_audit.py"
SPEC = importlib.util.spec_from_file_location("open011", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SOURCE = ROOT / "research/broad-discovery/OPEN011_Q2FY27_EVIDENCE_INPUT_20261029.json"


@pytest.fixture
def packet():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def test_exact_three_new_quarter_sources_and_no_trade(packet):
    r = MODULE.evaluate(packet)
    assert r["schema"] == "OPEN011_20261029_FY27_Q2_ORIGINAL_DISCLOSURE_CHALLENGE_V1"
    assert r["source_bytes_pinned"] is False
    assert r["exchange_auction_price_verified"] is False
    assert r["approved_positions"] == 0
    assert r["original_HG009_H002_H003_frozen"] is True
    assert set(r) == {
        "schema", "analysed_on", "source_bytes_pinned",
        "exchange_auction_price_verified", "approved_positions",
        "original_HG009_H002_H003_frozen", "ACUTAAS", "INDIAMART", "CENTENKA"
    }


def test_acutaas_cash_growth_with_parent_nci_split(packet):
    a = MODULE.evaluate(packet)["ACUTAAS"]
    assert a["H1_consolidated_CFO_cr"] == 215.919
    assert a["H1_previous_CFO_cr"] == 136.5049
    assert a["H1_CFO_growth_pct"] == 58.18
    assert a["H1_cash_PPE_intangible_CWIP_cr"] == 123.9204
    assert a["H1_cash_after_selected_PPE_cr"] == 91.9986
    assert a["prior_H1_cash_after_selected_PPE_cr"] == -4.6489
    assert a["inventory_cash_absorption_cr"] == -48.9574
    assert a["H1_parent_PAT_cr"] == 199.4293
    assert a["H1_noncontrolling_PAT_cr"] == -1.2941
    assert a["H1_group_PAT_cr"] == 198.1352
    assert a["Q2_revenue_growth_pct"] == 42.68
    assert a["Q2_EBITDA_growth_pct"] == 84.68
    assert a["Korean_75pct_owned_plant_in_trials"] is True


def test_acutaas_high_valuation_reverse_hurdle_is_not_forecast(packet):
    a = MODULE.evaluate(packet)["ACUTAAS"]
    assert a["reference_issued_shares"] == 81871200
    assert a["reference_equity_market_cap_cr"] == 32257.2528
    assert a["annualized_H1_diluted_EPS_proxy_inr"] == 48.56
    assert a["price_to_annualized_H1_diluted_EPS_proxy"] == 81.14
    assert a["annualized_selected_cash_as_pct_of_market_cap"] == 0.57
    assert a[
        "ten_year_EPS_CAGR_required_for_hypothetical_12pct_gross_return_with_terminal_30PE_pct"
    ] == 23.72
    assert a["required_growth_is_forecast"] is False
    assert a["investment_decision"] == "VALUATION_GATE_FAILED_NO_BUY"


def test_indiamart_no_fake_rounding_or_audited_cash(packet):
    i = MODULE.evaluate(packet)["INDIAMART"]
    assert i["Q2_revenue_growth_pct"] == 9.72
    assert i["reported_Q2_operating_cash_cr"] == 135
    assert i["reported_Q1_operating_cash_cr"] == 163
    assert i["Q2_operating_cash_qoq_pct"] == -17.18
    assert i["q2_cash_investments_cr"] == 3234
    assert i["cash_investments_change_qoq_cr"] == -319
    assert i["q2_parent_fraction_of_group_marked_cash_pct"] == 91.84
    assert i["paid_suppliers_reported_end_rounded"] == 217000
    assert i["paid_supplier_exact_sequential_change_call_only"] == -615
    assert i["exact_delta_not_derived_from_rounded_217k_218k"] is True
    assert i["audited_H1_CFO_cr"] is None
    assert i["fully_diluted_issuer_shares"] is None


def test_century_q1_inventory_windfall_not_compounder(packet):
    c = MODULE.evaluate(packet)["CENTENKA"]
    assert c["Q2_revenue_yoy_pct"] == 36.59
    assert c["Q2_EBITDA_qoq_pct"] == -61.73
    assert c["Q2_PAT_qoq_pct"] == -70.03
    assert c["reported_Q2_EBITDA_margin_pct"] == 5.88
    assert c["reported_Q1_EBITDA_margin_pct"] == 15.46
    assert c["source_issuer_Q1_low_cost_opening_inventory_windfall"] is True
    assert c["reference_market_cap_cr"] == 1022.58
    assert c["reference_Sept_equity_book_price_ratio"] == 0.6585
    assert c["P_to_annualized_Q2_PAT_illustration"] == 13.83
    assert c["P_to_annualized_H1_PAT_illustration"] == 6.38
    assert c["annualization_is_stable_earnings_estimate"] is False
    assert c["issuer_cashflow_verified"] is False


@pytest.mark.parametrize(("key", "value"), [
    ("as_of_IST", "2026-10-15"),
    ("market_price_date", "2026-10-23"),
    ("experiment", "PROSPECTIVE_HG009_ALPHA"),
])
def test_no_posthoc_source_backfill(packet, key, value):
    edited = copy.deepcopy(packet)
    edited[key] = value
    with pytest.raises(ValueError):
        MODULE.evaluate(edited)


def test_original_byte_and_price_proof_cannot_be_invented(packet):
    edited = copy.deepcopy(packet)
    edited["source_limits"]["canonical_original_file_SHA256"] = "a" * 64
    with pytest.raises(ValueError, match="custody"):
        MODULE.evaluate(edited)
    edited = copy.deepcopy(packet)
    edited["source_limits"]["official_exchange_closing_auction_price_verified"] = True
    with pytest.raises(ValueError, match="custody"):
        MODULE.evaluate(edited)


def test_no_authorized_capital_or_fake_parent_cash(packet):
    edited = copy.deepcopy(packet)
    edited["capital_permissions"]["approved_buys"] = 1
    with pytest.raises(ValueError, match="approved"):
        MODULE.evaluate(edited)
    edited = copy.deepcopy(packet)
    edited["issuer_records"][0]["parent_owner_distributable_cash"] = 91.9986
    with pytest.raises(ValueError, match="parent owner"):
        MODULE.evaluate(edited)


def test_negative_nci_and_group_equality_matters(packet):
    edited = copy.deepcopy(packet)
    edited["issuer_records"][0]["h1_noncontrolling_profit_lakh"] = 129.41
    with pytest.raises(ValueError, match="minority"):
        MODULE.evaluate(edited)
    edited = copy.deepcopy(packet)
    edited["issuer_records"][0]["h1_inventory_cash_adjustment_lakh"] = 4895.74
    with pytest.raises(ValueError, match="inventory"):
        MODULE.evaluate(edited)


def test_indiamart_dont_infer_exact_delta_from_rounded_suppliers(packet):
    edited = copy.deepcopy(packet)
    edited["issuer_records"][1]["supplier_exact_sequential_decrease_from_call_transcript"] = -1000
    with pytest.raises(ValueError, match="supplier delta"):
        MODULE.evaluate(edited)
    edited = copy.deepcopy(packet)
    edited["issuer_records"][1]["h1_audited_after_tax_CFO_cr_exact"] = 298
    with pytest.raises(ValueError, match="invented"):
        MODULE.evaluate(edited)


def test_century_issuer_priced_inventory_or_profit_dates_not_faked(packet):
    edited = copy.deepcopy(packet)
    edited["issuer_records"][2]["h1_issuer_actual_after_tax_CFO_cr"] = 100
    with pytest.raises(ValueError, match="validated"):
        MODULE.evaluate(edited)
    edited = copy.deepcopy(packet)
    edited["issuer_records"][2]["Q1_issuer_explicit_early_inventory_cost_tailwind"] = False
    with pytest.raises(ValueError, match="inventory"):
        MODULE.evaluate(edited)


def test_no_future_crizac_results_or_tender_awards(packet):
    edited = copy.deepcopy(packet)
    edited["next_decisive_events"][0]["confirmed_published_asof"] = True
    with pytest.raises(ValueError, match="future"):
        MODULE.evaluate(edited)
    edited = copy.deepcopy(packet)
    edited["next_decisive_events"][1]["confirmed_award_asof"] = True
    with pytest.raises(ValueError, match="future"):
        MODULE.evaluate(edited)
