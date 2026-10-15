"""Archived original NSE statement rows, not modeled expected stock returns."""

from __future__ import annotations

import copy
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p012_datamatics_cash import (
    BALANCE_ROWS,
    CASH_ROWS,
    FIRST_RECEIPT,
    ORIGINAL_SOURCE,
    check_row_tokens,
    build_datamatics_original_cash_bridge,
    validate_datamatics_original_cash_bridge,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/hg009/hg009-p012-datamatics-fy26-cash-bridge-v1.json"


def test_original_nse_23_page_pdf_and_cashflow_reconcile():
    doc = build_datamatics_original_cash_bridge(ROOT)
    assert doc["symbol"] == "DATAMATICS"
    assert doc["isin"] == "INE365B01017"
    assert doc["original_pdf_page_count"] == 23
    assert doc["page_zero_based_cashflow"] == 7
    assert doc["page_zero_based_balance_sheet"] == 6
    assert len(doc["exact_original_pdf_cashflow_row_labels_and_values_replayed"]) == (
        len(CASH_ROWS)
    )
    assert len(doc["exact_original_pdf_balance_row_labels_and_values_replayed"]) == (
        len(BALANCE_ROWS)
    )
    assert doc["fy26_operating_cash_cr"] == 323.99
    assert doc["fy26_cfo_less_fixed_asset_cash_cr_not_owner_fcf"] == 284.42
    assert doc["fy26_net_investing_cash_cr"] == -316.54
    assert doc["fy26_cfo_after_all_investing_cr_not_owner_fcf"] == 7.45
    assert doc["fy26_net_financing_cash_cr"] == -83.67
    assert doc["fy26_annual_cash_change_cr"] == -76.22
    assert doc["fy26_investment_purchase_net_cr_not_expense"] == 262.76
    assert doc["fy26_acquisition_cash_outflow_cr"] == 33.93
    assert doc["fy26_lease_principal_paid_cr"] == 23.98
    assert doc["fy26_interest_paid_cr"] == 13.74
    assert doc["fy26_dividend_paid_cr"] == 29.55
    assert doc["fy26_current_plus_noncurrent_investments_cr_not_unrestricted"] == (
        638.9
    )
    assert doc["fy26_reported_borrowings_total_cr"] == 141.36
    assert doc["fy26_lease_liability_total_cr"] == 78.57
    assert doc["fy26_goodwill_cr"] == 611.12
    assert doc["cash_residual_is_not_sustainable_earnings"] is True
    assert doc["investment_purchase_is_not_a_cost_of_goods_or_permanent_cash_loss"]
    assert doc["financial_investments_unrestricted_or_distributable_verified"] is False
    assert doc["probability_weighted_shareholder_value_cr"] is None
    assert doc["portfolio_eligibility_allowed"] is False
    assert doc["live_capital_allowed"] is False
    validate_datamatics_original_cash_bridge(doc, root=ROOT)


def test_original_pdf_receipt_and_sha_must_be_archived_and_unchanged():
    receipt = json.loads((ROOT / FIRST_RECEIPT).read_text("utf-8"))
    assert receipt["http_status"] == 200
    assert receipt["raw_sha256"] == (
        "f96ecf4e698b4ee311126479fa20de0e7021449efc50cffa28a069dde40e8c77"
    )
    raw = gzip.decompress((ROOT / ORIGINAL_SOURCE).read_bytes())
    assert len(raw) == 4068966
    assert raw.startswith(b"%PDF")
    assert build_datamatics_original_cash_bridge(ROOT)["original_raw_sha256"] == (
        receipt["raw_sha256"]
    )


def test_source_row_association_required_not_just_unrelated_numbers():
    assert check_row_tokens(
        "Net cash flow from operating activities (A) 50.52 25.21 323.99 223.72\n",
        {"fy26_cfo": CASH_ROWS["fy26_cfo"]},
        source_label="synthetic",
    ) == ["fy26_cfo"]
    with pytest.raises(AlphaContractError, match="cashflow PDF row absent"):
        check_row_tokens(
            "An unrelated heading 323.99\nNet cash flow from operating activities 7.00",
            {"fy26_cfo": CASH_ROWS["fy26_cfo"]},
            source_label="cashflow",
        )


def test_immutability_and_check_mode_no_rewrites():
    expected = build_datamatics_original_cash_bridge(ROOT)
    assert json.loads(REPORT.read_text(encoding="utf-8")) == expected
    done = subprocess.run(
        [
            sys.executable, "scripts/materialize_hg009_p012_datamatics.py",
            "--check",
        ],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    status = json.loads(done.stdout)
    assert status["state"] == "VERIFIED"
    assert status["report_sha256"] == expected["report_sha256"]
    altered = copy.deepcopy(expected)
    altered["fy26_annual_cash_change_cr"] = 75.0
    with pytest.raises(AlphaContractError, match="packet hash changed"):
        validate_datamatics_original_cash_bridge(altered, root=ROOT)
