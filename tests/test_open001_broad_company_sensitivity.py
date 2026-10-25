"""Fail-closed reproducibility for OPEN001, no live-capital or alpha promotion."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/open001_broad_company_sensitivity.py"
SPEC = importlib.util.spec_from_file_location("open001", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ORIGINAL = (
    REPO / "research/broad-discovery/open001-bls-transrail-oct2026-source-input.json"
)


@pytest.fixture
def packet():
    return json.loads(ORIGINAL.read_text())


def test_source_arithmetic_and_no_trade_gate(packet):
    report = MODULE.evaluate(packet)
    assert report["approved_live_capital"] is False
    assert report["used_known_historical_results_to_modify_original_HG009"] is False
    assert report["investment_readiness"] == "NOT_ESTABLISHED"
    bls, trans = report["candidates"]
    assert (bls["symbol"], trans["symbol"]) == ("BLS", "TRANSRAILL")
    assert bls["unresolved_official_procurement_tenders"] == 4
    assert trans["unresolved_official_procurement_tenders"] is None
    assert bls["FY26_CFO_less_selected_PPE_crore"] == 765.8431
    assert bls["FY26_naive_CFO_less_PPE_to_observed_mcap_pct"] == 8.93
    assert bls["visa_share_of_reported_segment_results_pct"] == 88.39
    assert trans["FY26_CFO_less_selected_PPE_crore"] == 394.17
    assert trans["FY26_naive_CFO_less_PPE_to_observed_mcap_pct"] == 6.84
    assert all(x["verified_parent_owner_cash_crore"] is None for x in report["candidates"])
    assert all(
        y["probability"] is None and not y["is_price_target"]
        for x in report["candidates"]
        for y in x["two_year_conditional_sensitivities"]
    )


def test_two_year_conditional_sensitivity_results(packet):
    report = MODULE.evaluate(packet)
    bls, trans = report["candidates"]
    a = {r["case"]: r["conditional_two_year_value_inr"]
         for r in bls["two_year_conditional_sensitivities"]}
    b = {r["case"]: r["conditional_two_year_value_inr"]
         for r in trans["two_year_conditional_sensitivities"]}
    assert a == {
        "bear": 133.12,
        "flat_no_rerating": 199.68,
        "conditional_base": 333.97,
        "optimistic": 463.39,
    }
    assert b == {
        "bear": 224.25,
        "flat_no_rerating": 358.8,
        "conditional_base": 523.13,
        "optimistic": 749.39,
    }


def test_fails_when_noncontrolling_profit_is_assigned_to_parent(packet):
    p = copy.deepcopy(packet)
    p["candidates"][0]["fy26_parent_attributable_pat_crore"] += 37.1024
    with pytest.raises(ValueError, match="NCI"):
        MODULE.evaluate(p)


@pytest.mark.parametrize("symbol,field,value", [
    ("BLS", "price_date", "2026-10-24"),
    ("TRANSRAILL", "reference_financial_year_end", "2025-03-31"),
    ("BLS", "fy26_diluted_eps_inr", 0),
    ("TRANSRAILL", "fy26_consolidated_after_tax_cfo_crore", float("nan")),
])
def test_bad_original_or_stale_inputs_fail(packet, symbol, field, value):
    p = copy.deepcopy(packet)
    i = next(x for x in p["candidates"] if x["symbol"] == symbol)
    i[field] = value
    with pytest.raises(ValueError):
        MODULE.evaluate(p)


def test_reject_live_capital_or_fabricated_owner_cash(packet):
    p = copy.deepcopy(packet)
    p["status"] = "TRADE_APPROVED"
    with pytest.raises(ValueError, match="status"):
        MODULE.evaluate(p)
    p = copy.deepcopy(packet)
    p["candidates"][0]["conservative_or_parent_distributable_owner_cash_crore"] = 765.84
    with pytest.raises(ValueError, match="owner cash"):
        MODULE.evaluate(p)


def test_reject_unsupported_model_and_extra_candidates(packet):
    p = copy.deepcopy(packet)
    p["candidates"][0]["hypothetical_two_year_scenarios"][0]["terminal_pe_multiple"] = 100
    with pytest.raises(ValueError, match="out of range"):
        MODULE.evaluate(p)
    p = copy.deepcopy(packet)
    p["candidates"][1]["symbol"] = "INJECT"
    with pytest.raises(ValueError, match="expected two"):
        MODULE.evaluate(p)


def test_no_assumed_procurement_winner_or_backdated_bid_date(packet):
    p = copy.deepcopy(packet)
    p["candidates"][0]["pending_mission_procurement_2026"][0]["awardee"] = "BLS"
    with pytest.raises(ValueError, match="no bid or award"):
        MODULE.evaluate(p)
    p = copy.deepcopy(packet)
    p["candidates"][0]["pending_mission_procurement_2026"][3]["bid_opening"] = "2026-10-01"
    with pytest.raises(ValueError, match="no bid or award"):
        MODULE.evaluate(p)
    p = copy.deepcopy(packet)
    p["candidates"][0]["pending_mission_procurement_2026"].pop()
    with pytest.raises(ValueError, match="tender watch"):
        MODULE.evaluate(p)
