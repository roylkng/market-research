"""P015 reverse hurdles must not be reported as forecast returns or fair values."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p015_hurdles import (
    SYMBOLS,
    build_reverse_cash_hurdles,
    load_sources,
    materialize,
    validate_result,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/hg009/hg009-p015-ace-acutaas-hurdles-v1.json"


def _rows():
    return {
        row["symbol"]: row for row in materialize(ROOT)["two_case_records"]
    }


def test_original_oct15_two_companies_and_dated_not_current_equity():
    result = materialize(ROOT)
    assert result["fixed_companies"] == list(SYMBOLS)
    assert result["realizable_equity_valuations_complete"] == 0
    assert result["investment_price_targets_created"] == 0
    assert result["live_capital_allowed"] is False
    assert result["published_after_first_market_outcome_not_first_day_preregistration"]
    assert len(result["two_case_records"]) == 2
    assert len(result["prior_original_source_receipts"]) == 3
    for row in result["two_case_records"]:
        assert row["dated_price_EQ_close_inr"] > 0
        assert row["reporting_basis"] == "STANDALONE_UNAUDITED_Q1FY27"
        assert row["current_fully_diluted_shares_verified"] is False
        assert row["issuer_q1_raw_HTML_retained_and_replayed"] is False
        assert row["future_price_target_inr"] is None
        assert row["expected_1y_or_3y_net_return"] is None
        assert row["capital_eligible"] is False
        assert row["these_multiples_are_unsupported_assumptions"] is True


def test_ACE_q1_parent_capital_and_cash_multiple_are_cross_date_only():
    ace = _rows()["ACE"]
    assert ace["dated_price_EQ_close_inr"] == 1155.7
    assert ace["reported_June_basic_shares_crore_not_Oct_diluted"] == 11.91
    assert ace["cross_date_illustrative_basic_market_cap_cr"] == 13764.39
    assert ace["fy26_CONSOLIDATED_CFO_cr"] == 417.27
    assert ace["fy26_CFO_less_PPE_cr_not_owner_FCF"] == 324.01
    assert ace["CFO_yield_on_cross_date_basic_cap_pct_not_owner_yield"] == 3.032
    assert ace["CFO_less_PPE_yield_pct_not_owner_yield"] == 2.354
    assert ace["cross_date_cap_to_FY26_CFO_less_PPE_if_positive"] == 42.481
    assert ace["q1_standalone_reported_PBT_cr"] == 156.79
    assert ace["q1_standalone_other_income_cr"] == 54.43
    assert ace["other_income_as_percent_of_Q1_standalone_PBT"] == 34.72
    assert ace["q1_PBT_less_other_income_not_owner_earnings_cr"] == 102.36
    assert ace["reverse_cash_for_50pct_ONE_TIME_gross_price_lift_at_16x_cr"] == 1290.41
    assert ace["reverse_cash_for_50pct_CAGR_3Y_at_16x_cr"] == 2903.43


def test_ACUTAAS_high_capex_and_undocumented_incremental_project_returns():
    a = _rows()["ACUTAAS"]
    assert a["dated_price_EQ_close_inr"] == 3132.5
    assert a["reported_June_basic_shares_crore_not_Oct_diluted"] == 8.18712
    assert a["cross_date_illustrative_basic_market_cap_cr"] == 25646.15
    assert a["fy26_CONSOLIDATED_CFO_cr"] == 292.1736
    assert a["fy26_CFO_less_PPE_cr_not_owner_FCF"] == -35.8052
    assert a["CFO_yield_on_cross_date_basic_cap_pct_not_owner_yield"] == 1.139
    assert a["CFO_less_PPE_yield_pct_not_owner_yield"] == -0.14
    assert a["cross_date_cap_to_FY26_CFO_less_PPE_if_positive"] is None
    assert a["q1_standalone_reported_PBT_cr"] == 104.015
    assert a["q1_standalone_other_income_cr"] == 4.476
    assert a["q1_PBT_less_other_income_not_owner_earnings_cr"] == 99.539
    assert a["reverse_cash_for_50pct_ONE_TIME_gross_price_lift_at_16x_cr"] == 2404.33
    assert a["reverse_cash_for_50pct_CAGR_3Y_at_16x_cr"] == 5409.74


def test_missing_or_rewritten_original_share_basis_blocks_review():
    originals, receipts = load_sources(ROOT)
    changed = copy.deepcopy(originals)
    changed["equity"]["issuer_rows"][0]["isin"] = "INE000000001"
    with pytest.raises(AlphaContractError, match="source/ISIN/period"):
        build_reverse_cash_hurdles(changed, receipts)
    changed = copy.deepcopy(originals)
    changed["market"]["source_identity_rows"][0]["symbol"] = "FAKE_ALPHA_WINNER"
    with pytest.raises(AlphaContractError, match="original signed source drift"):
        build_reverse_cash_hurdles(changed, receipts)

    changed = copy.deepcopy(originals)
    changed["audited"]["symbol_records"][0][
        "source_CFO_less_PPE_cash_proxy_cr_not_owner_fcf"
    ] *= 2
    with pytest.raises(AlphaContractError, match="original signed source drift"):
        build_reverse_cash_hurdles(changed, receipts)

    altered = materialize(ROOT)
    altered["two_case_records"][0]["future_price_target_inr"] = 5000
    with pytest.raises(AlphaContractError, match="signed original cash hurdle"):
        validate_result(altered, ROOT)


def test_unaltered_original_sources_reproduce_bit_for_bit():
    expected = materialize(ROOT)
    assert expected == json.loads(REPORT.read_text(encoding="utf-8"))
    assert expected["packet_sha256"] == digest({
        k: v for k, v in expected.items() if k != "packet_sha256"
    })
    done = subprocess.run(
        [sys.executable, "scripts/materialize_hg009_p015.py", "--check"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    state = json.loads(done.stdout)
    assert state["state"] == "VERIFIED"
    assert state["investable"] == 0
