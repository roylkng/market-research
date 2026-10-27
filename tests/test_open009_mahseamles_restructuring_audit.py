"""OPEN009: reject imaginary demerger arbitrage and fake owner cash."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/open009_mahseamles_restructuring_audit.py"
SPEC = importlib.util.spec_from_file_location("open009_mahseamles_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
DATA = (
    ROOT / "research/broad-discovery/OPEN009_MAHSEAMLES_CASH_DEMERGER_INPUT_20261027.json"
)


@pytest.fixture
def packet():
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_exact_source_financial_and_entitlement_arithmetic(packet):
    r = MODULE.analyze(packet)
    assert r["market_cap_using_original_share_count_crore"] == 7147.5201
    assert r["fy26_parent_PAT_crore"] == 701.28
    assert r["fy26_diluted_pe"] == 10.19
    assert r["dividend_paid_crore"] == 134.0
    assert r["cash_dividend_inr_per_share"] == 10.0
    assert r["historic_dividend_yield_pct"] == 1.87
    assert r["FY26_reported_CFO_after_selected_PPE_crore"] == 763.13
    assert r["FY26_working_capital_release_crore"] == 384.22
    assert r["FY26_stress_excluding_positive_wc_release_after_selected_PPE_crore"] == 378.91
    assert r["FY25_CFO_after_selected_PPE_crore"] == 586.41
    assert r["FY26_reported_proxy_yield_pct"] == 10.68
    assert r["FY26_working_capital_stress_proxy_yield_pct"] == 5.30
    assert r["March_current_investments_crore"] == 3599.96
    assert r["March_FVTPL_portfolio_crore"] == 3422.73
    assert r["March_gross_current_assets_investments_cash_crore"] == 3679.18
    assert r["March_marked_assets_less_named_borrowings_crore"] == 3665.82
    assert r["reported_at_least_pledged_bonds_crore"] == 34.1
    assert r["Q1_FY27_revenue_YoY_pct"] == -4.72


def test_splitting_business_does_not_create_free_money(packet):
    r = MODULE.analyze(packet)
    assert r["scheme_splits_existing_economic_rights_three_ways"] is True
    assert r["scheme_effective_confirmed"] is False
    assert r["scheme_creates_free_additional_value"] is False
    assert r["owner_distributable_cash_verified"] is False
    assert r["capital_authorized"] is False
    assert r["recommendation"] == "RESEARCH_ONLY_NO_BUY"


def test_mark_scenarios_are_not_expected_shareholder_returns(packet):
    r = MODULE.analyze(packet)
    cases = r["investment_market_mark_sensitivities"]
    assert [x["original_FVTPL_haircut_pct"] for x in cases] == [0, 10, 20, 30]
    assert [x["loss_on_March_FVTPL_portfolio_crore"] for x in cases] == [
        0, 342.27, 684.55, 1026.82
    ]
    assert [x["loss_as_pct_Oct26_equity_cap"] for x in cases] == [
        0, 4.79, 9.58, 14.37
    ]
    assert all(x["interpreted_as_stock_price_forecast"] is False for x in cases)


@pytest.mark.parametrize(("field", "value"), [
    ("price_date", "2026-10-27"),
    ("scope", "RETROACTIVE_HG009_ALPHA"),
    ("research_date", "2026-10-15"),
])
def test_date_and_alpha_source_cutoff_guard(packet, field, value):
    altered = copy.deepcopy(packet)
    altered[field] = value
    with pytest.raises(ValueError):
        MODULE.analyze(altered)


@pytest.mark.parametrize(("field", "value"), [
    ("shares_at_2026_03_31", 100000000),
    ("face_value_inr", 10),
    ("original_hg009_arm", "ZERO_LANE"),
    ("isin", "INEFAKE00000"),
])
def test_dont_change_issuer_identity_or_denominator(packet, field, value):
    altered = copy.deepcopy(packet)
    altered["identity"][field] = value
    with pytest.raises(ValueError):
        MODULE.analyze(altered)


def test_cashflow_wont_accept_fabricated_working_capital(packet):
    altered = copy.deepcopy(packet)
    altered["fy26_consolidated"]["trade_receivable_working_capital_release"] = 0
    with pytest.raises(ValueError, match="reconciliation"):
        MODULE.analyze(altered)


def test_fvpl_not_equal_to_cash_and_cannot_exceed_current_portfolio(packet):
    altered = copy.deepcopy(packet)
    altered["fy26_consolidated"]["current_investments_at_FVTPL"] = 4500
    with pytest.raises(ValueError, match="FVTPL"):
        MODULE.analyze(altered)


def test_frozen_investment_cash_and_scheme_state_not_approvals(packet):
    altered = copy.deepcopy(packet)
    altered["controls"]["investment_approved"] = True
    with pytest.raises(ValueError, match="approval"):
        MODULE.analyze(altered)
    altered = copy.deepcopy(packet)
    altered["controls"]["normalized_parent_owner_FCFE"] = 763.13
    with pytest.raises(ValueError, match="approval"):
        MODULE.analyze(altered)
    altered = copy.deepcopy(packet)
    altered["scheme"]["legal_effective_and_separate_listing_completed"] = True
    with pytest.raises(ValueError, match="finality"):
        MODULE.analyze(altered)
    altered = copy.deepcopy(packet)
    altered["scheme"]["company_describes_share_exchange_as_value_neutral"] = False
    with pytest.raises(ValueError, match="value-neutral"):
        MODULE.analyze(altered)


def test_scheme_fraction_approval_and_external_raw_custody_not_invented(packet):
    altered = copy.deepcopy(packet)
    altered["scheme"]["USL_shares_per_5_MAHSEAMLES"] = 5
    with pytest.raises(ValueError, match="ratios"):
        MODULE.analyze(altered)
    altered = copy.deepcopy(packet)
    altered["source_evidence"]["original_FY26_audited_SHA256"] = "a" * 64
    with pytest.raises(ValueError, match="custody"):
        MODULE.analyze(altered)


def test_negative_or_nonfinite_inputs_rejected(packet):
    altered = copy.deepcopy(packet)
    altered["market"]["NSE_2026_10_26_close_inr"] = float("nan")
    with pytest.raises(ValueError, match="invalid"):
        MODULE.analyze(altered)
    altered = copy.deepcopy(packet)
    altered["fy26_consolidated"]["selected_PPE_cash_purchases"] = -169.67
    with pytest.raises(ValueError, match="invalid"):
        MODULE.analyze(altered)
