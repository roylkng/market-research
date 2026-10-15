"""HG009 P014 source replay and symmetry tests. No model picks from H1."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p014_economics import (
    PREDECLARED,
    build_review,
    load_inputs,
    materialize,
    validate_review,
)

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "research/hg009/hg009-p014-economic-symmetry-and-cash-v1.json"


def test_fixed_ten_identities_original_oct15_and_no_investment_promotion():
    result = materialize(ROOT)
    assert result["case_count"] == 10
    assert [r["symbol"] for r in result["cash_flow_and_other_income_diagnostics"]] == list(
        PREDECLARED
    )
    assert result["price_source_EQ_coverage_count"] == 10
    assert result["outcome_data_seen_before_posthoc_review"] is True
    assert result["this_is_not_preregistered_first_day_alpha"] is True
    assert result["stock_selection_fitted_to_oct15_prices"] is False
    assert result["investment_value_ready_count"] == 0
    assert result["scenario_calibration_complete_count"] == 0
    assert result["live_capital_allowed"] is False
    for row in result["cash_flow_and_other_income_diagnostics"]:
        assert row["price_date"] == "2026-10-15"
        assert row["original_oct15_official_EQ_close_inr_not_current_quote"] > 0
        assert row["predicted_1year_or_3year_after_cost_return"] is None
        assert row["investable_risk_adjusted_value_per_share"] is None
        assert row["capital_eligible"] is False
    assert result["diligence_source_lanes_not_expected_return_rankings"] == {
        "CASH_FLOW_REPLAY_NEEDS_ATTRIBUTION": [
            "ACE", "ACUTAAS", "DATAMATICS", "MAYURUNIQ", "TRAVELFOOD",
        ],
        "QUARTER_OTHER_INCOME_SYMMETRY_NEEDS_CONSOLIDATION": ["PIXTRANS"],
        "ORIGINAL_OPERATING_CASH_OR_LEGAL_SOURCE_MISSING": [
            "ANANTRAJ", "INOXGREEN", "POKARNA", "SAMBHV",
        ],
    }
    validate_review(result, ROOT)


def test_ACE_ACUTAAS_TRAVELFOOD_original_fy26_bank_cash_reconciliation():
    result = materialize(ROOT)
    by = {c["symbol"]: c["source_reported_economics_not_owner_fcf"]
          for c in result["cash_flow_and_other_income_diagnostics"]}
    assert by["ACE"]["CFO_less_PPE_proxy_cr_not_owner_FCF"] == 324.01
    assert by["ACE"]["CFO_after_all_investing_cr_not_owner_FCF"] == 67.38
    assert by["ACUTAAS"]["CFO_less_PPE_proxy_cr_not_owner_FCF"] == -35.8052
    assert by["ACUTAAS"]["CFO_after_all_investing_cr_not_owner_FCF"] == 26.2306
    assert by["TRAVELFOOD"]["CFO_less_PPE_proxy_cr_not_owner_FCF"] == 354.436
    assert by["TRAVELFOOD"]["CFO_after_all_investing_cr_not_owner_FCF"] == 243.161
    for symbol in ("ACE", "ACUTAAS", "TRAVELFOOD"):
        row = by[symbol]
        assert round(
            row["CFO_after_all_investing_cr_not_owner_FCF"]
            + row["net_financing_cash_cr"], 4
        ) == row["net_reported_cash_change_cr"]
        assert row["financing_cash_is_owner_cash"] is False
        assert row["financial_investments_treated_as_expense"] is False


def test_mayur_and_datamatics_investing_is_not_permanent_loss_or_free_cash():
    result = materialize(ROOT)
    by = {c["symbol"]: c["source_reported_economics_not_owner_fcf"]
          for c in result["cash_flow_and_other_income_diagnostics"]}
    mayur = by["MAYURUNIQ"]
    assert mayur["CFO_less_PPE_proxy_cr_not_owner_FCF"] == 108.9456
    assert mayur["net_asset_placement_cr_not_expense"] == 105.8599
    assert mayur["CFO_after_all_investing_cr_not_owner_FCF"] == 18.1056
    assert mayur["restricted_vs_unrestricted_investments_verified"] is False
    dat = by["DATAMATICS"]
    assert dat["CFO_less_PPE_proxy_cr_not_owner_FCF"] == 284.42
    assert dat["CFO_after_all_investing_cr_not_owner_FCF"] == 7.45
    assert dat["net_investment_purchase_cr_not_expense"] == 262.76
    assert dat["financial_investments_distributable_verified"] is False
    assert result["all_historical_investing_asset_placements_are_permanent_expense"] is False


def test_pix_must_compare_same_other_income_exclusion_on_both_quarters():
    result = materialize(ROOT)
    pix = next(
        row["source_reported_economics_not_owner_fcf"]
        for row in result["cash_flow_and_other_income_diagnostics"]
        if row["symbol"] == "PIXTRANS"
    )
    assert pix["basis"] == "Q1FY27_VS_Q1FY26_STANDALONE_UNAUDITED"
    assert pix["current_FVTPL_in_other_income_cr"] == 25.2949
    assert pix[
        "asymmetric_only_current_FVTPL_excluded_growth_pct_not_comparable"
    ] == 14.71
    assert pix[
        "symmetric_both_periods_PBT_ex_other_income_growth_pct_not_owner_FCF"
    ] == pytest.approx(99.68, abs=0.01)
    assert result["single_adjustment_pix_is_valid_symmetric_growth_claim"] is False


def test_original_filing_bytes_tamper_and_unsigned_report_rejected():
    source, receipts = load_inputs(ROOT)
    wrong = copy.deepcopy(source)
    wrong["pix"]["quarter_numbers_recalculated_to_inr_crore"][
        "Q1FY27_STANDALONE"
    ]["other_income"] += 1
    with pytest.raises(AlphaContractError, match="PIX current symmetric income"):
        build_review(wrong, receipts)
    wrong = copy.deepcopy(source)
    wrong["market"]["source_identity_rows"][0]["symbol"] = "FUTURE_WINNER"
    with pytest.raises(AlphaContractError, match="same-ISIN original Oct15 quote"):
        build_review(wrong, receipts)
    bad = materialize(ROOT)
    bad["cash_flow_and_other_income_diagnostics"][0][
        "investable_risk_adjusted_value_per_share"
    ] = 99999
    with pytest.raises(AlphaContractError, match="signed review hash"):
        validate_review(bad, ROOT)


def test_reproducible_packet_and_standalone_check_command():
    expected = materialize(ROOT)
    assert json.loads(PATH.read_text(encoding="utf-8")) == expected
    proc = subprocess.run(
        [sys.executable, "scripts/materialize_hg009_p014.py", "--check"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    summary = json.loads(proc.stdout)
    assert summary["state"] == "VERIFIED"
    assert summary["company_count"] == 10
    assert summary["investable"] == 0
