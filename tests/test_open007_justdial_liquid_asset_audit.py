"""OPEN007 original-source financial arithmetic and no-buy tamper regressions."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/open007_justdial_liquid_asset_audit.py"
SPEC = importlib.util.spec_from_file_location("open007_justdial_audit", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
INPUT = (
    ROOT / "research/broad-discovery/OPEN007_JUSTDIAL_CASH_BRIDGE_INPUT_20261026.json"
)


@pytest.fixture
def source():
    return json.loads(INPUT.read_text(encoding="utf-8"))


def test_exact_share_count_avoids_inconsistent_secondary_market_cap(source):
    report = MODULE.evaluate(source)
    assert report["market_cap_exact_share_count_cr"] == 5943.2264
    assert report["gross_liquid_book_marks_cr"] == 6113.95
    assert report["all_reported_liabilities_book_cr"] == 940.61
    assert report["liquid_after_all_reported_liabilities_cr"] == 5173.34
    assert report["market_implied_residual_franchise_and_other_assets_cr"] == 769.89
    assert report["gross_liquid_pct_market_cap"] == 102.87
    assert report["portfolio_markdown_to_remove_gross_cash_over_cap_pct"] == 2.79
    assert report["deferred_revenue_is_not_double_subtracted"] is True
    assert report["capital_authorized"] is False


def test_historical_operating_cash_quality_and_cash_run_rate_are_not_fcfe(source):
    r = MODULE.evaluate(source)
    assert r["FY26_CFO_yoy_pct"] == -13.74
    assert r["H1_FY27_CFO_yoy_pct"] == 0.17
    assert r["illustrative_H1_cash_after_selected_ppe_intangible_lease_cr"] == 95.34
    assert r["illustrative_annualized_cash_run_rate_cr"] == 190.68
    assert r["asset_realization_to_minority_shareholders_verified"] is False


def test_portfolio_risk_is_not_a_price_target(source):
    rows = MODULE.evaluate(source)["portfolio_stress_scenarios"]
    assert [x["gross_portfolio_haircut_pct"] for x in rows] == [0, 5, 10, 15, 20]
    assert [x["residual_market_price_of_business_and_other_assets_cr"] for x in rows] == [
        769.89, 1075.58, 1381.28, 1686.98, 1992.68,
    ]
    assert [x["residual_to_annualized_Q2_ebitda_x"] for x in rows] == [
        2.12, 2.96, 3.81, 4.65, 5.49,
    ]
    assert all(x["forecast_probability"] is None for x in rows)
    assert all(x["capital_approved"] is False for x in rows)


@pytest.mark.parametrize(("field", "value"), [
    ("shares_outstanding_exact", 103000000),
    ("price_date", "2026-10-27"),
    ("q2_date", "2025-09-30"),
    ("isin", "INEWRONG0000"),
    ("unit_source", "INR_LAKHS"),
])
def test_cannot_mutate_identity_share_units_or_dates(source, field, value):
    changed = copy.deepcopy(source)
    changed[field] = value
    with pytest.raises(ValueError):
        MODULE.evaluate(changed)


def test_source_raw_custody_cannot_be_fabricated(source):
    edited = copy.deepcopy(source)
    edited["original_pdf_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="custody"):
        MODULE.evaluate(edited)


def test_owner_cash_inference_or_buy_rating_is_prohibited(source):
    for field, value in (
        ("capital_authorized", True),
        ("normalized_parent_FCFE_crore", 190.68),
        ("intrinsic_value_per_share_inr", 1200),
        ("no_H002_H003_HG009_retroactive_change", False),
    ):
        edited = copy.deepcopy(source)
        edited[field] = value
        with pytest.raises(ValueError):
            MODULE.evaluate(edited)


def test_no_backfill_of_dividends_or_liquidation_approval(source):
    edited = copy.deepcopy(source)
    edited["FY26_dividend"] = "HIGH_DIVIDEND_2026"
    with pytest.raises(ValueError, match="dividend"):
        MODULE.evaluate(edited)
    edited = copy.deepcopy(source)
    edited["independently_verified_accessible_cash_crore"] = 6113.95
    with pytest.raises(ValueError, match="unverified"):
        MODULE.evaluate(edited)


def test_reported_assets_and_liabilities_have_to_reconcile(source):
    edited = copy.deepcopy(source)
    edited["total_equity_million"] = edited["total_assets_million"] + 100
    with pytest.raises(ValueError, match="balance-sheet"):
        MODULE.evaluate(edited)
    edited = copy.deepcopy(source)
    edited["deferred_revenue_crore"] = 2000
    with pytest.raises(ValueError, match="deferred revenue"):
        MODULE.evaluate(edited)


def test_no_unapproved_portfolio_haircut_or_nan(source):
    edited = copy.deepcopy(source)
    edited["portfolio_haircut_assumptions"] = [0, 0.05, 0.1, 0.2]
    with pytest.raises(ValueError, match="sensitivity"):
        MODULE.evaluate(edited)
    edited = copy.deepcopy(source)
    edited["H1_CFO_million"] = float("nan")
    with pytest.raises(ValueError, match="invalid"):
        MODULE.evaluate(edited)
