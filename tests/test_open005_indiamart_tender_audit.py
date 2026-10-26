"""OPEN005 audit tests: cross-perimeter cash, source time and tender non-claims."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/open005_indiamart_tender_audit.py"
SPEC = importlib.util.spec_from_file_location("open005_indiamart", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
FILE = ROOT / "research/broad-discovery/OPEN005_INDIAMART_CASH_BLS_TENDER_INPUT_20261026.json"


@pytest.fixture
def record():
    return json.loads(FILE.read_text(encoding="utf-8"))


def test_exact_original_audited_cash_replay(record):
    r = MODULE.evaluate(record)
    x = r["INDIAMART"]
    assert r["return_alpha_verified"] is False
    assert r["approved_investments"] == 0
    assert x["fy26_consolidated_after_tax_cfo_crore"] == 694.2
    assert x["fy25_consolidated_after_tax_cfo_crore"] == 623.2
    assert x["cfo_growth_pct"] == 11.3928
    assert x["before_working_capital_operating_profit_growth_pct"] == 4.1345
    assert x["contract_liability_inflow_share_of_CFO_pct"] == 41.429
    assert x["FY26_group_selected_use_cash_crore"] == 674.0
    assert x["FY26_group_after_selected_deferred_consideration_crore"] == 647.2
    assert x["FY26_group_after_selected_dividends_crore"] == 347.2
    assert x["FY26_group_selected_use_cash_if_no_contract_liability_increase_crore"] == 386.4
    assert x["FY26_group_selected_use_cash_if_FY25_contract_liability_pace_crore"] == 624.1


def test_parent_group_boundary_and_scenario_denominators(record):
    x = MODULE.evaluate(record)["INDIAMART"]
    assert x["FY26_parent_after_tax_CFO_crore"] == 668.5
    assert x["parent_share_of_group_CFO_pct"] == 96.2979
    assert x["FY26_parent_selected_use_cash_crore"] == 653.9
    assert x["FY26_parent_selected_use_cash_after_common_dividends_crore"] == 353.9
    assert x["reported_group_CFO_selected_use_yield_at_stale_intraday_cap_pct"] == 7.1672
    assert x["no_liability_increment_stress_yield_at_intraday_cap_pct"] == 4.1089
    assert x["latest_Q1_deferred_revenue_crore"] == 2014
    assert x["latest_Q1_cash_investments_crore"] == 3553
    assert x["latest_Q1_parent_cash_investments_crore"] == 3316
    assert x["latest_Q1_parent_share_of_group_cash_investments_pct"] == 93.3296
    assert x["paying_suppliers_net_change"] == -1850
    assert x["fully_distributable_parent_FCFE_crore"] is None
    assert x["unrestricted_parent_cash_crore"] is None


def test_bid_time_is_not_award_time(record):
    r = MODULE.evaluate(record)
    by_id = {x["id"]: x for x in r["BLS_tender_status"]}
    assert by_id["2026_MEA_852512_1"]["observation_status"] == (
        "SCHEDULE_HOUR_PASSED_NO_OPENING_PROOF"
    )
    assert by_id["2026_MEA_852578_1"]["observation_status"] == (
        "SCHEDULE_HOUR_NOT_REACHED_NO_OPENING_PROOF"
    )
    assert by_id["2026_MEA_852518_1"]["observation_status"] == (
        "SCHEDULED_DAY_EXACT_HOUR_UNVERIFIED"
    )
    assert by_id["2026_MEA_853372_1"]["observation_status"] == (
        "SCHEDULE_HOUR_NOT_REACHED_NO_OPENING_PROOF"
    )
    assert all(
        x["award_verified"] is False and x["bidder_identity_verified"] is False
        for x in by_id.values()
    )


@pytest.mark.parametrize("field,value", [
    ("schema", "PROSPECTIVE_SIGNAL"),
    ("research_type", "BUY_APPROVED"),
    ("as_of_local", "2026-10-27T17:00:00+05:30"),
])
def test_cannot_relabel_or_backdate_evidence(record, field, value):
    altered = copy.deepcopy(record)
    altered[field] = value
    with pytest.raises(ValueError):
        MODULE.evaluate(altered)


def test_cannot_fabricate_raw_archive_or_trade_permission(record):
    altered = copy.deepcopy(record)
    altered["source_integrity"]["original_pdf_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="custody"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(record)
    altered["freeze"]["investment_authorized"] = True
    with pytest.raises(ValueError, match="capital"):
        MODULE.evaluate(altered)


def test_cannot_claim_unpublished_future_earnings(record):
    altered = copy.deepcopy(record)
    altered["indiamart"]["next_financial_result_published_as_of_cutoff"] = True
    with pytest.raises(ValueError, match="backfilled"):
        MODULE.evaluate(altered)


def test_reject_bad_cash_and_period_values(record):
    altered = copy.deepcopy(record)
    altered["indiamart"]["fy26_consolidated_crore"]["after_tax_operating_cash"] = float("nan")
    with pytest.raises(ValueError, match="nonfinite"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(record)
    altered["indiamart"]["fy26_consolidated_crore"]["cash_generated_before_tax"] = 900
    with pytest.raises(ValueError, match="cash generated"):
        MODULE.evaluate(altered)


def test_forbid_mixing_balance_sheet_cash_and_service_obligations(record):
    altered = copy.deepcopy(record)
    altered["indiamart"]["cash_and_deferred_revenue_are_not_interchangeable"] = False
    with pytest.raises(ValueError, match="separate"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(record)
    altered["indiamart"]["parent_cash_not_equivalent_to_fully_distributable_cash"] = False
    with pytest.raises(ValueError, match="not proven"):
        MODULE.evaluate(altered)


def test_tender_claims_require_new_independent_registration(record):
    altered = copy.deepcopy(record)
    altered["BLS_tenders"][0]["award_confirmed"] = True
    with pytest.raises(ValueError, match="unverified tender"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(record)
    altered["BLS_tenders"][1]["bidder_names_confirmed"] = True
    with pytest.raises(ValueError, match="unverified tender"):
        MODULE.evaluate(altered)


def test_source_or_local_tender_clock_must_not_shift(record):
    altered = copy.deepcopy(record)
    altered["BLS_tenders"][1]["published_opening_local"] = (
        "2026-10-26T18:00:00+00:00"
    )
    with pytest.raises(ValueError, match="IST offset"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(record)
    altered["indiamart"]["reference_market_cap_observed_at"] = (
        "2026-10-26T15:40:00+05:30"
    )
    with pytest.raises(ValueError, match="observation"):
        MODULE.evaluate(altered)
