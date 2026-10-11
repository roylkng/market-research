from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_anantraj_qip_cash_ledger import (
    AUDIT_ID,
    LEGAL_REVIEW_PATH,
    OBJECT_ROWS,
    REPORT_SHA256,
    SOURCE_PDF_PATH,
    SOURCE_RECEIPT_PATH,
    _decimal_rows,
    _legal_gate,
    _original_pages,
    build_qip_scheme_cash_review,
)


def _report() -> dict:
    return build_qip_scheme_cash_review(Path("."))


def test_original_exchange_21_pages_and_complete_prior_scheme_provenance() -> None:
    report = _report()
    assert report["review_id"] == AUDIT_ID
    assert report["original_nse_pdf_sha256"] == REPORT_SHA256
    assert report["original_pdf_page_count"] == 21
    assert report["legal_scheme_review_id"] == (
        "HG007-P026-ANANTRAJ-DEMERGER-SOURCE-CLAUSES-v1"
    )
    assert len(report["evidence_page_locators"]) == 8
    assert len(report["issuer_monitor_QIP_objects"]) == 6
    assert all(x["source_pdf_sha256"] == REPORT_SHA256 for x in report["evidence_page_locators"])
    assert all(len(x["page_text_sha256"]) == 64 for x in report["evidence_page_locators"])


def test_six_original_june_cash_categories_reconcile_without_fabricated_assets() -> None:
    report = _report()
    by_key = {row["object_id"]: row for row in report["issuer_monitor_QIP_objects"]}
    assert set(by_key) == {row[0] for row in OBJECT_ROWS}
    assert report["reported_QIP_gross_proceeds_inr_crore"] == 1100.0
    assert report["reported_cumulative_used_by_june30_inr_crore"] == 410.01
    assert report["reported_unused_by_june30_inr_crore"] == 689.99
    assert report["reported_QIP_net_proceeds_inr_crore"] == 1072.20
    cloud = by_key["CLOUD_SUBSIDIARY"]
    assert cloud["gross_qip_object_allocation_inr_crore"] == 440
    assert cloud["utilized_before_april2026_inr_crore"] == 52.03
    assert cloud["utilized_during_april_june2026_inr_crore"] == 29.23
    assert cloud["cumulative_utilized_june30_inr_crore"] == 81.26
    assert cloud["monitored_unutilized_june30_inr_crore"] == 358.74
    assert by_key["OTHER_PARENT_CONSTRUCTION"]["monitored_unutilized_june30_inr_crore"] == (
        154.41
    )
    assert by_key["LAND_AND_RIGHTS"]["cumulative_utilized_june30_inr_crore"] == 70.92
    assert by_key["BORROWING_REPAYMENT"]["monitored_unutilized_june30_inr_crore"] == 0
    assert by_key["GENERAL_CORPORATE_PURPOSES"][
        "monitored_unutilized_june30_inr_crore"
    ] == 61.93
    assert by_key["QIP_ISSUE_EXPENSES"]["cumulative_utilized_june30_inr_crore"] == 26.97
    assert report["non_cloud_unused_allocations_inr_crore"] == 331.25
    assert report["cloud_qip_unused_is_newco_free_cash"] is False
    assert report["non_cloud_unused_may_not_be_relabelled_cloud_assets"] is True


def test_original_june_fdr_total_mismatch_and_commingled_account_stays_blocked() -> None:
    report = _report()
    assert report["monitoring_report_same_date_fdr_total_inr_crore"] == 690.01
    assert report["fdr_less_unutilized_report_discrepancy_inr_crore"] == 0.02
    assert report["fdr_total_discrepancy_explained_by_original_source"] is False
    assert report["original_monitor_disclosed_cash_credit_commingling"] is True
    assert report["monitoring_agency_performed_independent_financial_audit"] is False
    assert report["full_post_june_bank_maturity_and_uses_reconciled"] is False


def test_demerger_legal_debt_cash_and_equity_remain_unquantified() -> None:
    report = _report()
    for field in (
        "demerger_cloud_qip_cash_amount_as_of_effective_date_inr_crore",
        "demerger_direct_operating_debt_inr_crore",
        "demerger_pro_rata_general_purpose_debt_inr_crore",
        "demerger_intercompany_balances_to_eliminate_inr_crore",
    ):
        assert report[field] is None
    for flag in (
        "underlying_cloud_capex_assets_valued_from_monitored_spending",
        "scheme_legally_effective_confirmed",
        "newco_net_cash_or_equity_value_calculated",
        "prospective_return_outcomes_opened",
        "company_completion_probability_published",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert report[flag] is False
    assert "GENERAL_PURPOSE_BORROWINGS_PRO_RATA" in report["relevant_proposed_legal_clauses"]
    assert "EARMARKED_DEVELOPMENT_QIP_FUNDS" in report["relevant_proposed_legal_clauses"]


def test_tampered_original_pdf_or_receipt_cannot_pass(tmp_path: Path) -> None:
    for path in (SOURCE_PDF_PATH, SOURCE_RECEIPT_PATH, LEGAL_REVIEW_PATH):
        dest = tmp_path / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
    _original_pages(tmp_path)
    _legal_gate(tmp_path)
    pdf = tmp_path / SOURCE_PDF_PATH
    pdf.write_bytes(pdf.read_bytes() + b"tampering")
    with pytest.raises(ValueError, match="original bytes changed"):
        _original_pages(tmp_path)
    pdf.write_bytes(SOURCE_PDF_PATH.read_bytes())
    receipt = tmp_path / SOURCE_RECEIPT_PATH
    receipt.write_bytes(receipt.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Git blob changed"):
        _original_pages(tmp_path)


def test_mutated_proposed_cloud_debt_or_qip_use_not_accepted(tmp_path: Path) -> None:
    for path in (SOURCE_PDF_PATH, SOURCE_RECEIPT_PATH, LEGAL_REVIEW_PATH):
        dest = tmp_path / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
    legal = tmp_path / LEGAL_REVIEW_PATH
    legal.write_bytes(legal.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Git blob changed"):
        _legal_gate(tmp_path)

    original = deepcopy(OBJECT_ROWS)
    assert original[0][0] == "CLOUD_SUBSIDIARY"
    rows = _decimal_rows()
    assert len(rows) == len(original)
    assert sum(x["gross_qip_object_allocation_inr_crore"] for x in rows) == 1100.0


def test_cli_reproduces_six_source_cash_objects_with_no_returns(tmp_path: Path) -> None:
    out = tmp_path / "anantraj-cash.json"
    command = [
        sys.executable, "scripts/reconcile_hg007_anantraj_qip_cash.py",
        "--out", str(out),
    ]
    first = subprocess.run(command, check=True, capture_output=True, text=True)
    summary = json.loads(first.stdout)
    assert summary["qip_unutilized_june_inr_cr"] == 689.99
    assert summary["cloud_unutilized_june_inr_cr"] == 358.74
    assert summary["fdr_difference_inr_cr"] == 0.02
    assert summary["pro_forma_newco_cash_verified"] is False
    assert summary["live_capital_allowed"] is False
    assert json.loads(out.read_text(encoding="utf-8")) == _report()
    subprocess.run(
        command + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    out.write_text(out.read_text(encoding="utf-8") + "\nFAKE ASHOK CLOUD CASH")
    later = subprocess.run(
        command + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert later.returncode != 0
    assert "source ledger changed" in later.stderr
