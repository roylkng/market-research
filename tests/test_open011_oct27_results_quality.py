"""OPEN011: no invented issuer margin, cash rights, growth, forecast or award."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/open011_oct27_results_quality.py"
SPEC = importlib.util.spec_from_file_location("open011_issuer", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
INPUT = ROOT / "research/broad-discovery/OPEN011_OCT27_RESULTS_INPUT_20261028.json"


@pytest.fixture
def packet():
    return json.loads(INPUT.read_text(encoding="utf-8"))


def test_frozen_experiment_and_no_buy(packet):
    r = MODULE.audit(packet)
    assert r["as_of"] == "2026-10-28"
    assert r["capital_authorized"] is False
    assert r["investor_ready_picks"] == 0
    assert r["BLS_tender_award_verified"] is False


def test_indiamart_subscription_erosion_and_cash_definition_unknown(packet):
    x = MODULE.audit(packet)["INDIAMART"]
    assert x["paying_suppliers_rounded"] == 217000
    assert x["actual_quarter_net_supplier_change"] == -615
    assert x["unique_business_inquiries_yoy_pct"] == -14
    assert x["Q2_CFO_group_crore"] == 135
    assert x["Q2_CFO_parent_crore"] == 124
    assert x["Q2_group_CFO_share_from_parent_pct"] == 91.85
    assert x["reported_margin_pct"] == 37.06
    assert x["management_long_run_margin_pct"] == 33
    assert x["cash_accounting_perimeter_Q1_to_Q2_reconciled"] is False
    assert x["Q1_to_Q2_cash_change_crore"] is None
    assert x["full_parent_owner_cash_available"] is None


def test_indiamart_cash_adjusted_multiple_not_fair_value(packet):
    r = MODULE.audit(packet)["INDIAMART"]
    cases = r["cash_adjusted_valuation_sensitivities"]
    assert len(cases) == 8
    one = next(x for x in cases if
               x["normalized_operating_margin_pct_assumed"] == 33
               and x["fraction_of_treasury_assumed_accessible"] == 1)
    none = next(x for x in cases if
                x["normalized_operating_margin_pct_assumed"] == 33
                and x["fraction_of_treasury_assumed_accessible"] == 0)
    higher = next(x for x in cases if
                  x["normalized_operating_margin_pct_assumed"] == 37
                  and x["fraction_of_treasury_assumed_accessible"] == 1)
    assert one["equity_cap_less_accessible_cash_crore"] == 6235
    assert one["illustrative_annualized_EBITDA_crore"] == 566.28
    assert one["illustrative_cash_adjusted_to_ebitda_multiple"] == 11.01
    assert none["illustrative_cash_adjusted_to_ebitda_multiple"] == 16.72
    assert higher["illustrative_cash_adjusted_to_ebitda_multiple"] == 9.82
    assert all(c["is_true_enterprise_value"] is False for c in cases)
    assert all(c["is_price_target_or_return_prediction"] is False for c in cases)


def test_century_enka_reversal_is_visible(packet):
    c = MODULE.audit(packet)["CENTENKA"]
    assert c["Q2_revenue_yoy_pct"] == 36.59
    assert c["Q2_EBITDA_yoy_pct"] == 3.83
    assert c["Q2_PAT_yoy_pct"] == -17.20
    assert c["Q2_EBITDA_margin_pct"] == 5.88
    assert c["year_ago_EBITDA_margin_pct"] == 7.74
    assert c["Q1_to_Q2_EBITDA_change_pct"] == -61.69
    assert c["Q1_to_Q2_PAT_change_pct"] == -70.03
    assert c["original_cashflow_verified"] is False


def test_acutaas_growth_but_expensive_annualization_not_forecast(packet):
    a = MODULE.audit(packet)["ACUTAAS"]
    assert a["Q2_EBITDA_margin_pct"] == 40.28
    assert a["mcap_to_Q2_parent_profit_annualized_x"] == 60.67
    assert a["mcap_to_H1_parent_profit_annualized_x"] == 76.15
    assert a["annualized_multiple_is_intrinsic_valuation"] is False
    assert a["growth_guidance_company_not_certainty"] is True
    assert a["fully_verified_parent_FCFE_crore"] is None


@pytest.mark.parametrize(("field","value"),[
    ("as_of_date", "2026-10-15"),
    ("purpose", "RETROACTIVE_HG009_ALPHA"),
    ("raw_pdf_archive_present", True),
    ("raw_pdf_sha256", "a" * 64),
    ("live_capital_authorized", True),
    ("frozen_H002_H003_HG009_unchanged", False),
])
def test_frozen_cutoff_and_primary_receipts_fail_closed(packet,field,value):
    changed = copy.deepcopy(packet)
    changed[field] = value
    with pytest.raises(ValueError):
        MODULE.audit(changed)


def test_reject_fake_award_and_rounded_subscriber_inference(packet):
    p = copy.deepcopy(packet)
    p["BLS_tender_observation"]["authenticated_award_found"] = True
    with pytest.raises(ValueError, match="tender"):
        MODULE.audit(p)
    p = copy.deepcopy(packet)
    p["issuer_data"]["INDIAMART"]["paying_suppliers_net_additions"] = 650
    with pytest.raises(ValueError, match="operational"):
        MODULE.audit(p)


def test_must_not_silently_reconcile_different_cash_perimeters(packet):
    p = copy.deepcopy(packet)
    p["issuer_data"]["INDIAMART"]["cash_balance_period_and_definition_consistency_verified"] = True
    with pytest.raises(ValueError, match="unreconciled"):
        MODULE.audit(p)
    p = copy.deepcopy(packet)
    p["issuer_data"]["INDIAMART"]["wholly_accessible_parent_cash_verified"] = True
    with pytest.raises(ValueError, match="certified"):
        MODULE.audit(p)


def test_refuse_false_original_source_and_issuer_promotion(packet):
    p = copy.deepcopy(packet)
    p["issuer_data"]["CENTENKA"]["original_pdf_download_state"] = "HASH_VERIFIED"
    with pytest.raises(ValueError, match="original"):
        MODULE.audit(p)
    p = copy.deepcopy(packet)
    p["issuer_data"]["ACUTAAS"]["owner_FCFE_crore"] = 500
    with pytest.raises(ValueError, match="owner"):
        MODULE.audit(p)
    p = copy.deepcopy(packet)
    p["issuer_data"]["ACUTAAS"]["operating_revenue_vs_total_income_not_same"] = False
    with pytest.raises(ValueError, match="recurring revenue"):
        MODULE.audit(p)
