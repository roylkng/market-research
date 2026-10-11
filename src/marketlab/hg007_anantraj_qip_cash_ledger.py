"""Original-source, date-specific Anant Raj QIP cash-use ledger and demerger guard.

The August 8 Infomerics report concerns utilization through JUNE 30 2026.
A monitored 'unutilized' object is not an independently checked bank
balance on October 11 or legally transferred cash to Ashok Cloud.

The proposed 48-page composite scheme contains clauses routing earmarked
cash/debt and intercompany balances, but no executed transfer schedule.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

AUDIT_ID = "HG007-P029-ANANTRAJ-JUNE2026-QIP-OBJECT-AND-DEMERGER-BRIDGE-v1"
REPORT_SHA256 = "13d0c6237f6273dfeefacb1c49003d339e4285280a6288f1589b4df44613a45d"
SOURCE_RECEIPT_PATH = Path(
    "research/hg007/anantraj-qip-monitor-june2026/nse-original-receipt-v1.json"
)
SOURCE_RECEIPT_GIT_BLOB = "e8fa634a9db616d329c9b6dcfb0e3f3c482f4b92"
SOURCE_PDF_PATH = Path(
    "research/hg007/anantraj-qip-monitor-june2026/nse-original/sha256/"
    + REPORT_SHA256 + ".pdf"
)
LEGAL_REVIEW_PATH = Path(
    "research/hg007/anantraj-full-scheme/p026-clause-review-v1.json"
)
LEGAL_REVIEW_GIT_BLOB = "d1c18d07eaa6a756e0b83ac8e0f477dd33ac99f0"
LEGAL_ORIGINAL_SCHEME_SHA = (
    "76db08d6210360291e81ab7813302067acdb34206cd03561db1ce0ba7ffe528f"
)
TOTAL_GROSS = Decimal("1100.00")
TOTAL_SPENT_TO_MAR = Decimal("350.00")
TOTAL_SPENT_APR_JUN = Decimal("60.01")
TOTAL_SPENT_TO_JUNE = Decimal("410.01")
TOTAL_REMAINING = Decimal("689.99")
REPORTED_SBI_FDR_JUNE_TOTAL = Decimal("690.01")
NSE_RECEIPT_ID = "HG007-P028-ANANTRAJ-NSE-JUNE-QIP-MONITOR-ORIGINAL-v1"

# All figures are manually crosschecked against the ORIGINAL 21-page NSE
# PDF QIP object-utilization table (human pages 12-14).
# Explicit page locator prevents numbers being reattributed to other issuers
# or later updates. Values are *issuer/MA-reported*, not audited net cash.
OBJECT_ROWS = (
    ("CLOUD_SUBSIDIARY", 12, "440.00", "52.03", "29.23", "81.26", "358.74"),
    ("OTHER_PARENT_CONSTRUCTION", 12, "164.40", "7.13", "2.86", "9.99", "154.41"),
    ("LAND_AND_RIGHTS", 13, "185.00", "45.48", "25.44", "70.92", "114.08"),
    ("BORROWING_REPAYMENT", 13, "125.00", "125.00", "0.00", "125.00", "0.00"),
    ("GENERAL_CORPORATE_PURPOSES", 14, "157.80", "95.87", "0.00", "95.87", "61.93"),
    ("QIP_ISSUE_EXPENSES", 14, "27.80", "24.49", "2.48", "26.97", "0.83"),
)

SOURCE_PAGE_KEYWORDS = {
    4: ("issuer", "monitoring agency", "deviation"),
    6: ("1100.00", "27.80", "1072.20"),
    8: ("cash credit", "comingling", "ca certificate"),
    11: ("data centres", "cloud", "175.00"),
    12: ("440.00", "52.03", "29.23", "81.26", "358.74", "164.40", "154.41"),
    13: ("185.00", "45.48", "25.44", "70.92", "114.08", "125.00"),
    14: ("157.8", "95.87", "61.93", "27.80", "26.97", "0.83", "410.01", "689.99"),
    18: ("690.01", "state bank of india", "fdr"),
}
TRANSFER_GATES = (
    "EARMARKED_DEVELOPMENT_QIP_FUNDS",
    "BUSINESS_ONLY_BORROWINGS",
    "GENERAL_PURPOSE_BORROWINGS_PRO_RATA",
    "PARENT_RESULTANT_INTERCOMPANY_ELIMINATION",
    "RESULTANT_ASSUME_CLOUD_LIABILITIES",
    "LEGAL_EXCHANGE_AND_HOLDER_APPROVALS",
)


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _read_pinned_json(root: Path, relative: Path, blob: str) -> dict[str, Any]:
    raw = (root / relative).read_bytes()
    if _git_blob(raw) != blob:
        raise ValueError(f"original source JSON Git blob changed: {relative}")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise TypeError(f"original source JSON is not a mapping: {relative}")
    return obj


def _original_pages(root: Path) -> tuple[list[str], dict[str, Any]]:
    receipt = _read_pinned_json(
        root, SOURCE_RECEIPT_PATH, SOURCE_RECEIPT_GIT_BLOB
    )
    raw = (root / SOURCE_PDF_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != REPORT_SHA256 or len(raw) != 1_271_088:
        raise ValueError("NSE 21-page monitoring report original bytes changed")
    if (
        receipt.get("source_id") != NSE_RECEIPT_ID
        or receipt.get("source_sha256") != REPORT_SHA256
        or receipt.get("source_byte_count") != len(raw)
        or receipt.get("http_status") != 200
        or receipt.get("state") != "NSE_ORIGINAL_21PAGE_PDF_CAPTURED_NOT_CLOUD_ASSET_AUDIT"
        or receipt.get("cash_transferred_to_ashok_cloud_ascertained") is not False
        or receipt.get("live_capital_allowed") is not False
    ):
        raise ValueError("NSE original monitoring source receipt authority changed")
    try:
        pdf = PdfReader(io.BytesIO(raw), strict=False)
        if len(pdf.pages) != 21:
            raise ValueError("original NSE monitoring report page count changed")
        pages = [page.extract_text() or "" for page in pdf.pages]
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise ValueError("original NSE monitoring report PDF cannot be read") from exc
    expected_hashes = receipt.get("pdf_text_identity", {}).get("page_text_sha256")
    if (
        not isinstance(expected_hashes, list)
        or len(expected_hashes) != 21
        or [hashlib.sha256(p.encode()).hexdigest() for p in pages] != expected_hashes
    ):
        raise ValueError("all 21 original NSE PDF page-text hashes must match receipt")
    for page_no, required in SOURCE_PAGE_KEYWORDS.items():
        # Allow line breaks/spaces between words as PDF layout differs
        text = re.sub(r"\s+", " ", pages[page_no - 1]).casefold()
        numeric_text = text.replace(",", "")
        for token in required:
            if token not in numeric_text:
                raise ValueError(
                    f"original NSE page {page_no} missing {token} bound to QIP context"
                )
    return pages, receipt


def _legal_gate(root: Path) -> dict[str, Any]:
    legal = _read_pinned_json(root, LEGAL_REVIEW_PATH, LEGAL_REVIEW_GIT_BLOB)
    if (
        legal.get("review_id") != "HG007-P026-ANANTRAJ-DEMERGER-SOURCE-CLAUSES-v1"
        or legal.get("original_scheme_pdf_sha256") != LEGAL_ORIGINAL_SCHEME_SHA
        or legal.get("reviewed_specific_legal_clause_count") != 22
        or legal.get("scheme_asset_allocation_is_quantified_in_this_audit") is not False
        or legal.get("scheme_legal_approval_and_effective_date_verified") is not False
        or legal.get("equity_expected_returns_calculated") is not False
    ):
        raise ValueError("original P026 legal source scheme contract changed")
    clauses = legal.get("reviewed_clauses")
    if not isinstance(clauses, list):
        raise TypeError("P026 legal clause list missing")
    by_id = {row.get("clause_id") for row in clauses}
    if len(by_id) != len(clauses) or not set(TRANSFER_GATES).issubset(by_id):
        raise ValueError("P026 legal cash/debt/equity-transfer clauses unavailable")
    remaining = legal.get("unquantified_core_underwriting_inputs")
    if not isinstance(remaining, dict) or any(
        remaining.get(k) is not None
        for k in (
            "earmarked_data_centre_QIP_cash_at_transfer_inr_crore",
            "directly_attributable_business_borrowings_inr_crore",
            "general_purpose_borrowings_allocated_inr_crore",
            "intercompany_balances_cancelled_inr_crore",
        )
    ):
        raise ValueError("P026 legal transfer cash/debt was not source quantified")
    return legal


def _decimal_rows() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for key, page, allocated, before, during, cumulative, unused in OBJECT_ROWS:
        nums = list(map(Decimal, (allocated, before, during, cumulative, unused)))
        if any(value < 0 or not value.is_finite() for value in nums):
            raise ValueError("monitoring report contains negative or nonfinite amount")
        if nums[1] + nums[2] != nums[3] or nums[0] - nums[3] != nums[4]:
            raise ValueError(f"{key}: original QIP object does not reconcile")
        records.append({
            "object_id": key,
            "original_pdf_page_number": page,
            "gross_qip_object_allocation_inr_crore": float(nums[0]),
            "utilized_before_april2026_inr_crore": float(nums[1]),
            "utilized_during_april_june2026_inr_crore": float(nums[2]),
            "cumulative_utilized_june30_inr_crore": float(nums[3]),
            "monitored_unutilized_june30_inr_crore": float(nums[4]),
            "allocation_is_dated_monitoring_object_not_transferred_cash": True,
            "actual_legal_demerger_cash_received_by_newco_verified": False,
        })
    arrays = [
        (sum(Decimal(str(row[col])) for row in records), required, col)
        for col, required in (
            ("gross_qip_object_allocation_inr_crore", TOTAL_GROSS),
            ("utilized_before_april2026_inr_crore", TOTAL_SPENT_TO_MAR),
            ("utilized_during_april_june2026_inr_crore", TOTAL_SPENT_APR_JUN),
            ("cumulative_utilized_june30_inr_crore", TOTAL_SPENT_TO_JUNE),
            ("monitored_unutilized_june30_inr_crore", TOTAL_REMAINING),
        )
    ]
    for total, expected, name in arrays:
        if total != expected:
            raise ValueError(f"{name}: table sums disagree with source total")
    return records


def build_qip_scheme_cash_review(root: Path) -> dict[str, Any]:
    pages, original = _original_pages(root)
    legal = _legal_gate(root)
    rows = _decimal_rows()
    cloud = next(row for row in rows if row["object_id"] == "CLOUD_SUBSIDIARY")
    if cloud["gross_qip_object_allocation_inr_crore"] != 440.0:
        raise ValueError("original cloud QIP category allocation changed")
    if not math.isclose(
        TOTAL_REMAINING - REPORTED_SBI_FDR_JUNE_TOTAL, Decimal("-0.02"), abs_tol=1e-12
    ):
        raise ValueError("FDR 2 lakh difference arithmetic changed")
    by_page = [
        {
            "pdf_page": page_no,
            "page_text_sha256": hashlib.sha256(pages[page_no - 1].encode()).hexdigest(),
            "source_pdf_sha256": REPORT_SHA256,
        }
        for page_no in sorted(SOURCE_PAGE_KEYWORDS)
    ]
    return {
        "schema_version": 1,
        "review_id": AUDIT_ID,
        "classification": "ORIGINAL_NSE_MONITOR_QIP_DATED_OBJECT_LEDGER_NOT_NEWCO_CASH",
        "symbol": "ANANTRAJ",
        "data_cutoff_date": "2026-06-30",
        "original_exchange_publication_date": "2026-08-08",
        "original_nse_pdf_sha256": REPORT_SHA256,
        "original_source_url": original["original_source_url"],
        "original_nse_receipt_git_blob": SOURCE_RECEIPT_GIT_BLOB,
        "original_pdf_page_count": 21,
        "evidence_page_locators": by_page,
        "reported_QIP_gross_proceeds_inr_crore": float(TOTAL_GROSS),
        "reported_QIP_net_proceeds_inr_crore": 1072.20,
        "issuer_monitor_QIP_objects": rows,
        "reported_cumulative_used_by_june30_inr_crore": float(TOTAL_SPENT_TO_JUNE),
        "reported_unused_by_june30_inr_crore": float(TOTAL_REMAINING),
        "monitoring_report_same_date_fdr_total_inr_crore": float(
            REPORTED_SBI_FDR_JUNE_TOTAL
        ),
        "fdr_less_unutilized_report_discrepancy_inr_crore": 0.02,
        "fdr_total_discrepancy_explained_by_original_source": False,
        "historical_cloud_spend_for_subsidiary_inr_crore": (
            cloud["cumulative_utilized_june30_inr_crore"]
        ),
        "historical_cloud_qip_unused_allocation_inr_crore": (
            cloud["monitored_unutilized_june30_inr_crore"]
        ),
        "cloud_qip_unused_is_newco_free_cash": False,
        "non_cloud_unused_allocations_inr_crore": 331.25,
        "non_cloud_unused_may_not_be_relabelled_cloud_assets": True,
        "original_monitor_disclosed_cash_credit_commingling": True,
        "monitoring_agency_performed_independent_financial_audit": False,
        "legal_scheme_source_sha256": legal["original_scheme_pdf_sha256"],
        "legal_scheme_review_id": legal["review_id"],
        "legal_scheme_review_git_blob": LEGAL_REVIEW_GIT_BLOB,
        "relevant_proposed_legal_clauses": list(TRANSFER_GATES),
        "demerger_cloud_qip_cash_amount_as_of_effective_date_inr_crore": None,
        "demerger_direct_operating_debt_inr_crore": None,
        "demerger_pro_rata_general_purpose_debt_inr_crore": None,
        "demerger_intercompany_balances_to_eliminate_inr_crore": None,
        "underlying_cloud_capex_assets_valued_from_monitored_spending": False,
        "full_post_june_bank_maturity_and_uses_reconciled": False,
        "scheme_legally_effective_confirmed": False,
        "newco_net_cash_or_equity_value_calculated": False,
        "prospective_return_outcomes_opened": False,
        "company_completion_probability_published": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
