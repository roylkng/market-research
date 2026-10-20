"""L001 P023: independently replay four original economic disqualification gates."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p023_frontier import (
    ORIGINAL_UK_PDF_SHA,
    build_cross_company_falsification,
    load_original_review_sources,
    materialize_falsification_frontier,
    validate_falsification_frontier,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/l001/l001-p023-value-falsification-frontier-v1.json"


def _result():
    return materialize_falsification_frontier(ROOT)


def test_four_original_case_identifiers_are_preserved_without_investment_promotion():
    result = _result()
    assert result["analysis_date_ist"] == "2026-10-20"
    assert result["market_session_date_ist"] == "2026-10-19"
    assert result["issuer_hypotheses_reviewed"] == [
        "GESHIP", "ZUARIIND", "DATAMATICS", "SUNTV",
    ]
    assert [x["symbol"] for x in result["evidence"]] == [
        "GESHIP", "ZUARIIND", "DATAMATICS", "SUNTV",
    ]
    assert set(result["source_receipts"]) == {
        "p017", "p018", "p020", "p021", "p022_receipt",
    }
    assert result["economic_value_proven_cases"] == 0
    assert result["completed_probability_weighted_equity_valuations"] == 0
    assert result["investable_portfolio_candidates_approved"] == 0
    assert result["return_forecasts_created"] is False
    assert result["live_capital_allowed"] is False
    assert all(
        x["economic_mispricing_confirmed"] is False
        for x in result["evidence"]
    )


def test_geship_stale_nav_discount_and_fleet_haircut_not_margin_of_safety():
    ge = _result()["evidence"][0]
    assert ge["symbol"] == "GESHIP"
    assert ge["original_oct19_nse_eq_close_inr"] == 1519.3
    assert ge["historical_issuer_nav_per_old_share_inr_not_marked_current"] == 1886
    assert ge["headline_discount_percent_not_margin_of_safety"] == 19.44
    assert ge["frozen_reverse_test"][
        "noncash_NAV_haircut_wiping_reference_discount_percent"
    ] == 27.74
    assert ge["frozen_reverse_test"][
        "fleet_and_offshore_current_sale_value_verified"
    ] is False
    assert ge["frozen_reverse_test"][
        "legal_extinction_of_all_reacquired_shares_verified"
    ] is False


def test_zuari_underlying_listed_stakes_wedge_is_fragile_to_haircuts():
    zuari = _result()["evidence"][1]
    assert zuari["symbol"] == "ZUARIIND"
    assert zuari["oct19_five_listed_stake_marks_cr"] == pytest.approx(
        3764.9208
    )
    assert zuari["march_net_borrowings_cr_not_current"] == 2519.4245
    assert zuari["oct19_cap_using_old_basic_shares_cr"] == 771.6305
    assert zuari["hypothetical_undiscounted_stake_gap_cr_not_parent_equity"] == (
        pytest.approx(473.8658)
    )
    assert zuari["additional_stake_markdown_erasing_gap_percent"] == (
        pytest.approx(12.586, abs=0.001)
    )
    assert zuari["listed_stake_units_after_June_confirmed"] is False
    assert zuari["current_creditor_pledge_waterfall_reconciled"] is False


def test_datamatics_cash_required_is_not_a_fifty_percent_forecast():
    company = _result()["evidence"][2]
    assert company["symbol"] == "DATAMATICS"
    assert company["fy26_cash_proxy_cr_not_owner_cash"] == 284.42
    assert company[
        "hypothetical_cash_required_for_50pct_share_gross_at_16x_cr"
    ] == pytest.approx(430.97)
    assert company["cash_proxy_growth_required_percent_not_forecast"] == 51.53
    assert company["acquisition_consideration_209_69_cr_reconciled"] is False
    assert company["current_parent_diluted_equity_and_owner_cash_verified"] is False


def test_suntv_original_uk_pdf_archived_but_mixed_period_not_owner_cash():
    x = _result()["evidence"][3]
    assert x["symbol"] == "SUNTV"
    assert x["uk_franchise_deal_gbp"] == 100500000
    assert x["mixed_14_month_uk_operating_CFO_gbp"] == 2060217
    assert x["source_period_start"] == "2025-02-01"
    assert x["source_period_end"] == "2026-03-31"
    assert x["parent_control_effective"] == "2025-07-28"
    assert x["original_scanned_PDF_sha256_archived"] == ORIGINAL_UK_PDF_SHA
    assert x["original_visual_rows_independently_replayed_from_archive"] is False
    assert x["post_July28_recurring_owner_cash_reconciled"] is False
    assert [y["annual_owner_cash_necessary_gbp"] for y in
            x["reverse_owner_cash_yield_hurdles"]] == [
        5025000, 9045000, 12060000,
    ]
    assert [y["multiple_of_mixed14month_CFO_not_growth_forecast"] for y in
            x["reverse_owner_cash_yield_hurdles"]] == pytest.approx([
        2.4391, 4.3903, 5.8538,
    ])
    assert all(
        y["actual_recurring_postcontrol_cash_verified"] is False
        for y in x["reverse_owner_cash_yield_hurdles"]
    )


def test_source_document_tampering_or_claimed_annual_cash_fails_closed():
    original, receipts = load_original_review_sources(ROOT)
    p = copy.deepcopy(original)
    p["p018"]["stake_marks_by_date_cr"]["2026-10-19"] *= 2
    with pytest.raises(AlphaContractError, match="ZUARI"):
        build_cross_company_falsification(p, receipts)
    p = copy.deepcopy(original)
    p["p022_receipt"]["parent_owner_cash_verified"] = True
    with pytest.raises(AlphaContractError, match="UK PDF custody"):
        build_cross_company_falsification(p, receipts)
    p = copy.deepcopy(original)
    p["p021"]["subsidiary_14month_cash_is_post_control_only"] = True
    with pytest.raises(AlphaContractError, match="UK mixed-owner"):
        build_cross_company_falsification(p, receipts)

    result = _result()
    result["evidence"][2]["economic_mispricing_confirmed"] = True
    with pytest.raises(AlphaContractError, match="packet SHA mismatch"):
        validate_falsification_frontier(result, ROOT)


def test_frozen_original_report_reproduces_without_backdating_entries():
    report = _result()
    assert report["report_sha256"] == digest({
        key: value for key, value in report.items()
        if key != "report_sha256"
    })
    assert report == json.loads(OUTPUT.read_text(encoding="utf-8"))
    check = subprocess.run(
        [sys.executable, "scripts/materialize_l001_p023_frontier.py", "--check"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    receipt = json.loads(check.stdout)
    assert receipt["state"] == "VERIFIED"
    assert receipt["investable_cases_approved"] == 0
    assert receipt["source_sha256"] == report["report_sha256"]
