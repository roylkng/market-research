"""Zuari original stake/debt/segment bridge is NOT an investable price target."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p025_zuari_falsification import (
    Q1_PRESENTATION,
    build_zuari_falsification,
    load_pinned_prior,
    materialize_zuari_falsification,
    validate_zuari_falsification,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/l001/l001-p025-zuari-q1-debt-stake-falsification-v1.json"


def test_signed_original_Oct19_stakes_and_Q1_issuer_finance_are_distinct():
    r = materialize_zuari_falsification(ROOT)
    assert r["report_id"] == (
        "L001-P025-ZUARI-CROSSDATE-DEBT-SERVICE-VALUE-FALSIFICATION-v1"
    )
    assert r["analysis_date_ist"] == "2026-10-21"
    assert r["source_page_and_method"]["source_publication_date"] == "2026-08-14"
    assert r["source_page_and_method"]["original_pdf_bytes_archived_in_this_packet"] is False
    assert r["source_page_and_method"]["original_pdf_sha256_in_this_packet"] is None
    assert r["source_page_and_method"]["stake_table_pdf_page_zero_based"] == 19
    assert r["source_page_and_method"]["consolidated_profit_loss_pdf_page_zero_based"] == 24
    assert r["cross_date_basis"]["Oct19_parent_equity_cap_old_basic_shares_cr"] == (
        771.6305
    )
    assert r["cross_date_basis"]["NSE_Oct19_listed_stake_marks_using_June_units_cr"] == (
        3764.92078
    )
    assert r["cross_date_basis"]["March_2026_net_borrowings_cr_not_current"] == (
        2519.4245
    )
    assert r["cross_date_basis"]["issuer_June_2026_stakes_cr"] == 4223.0
    assert r["cross_date_basis"]["current_stake_units_and_parent_fully_diluted_equity_verified"] is False


def test_company_reported_profit_bridge_adds_up_without_operating_earnings_invention():
    r = materialize_zuari_falsification(ROOT)
    assert 8.05 + 13.74 - 61.54 == pytest.approx(-39.75)
    assert -39.75 + 34.37 == pytest.approx(-5.38)
    assert -5.38 + 4.81 == pytest.approx(-0.57)
    assert r["Q1_pretax_before_associate_profit_cr"] == -39.75
    assert r["Q1_reported_PBT_cr"] == -0.57
    assert r["issuer_Q1FY27_reported_segment_ebitda_cr"] == 8.05
    assert r["issuer_Q1FY27_reported_finance_cost_cr"] == 61.54
    assert r["Q1_segment_ebitda_finance_cost_shortfall_cr"] == 53.49
    assert r["Q1_segment_ebitda_divided_by_finance_cost"] == pytest.approx(0.130809)
    assert r["Q1_associate_JV_earnings_not_distributed_cash_cr"] == 34.37
    assert r["Q1_other_comprehensive_income_not_operating_cash_cr"] == 519.69
    assert r["OCI_is_not_free_cash_or_parent_shareholder_realized_profit"] is True


def test_stale_nav_gap_disappears_after_small_additional_markdown():
    r = materialize_zuari_falsification(ROOT)
    assert r["hypothetical_stale_balance_sheet_stake_gap_cr_not_attributable"] == (
        pytest.approx(473.86578)
    )
    assert r["additional_stake_markdown_erasing_stale_gap_percent_not_probability"] == (
        pytest.approx(12.586342)
    )
    rows = r["scenarios_without_operating_cashflow_or_new_debt_reconciliation"]
    assert len(rows) == 6
    assert rows[0]["illustrative_gap_after_stale_March_debt_and_old_cap_cr"] > 0
    assert rows[2]["illustrative_gap_after_stale_March_debt_and_old_cap_cr"] == (
        pytest.approx(97.373702)
    )
    assert rows[3]["illustrative_gap_after_stale_March_debt_and_old_cap_cr"] == (
        pytest.approx(0, abs=0.0001)
    )
    assert rows[-1]["illustrative_gap_after_stale_March_debt_and_old_cap_cr"] < 0
    assert all(row["debt_or_parent_cash_flow_updated"] is False for row in rows)


def test_mutating_source_finance_fact_prevents_signed_report():
    data, receipts = load_pinned_prior(ROOT)
    facts = dict(Q1_PRESENTATION)
    facts["consolidated_finance_cost_cr"] = 30.0
    with pytest.raises(AlphaContractError, match="consolidated P&L"):
        build_zuari_falsification(data, receipts, source_facts=facts)
    data["OCT19_LISTED_STAKES"]["stake_marks_by_date_cr"]["2026-10-19"] = 4000
    with pytest.raises(AlphaContractError, match="stake/debt/share bridge"):
        build_zuari_falsification(data, receipts)
    report = materialize_zuari_falsification(ROOT)
    altered = copy.deepcopy(report)
    altered["expected_1y_3y_net_return"] = 0.50
    with pytest.raises(AlphaContractError, match="report hash changed"):
        validate_zuari_falsification(altered, root=ROOT)
    edited = copy.deepcopy(report)
    edited.pop("report_sha256")
    edited["company_cashflow_and_lease_adjusted_NAV"] = 1900
    edited["report_sha256"] = digest(edited)
    with pytest.raises(AlphaContractError, match="not source reproducible"):
        validate_zuari_falsification(edited, root=ROOT)


def test_no_investable_value_and_packet_reproducibility():
    r = materialize_zuari_falsification(ROOT)
    assert r["current_debt_pledges_cash_waterfall_verified"] is False
    assert r["company_cashflow_and_lease_adjusted_NAV"] is None
    assert r["after_tax_liquidatable_listed_stake_value"] is None
    assert r["parent_shareholder_probability_weighted_fair_value"] is None
    assert r["expected_1y_3y_net_return"] is None
    assert r["valuation_or_buy_recommendation_authorized"] is False
    assert r["original_300_company_prospective_return_population_changed"] is False
    assert r["live_capital_allowed"] is False
    if REPORT.is_file():
        assert json.loads(REPORT.read_text(encoding="utf-8")) == r
    command = subprocess.run(
        [sys.executable, "scripts/materialize_l001_p025_zuari.py", "--check"],
        capture_output=True, text=True, cwd=ROOT, check=True,
    )
    assert json.loads(command.stdout)["capital_allowed"] is False
