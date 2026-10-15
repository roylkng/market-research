"""PIX reported growth, two original audited-unit regimes, and no alpha."""

from __future__ import annotations

import copy
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p011_pix_income import (
    DOCUMENTS,
    _extract_rows,
    build_pix_symmetric_income_bridge,
    verify_pix_symmetric_income_bridge,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/hg009/hg009-p011-pix-symmetric-quarter-profit-v1.json"


def _original(period: str) -> bytes:
    row = DOCUMENTS[period]
    return gzip.decompress((ROOT / (
        "research/hg009/p009-originals/PIXTRANS/"
        + row["raw_sha256"] + ".html.gz"
    )).read_bytes())


def test_first_original_pix_quarterly_filings_have_different_money_units():
    report = build_pix_symmetric_income_bridge(ROOT)
    assert report["issuer"] == "PIXTRANS"
    assert report["isin"] == "INE751B01018"
    assert report["reporting_basis"] == (
        "STANDALONE_UNAUDITED_QUARTER_COMPARISON"
    )
    assert report["original_unit_discrepancy"] == (
        "Q1FY26_INR_ACTUALS_VS_Q1FY27_INR_LAKH"
    )
    data = report["quarter_numbers_recalculated_to_inr_crore"]
    assert data["Q1FY26_STANDALONE"] == {
        "other_income": 14.1867,
        "pbt": 30.9666,
        "revenue": 110.6415,
        "total_expenses": 93.8616,
        "total_income": 124.8282,
    }
    assert data["Q1FY27_STANDALONE"] == {
        "other_income": 27.3112,
        "pbt": 60.8168,
        "revenue": 134.532,
        "total_expenses": 101.0264,
        "total_income": 161.8432,
        "fvtpl": 25.2949,
    }
    assert report["reported_pbt_yoy_pct"] == 96.39
    assert report["reported_revenue_yoy_pct"] == 21.59
    assert report["current_pbt_less_fvtpl_inr_crore"] == 35.5219
    assert report["current_other_income_less_fvtpl_inr_crore"] == 2.0163
    assert report[
        "asymmetric_current_less_fvtpl_vs_prior_reported_pbt_growth_pct"
    ] == 14.71
    assert report["prior_pbt_excluding_all_other_income_cr"] == 16.7799
    assert report["current_pbt_excluding_all_other_income_cr"] == 33.5056
    assert report["symmetric_pbt_excluding_all_other_income_yoy_pct"] == 99.68
    assert report["current_fvtpl_share_of_reported_pbt_pct"] == 41.59


def test_symmetric_but_not_owner_cash_or_company_fair_value():
    report = build_pix_symmetric_income_bridge(ROOT)
    for field in (
        "asymmetric_comparison_is_normalized_operating_growth",
        "all_other_income_excluded_comparison_is_owner_cash",
        "prior_quarter_fvtpl_component_independently_verified",
        "consolidated_quarter_earnings_reconciled",
        "standalone_to_parent_cash_attribution_verified",
        "latest_fully_diluted_parent_shares_verified",
        "owner_cashflow_or_financial_asset_realization_verified",
        "investment_recommendation_authorized",
        "live_capital_allowed",
    ):
        assert report[field] is False
    assert report["expected_stock_return"] is None
    verify_pix_symmetric_income_bridge(report, ROOT)


def test_raw_source_row_or_fvtpl_note_change_fails_closed():
    for period in DOCUMENTS:
        raw = _original(period)
        numbers = _extract_rows(raw, expected=DOCUMENTS[period])
        assert numbers["pbt"] > 0
    previous = _original("Q1FY26_STANDALONE")
    damaged = previous.replace(b"309666000", b"309666001")
    assert damaged != previous
    with pytest.raises(AlphaContractError, match="original reported cell"):
        _extract_rows(damaged, expected=DOCUMENTS["Q1FY26_STANDALONE"])
    current = _original("Q1FY27_STANDALONE")
    altered = current.replace(b"2,529.49", b"2,529.48", 1)
    assert altered != current
    with pytest.raises(AlphaContractError, match="original issuer note"):
        _extract_rows(altered, expected=DOCUMENTS["Q1FY27_STANDALONE"])


def test_source_report_sha_and_no_future_return_tampering():
    report = build_pix_symmetric_income_bridge(ROOT)
    broken = copy.deepcopy(report)
    broken["expected_stock_return"] = 0.5
    with pytest.raises(AlphaContractError, match="signature altered"):
        verify_pix_symmetric_income_bridge(broken, ROOT)
    broken["packet_sha256"] = digest({
        k: v for k, v in broken.items() if k != "packet_sha256"
    })
    with pytest.raises(AlphaContractError, match="no longer reproduces"):
        verify_pix_symmetric_income_bridge(broken, ROOT)


def test_direct_cli_before_and_after_report_freeze(tmp_path: Path):
    current = build_pix_symmetric_income_bridge(ROOT)
    if REPORT.exists():
        assert json.loads(REPORT.read_text("utf-8")) == current
    scratch = tmp_path / "pix-source.json"
    generated = subprocess.run(
        [
            sys.executable, "scripts/materialize_hg009_p011_pix.py",
            "--output", str(scratch),
        ],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert json.loads(generated.stdout)["packet_sha256"] == current["packet_sha256"]
    checked = subprocess.run(
        [
            sys.executable, "scripts/materialize_hg009_p011_pix.py",
            "--output", str(scratch), "--check",
        ],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert json.loads(checked.stdout)["state"] == "VERIFIED"
