"""Reconcile original Oct7 vs Oct9 INOXGREEN/Vibhav equity milestones.

The Oct9 VEPL allotment is complete, but the WWIL operating-business
transfer remains unverified. A completed subsidiary equity conversion does
not by itself create new cash or a listed-share price target.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from pypdf import PdfReader

SOURCES = {
    "old_oct07": (
        "research/hg007/wwil-bse-original/reconciled-issuer-terms-v1.json",
        "c40af0367686c0602653576f072755f776ff8cec",
    ),
    "new_oct09": (
        "research/hg007/wwil-oct09-vibhav-conversion/source-receipt-v1.json",
        "5488c0428f51d9ffa6ae0d5e0a06813f9036083c",
    ),
    "listed_parent_fd_asof": (
        "research/hg007/hg007-p044-inoxgreen-publication-safe-fd-v1.json",
        "c1a21bc5101688924be013911f5b9c88abb1ef99",
    ),
    "frozen_28_case_board": (
        "research/hg007/hg007-p009-28-case-capital-readiness-overlay-v1.json",
        "a502a582e93b408baba38dca7b95532836646700",
    ),
}
ORIGINAL_OCT09_PDF_SHA = "12a0a512c279ee6580120b82346bc85c1720c4ae0e5959edd9b7d3225e9b898f"
REVIEW_ID = "HG007-P046-INOXGREEN-2026-10-09-VEPL-CONVERSION-STATE-v1"


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_pinned_sources(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    values: dict[str, Any] = {}
    receipts: dict[str, Any] = {}
    for label, (rel, expected) in SOURCES.items():
        raw = (root / rel).read_bytes()
        if _blob(raw) != expected:
            raise ValueError(f"{label}: original research Git blob changed")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise TypeError(f"{label} source must be JSON object")
        values[label] = value
        receipts[label] = {
            "path": rel, "git_blob_sha": expected,
            "original_raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    original = (
        root / "research/hg007/wwil-oct09-vibhav-conversion/raw/sha256"
        / f"{ORIGINAL_OCT09_PDF_SHA}.pdf"
    )
    bytes_pdf = original.read_bytes()
    if hashlib.sha256(bytes_pdf).hexdigest() != ORIGINAL_OCT09_PDF_SHA:
        raise ValueError("original 9 Oct issuer PDF original SHA mismatch")
    captured = values["new_oct09"]
    if captured.get("original_pdf_sha256") != ORIGINAL_OCT09_PDF_SHA or captured.get(
        "original_pdf_size"
    ) != len(bytes_pdf):
        raise ValueError("original PDF/issuer receipt identity mismatch")
    pages = list(PdfReader(io.BytesIO(bytes_pdf), strict=False).pages)
    if len(pages) != 2:
        raise ValueError("original 9 Oct PDF must have exactly two verified pages")
    expected_page_hashes = captured.get(
        "text_verified_disclosure_fields_not_investment_approval", {}
    ).get("page_text_sha256")
    actual_page_hashes = [
        hashlib.sha256((page.extract_text() or "").encode()).hexdigest()
        for page in pages
    ]
    if actual_page_hashes != expected_page_hashes:
        raise ValueError("original 9 Oct text pages do not match first source capture")
    receipts["new_oct09_pdf"] = {
        "path": str(original.relative_to(root)),
        "raw_sha256": ORIGINAL_OCT09_PDF_SHA,
        "bytes": len(bytes_pdf),
    }
    return values, receipts


def reconcile_oct09_status(inputs: dict[str, Any], receipts: dict[str, Any]) -> dict[str, Any]:
    if set(inputs) != set(SOURCES):
        raise ValueError("missing original source family")
    old = inputs["old_oct07"]
    newer = inputs["new_oct09"]
    fd = inputs["listed_parent_fd_asof"]
    board = inputs["frozen_28_case_board"]
    facts = old.get("disclosed_terms")
    event = newer.get("text_verified_disclosure_fields_not_investment_approval")
    if not isinstance(facts, dict) or not isinstance(event, dict):
        raise TypeError("dated original issuer statements required")
    old_required = {
        "wwil_cash_consideration_paid_inr_crore": 550,
        "parent_cash_equity_subscription_inr_crore": 250,
        "parent_unsecured_intercompany_deposit_inr_crore": 200,
        "authum_intercompany_deposit_inr_crore": 100,
        "vibhav_equity_paid_up_after_subscription_inr_crore": 250.01,
        "vibhav_parent_current_ordinary_equity_ownership_pct": 100,
        "parent_loan_up_to_50_crore_principal_may_convert": 50,
    }
    if (
        old.get("review_id")
        != "HG007-P005-2026-10-07-INOXGREEN-WWIL-TEXT-TERM-REVIEW-v1"
        or old.get("wwil_transfer_legally_completed_verified") is not False
        or old.get("loan_conversion_completed_verified") is not False
        or old.get("live_capital_allowed") is not False
    ):
        raise ValueError("original Oct7 issuer stage no longer frozen")
    for key, expected in old_required.items():
        val = facts.get(key)
        if not isinstance(val, dict) or val.get("reported_value") != expected:
            raise ValueError("Oct7 issuer funding changed: " + key)
    if (
        newer.get("source_id")
        != "HG007-P045-INOXGREEN-2026-10-09-VIBHAV-EQUITY-CONVERSION-SOURCE-v1"
        or newer.get("source_state") != "OFFICIAL_NSE_OCT09_PDF_CAPTURED_UNREVIEWED"
        or newer.get("wwil_undertaking_transfer_completed") is not False
        or newer.get("source_first_public_timestamp_verified") is not False
        or newer.get("live_capital_allowed") is not False
        or event.get("filing_date_ist") != "2026-10-09"
        or event.get("vibhav_conversion_date_ist") != "2026-10-09"
        or event.get("total_existing_icds_converted_inr_crore") != 150
        or event.get("inoxgreen_icd_converted_inr_crore") != 50
        or event.get("authum_icd_converted_inr_crore") != 100
        or event.get("inoxgreen_new_vibhav_equity_shares_crore") != 5
        or event.get("authum_new_vibhav_equity_shares_crore") != 10
        or event.get("subsidiary_paid_up_cap_after_conversion_inr_crore") != 400.01
        or event.get("reported_issuer_vibhav_ownership_pct") != 75
        or event.get("reported_authum_vibhav_ownership_pct") != 25
        or event.get("conversion_is_noncash") is not True
        or event.get("post_conversion_vibhav_wholly_owned") is not False
    ):
        raise ValueError("original Oct9 postconversion issuer facts changed")
    if (
        fd.get("audit_id")
        != "HG007-P044-INOXGREEN-DATED-ORIGINAL-FD-PUBLICATION-GATE-v1"
        or fd.get("original_september_29_reported_fully_diluted_shares")
        != 422_070_138
        or fd.get("independently_verified_current_october_13_fully_diluted_count")
        is not False
        or fd.get("live_capital_allowed") is not False
    ):
        raise ValueError("listed parent FD report was promoted without verification")
    rows = board.get("casework_with_capital_readiness")
    if (
        board.get("overlay_id")
        != "HG007-P009-POST-QIP-28-CASE-CAPITAL-READINESS-v1"
        or not isinstance(rows, list)
        or len(rows) != 28
        or board.get("live_capital_allowed") is not False
    ):
        raise ValueError("original 28-case hidden-gem selection changed")
    identities = [row.get("symbol") for row in rows if isinstance(row, dict)]
    if len(identities) != 28 or len(set(identities)) != 28 or identities.count("INOXGREEN") != 1:
        raise ValueError("original HG007 28 issuer identities changed")
    parent_capital = 250.01 + 50
    external_capital = 100
    if not math.isclose(parent_capital + external_capital, 400.01):
        raise ValueError("original VEPL noncash conversion capital amounts disagree")

    casework = []
    for original in rows:
        case = deepcopy(original)
        if case["symbol"] == "INOXGREEN":
            if case.get("economic_sensitivity_state") != "PAYOFF_FRAMEWORK_BLOCKED_SOURCE_PARTIAL":
                raise ValueError("original INOXGREEN blocked payoff context modified")
            case["latest_documented_vepl_milestone"] = {
                "issuer_filing_date_ist": "2026-10-09",
                "equity_allotment": "COMPLETED_VIBHAV_ICD_TO_EQUITY",
                "minority_ownership": {"INOXGREEN_percent": 75, "AUTHUM_percent": 25},
                "vepl_legal_subsidiary_still_controlled": True,
                "new_cash_inflow_from_conversion": False,
                "wwil_underlying_om_business_transfer_completed_verified": False,
                "completion_probability_or_target_price_validated": False,
                "stock_or_portfolio_approval": False,
            }
        casework.append(case)
    return {
        "schema_version": 1,
        "review_id": REVIEW_ID,
        "classification": "FROZEN_ASOF_STAGE_AMENDMENT_NOT_SHAREHOLDER_RETURN",
        "research_as_of_ist": "2026-10-13",
        "source_receipts": receipts,
        "oct07_preconversion_state_preserved": {
            "as_of_original_filing_date": "2026-10-07",
            "vibhav_equity_parent_ownership_pct": 100,
            "funding_conversion_status": "PROPOSED_OPTIONAL_FUTURE",
            "wwil_bta_cash_payment_reported_inr_crore": 550,
            "wwil_business_transfer_conditions_cleared": False,
        },
        "oct09_completed_equity_milestone": {
            "event_date": "2026-10-09",
            "vepl_deposit_to_equity_conversion_completed": True,
            "total_converted_inr_crore": 150,
            "issuer_converted_inr_crore": 50,
            "authum_converted_inr_crore": 100,
            "post_conversion_vibhav_paid_up_capital_inr_crore": 400.01,
            "issuer_reported_vibhav_ownership_pct": 75,
            "authum_reported_vibhav_ownership_pct": 25,
            "source_capital_ratio_issuer_computed_pct": (
                100 * parent_capital / (parent_capital + external_capital)
            ),
            "new_cash_raised_in_vepl_from_conversion_inr_crore": 0,
            "wwil_underlying_business_transfer_closing_proven": False,
        },
        "conditionally_implied_parent_outstanding_icd_principal_inr_crore": 150,
        "actual_parent_remaining_principal_accrued_interest_verified": False,
        "authum_future_loan_and_noncontrolling_interest_terms_fully_reviewed": False,
        "official_source_first_public_timestamp_verified": False,
        "oct09_market_close_time_safe_use_verified": False,
        "listed_issuer_sep29_fd_shares_verified_then_not_current": 422_070_138,
        "listed_issuer_current_oct13_fd_count_verified": False,
        "original_28_company_selection_changed": False,
        "casework_with_current_vepl_milestone": casework,
        "missing_original_underwriting_evidence": [
            "WWIL_BTA_CONDITIONS_PRECEDENT_EFFECTIVE_DATE_AND_CLOSE_CERTIFICATE",
            "ACQUIRED_O_AND_M_NORMALIZED_EBITDA_FCF_RECEIVABLES_AND_CHURN",
            "AUTHUM_ORIGINAL_OCT10_COUNTERPARTY_FILING_AND_FACILITY_TERMS",
            "POST_CONVERSION_VEPL_SUBSIDIARY_NET_DEBT_INTERCOMPANY_ELIMINATIONS",
            "CURRENT_INOXGREEN_EQUITY_FD_ESOPS_PLEDGE_AND_NET_DEBT",
        ],
        "company_completion_probabilities_published": 0,
        "expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
