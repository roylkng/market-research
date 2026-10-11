"""Page-bound issuer legal-clause review for the proposed ANANTRAJ cloud demerger.

All 48 original pages are SHA-verified against the immutable HG007-P025
source index; source clauses are proposed contractual language, not executed
cash/debt transfers, effective approvals, or investment recommendations.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from marketlab.hg007_anantraj_scheme_pages import INDEX_ID, PAGE_COUNT, PDF_SHA256

AUDIT_ID = "HG007-P026-ANANTRAJ-DEMERGER-SOURCE-CLAUSES-v1"
PAGE_DIR = Path("research/hg007/anantraj-full-scheme/page-text-v1")
PAGE_INDEX_BLOB = "24db2f0cde331a9dc1b38764d34f99f22465bfc5"
LOOKTHROUGH_PATH = Path(
    "research/hg007/anantraj-july2026-originals/"
    "conditional-parent-direct-newco-ownership-v1.json"
)
LOOKTHROUGH_BLOB = "2d29a95a1e7a9b804fe5b18a76a4de1fe2341757"

# These are bounded analyst interpretations supported by required anchors
# on original PDF pages. Never treated as an actual balance-sheet schedule.
CLAUSES: tuple[tuple[str, int, tuple[str, ...], str], ...] = (
    ("ARL_REMAINING_BUSINESS", 6,
     ("ARL Remaining Business", "other than those specified"),
     "Real estate and other business outside the proposed cloud undertaking remain with ARL."),
    ("FUTURE_RECORD_DATE", 6,
     ("Demerger Record Date", "mutually agreed date to be fixed"),
     "Actual shareholder record date is to be set later by the relevant boards."),
    ("CLOUD_SCOPE_AFTER_MERGER", 6,
     ("Demerged Undertaking", "Data Centre Business of ARL"),
     "Demerged scope includes cloud operations and ARCPL items first vested in ARL."),
    ("EARMARKED_DEVELOPMENT_QIP_FUNDS", 7,
     ("qualified institutions placement", "development, expansion, funding"),
     "Funds earmarked for cloud investment, potentially including QIP proceeds, fall within proposed undertaking."),
    ("BUSINESS_ONLY_BORROWINGS", 7,
     ("Loans and borrowings", "solely for"),
     "Borrowings raised and used solely for the cloud business are included."),
    ("GENERAL_PURPOSE_BORROWINGS_PRO_RATA", 8,
     ("general or multipurpose borrowings", "same proportion"),
     "General-purpose borrowings may be allocated by the transferred-assets-to-total-assets ratio."),
    ("BOARD_DISPUTE_ALLOCATION", 8,
     ("Any issue as to whether any Asset", "mutually decided"),
     "The boards can determine disputes over whether items belong to the undertaking."),
    ("EFFECTIVE_FIRST_OF_NEXT_MONTH_AFTER_CONDITIONS", 8,
     ("first day of the month following", "Clause 37.1"),
     "Effective date depends on the month all conditional approvals/actions have occurred."),
    ("PARENT_RETAINS_NONCLOUD", 28,
     ("ARL Remaining Business", "shall continue to belong"),
     "Remaining ARL assets and liabilities do not automatically transfer with cloud undertaking."),
    ("PARENT_RESULTANT_INTERCOMPANY_ELIMINATION", 31,
     ("inter-company loans", "come to an end automatically"),
     "Relevant parent-resultant intercompany balances are canceled on effectiveness."),
    ("RESULTANT_ASSUME_CLOUD_LIABILITIES", 32,
     ("Liabilities of the Demerged Company", "Liabilities of the Resultant Company"),
     "Cloud business liabilities and relevant post-appointed-date obligations vest in resultant company."),
    ("ASSET_ATTACHED_EXISTING_CHARGES", 33,
     ("All Encumbrances", "continue to relate and attach"),
     "Existing charges on transferred assets generally remain attached, not expanded to unrelated assets."),
    ("DIRECT_SHARE_ENTITLEMENT_ONE_FOR_ONE_PROPOSED", 37,
     ("1 (one) fully paid-up equity share", "for every 1 (one)"),
     "Proposed direct entitlement is one resulting-company share per eligible existing ARL share."),
    ("PARENT_NEWCO_SHARES_NOT_CANCELLED", 37,
     ("shall not extinguish", "existing shareholding held by ARL in Ashok Cloud"),
     "Proposed new allotment does not cancel pre-existing parent-owned Ashok Cloud shares."),
    ("ENTITLEMENT_RATIO_CAN_CHANGE", 37,
     ("Share Entitlement Ratio may", "be adjusted"),
     "Intervening capital issuance/restructuring can change the proposed 1-for-1 ratio."),
    ("AUTHORIZED_CAPITAL_NOT_ISSUED", 41,
     ("Authorised Share Capital", "73,44,49,483"),
     "734,449,483 is proposed authorized newco equity capacity, not proof of issued or record-date shares."),
    ("PARENT_BOOK_VALUE_REDUCTION", 41,
     ("assets, liabilities and reserves", "respective carrying value"),
     "Transferred items are to be removed at carrying value from standalone ARL accounts."),
    ("RESULTANT_COMMON_CONTROL_BOOK_VALUES", 42,
     ("Pooling of Interest Method", "respective carrying"),
     "Ashok Cloud is proposed to recognize undertaking at carrying values under common-control accounting."),
    ("RESULTANT_INTERCOMPANY_CANCELLATION", 42,
     ("inter-company balances", "stand cancelled"),
     "Duplicative parent/newco intercompany balances are proposed to be canceled."),
    ("LEGAL_EXCHANGE_AND_HOLDER_APPROVALS", 45,
     ("Stock Exchanges", "respective requisite majorities"),
     "Exchange non-objection and prescribed shareholder/creditor consents are conditions."),
    ("TRIBUNAL_AND_ROC_NONCOMPLETION_GATE", 46,
     ("certified copy of the order", "Scheme shall not come into effect"),
     "Tribunal sanction and required ROC filings precede effectiveness; the proposal is not a closing record."),
    ("SPECIFIC_IMMOVABLE_LOCATIONS", 48,
     ("Plot No. CP-1", "Plot No. TP-1"),
     "Annexure A identifies plots at Manesar and Rai/Sonipat, without independently valuing them."),
)


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _verify_source_pages(root: Path) -> tuple[dict, dict[int, str]]:
    original_index_raw = (root / PAGE_DIR / "page-index-v1.json").read_bytes()
    if _git_blob(original_index_raw) != PAGE_INDEX_BLOB:
        raise ValueError("original 48-page source index Git blob modified")
    original_index = json.loads(original_index_raw)
    if (
        original_index.get("index_id") != INDEX_ID
        or original_index.get("pdf_original_sha256") != PDF_SHA256
        or original_index.get("page_count") != PAGE_COUNT
        or original_index.get("full_liability_asset_semantic_audit_completed") is not False
        or original_index.get("live_capital_allowed") is not False
    ):
        raise ValueError("original issuer PDF clause source/approval identity invalid")

    source_files = original_index.get("pages")
    if not isinstance(source_files, list) or len(source_files) != PAGE_COUNT:
        raise ValueError("original page source accounting changed")
    texts: dict[int, str] = {}
    for number, info in enumerate(source_files, 1):
        if not isinstance(info, dict) or info.get("page_number") != number:
            raise ValueError("original page number changed")
        filename = f"original-page-{number:02d}.txt"
        if info.get("file_name") != filename:
            raise ValueError("original page file name changed")
        raw = (root / PAGE_DIR / filename).read_bytes()
        text = raw.decode("utf-8")
        if (
            hashlib.sha256(raw).hexdigest() != info.get("source_page_text_sha256")
            or len(text) != info.get("character_count")
            or info.get("issuer_proposed_terms_are_legal_approval") is not False
        ):
            raise ValueError(f"original issuer page {number} is not SHA-verified")
        texts[number] = text
    return original_index, texts


def _verify_proxy(root: Path) -> tuple[dict, dict]:
    raw = (root / LOOKTHROUGH_PATH).read_bytes()
    if _git_blob(raw) != LOOKTHROUGH_BLOB:
        raise ValueError("original P022 conditional shareholder lookthrough changed")
    source = json.loads(raw)
    if not isinstance(source, dict):
        raise TypeError("shareholder proxy source must be a JSON object")
    p = source.get("illustrative_no_other_newco_share_events_scenario")
    if not isinstance(p, dict):
        raise TypeError("conditional ownership scenario missing")
    if (
        source.get("live_capital_allowed") is not False
        or source.get("proposed_scheme", {}).get("effective_nclt_scheme_verified") is not False
        or p.get("newco_parent_retained_shares_IF_NOT_CANCELLED") != 374_572_553
        or p.get("newco_direct_new_shares_if_1_to_1") != 359_876_930
        or p.get("total_newco_shares_if_effective") != 734_449_483
        or p.get("realized_shareholder_distribution_or_value_creation_verified") is not False
    ):
        raise ValueError("frozen owner-level economic claim became inconsistent")
    return source, {
        "source_path": str(LOOKTHROUGH_PATH),
        "git_blob_sha": LOOKTHROUGH_BLOB,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }


def build_source_clause_review(root: Path) -> dict[str, Any]:
    index, pages = _verify_source_pages(root)
    _owner, proxy = _verify_proxy(root)
    excerpts = []
    for clause_id, page_num, anchors, meaning in CLAUSES:
        normalized = re.sub(r"\s+", " ", pages[page_num]).casefold()
        for anchor in anchors:
            if re.sub(r"\s+", " ", anchor).casefold() not in normalized:
                raise ValueError(f"original PDF page {page_num} missing clause {clause_id}: {anchor}")
        source_page = index["pages"][page_num - 1]
        excerpts.append({
            "clause_id": clause_id,
            "source_pdf_page": page_num,
            "source_page_text_sha256": source_page["source_page_text_sha256"],
            "verified_original_clause_anchors": list(anchors),
            "interpretation_only_not_completed_transaction": meaning,
            "issuer_source_review_scope": "PROPOSED_SCHEME_CLAUSE_TEXT",
            "actual_balance_sheet_amount_verified": False,
        })
    if len({row["clause_id"] for row in excerpts}) != len(CLAUSES):
        raise ValueError("source clause identities not unique")

    return {
        "schema_version": 1,
        "review_id": AUDIT_ID,
        "classification": "FULL_ORIGINAL_SCHEME_TEXT_CLAUSE_AUDIT_NOT_FAIR_VALUE_OR_LEGAL_CLOSE",
        "symbol": "ANANTRAJ",
        "original_scheme_pdf_sha256": PDF_SHA256,
        "original_48_page_index_git_blob": PAGE_INDEX_BLOB,
        "source_conditional_parent_direct_ownership": proxy,
        "all_48_original_page_hashes_verified": True,
        "reviewed_specific_legal_clause_count": len(excerpts),
        "reviewed_clauses": excerpts,
        "conditional_capital_reconciliation": {
            "newco_authorized_ordinary_share_capacity_in_draft": 734_449_483,
            "illustrative_existing_parent_newco_shares": 374_572_553,
            "illustrative_eligible_ARL_newco_entitlement_proxy_shares": 359_876_930,
            "matches_conditional_2_layer_total_arithmetic": True,
            "actual_future_newco_issued_shares_verified": False,
            "record_date_basic_eligible_shares_verified": False,
            "ratio_not_subject_to_later_adjustment_verified": False,
        },
        "unquantified_core_underwriting_inputs": {
            "transferred_operating_fixed_assets_book_value_inr_crore": None,
            "transferred_real_estate_land_value_inr_crore": None,
            "earmarked_data_centre_QIP_cash_at_transfer_inr_crore": None,
            "directly_attributable_business_borrowings_inr_crore": None,
            "general_purpose_borrowings_allocated_inr_crore": None,
            "actual_transferred_assets_ratio_for_debt_allocation": None,
            "transferred_contingent_guarantees_and_tax_inr_crore": None,
            "intercompany_balances_cancelled_inr_crore": None,
            "carveout_data_centre_free_cash_flow_inr_crore": None,
            "effective_and_record_dates": None,
        },
        "scheme_asset_allocation_is_quantified_in_this_audit": False,
        "scheme_legal_approval_and_effective_date_verified": False,
        "independent_legal_or_audited_financial_review_complete": False,
        "actual_cloud_equity_fair_value_calculated": False,
        "current_company_specific_completion_probability_published": False,
        "equity_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
