"""Adversarial proof that ₹1,190.88cr franchise acquisition is not owner FCF."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.l001_p019_suntv_original import (
    PDF_PAGE_INDICES,
    PAGE_REQUIRED_TEXT,
    archive_pdf_receipt,
    verify_annual_source_pages,
)
from marketlab.l001_p019_suntv_rights import (
    ANNUAL_REPORT_URL,
    PAGE_EVIDENCE,
    build_suntv_2026_cash_reconciliation,
    load_prior_evidence,
    validate_suntv_reconciliation,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/l001/l001-p019-suntv-franchise-rights-cash-bridge-v1.json"


def _original() -> dict:
    row, receipts = load_prior_evidence(ROOT)
    return build_suntv_2026_cash_reconciliation(row, receipts)


def test_parent_and_consolidated_financial_statements_do_not_double_count():
    x = _original()
    assert x["symbol"] == "SUNTV" and x["isin"] == "INE424H01027"
    assert x["fy26_consolidated_cfo_cr"] == 1801.64
    assert x["fy26_consolidated_ppe_cash_cr"] == 83.91
    assert x["fy26_consolidated_intangible_cash_cr"] == 2130.31
    assert x["fy26_cfo_less_ppe_only_proxy_cr_not_owner_cash"] == 1717.73
    assert x["fy26_cfo_less_ppe_intangibles_proxy_cr_not_owner_cash"] == -412.58
    assert x["SRL_parent_reported_cash_investment_cr"] == 1190.88
    assert x["SRL_consolidated_franchise_right_initial_asset_cr"] == 1190.88
    assert x["SRL_purchase_consideration_in_annual_note_cr"] == 1184.99
    assert x["purchase_consideration_vs_initial_right_asset_difference_cr"] == 5.89
    assert x["SRL_franchise_right_fx_translation_cr_not_new_cash"] == 57.39
    assert x["SRL_franchise_right_end_fy26_carrying_cr_not_cash"] == 1248.27
    assert x["source_categorized_franchise_rights_percent_of_intangible_cash"] == 55.9
    assert x["reported_intangible_cash_less_initial_franchise_rights_conditional_cr"] == 939.43
    assert x[
        "conditional_cfo_minus_ppe_less_residual_intangible_cr_not_owner_cash"
    ] == 778.30
    assert x["standalone_2026_cfo_less_ppe_and_non_franchise_intangibles_cr"] == 726.42
    assert x["source_2025_consolidated_cfo_less_ppe_and_intangibles_cr"] == 1280.65
    validate_suntv_reconciliation(x, root=ROOT)


def test_original_pdf_and_equity_economics_remain_explicitly_not_cleared():
    report = _original()
    for label in (
        "original_pdf_full_bytes_archived_in_this_report",
        "original_pdf_full_file_sha256_verified",
        "cashline_SRL_allocation_independently_traced_to_bank_payments",
        "residual_content_cash_is_maintenance_spending_verified",
        "current_fully_diluted_shares_verified",
        "financial_fair_value_established",
        "historical_method_frozen_prior_to_2026_10_15",
        "result_claims_prospective_oct15_alpha",
        "live_capital_allowed",
        "standalone_cash_investment_can_be_added_to_group_franchise_cash",
        "foreign_exchange_carrying_value_is_new_cash_spend",
    ):
        assert report[label] is False, label
    for label in (
        "group_shareholder_owner_cash_cr",
        "current_2026_10_20_equity_price",
        "parent_distributable_cash_including_cricket_rights",
        "stock_expected_1y_or_3y_return",
    ):
        assert report[label] is None, label
    assert report["conditional_2026_cash_proxy_not_proven_sustainable"] is True
    assert len(report["earlier_source_p014_p016_pinned_receipts"]) == 2


def test_data_tamper_or_replacing_carrying_value_as_cash_rejected():
    row, receipts = load_prior_evidence(ROOT)
    modified = copy.deepcopy(row)
    modified["fy26_intangible_cash_purchase_cr_reported"] = 938.51
    with pytest.raises(AlphaContractError, match="cash terms conflict"):
        build_suntv_2026_cash_reconciliation(modified, receipts)
    x = _original()
    x["conditional_cfo_minus_ppe_less_residual_intangible_cr_not_owner_cash"] = 999
    with pytest.raises(AlphaContractError, match="report SHA mismatch"):
        validate_suntv_reconciliation(x, root=ROOT)


def _synthetic_inspected_pages() -> dict[int, str]:
    return {
        page: "Sun TV original annual FY26 test-only page. "
        + (" ".join(needed) * 3)
        for page, needed in PAGE_REQUIRED_TEXT.items()
    }


def test_page_specific_source_contract_cannot_swap_standalone_and_consolidated():
    assert set(PDF_PAGE_INDICES) == set(PAGE_REQUIRED_TEXT)
    inspected = _synthetic_inspected_pages()
    check = verify_annual_source_pages(inspected)
    assert check["page_count"] == 5
    assert check["full_original_cash_receipts_independently_verified"] is False
    inspected[160] = inspected[77]
    with pytest.raises(AlphaContractError, match="original page 160"):
        verify_annual_source_pages(inspected)
    with pytest.raises(AlphaContractError, match="incomplete issuer PDF"):
        verify_annual_source_pages({77: inspected[77]})


def test_pdf_receipt_refuses_non_pdf_or_unaware_capture(tmp_path: Path):
    from datetime import UTC, datetime

    with pytest.raises(AlphaContractError, match="invalid real annual report"):
        archive_pdf_receipt(
            b"not a PDF", captured_at_utc=datetime.now(UTC), root=tmp_path
        )
    with pytest.raises(AlphaContractError, match="invalid real annual report"):
        archive_pdf_receipt(
            b"%PDF" + b"0" * 40000,
            captured_at_utc=datetime(2026, 10, 20, 12),
            root=tmp_path,
        )


def test_public_original_url_fixed_and_self_hash_reproducible():
    a = _original()
    assert a["original_report_pdf_url"] == ANNUAL_REPORT_URL
    assert a["original_filing_page_evidence"] == PAGE_EVIDENCE
    assert a == json.loads(OUTPUT.read_text(encoding="utf-8"))
    run = subprocess.run(
        [sys.executable, "scripts/materialize_l001_p019_suntv.py", "--check"],
        cwd=ROOT, capture_output=True, check=True, text=True,
    )
    msg = json.loads(run.stdout)
    assert msg["state"] == "VERIFIED"
    assert msg["live_capital_allowed"] is False
    assert msg["bridge_sha256"] == a["report_sha256"]
