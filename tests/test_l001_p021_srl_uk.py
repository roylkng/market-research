"""UK 14-month operating cash is neither annualized nor parent owner FCF."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.l001_p021_srl_uk import (
    build_uk_cash_case,
    load_original_sources,
    materialize,
    verify,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/l001/l001-p021-srl-uk-14month-cash-analysis-v1.json"


def _source() -> tuple[dict, dict, dict]:
    return load_original_sources(ROOT)


def test_exact_uk_original_14month_cash_and_revenue_algebra():
    report = materialize(ROOT)
    facts = report["historical_original_gbp_tables"]
    assert facts["revenue"] == 7993088
    assert facts["broadcast_income"] == 5579226
    assert facts["sponsorship_income"] == 1131351
    assert facts["ticket_income"] == 1029696
    assert facts["other_income"] == 252815
    assert facts["gross_profit"] == 1828387
    assert facts["operating_profit"] == 1709990
    assert facts["profit_before_tax"] == 1629501
    assert facts["profit_after_tax"] == 1222126
    assert facts["net_operating_cash_inflow"] == 2060217
    assert facts["cash_interest_paid"] == 80489
    assert facts["cash_dividends_paid"] == 141869
    assert facts["cash_beginning"] == 146015
    assert facts["cash_end"] == 1983874
    assert report["statement_arithmetic_reconciled"] is True
    assert report["broadcast_revenue_fraction"] == pytest.approx(0.6980, abs=0.0002)
    verify(report, ROOT)


def test_franchise_cost_to_mixed_period_cash_is_not_roic():
    report = materialize(ROOT)
    assert report["parent_control_effective"] == "2025-07-28"
    assert report["source_period_start"] == "2025-02-01"
    assert report["source_period_end"] == "2026-03-31"
    assert report["original_deal_cash_consideration_gbp"] == 100500000
    assert report["reported_14month_operating_cfo_gbp"] == 2060217
    assert report["reported_14month_cfo_less_financing_interest_gbp"] == 1979728
    assert report["reported_mixed_period_cfo_to_deal_price_pct_not_roic"] == pytest.approx(2.05, abs=0.01)
    assert report["reported_mixed_period_cfo_less_interest_to_deal_price_pct_not_roic"] == pytest.approx(1.97, abs=0.01)
    targets = report["illustrative_owner_cash_yield_hurdles_not_forecasts"]
    assert [x["annual_owner_cash_needed_gbp"] for x in targets] == [
        5025000, 9045000, 12060000
    ]
    assert targets[1]["ratio_to_mixed_14month_operating_cash_not_growth_forecast"] == pytest.approx(
        9045000 / 2060217, abs=0.0001
    )
    for flag in (
        "subsidiary_14month_cash_is_post_control_only",
        "reported_dividends_were_post_suntv_control",
        "reported_cfo_is_normalized_parent_owner_fcf",
        "cross_currency_fx_adjusted_cash_return_calculated",
        "investor_required_cash_yield_calibrated",
        "actual_investor_rate_of_return_calculated",
        "expected_stock_return_estimated",
        "current_suntv_fair_value_calculated",
        "portfolio_eligible",
        "live_capital_allowed",
    ):
        assert report[flag] is False, flag


def test_raw_source_missing_is_explicit_not_automated_page_number_verification():
    report = materialize(ROOT)
    assert report["original_full_pdf_archived_in_this_source_packet"] is False
    assert report["original_full_pdf_sha256"] is None
    assert report["original_first_retrieval_at_utc"] is None
    assert report["subsequent_pdf_capture_receipt_is_a_distinct_record"] is True
    assert report["original_document_scanned_visual_source"] is True


def test_synthetic_original_filing_mutations_block_at_accounting_equations():
    facts, parent, receipt = _source()
    broken = copy.deepcopy(facts)
    broken["monetary_facts_gbp"]["broadcast_income"] -= 100
    with pytest.raises(AlphaContractError, match="statement equations differ"):
        build_uk_cash_case(broken, parent, receipt)
    broken = copy.deepcopy(facts)
    broken["source_reported_ownership_start"] = "2025-01-01"
    with pytest.raises(AlphaContractError, match="period"):
        build_uk_cash_case(broken, parent, receipt)
    broken = copy.deepcopy(facts)
    broken["parent_disclosed_acquisition_consideration_gbp"] = 5000000
    with pytest.raises(AlphaContractError, match="purchase consideration"):
        build_uk_cash_case(broken, parent, receipt)


def test_original_report_replays_and_direct_cli_is_read_only():
    original = materialize(ROOT)
    assert json.loads(OUTPUT.read_text("utf-8")) == original
    run = subprocess.run(
        [sys.executable, "scripts/materialize_l001_p021_srl_uk.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    r = json.loads(run.stdout)
    assert r["state"] == "VERIFIED"
    assert r["report_sha256"] == original["report_sha256"]
    assert r["live_capital_allowed"] is False
