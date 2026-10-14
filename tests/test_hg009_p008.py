"""Original NSE cash evidence is not yet company-owner cash or a buy rating."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p008_underwriting import (
    GATES,
    SYMBOLS,
    build_packet,
    load_sources,
    materialize,
    validate_packet,
)
from marketlab.hg009_p008_valuation import (
    SOURCE_KEYS,
    evaluate_issuer_equity_dcf,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/hg009/hg009-p008-ten-underwriting-evidence-v1.json"


def _company(symbol: str) -> dict:
    report = materialize(ROOT)
    return next(row for row in report["cases"] if row["symbol"] == symbol)


def test_complete_original_ten_case_research_identity_and_pinned_sources():
    report = materialize(ROOT)
    assert report["company_count"] == 10
    assert [r["symbol"] for r in report["cases"]] == list(SYMBOLS)
    assert len({x["frozen_isin"] for x in report["cases"]}) == 10
    assert len(report["ten_proof_fields"]) == 10
    assert tuple(report["ten_proof_fields"]) == GATES
    assert report["original_consolidated_fy26_new_issuer_cash_pilots"] == 3
    assert set(report["prior_source_git_sha_receipts"]) == {
        "hg007", "five", "datamatics", "hundred", "accounting", "new_fy26",
    }
    assert report["fully_underwritten_equity_valuations_count"] == 0
    assert report["shareholder_owner_fcf_normalized_count"] == 0
    assert report["paper_investment_eligibility_count"] == 0
    assert report["live_capital_allowed"] is False
    for row in report["cases"]:
        assert len(row["ten_proof_gates"]) == 10
        assert row["normalized_owner_cashflow_cr"] is None
        assert row["current_fair_value_per_share"] is None
        assert row["bear_base_bull_attributable_equity_values"] is None
        assert row["calibrated_scenario_probabilities"] is None
        assert row["portfolio_eligibility_allowed"] is False
        assert row["live_capital_allowed"] is False


def test_new_fy26_original_consolidated_cash_exhibits_funding_differences():
    a = _company("ACUTAAS")["reported_financial_hurdle_not_equity_value"]
    b = _company("ACE")["reported_financial_hurdle_not_equity_value"]
    c = _company("TRAVELFOOD")["reported_financial_hurdle_not_equity_value"]
    assert a["cash_flow_cfo_cr"] == 292.1736
    assert a["cash_ppe_spend_cr"] == 327.9788
    assert a["simple_cfo_less_ppe_cr"] == -35.8052
    assert a["reported_borrowings_cr_not_current"] == 26.4908
    assert a["reported_nci_equity_cr_not_shareholder_cash"] == 57.1892
    assert b["cash_flow_cfo_cr"] == 417.27
    assert b["cash_ppe_spend_cr"] == 93.26
    assert b["simple_cfo_less_ppe_cr"] == 324.01
    assert b["reported_current_investments_cr_not_unrestricted"] == 560.26
    assert c["cash_flow_cfo_cr"] == 392.968
    assert c["cash_ppe_spend_cr"] == 38.532
    assert c["simple_cfo_less_ppe_cr"] == 354.436
    assert c["lease_principal_financing_cr"] == 123.704
    assert c["interest_paid_financing_cr"] == 30.056
    assert c["simple_cfo_less_ppe_and_lease_cr"] == 230.732
    assert c["simple_cfo_less_ppe_lease_interest_cr"] == 200.676
    for case in (a, b, c):
        assert case["original_html_sha256"] is None
        assert case["original_html_bytes_archived"] is False
        assert case["owner_cash_flow_verified"] is False
        assert case["maintenance_capex_verified"] is False
        assert case["reported_cash_cr_not_verified_excess"] >= 0
        assert case["reported_current_investments_cr_not_unrestricted"] >= 0


def test_existing_datamatics_mayur_and_pix_do_not_mix_reporting_bases():
    d = _company("DATAMATICS")["reported_financial_hurdle_not_equity_value"]
    m = _company("MAYURUNIQ")["reported_financial_hurdle_not_equity_value"]
    p = _company("PIXTRANS")["reported_financial_hurdle_not_equity_value"]
    assert d["cash_flow_cfo_cr"] == 323.99
    assert d["simple_cfo_less_ppe_cr"] == 284.42
    assert m["cash_flow_cfo_cr"] == 133.1527
    assert m["simple_cfo_less_ppe_cr"] == 108.9456
    assert p["basis"] == "Q1FY27_STANDALONE_UNAUDITED_PBT_QUALITY_ONLY"
    assert p["fvtpl_gain_in_reported_pbt_cr"] == 25.2949
    assert p["pbt_excluding_one_fvtpl_item_cr"] == 35.5219
    assert p["operating_cfo_cr"] is None
    assert _company("POKARNA")["reported_financial_hurdle_not_equity_value"] is None


def test_original_source_mutation_and_case_packet_tamper_fail_closed():
    data, receipts = load_sources(ROOT)
    damaged = copy.deepcopy(data)
    damaged["hg007"]["cases"][0]["symbol"] = "FAKE_FUTURE_WINNER"
    with pytest.raises(AlphaContractError, match="not in original"):
        build_packet(damaged, receipts)
    damaged_report = materialize(ROOT)
    damaged_report["cases"][0]["current_fair_value_per_share"] = 100000
    with pytest.raises(AlphaContractError, match="SHA altered"):
        validate_packet(damaged_report, ROOT)


def _synthetic_full_evidence():
    raw = {key: f"TEST_ONLY_{key}".encode() for key in SOURCE_KEYS}
    meta = {
        key: {
            "independently_verified_original_source": True,
            "original_raw_bytes_archived": True,
            "original_document_url": f"https://example.invalid/test/{key}",
            "frozen_as_of_date": "2026-10-14",
            "sha256": hashlib.sha256(raw[key]).hexdigest(),
        }
        for key in SOURCE_KEYS
    }
    identity = {
        "symbol": "SYNTHETIC_NONLISTED_FIXTURE",
        "isin": "INE000000001",
        "accounting_regime": "NONFINANCIAL_CONSOLIDATED_EQUITY_OWNER_CASH",
    }
    cash = {
        "normalized_owner_cash_cr": 100,
        "separately_verified_excess_cash_cr": 30,
        "period_end": "2026-03-31",
        "parent_minorities_reconciled": True,
        "maint_and_growth_capex_separated": True,
        "cash_financing_lease_reconciled": True,
        "working_capital_normalized": True,
        "restricted_investment_cash_excluded": True,
    }
    market = {
        "date": "2026-10-14",
        "current_fully_diluted_shares": 10000000,
        "dated_original_nse_eq_price_inr": 200,
        "required_equity_return_fraction": 0.15,
        "total_round_trip_impact_fees_tax_fraction": 0.02,
        "shareholder_discount_rate": 0.12,
        "corporate_action_basis_verified": True,
        "order_book_depth_and_impact_verified": True,
    }
    scenarios = [
        {
            "name": "BEAR", "annual_owner_cash_growth_plus_one": 0.9,
            "terminal_cash_to_equity_multiple": 8,
            "historical_base_rate_events": 20,
        },
        {
            "name": "BASE", "annual_owner_cash_growth_plus_one": 1.07,
            "terminal_cash_to_equity_multiple": 14,
            "historical_base_rate_events": 50,
        },
        {
            "name": "BULL", "annual_owner_cash_growth_plus_one": 1.2,
            "terminal_cash_to_equity_multiple": 22,
            "historical_base_rate_events": 30,
        },
    ]
    return {
        "identity": identity, "owner_cash": cash, "market": market,
        "scenarios": scenarios, "source_meta": meta, "original_bytes": raw,
    }


def test_synthetic_three_year_equity_dcf_reconciles_and_forbids_capital():
    inputs = _synthetic_full_evidence()
    report = evaluate_issuer_equity_dcf(**inputs)
    assert report["horizon_years"] == 3
    assert len(report["scenarios"]) == 3
    assert [row["name"] for row in report["scenarios"]] == [
        "BEAR", "BASE", "BULL",
    ]
    assert [row["empirical_base_rate_probability"] for row in report["scenarios"]] == [
        0.2, 0.5, 0.3,
    ]
    assert report["weighted_per_share_value_inr"] > 0
    assert report["not_a_causal_llm_alpha_test"] is True
    assert report["live_capital_allowed"] is False
    assert report["model_sha256"] is not None


def test_real_incomplete_research_inputs_cannot_be_run_as_investable_dcf():
    fixture = _synthetic_full_evidence()
    fixture["owner_cash"]["working_capital_normalized"] = False
    with pytest.raises(AlphaContractError, match="reconciliation incomplete"):
        evaluate_issuer_equity_dcf(**fixture)
    fixture = _synthetic_full_evidence()
    fixture["source_meta"]["owner_cash_source"]["original_raw_bytes_archived"] = False
    with pytest.raises(AlphaContractError, match="incomplete source gate"):
        evaluate_issuer_equity_dcf(**fixture)
    fixture = _synthetic_full_evidence()
    fixture["original_bytes"]["owner_cash_source"] += b"tampered"
    with pytest.raises(AlphaContractError, match="source hash mismatch"):
        evaluate_issuer_equity_dcf(**fixture)
    fixture = _synthetic_full_evidence()
    fixture["scenarios"][1]["historical_base_rate_events"] = 0
    with pytest.raises(AlphaContractError, match="calibration"):
        evaluate_issuer_equity_dcf(**fixture)


def test_stable_report_and_cli_check_are_read_only():
    expected = materialize(ROOT)
    assert expected == json.loads(OUTPUT.read_text(encoding="utf-8"))
    done = subprocess.run(
        [sys.executable, "scripts/materialize_hg009_p008.py", "--check"],
        check=True, cwd=ROOT, capture_output=True, text=True,
    )
    assert json.loads(done.stdout)["state"] == "VERIFIED"
