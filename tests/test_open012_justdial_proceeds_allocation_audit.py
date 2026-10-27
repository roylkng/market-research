"""OPEN012: evidence-bound proceeds-purpose sensitivity with anti-buy checks."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/open012_justdial_proceeds_allocation_audit.py"
SPEC = importlib.util.spec_from_file_location("open012", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
EVIDENCE = (
    ROOT / "research/broad-discovery/OPEN012_JUSTDIAL_PREFERENTIAL_CAPITAL_INPUT_20261027.json"
)


@pytest.fixture
def original():
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def test_original_RRVL_raise_against_open007_share_market_evidence(original):
    r = MODULE.audit(original)
    assert r["name"] == "JUSTDIAL"
    assert r["original_2021_injection_crore"] == 2164.88
    assert r["original_issue_share_count"] == 21177636
    assert r["current_net_book_liquid_after_all_liabilities_crore"] == 5173.34
    assert r["october_26_market_cap_crore"] == 5943.2264
    assert r["annual_report_does_not_independently_verify_current_2026_09_remaining_balance"]
    assert r["declared_legally_cash_restricted_amount_crore"] is None
    assert r["Q2_other_income_as_pct_total_PBT"] == 40.54
    assert r["normalized_parent_owner_cash_crore"] is None
    assert r["intrinsic_value_per_share_inr"] is None
    assert r["approved_capital"] is False


def test_hypothetical_deployment_changes_operating_residual_not_legal_cash_debt(original):
    rows = MODULE.audit(original)["sensitivity_not_a_share_price_or_fair_value_forecast"]
    assert [x["hypothetical_fraction_of_2021_raise_deployed_elsewhere_pct"] for x in rows] == [
        0, 25, 50, 75, 100
    ]
    assert [x["illustrative_2021_raise_excluded_from_immediate_distribution_crore"] for x in rows] == [
        0, 541.22, 1082.44, 1623.66, 2164.88
    ]
    assert [x["net_book_liquidity_available_after_hypothetical_allocation_crore"] for x in rows] == [
        5173.34, 4632.12, 4090.90, 3549.68, 3008.46
    ]
    assert [x["market_residual_business_PLUS_committed_growth_capital_crore"] for x in rows] == [
        769.89, 1311.11, 1852.33, 2393.55, 2934.77
    ]
    assert [x["market_residual_to_annualized_Q2_operating_EBITDA_x"] for x in rows] == [
        2.12, 3.61, 5.11, 6.60, 8.09
    ]
    assert [x["market_residual_to_twice_H1_selected_cash_x"] for x in rows] == [
        4.04, 6.88, 9.71, 12.55, 15.39
    ]
    assert all(not x["legally_restricted_amount_proven"] for x in rows)
    assert all(not x["is_equity_price_target"] for x in rows)


@pytest.mark.parametrize(("field","value"), [
    ("record_date", "2026-10-15"),
    ("reason","LIVE_STOCK_SIGNAL"),
    ("source_isin", "INEFAKE01018"),
    ("source_company","INDIAMART"),
])
def test_forbid_alpha_leakage_or_identity_change(original,field,value):
    changed = copy.deepcopy(original)
    changed[field] = value
    with pytest.raises(ValueError):
        MODULE.audit(changed)


def test_raw_2021_and_2026_original_custody_not_fabricated(original):
    changed = copy.deepcopy(original)
    changed["source_custody"]["annual_2026_pdf_raw_bytes_in_git"] = True
    with pytest.raises(ValueError,match="custody"):
        MODULE.audit(changed)
    changed = copy.deepcopy(original)
    changed["source_custody"]["reliance_2021_pdf_sha256_in_git"] = "a"*64
    with pytest.raises(ValueError,match="custody"):
        MODULE.audit(changed)


def test_2021_transaction_price_and_share_count_must_match_original(original):
    for key,value in (
        ("historical_injected_equity_shares",5000000),
        ("per_share_subscription_price_inr",200),
        ("historical_injection_crore_reported",3000),
    ):
        changed = copy.deepcopy(original)
        changed["source_2021_raise"][key] = value
        with pytest.raises(ValueError):
            MODULE.audit(changed)


def test_2026_09_unused_balance_must_not_be_invented(original):
    for field,value in (
        ("FY27_September_actual_unused_balance_evidenced_in_rupees",21648800000),
        ("cash_earmarked_legally_restricted_verified",True),
        ("FY26_original_objects_detailed_text_independently_acquired",True),
    ):
        changed = copy.deepcopy(original)
        changed["source_2021_raise"][field] = value
        with pytest.raises(ValueError,match="legally frozen"):
            MODULE.audit(changed)


def test_no_intrinsic_valuation_or_buy_promoted(original):
    for field,value in (
        ("no_operating_business_intrinsic_value_estimated",False),
        ("no_live_capital",False),
        ("no_frozen_H002_H003_HG009_changes",False),
    ):
        changed = copy.deepcopy(original)
        changed["research_limits"][field] = value
        with pytest.raises(ValueError):
            MODULE.audit(changed)


def test_earnings_double_counting_guard(original):
    changed = copy.deepcopy(original)
    changed["accounting"]["Q2_other_income_crore"] = 70.56
    with pytest.raises(ValueError,match="treasury income"):
        MODULE.audit(changed)
    changed = copy.deepcopy(original)
    changed["accounting"]["Q1Q2_qtr_income_is_not_equivalent_to_franchise_EBITDA"] = False
    with pytest.raises(ValueError,match="treasury"):
        MODULE.audit(changed)


def test_sensitivity_fractions_must_be_prespecified(original):
    changed = copy.deepcopy(original)
    changed["hypothetical_scenarios"][
        "fraction_historical_raise_not_treated_as_immediately_distributable"
    ] = [0,0.2,0.4,0.6,0.8,1]
    with pytest.raises(ValueError,match="sensitivity"):
        MODULE.audit(changed)
