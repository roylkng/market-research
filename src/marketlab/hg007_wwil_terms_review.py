"""Page-bound term corrections to WWIL's original 7 October BSE disclosure.

Facts are *issuer-filed statements*, not independent proof of economic
completion, enterprise value, loan conversion or target earnings. The six
pages are verified byte-for-byte against the exact P003 original PDF and
the P004 anchored extraction before producing a source review.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from marketlab.hg007_original_pages import (
    EXPECTED_SHA,
    build_original_pdf_page_packet,
    validate_original_pdf_page_packet,
)

REVIEW_ID = "HG007-P005-2026-10-07-INOXGREEN-WWIL-TEXT-TERM-REVIEW-v1"
PAGES_PATH = Path("research/hg007/wwil-bse-original/original-page-text-v1.json")
PAGES_GIT_BLOB = "013f76b6cbdef493db088832ba48d314200a6aa5"
EXPECTED_PAGE_HASHES = (
    "4b3838dcb9fdf6c955b2e1370edd639287b43203846abdb4b88d39fe48b83bd0",
    "739124f16ce9188aa72a7a471878b2273e7eaeddf79d3f8332951c4a614e5e24",
    "5b4602af3d50cfca02100283a374a66e6821cd196d97fe9d083492a027938cec",
    "e92aa2c56bf763ec1ac3418cded48460123f36bc18d16ffd83390de024c48fd2",
    "0ebab5c1f4a2c54f59df04d303526d6498def809f06c8ef1fe2de7c40516077d",
    "43d5745e32a197e2f6b2957468738847c5cea260ec6202efc83405665e31bdc9",
)

# Analyst-checked, minimal *original page* substrings supporting bounded
# interpretation. A filing's disclosed statement is not independent proof
# of the business closing or future cash flows.
SOURCE_FACTS: tuple[dict[str, Any], ...] = (
    {"field": "nclt_plan_approval_date", "value": "2026-07-27", "page": 1,
     "page_anchors": ("27 th july, 2026", "resolution plan"), "state": "ISSUER_REPORTED"},
    {"field": "imc_deadline_extension", "value": "2026-10-08", "page": 1,
     "page_anchors": ("september 25, 2026", "8th october, 2026"),
     "state": "ISSUER_REPORTED_WINDOW_NOT_CLOSING_CERTIFICATE"},
    {"field": "bta_executed", "value": True, "page": 1,
     "page_anchors": ("business transfer", "agreement", "executed"),
     "state": "ISSUER_REPORTED_EXECUTION"},
    {"field": "wwil_cash_consideration_paid_inr_crore", "value": 550.0, "page": 1,
     "page_anchors": ("6 th october, 2026", "rs. 550 crore"),
     "state": "ISSUER_REPORTED_PAYMENT_NOT_COMPLETED_TRANSFER"},
    {"field": "wwil_business_transfer_requires_bta_conditions", "value": True, "page": 1,
     "page_anchors": ("conditions precedent", "will be completed"),
     "state": "PENDING_CONDITIONS_NEVER_INTERPRET_AS_CLOSED"},
    {"field": "parent_total_funding_inr_crore", "value": 450.0, "page": 2,
     "page_anchors": ("rs. 450 crore", "vibhav by the company"),
     "state": "ISSUER_REPORTED"},
    {"field": "parent_cash_equity_subscription_inr_crore", "value": 250.0, "page": 2,
     "page_anchors": ("rs. 250", "subscription to its equity shares"),
     "state": "ISSUER_REPORTED"},
    {"field": "parent_unsecured_intercompany_deposit_inr_crore", "value": 200.0, "page": 2,
     "page_anchors": ("rs. 200 crore", "inter corporate deposit"),
     "state": "ISSUER_REPORTED"},
    {"field": "authum_intercompany_deposit_inr_crore", "value": 100.0, "page": 2,
     "page_anchors": ("authum", "rs. 100 crore"),
     "state": "ISSUER_REPORTED_OUTSIDE_FUNDING"},
    {"field": "authum_future_securities_conversion_disclosed", "value": True, "page": 2,
     "page_anchors": ("authum", "to be converted into equity/securities"),
     "state": "PROPOSED_FUTURE_CONVERSION_NOT_EXECUTED"},
    {"field": "vibhav_equity_paid_up_after_subscription_inr_crore",
     "value": 250.01, "page": 3,
     "page_anchors": ("rs. 250.01 crore", "after considering", "above allotment"),
     "state": "ISSUER_REPORTED_SUBSIDIARY_PAID_UP_CAPITAL"},
    {"field": "vibhav_previous_fy26_revenue_inr_crore", "value": 0.0, "page": 3,
     "page_anchors": ("turnover of vibhav", "was nil"),
     "state": "SUBSIDIARY_HISTORICAL_NOT_WWIL_ACQUIRED_BUSINESS"},
    {"field": "vibhav_parent_current_ordinary_equity_ownership_pct",
     "value": 100.0, "page": 4,
     "page_anchors": ("100% of the equity share", "allotment of equity shares", "completed"),
     "state": "AS_OF_FILING_BEFORE_LOAN_CONVERSIONS"},
    {"field": "new_equity_subscription_share_count_crore", "value": 25.0, "page": 4,
     "page_anchors": ("25 crore equity shares", "issued at par"),
     "state": "ISSUER_REPORTED_COMPLETED_SUBSCRIPTION"},
    {"field": "new_equity_subscription_face_value_inr", "value": 10.0, "page": 4,
     "page_anchors": ("face value of rs. 10", "rights issue basis"),
     "state": "ISSUER_REPORTED_COMPLETED_SUBSCRIPTION"},
    {"field": "parent_loan_annual_coupon_pct", "value": 12.0, "page": 5,
     "page_anchors": ("fixed interest rate of 12%", "per annum"),
     "state": "PARENT_TO_SUBSIDIARY_INTRA_GROUP_COUPON"},
    {"field": "parent_loan_unsecured_and_subordinated", "value": True, "page": 5,
     "page_anchors": ("unsecured rupee loan", "subordinated", "third -party debt"),
     "state": "SUBORDINATE_TO_RESTRUCTURED_AND_OTHER_THIRD_PARTY_DEBT"},
    {"field": "parent_loan_repayment_blocked_until_prior_debt_repaid", "value": True,
     "page": 5,
     "page_anchors": ("shall not be repaid", "prior to full repayment"),
     "state": "CONTRACTUAL_REPAYMENT_RESTRICTION"},
    {"field": "parent_loan_up_to_50_crore_principal_may_convert", "value": 50.0,
     "page": 5,
     "page_anchors": ("upto rs. 50 crore", "along with accrued", "may be converted"),
     "state": "OPTIONAL_BY_MUTUAL_AGREEMENT_NOT_COMMITTED_EQUITY"},
    {"field": "parent_loan_bullet_date_fixed", "value": False, "page": 5,
     "page_anchors": ("bullet", "date to be mutually agreed"),
     "state": "MATURITY_UNSPECIFIED_IN_ORIGINAL_DISCLOSURE"},
    {"field": "parent_loan_executed_date", "value": "2026-09-25", "page": 6,
     "page_anchors": ("25th september, 2026", "lender: inox green"),
     "state": "ISSUER_REPORTED"},
)

BLOCKERS = (
    "BTA_ALL_CONDITIONS_PRECEDENT_AND_SEPARATE_LEGAL_CLOSE_NOTICE",
    "WWIL_CARVEOUT_NORMALIZED_EBITDA_CASH_CONVERSION_AND_RENEWAL_CHURN",
    "AUTHUM_LOAN_COUPON_PRIORITY_SECURITY_MATURITY_AND_CONVERSION_PRICE",
    "PARENT_OPTIONAL_50CR_PLUS_ACCRUED_CONVERSION_CLASS_PRICE_AND_EFFECTIVE_DATE",
    "MINORITY_RIGHTS_AND_FULLY_DILUTED_SUBSIDIARY_CAPITAL",
    "INTRA_GROUP_LOAN_ELIMINATION_AND_STANDALONE_CREDIT_RECOVERY_RISK",
    "LATEST_INOXGREEN_FD_SHARES_POST_QIP_AND_NET_FINANCIAL_ASSETS",
    "SOURCE_PDF_VISUAL_PAGE_LAYOUT_AND_ANNEXURE_REVIEW",
)


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_verified_page_text(repo_root: Path) -> dict[str, Any]:
    source = repo_root / PAGES_PATH
    raw = source.read_bytes()
    if _git_blob(raw) != PAGES_GIT_BLOB:
        raise ValueError("HG007-P004 original page-text Git blob drifted")
    packet = json.loads(raw)
    if not isinstance(packet, dict):
        raise TypeError("original PDF page packet must be JSON object")
    validate_original_pdf_page_packet(packet)
    if packet != build_original_pdf_page_packet(repo_root):
        raise ValueError("recorded page text no longer reproducible from original PDF bytes")
    hashes = tuple(page["text_sha256"] for page in packet["pages"])
    if len(hashes) != 6 or hashes != EXPECTED_PAGE_HASHES:
        raise ValueError("original six page text hashes disagree with independent review")
    return packet


def build_text_facts(packet: dict[str, Any]) -> dict[str, Any]:
    validate_original_pdf_page_packet(packet)
    hashes = tuple(page["text_sha256"] for page in packet["pages"])
    if hashes != EXPECTED_PAGE_HASHES:
        raise ValueError("source pages must match six independently pinned originals")
    by_page = {page["page_number"]: page for page in packet["pages"]}
    facts: dict[str, dict[str, Any]] = {}
    for fact in SOURCE_FACTS:
        page = by_page[fact["page"]]
        normalized = re.sub(r"\s+", " ", page["extracted_text"].casefold())
        for anchor in fact["page_anchors"]:
            if anchor not in normalized:
                raise ValueError(
                    f"original issuer page {fact['page']} does not support {fact['field']}: {anchor}"
                )
        facts[fact["field"]] = {
            "reported_value": fact["value"],
            "issuer_statement_state": fact["state"],
            "source_pdf_page_number": fact["page"],
            "source_page_text_sha256": page["text_sha256"],
            "original_pdf_sha256": EXPECTED_SHA,
        }
    if len(facts) != len(SOURCE_FACTS):
        raise ValueError("duplicate original WWIL fact identity")

    values = {field: row["reported_value"] for field, row in facts.items()}
    if not (
        math.isclose(
            values["parent_cash_equity_subscription_inr_crore"]
            + values["parent_unsecured_intercompany_deposit_inr_crore"]
            + values["authum_intercompany_deposit_inr_crore"],
            values["wwil_cash_consideration_paid_inr_crore"],
        )
        and math.isclose(
            values["parent_cash_equity_subscription_inr_crore"]
            + values["parent_unsecured_intercompany_deposit_inr_crore"],
            values["parent_total_funding_inr_crore"],
        )
        and math.isclose(
            values["new_equity_subscription_share_count_crore"]
            * values["new_equity_subscription_face_value_inr"],
            values["parent_cash_equity_subscription_inr_crore"],
        )
    ):
        raise ValueError("original company equity/loan/cash funding does not reconcile")

    raw_parent_loan = values["parent_unsecured_intercompany_deposit_inr_crore"]
    coupon = values["parent_loan_annual_coupon_pct"]
    annual_nominal = raw_parent_loan * coupon / 100.0

    return {
        "schema_version": 1,
        "review_id": REVIEW_ID,
        "classification": (
            "SOURCE_VERIFIED_ISSUER_PAGE_TEXT_TERMS_NOT_TRANSACTION_CLOSE_OR_STOCK_VALUE"
        ),
        "source_original_pdf_sha256": EXPECTED_SHA,
        "source_pdf_page_count": len(hashes),
        "source_original_pages_git_blob_sha": PAGES_GIT_BLOB,
        "review_scope": "SIX_PAGE_TEXT_ONLY_NO_VISUAL_SIGNATURE_OR_IMAGE_APPROVAL",
        "disclosed_terms": facts,
        "disclosed_term_count": len(facts),
        "arithmetic_crosschecks": {
            "issuer_reported_purchase_payment_inr_crore": 550.0,
            "parent_plus_external_funding_reconciles_to_payment": True,
            "parent_cash_subscription_and_loan_reconciles_to_450cr": True,
            "250cr_at_par_equals_25cr_shares_times_10inr": True,
            "parent_200cr_annual_nominal_12pct_intragroup_coupon_inr_crore": (
                annual_nominal
            ),
            "coupon_cash_paid_proven": False,
            "coupon_is_consolidated_group_external_profit": False,
        },
        "material_previous_provisional_interpretation_corrections": [
            {
                "older_assumption": (
                    "INOXGREEN 50cr loan principal is to be converted at a future date"
                ),
                "original_annexure_source_corrected": (
                    "Up to 50cr of parent principal plus accrued interest MAY be "
                    "converted into securities at mutually agreed terms; "
                    "conversion date, class and price are not fixed here"
                ),
                "original_pdf_page": 5,
                "correction_class": "OPTIONAL_CONVERSION_NOT_CERTAIN",
            },
            {
                "older_assumption": (
                    "Post-conversion ~75pct ordinary share ownership is established"
                ),
                "original_annexure_source_corrected": (
                    "Vibhav is 100pct owned as of filing; Authum has a proposed "
                    "100cr future securities conversion but neither issue "
                    "price nor class nor effective future dilution is specified"
                ),
                "original_pdf_page": 2,
                "correction_class": "POST_CONVERSION_CAP_TABLE_UNKNOWN",
            },
            {
                "older_assumption": (
                    "No government approvals is equivalent to WWIL acquisition completed"
                ),
                "original_annexure_source_corrected": (
                    "No further approval statement relates to the listed-company "
                    "subscription into Vibhav, whereas WWIL BTA transfer explicitly "
                    "remains conditional"
                ),
                "original_pdf_page": 3,
                "correction_class": "SUBSIDIARY_SUBSCRIPTION_NOT_TARGET_TRANSFER",
            },
            {
                "older_assumption": "Vibhav previous nil turnover means WWIL O&M turnover nil",
                "original_annexure_source_corrected": (
                    "Vibhav as a previously registered subsidiary had zero FY26 "
                    "turnover; separate WWIL acquired carveout revenue/EBITDA "
                    "is not quantified in this six-page filing"
                ),
                "original_pdf_page": 3,
                "correction_class": "ISSUER_TARGET_FINANCIAL_IDENTITY_DISTINCTION",
            },
        ],
        "remaining_independent_source_requests": list(BLOCKERS),
        "selected_original_page_text_statement_review_complete": True,
        "page_image_visual_review_complete": False,
        "fully_independent_company_due_diligence_complete": False,
        "bta_conditions_satisfied": False,
        "wwil_transfer_legally_completed_verified": False,
        "loan_conversion_completed_verified": False,
        "post_conversion_parent_ownership_percent_verified": False,
        "actual_parent_receivable_coupon_payment_verified": False,
        "wwil_ebitda_cashflow_verified": False,
        "company_completion_probability_published": False,
        "current_fd_valuation_verified": False,
        "expected_returns_calculated": False,
        "live_capital_allowed": False,
        "portfolio_eligibility_allowed": False,
    }
