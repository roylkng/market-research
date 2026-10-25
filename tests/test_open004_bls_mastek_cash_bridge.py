"""OPEN004 verification: no intercompany dividend duplication, no invented FCFE."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/open004_bls_mastek_cash_bridge.py"
SPEC = importlib.util.spec_from_file_location("open004_cash_bridge", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
DATA = (
    ROOT / "research/broad-discovery/OPEN004_BLS_MASTEK_CASH_SOURCES_20261025.json"
)


@pytest.fixture
def packet():
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_replay_bls_real_parent_group_bridge(packet):
    r = MODULE.evaluate(packet)
    b = r["BLS"]
    assert r["capital_authorized"] is False
    assert r["verified_parent_owner_fcfe"] is None
    assert r["price_targets"] is None
    assert b["group_cash_after_ppe_lease_interest_crore"] == 705.6919
    assert b["group_cash_after_selected_acquisition_uses_crore"] == 648.0169
    assert b["naive_cash_ratio_after_ppe_lease_interest_pct"] == 8.2313
    assert b["naive_cash_ratio_after_selected_acquisition_uses_pct"] == 7.5586
    assert b["parent_cfo_crore"] == 62.2815
    assert b["parent_actual_dividends_received_from_subs_crore"] == 102.4435
    assert b["parent_cash_after_ppe_lease_including_sub_dividends_crore"] == 109.4098
    assert b["parent_cash_after_including_ordinary_dividend_paid_crore"] == -13.9396
    assert b["group_cashlike_before_restrictions_crore"] == 1512.5405
    assert b["group_cashlike_less_borrowings_and_lease_liabilities_crore"] == 1081.9653
    assert b["cash_legally_available_to_parent_crore"] is None
    assert b["double_counting_parent_receipts_in_group_cash_forbidden"] is True


def test_mastek_h1_cash_and_q2_underlying_profit(packet):
    m = MODULE.evaluate(packet)["MASTEK"]
    assert m["h1_current_after_tax_cfo_crore"] == 99.08
    assert m["h1_prior_after_tax_cfo_crore"] == 139.36
    assert m["cfo_yoy_change_pct"] == -28.9036
    assert m["h1_current_after_ppe_and_lease_crore"] == 59.7
    assert m["h1_prior_after_ppe_and_lease_crore"] == 110.78
    assert m["cash_proxy_yoy_change_pct"] == -46.1094
    assert m["h1_current_after_selected_finance_interest_crore"] == 47.45
    assert m["h1_prior_after_selected_finance_interest_crore"] == 94.17
    assert m["Q2_current_pbt_ex_exceptional_crore"] == 130.74
    assert m["Q2_underlying_pbt_yoy_change_pct"] == -2.5056
    assert m["h1_bad_debts_written_off_crore"] == 25.90
    assert m["Q2_property_sale_gain_standalone_crore"] == 47.26
    assert m["h1_property_sale_investing_cash_net_tax_crore"] == 46.39
    assert m["backlog_sequential_change_pct"] == -6.5549
    assert m["cash_after_selected_claims_not_owner_fcfe"] is True


@pytest.mark.parametrize("field,value", [
    ("schema", "UNFROZEN"),
    ("type", "PROSPECTIVE_STOCK_ALPHA"),
    ("prices_observed_at", "2026-10-27"),
])
def test_protocol_or_clocks_cannot_change(packet, field, value):
    changed = copy.deepcopy(packet)
    changed[field] = value
    with pytest.raises(ValueError):
        MODULE.evaluate(changed)


def test_original_raw_source_receipt_cannot_be_fabricated(packet):
    changed = copy.deepcopy(packet)
    changed["evidence_custody"]["raw_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="custody"):
        MODULE.evaluate(changed)


def test_portfolio_or_valuation_cannot_be_approved(packet):
    changed = copy.deepcopy(packet)
    changed["approval"]["capital_authorized"] = True
    with pytest.raises(ValueError, match="promoted"):
        MODULE.evaluate(changed)
    changed = copy.deepcopy(packet)
    changed["approval"]["parent_owner_fcfe_verified"] = True
    with pytest.raises(ValueError, match="promoted"):
        MODULE.evaluate(changed)


def test_no_bls_group_profit_belonging_to_minority(packet):
    changed = copy.deepcopy(packet)
    changed["BLS"]["consolidated"]["parent_attributable_profit_crore"] += 37.1024
    with pytest.raises(ValueError, match="attribution"):
        MODULE.evaluate(changed)


def test_no_unrealistic_numeric_financial_source(packet):
    changed = copy.deepcopy(packet)
    changed["MASTEK"]["H1_FY27"]["after_tax_cfo_crore"] = float("nan")
    with pytest.raises(ValueError, match="nonnegative"):
        MODULE.evaluate(changed)
    changed = copy.deepcopy(packet)
    changed["BLS"]["standalone_parent"]["subsidiary_dividends_investing_inflow_crore"] = -102.4435
    with pytest.raises(ValueError, match="nonnegative"):
        MODULE.evaluate(changed)


def test_must_not_confuse_parent_and_consolidated_raw_sources(packet):
    changed = copy.deepcopy(packet)
    changed["BLS"]["standalone_original_nse"] = "http://invalid.local"
    with pytest.raises(ValueError, match="source identity"):
        MODULE.evaluate(changed)
    changed = copy.deepcopy(packet)
    changed["MASTEK"]["fy27_H1_end"] = "2025-09-30"
    with pytest.raises(ValueError, match="observation period"):
        MODULE.evaluate(changed)
