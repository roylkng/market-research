from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_devx_lease_economics import (
    CREDIT_SHA,
    NSE_SHA,
    REPORT_ID,
    STANDALONE_INR_CRORE,
    build_devx_lease_cash_bridge,
    load_original_devx_evidence,
)


@pytest.fixture(scope="module")
def source() -> tuple[dict, dict, dict]:
    return load_original_devx_evidence(Path("."))


@pytest.fixture(scope="module")
def report(source: tuple[dict, dict, dict]) -> dict:
    return build_devx_lease_cash_bridge(*source)


def test_both_actual_originals_and_accounting_page_sha(source: tuple[dict, dict, dict]) -> None:
    original, market, receipt = source
    assert original["context_id"] == "HG005-D003-v1"
    assert market["price_session"] == "2026-10-01"
    assert receipt["nse_pdf"]["sha256"] == NSE_SHA
    assert receipt["nse_pdf"]["standalone_statement_page"] == 28
    assert len(receipt["nse_pdf"]["page_text_sha256"]) == 64
    assert receipt["oct8_acuite"]["sha256"] == CREDIT_SHA
    assert receipt["bundle_source"]["git_blob_sha"]
    assert len(receipt["oct8_acuite"]["normalized_text_sha256"]) == 64


def test_standalone_indas_and_cash_rent_fully_reconcile(report: dict) -> None:
    assert report["analysis_id"] == REPORT_ID
    fy = report["fy26_standalone_issuer_reported"]
    assert fy["fy26_revenue"] == 170.91
    assert fy["fy26_indas_ebitda"] == 103.46
    assert fy["fy26_cash_ebit"] == 36.55
    assert fy["fy26_rent_outflow"] == 66.92
    assert fy["fy26_lease_interest"] == 27.20
    assert fy["fy26_right_of_use_depreciation"] == 50.24
    assert fy["reported_ebitda_margin_pct"] == pytest.approx(60.53478438944474)
    assert fy["reported_cash_ebit_margin_pct"] == pytest.approx(21.385524545)
    assert fy["cash_ebit_as_ratio_of_indas_ebitda_pct"] == pytest.approx(
        100*36.55/103.46
    )
    assert fy["indas_ebitda_less_cash_rent_less_cash_ebit_rounding_cr"] == (
        pytest.approx(-0.01)
    )
    assert fy["standalone_does_not_equal_rating_consolidated_scope"] is True


def test_oct8_credit_rating_winstons_not_operational_earnings(report: dict) -> None:
    credit=report["oct8_independent_credit_report"]
    assert credit["credit_date"] == "2026-10-08"
    assert credit["rating"] == "ACUITE BBB"
    assert credit["outlook"] == "Stable"
    assert credit["rated_ncd_tranches_cr"] == [25.0, 75.0]
    assert credit["rated_ncd_outstanding_cr"] == 100
    assert credit["additional_ncd_proposed_not_issued_cr"] == 50
    assert credit["ncd_coupon_pct"] == 11.75
    assert credit["full_year_nominal_coupon_on_100cr_ncd_at_11_75pct_cr"] == 11.75
    assert credit["50cr_proposed_ncd_interest_rate_unknown"] is True
    assert credit["fy26_debt_ebitda_including_lease"] == 3.11
    assert credit["fy26_debt_ebitda_excluding_lease"] == 1.32
    assert credit["september_operational_space_msf"] == 1.13
    assert credit["fy26_ahmedabad_revenue_pct_approx"] == 46
    assert credit["credit_rating_is_not_audited_stock_return_or_fair_value"] is True
    frozen=report["frozen_hg005_hurdle_not_modified"]
    assert frozen["legacy_price_session"] == "2026-10-01"
    assert frozen["signed_winston_straight_lease_area_sqft"] == 450000
    assert frozen["legacy_50pct_uplift_15x_incremental_indas_ebitda_hurdle_cr"] == (
        pytest.approx(11.847268466)
    )
    assert frozen["legacy_straight_lease_project_earnings_verified"] is False


def test_scenarios_are_math_only_not_return_fits(report: dict) -> None:
    s = report["purely_algebraic_not_prospective_scenarios"]
    old = report["frozen_hg005_hurdle_not_modified"][
        "legacy_50pct_uplift_15x_incremental_indas_ebitda_hurdle_cr"
    ]
    cash_ratio=STANDALONE_INR_CRORE["fy26_cash_ebit"]/STANDALONE_INR_CRORE["fy26_indas_ebitda"]
    assert s["if_same_historic_company_mix_cash_ebit_hurdle_equivalent_cr"] == (
        pytest.approx(old*cash_ratio)
    )
    assert s["if_cash_ebit_hurdle_equals_legacy_ebitda_cr_needed_indas_ebitda_at_historic_ratio_cr"] == (
        pytest.approx(old/cash_ratio)
    )
    assert s["historic_company_mix_cannot_be_ascribed_to_new_winston_project"] is True
    assert s["15x_indas_ebitda_multiple_not_15x_cash_ebit_or_fcf_multiple"] is True
    for value in ("winston_realized_income_verified",
                  "cash_flow_earnings_to_current_valuation_reconciled",
                  "company_completion_probability_published",
                  "expected_returns_calculated",
                  "portfolio_eligibility_allowed",
                  "live_capital_allowed"):
        assert report[value] is False


def test_old_hg005_source_not_rewritten_and_modified_hurdle_fails(source:tuple[dict,dict,dict]) -> None:
    original,market,receipt=source
    original_before=deepcopy(original)
    market_before=deepcopy(market)
    build_devx_lease_cash_bridge(original,market,receipt)
    assert original == original_before
    assert market == market_before
    altered=deepcopy(original)
    altered["key_hurdles"]["DEVX"][
        "fifty_pct_uplift_at_15x_required_incremental_annual_ebitda_inr_crore"
    ]=20
    with pytest.raises(ValueError,match="original DevX"):
        build_devx_lease_cash_bridge(altered,market,receipt)


def test_cli_produces_immutable_reproducible_source_only_report(tmp_path:Path,report:dict) -> None:
    target=tmp_path/"lease-bridge.json"
    cmd=[sys.executable,"scripts/build_hg007_devx_lease_bridge.py","--out",str(target)]
    one=subprocess.run(cmd,check=True,text=True,capture_output=True)
    p=json.loads(one.stdout)
    assert p["symbol"]=="DEVX"
    assert p["source_lease_ebitda_reconciled"] is True
    assert p["live_capital_allowed"] is False
    assert json.loads(target.read_text(encoding="utf-8"))==report
    subprocess.run(cmd+["--verify-existing"],check=True,text=True,capture_output=True)
    target.write_text(target.read_text(encoding="utf-8")+"fabricated",encoding="utf-8")
    res=subprocess.run(cmd+["--verify-existing"],check=False,text=True,capture_output=True)
    assert res.returncode!=0
    assert "changed from exact original" in res.stderr
