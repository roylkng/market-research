"""OPEN012 Q2 challenge, round-source checks and no-backfill invariants."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/open012_q2_operating_inflection_audit.py"
SPEC = importlib.util.spec_from_file_location("open012_q2", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
INPUT = (
    ROOT / "research/broad-discovery/OPEN012_Q2_INDIAMART_CENTENKA_INPUT_20261027.json"
)


@pytest.fixture
def packet():
    return json.loads(INPUT.read_text(encoding="utf-8"))


def test_indiamart_original_prior_period_and_secondhand_current_compare(packet):
    r = MODULE.compute(packet)["INDIAMART"]
    assert r["consolidated_revenue_YoY_pct"] == 9.72
    assert r["consolidated_EBITDA_YoY_pct"] == 22.31
    assert r["consolidated_group_PAT_YoY_pct"] == 9.64
    assert r["consolidated_operating_cash_YoY_pct"] == 18.42
    assert r["consolidated_collections_YoY_pct"] == 9.11
    assert r["consolidated_deferred_revenue_YoY_pct"] == 15.94
    assert r["paying_suppliers_YoY_pct"] == -2.25
    assert r["ARPU_YoY_pct"] == 10.77
    assert r["CFO_to_collections_Q2FY26_pct"] == 28.08
    assert r["CFO_to_collections_Q2FY27_pct"] == 30.47


def test_indiamart_qoq_recovery_does_not_imply_subscriber_recovery(packet):
    r = MODULE.compute(packet)["INDIAMART"]
    assert r["consolidated_revenue_QoQ_pct"] == 3.62
    assert r["consolidated_EBITDA_QoQ_pct"] == 8.90
    assert r["consolidated_group_PAT_QoQ_pct"] == -47.09
    assert r["consolidated_operating_cash_QoQ_pct"] == -17.18
    assert r["consolidated_collections_QoQ_pct"] == -4.32
    assert r["paying_suppliers_QoQ_pct"] == -0.46
    assert r["CFO_to_collections_Q1FY27_pct"] == 35.21


def test_century_enka_standalone_comparators_and_margin_reversal(packet):
    r = MODULE.compute(packet)["CENTENKA"]
    assert r["standalone_revenue_YoY_pct"] == 36.59
    assert r["standalone_EBITDA_YoY_pct"] == 3.83
    assert r["standalone_PAT_YoY_pct"] == -17.38
    assert r["standalone_revenue_QoQ_pct"] == 0.71
    assert r["standalone_EBITDA_QoQ_pct"] == -61.69
    assert r["standalone_PAT_QoQ_pct"] == -69.60
    assert r["standalone_EBITDA_margin_Q1FY27_pct"] == 15.47
    assert r["standalone_EBITDA_margin_Q2FY27_pct"] == 5.88
    assert r["materials_pct_of_revenue_Q1_FY27"] == 58.7
    assert r["materials_pct_of_revenue_Q2_FY27"] == 66.9
    assert r["group_PAT_Q2_FY27_crore_secondary_only"] == 18.49
    assert r["source_original_Q2_consolidated_operating_cash_crore"] is None


def test_frozen_original_trials_unchanged_and_buy_blocked(packet):
    r = MODULE.compute(packet)
    assert r["original_HG009_alpha_panel_modified"] is False
    assert r["current_Q2_original_source_eligible"] is False
    assert r["capital_authorized"] is False
    assert r["investment_recommendation"] == "NONE"


@pytest.mark.parametrize(("field","value"), [
    ("schema","RETROACTIVE-HG009-20261015"),
    ("status","PAPER_BUY_FROZEN_ALPHA"),
    ("date","2026-10-15"),
    ("market_price_reference_date","2026-10-27"),
])
def test_wrong_protocol_or_market_clock_fails(packet,field,value):
    p = copy.deepcopy(packet)
    p[field] = value
    with pytest.raises(ValueError):
        MODULE.compute(p)


def test_original_q2_filing_or_cash_assertions_not_invented(packet):
    for key,value in (
        ("source_raw_bytes_for_current_Q2_not_archived", False),
        ("investment_approved", True),
        ("current_q2_exchange_dissemination_time_verified", True),
        ("owner_cash_verified", True),
    ):
        p = copy.deepcopy(packet)
        p["guards"][key] = value
        with pytest.raises(ValueError, match="provenance|approval"):
            MODULE.compute(p)


def test_yoy_cash_growth_sign_must_not_be_conflated_with_qoq(packet):
    p = copy.deepcopy(packet)
    p["indiamart"]["Q2_FY27"]["consolidated_operating_cash"] = 100
    with pytest.raises(ValueError, match="CFO growth"):
        MODULE.compute(p)


def test_no_positive_supplier_net_addition_without_new_source(packet):
    p = copy.deepcopy(packet)
    p["indiamart"]["Q2_FY27"]["paying_suppliers"] = 230000
    with pytest.raises(ValueError, match="supplier growth"):
        MODULE.compute(p)


def test_current_financial_result_source_not_original_cash_ledger(packet):
    p = copy.deepcopy(packet)
    p["indiamart"]["Q2_FY27"]["basis"] = "ORIGINAL_PDF_ADMITTED"
    with pytest.raises(ValueError, match="provenance"):
        MODULE.compute(p)
    p = copy.deepcopy(packet)
    p["centuryenka"]["Q2_original_issuer_signed_results_URL"] = (
        "https://nsearchives.nseindia.com/corporate/fabricated.pdf"
    )
    with pytest.raises(ValueError, match="falsely asserted"):
        MODULE.compute(p)


def test_cannot_misstate_cost_increase_or_reporting_currency(packet):
    p = copy.deepcopy(packet)
    p["centuryenka"]["Q2_FY27_standalone"][
        "raw_material_net_cost_fraction_of_revenue"
    ] = 0.50
    with pytest.raises(ValueError, match="raw input cost rise"):
        MODULE.compute(p)
    p = copy.deepcopy(packet)
    p["centuryenka"]["units"] = "INR_LAKH"
    with pytest.raises(ValueError, match="identity/unit"):
        MODULE.compute(p)
