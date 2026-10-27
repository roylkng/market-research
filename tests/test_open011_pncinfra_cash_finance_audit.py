"""OPEN011: original-L001-P016 anchored PNCINFRA debt and CFO cash bridge.

All hard source identities, market cutoffs and no-buy gates fail closed.
"""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/open011_pncinfra_cash_finance_audit.py"
SPEC = importlib.util.spec_from_file_location("open011_pncinfra", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
INPUT = ROOT / "research/broad-discovery/OPEN011_PNCINFRA_LEVERED_CASH_INPUT_20261027.json"
PRIOR = ROOT / "research/l001/l001-p016-owner-cash-evidence-gates-100-v1.json"


@pytest.fixture
def original():
    return json.loads(INPUT.read_text(encoding="utf-8"))


@pytest.fixture
def baseline():
    return json.loads(PRIOR.read_text(encoding="utf-8"))


def test_cfo_rereplayed_against_signed_original_100(original, baseline):
    result = MODULE.audit(original, baseline)
    assert result["posthoc_original_sample_member"] is True
    assert result["equity_shares_millions"] == 256.539
    assert result["market_cap_crore"] == 3428.6437
    assert result["group_debt_crore"] == 5150.8476
    assert result["unverified_bank_and_cash_crore"] == 2237.8268
    assert result["group_net_borrowings_if_all_cash_accessible_crore"] == 2913.0208
    assert result["illustrative_enterprise_value_crore"] == 6341.6645
    assert result["CFO_reported_crore"] == 4592.9651
    assert result["FY26_cash_CFO_less_PPE_crore_NOT_owner_cash"] == 4266.9575
    assert result["FY26_actual_cash_change_crore"] == -269.7115
    assert result["asset_sale_gain_not_treated_as_recurring"] is True
    assert result["PAT_ex_only_337crore_road_sale_gain_crore"] == 494.77
    assert result["is_stock_selection_alpha"] is False
    assert result["is_investment_approved"] is False
    assert result["parent_owner_cash_verified"] is False


def test_working_capital_release_debt_service_falsifies_naive_cfo(original, baseline):
    result = MODULE.audit(original, baseline)
    assert result["trade_receivable_cash_release_crore"] == 4146.1024
    assert result["trade_receivable_release_pct_of_CFO"] == 90.27
    assert result["all_wc_releases_net_crore"] == 3631.5826
    assert result["before_WC_after_tax_operating_cash_crore"] == 961.3825
    assert result["after_PPE_before_interest_crore"] == 635.3749
    assert result["after_PPE_finance_interest_and_leases_crore"] == 48.3153
    assert result["strict_selected_cash_pct_of_cap"] == 1.41
    assert result["court_debarment_stay_is_interim"] is True
    assert result["court_next_hearing"] == "2026-11-26"
    assert result["Q2_FY27_real_data_available"] is False


@pytest.mark.parametrize(("field", "replacement"), [
    ("schema", "RETROACTIVE_ALPHA"),
    ("evidence_type", "PROSPECTIVE_BUY"),
    ("created_asof_date", "2026-10-15"),
    ("price_date", "2026-10-27"),
    ("isin", "INVALID"),
    ("original_HG009_SELECTED_member", False),
])
def test_source_issuer_clock_and_experiment_cannot_change(
    original, baseline, field, replacement
):
    changed = copy.deepcopy(original)
    changed[field] = replacement
    with pytest.raises(ValueError):
        MODULE.audit(changed, baseline)


@pytest.mark.parametrize(("field", "replacement"), [
    ("normalized_sustainable_parent_owner_FCFE_cr", 48.3153),
    ("parent_shareholder_debt_attribution_verified", True),
    ("portfolio_entry_authorized", True),
    ("permanent_legal_bidding_eligibility_verified", True),
    ("calibrated_1_or_3_year_stock_return_probability", 0.75),
])
def test_no_false_owner_cash_capital_or_legal_clearance(
    original, baseline, field, replacement
):
    changed = copy.deepcopy(original)
    changed["terminal_gates"][field] = replacement
    with pytest.raises(ValueError, match="false owner cash"):
        MODULE.audit(changed, baseline)


def test_original_100_report_and_xml_sha_cannot_drift(original, baseline):
    corrupted = copy.deepcopy(baseline)
    corrupted["company_cashflow_classification_rows"] = [
        row for row in corrupted["company_cashflow_classification_rows"]
        if row["symbol"] != "PNCINFRA"
    ]
    with pytest.raises(ValueError, match="no longer unique"):
        MODULE.audit(original, corrupted)
    corrupted = copy.deepcopy(baseline)
    corrupted["report_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="signed report"):
        MODULE.audit(original, corrupted)
    changed = copy.deepcopy(original)
    changed["sources"]["original_exchange_XML_sha256_from_l001"] = "f" * 64
    with pytest.raises(ValueError, match="XML identity"):
        MODULE.audit(changed, baseline)


@pytest.mark.parametrize(("field", "replacement"), [
    ("after_tax_operating_cash_flow", 9000),
    ("cash_PPE_and_intangible_spend", 0),
    ("trade_receivables_working_capital_release", 0),
    ("net_cash_from_financing", 0),
    ("cash_financing_interest_paid", float("nan")),
])
def test_accounting_bridge_signs_fail_if_source_rows_are_changed(
    original, baseline, field, replacement
):
    changed = copy.deepcopy(original)
    changed["FY26_group"][field] = replacement
    with pytest.raises(ValueError):
        MODULE.audit(changed, baseline)


def test_no_future_results_or_final_court_resolution(original, baseline):
    changed = copy.deepcopy(original)
    changed["court_and_catalyst"]["issuer_FY27_Q2_results_published_asof_research"] = True
    with pytest.raises(ValueError, match="court finality"):
        MODULE.audit(changed, baseline)
    changed = copy.deepcopy(original)
    changed["court_and_catalyst"]["permanent_clearance_verified"] = True
    with pytest.raises(ValueError, match="court finality"):
        MODULE.audit(changed, baseline)


def test_cash_cannot_be_called_fully_unrestricted(original, baseline):
    changed = copy.deepcopy(original)
    changed["risk_stresses"]["fully_unrestricted_other_bank_balances_unproven"] = False
    with pytest.raises(ValueError, match="restrictions"):
        MODULE.audit(changed, baseline)


def test_nonconsolidated_financial_scope_and_share_count_rejected(original, baseline):
    changed = copy.deepcopy(original)
    changed["FY26_group"]["scope"] = "STANDALONE"
    with pytest.raises(ValueError, match="accounting basis"):
        MODULE.audit(changed, baseline)
    changed = copy.deepcopy(original)
    changed["equity_paid_up_capital_lakh_inr"] = 515.0
    with pytest.raises(ValueError, match="shares changed"):
        MODULE.audit(changed, baseline)
