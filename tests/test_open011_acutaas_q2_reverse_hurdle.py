"""OPEN011: test reported accounting perimeter, future-cash nulls and valuation math."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/open011_acutaas_q2_reverse_hurdle.py"
SPEC = importlib.util.spec_from_file_location("open011_acutaas", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SOURCE = (
    ROOT / "research/broad-discovery/OPEN011_ACUTAAS_FY27Q2_REVERSE_HURDLE_INPUT_20261027.json"
)


@pytest.fixture
def study():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def test_growth_matched_to_exact_consolidated_accounting_basis(study):
    report = MODULE.evaluate(study)
    assert report["Q2_FY27_group_revenue_crore"] == 436.9164
    assert report["Q2_revenue_YoY_pct_recomputed_from_rounded_source"] == 42.69
    assert report["Q2_company_operating_EBITDA_crore"] == 176.0
    assert report["Q2_group_EBITDA_YoY_pct_from_rounded_source"] == 84.68
    assert report["Q2_company_EBITDA_margin_pct"] == 40.28
    assert report["Q2_company_group_PAT_crore"] == 123.1
    assert report["Q2_group_PAT_YoY_pct_from_rounded_source"] == 71.21
    assert report["Q2_profit_attributable_to_parent_crore"] == 125.1692
    assert report["Q2_standalone_PAT_crore"] == 135.7366
    assert report["Q2_group_noncontrolling_profit_or_loss_crore_approx"] == -2.0692
    assert report["H1_group_EBITDA_margin_pct"] == 37.70


def test_dated_reverse_hurdles_are_not_targets_or_forecasts(study):
    result = MODULE.evaluate(study)
    assert result["pre_publication_market_cap_crore"] == 27409.0
    assert result["pre_publication_share_price_inr"] == 3348.8
    assert result["doubled_H1_group_PAT_only_mechanical_reference_crore"] == 396.2704
    assert result["pre_release_market_cap_over_doubled_H1_group_PAT_x"] == 69.17
    assert result["conditional_three_year_terminal_equity_cap_for_12pct_return_crore"] == 38507.67
    cases = result["reverse_hurdle_cases"]
    assert [x["terminal_multiple_hypothesis_x"] for x in cases] == [20, 25, 30, 40]
    assert [x["required_year_3_group_PAT_crore"] for x in cases] == [
        1925.38, 1540.31, 1283.59, 962.69
    ]
    assert [x["required_3_year_PAT_CAGR_vs_doubled_H1_pct"] for x in cases] == [
        69.37, 57.23, 47.96, 34.43
    ]
    assert all(
        not x["trade_signal"] and not x["is_price_target"]
        and x["probability_calibrated"] is None
        for x in cases
    )


def test_standalone_CFO_is_not_fabricated_as_consolidated_FCF(study):
    result = MODULE.evaluate(study)
    assert result["H1_standalone_after_tax_CFO_crore"] == 216.1341
    assert result["H1_group_after_tax_CFO"] is None
    assert result["H1_group_CFO_to_PAT_conversion"] is None
    assert result["owner_cash_verified"] is False
    assert result["capital_authorized"] is False
    assert result["probability_validated"] is False


@pytest.mark.parametrize(("key","value"),[
    ("schema","BACKDATED_PROSPECTIVE_ALPHA"),
    ("status","BUY"),
    ("research_date","2026-10-15"),
])
def test_prohibits_signal_or_backdated_research(study,key,value):
    altered = copy.deepcopy(study)
    altered[key] = value
    with pytest.raises(ValueError):
        MODULE.evaluate(altered)


def test_source_status_cannot_claim_retrieval_or_raw_hash(study):
    altered = copy.deepcopy(study)
    altered["observation_basis"]["original_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="custody"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(study)
    altered["observation_basis"]["raw_original_bytes_archived"] = True
    with pytest.raises(ValueError, match="custody"):
        MODULE.evaluate(altered)


def test_cash_profit_perimeter_and_guaranteed_returns_are_blocked(study):
    altered = copy.deepcopy(study)
    altered["reported_H1_FY27"]["consolidated_after_tax_CFO_crore"] = 216.1341
    with pytest.raises(ValueError, match="group CFO"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(study)
    altered["reported_H1_FY27"]["group_FCFE_crore"] = 198.1352
    with pytest.raises(ValueError, match="group CFO"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(study)
    altered["approval"]["stock_trade_approved"] = True
    with pytest.raises(ValueError, match="approval"):
        MODULE.evaluate(altered)


def test_parent_pat_and_standalone_pat_are_not_group_pat(study):
    altered = copy.deepcopy(study)
    altered["reported_Q2_FY27"]["financial_transcription_profit_attributable_to_parent_crore"] = 123.1
    with pytest.raises(ValueError, match="parent/group"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(study)
    altered["reported_Q2_FY27"]["financial_transcription_standalone_tax_crore"] = 0.0
    with pytest.raises((ValueError, TypeError), match="positive"):
        MODULE.evaluate(altered)


def test_wrong_fiscal_year_or_quote_source_is_rejected(study):
    altered = copy.deepcopy(study)
    altered["reported_Q2_FY27"]["ended"] = "2025-09-30"
    with pytest.raises(ValueError, match="period"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(study)
    altered["observation_basis"]["market_price_date"] = "2026-10-27"
    with pytest.raises(ValueError, match="chronology"):
        MODULE.evaluate(altered)


def test_hypothetical_growth_not_treated_as_issuer_guidance(study):
    altered = copy.deepcopy(study)
    altered["company_revised_guidance"]["FY27_revenue_growth_low_pct"] = 60
    with pytest.raises(ValueError, match="guidance"):
        MODULE.evaluate(altered)
    altered = copy.deepcopy(study)
    altered["conditional_valuation_contract"]["hypothetical_terminal_PE_multiples"] = [40]
    with pytest.raises(ValueError, match="spec"):
        MODULE.evaluate(altered)
