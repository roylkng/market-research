"""Anant Raj/Ashok Cloud ownership look-through without double-counting.

Sources: three immutable original July 2026 NSE issuer PDFs and the
original frozen HG005 Oct1 price/old-FD denominator. The proposed scheme
is NOT approved/effective and the future record-date issued share count,
actual transferred net assets and adjusted return remain unknown.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

AUDIT_ID = "HG007-P022-ANANTRAJ-ASHOKCLOUD-CONDITIONAL-LOOKTHROUGH-v1"
RECEIPT_PATH = Path(
    "research/hg007/anantraj-july2026-originals/"
    "verified-original-source-receipts-v1.json"
)
RECEIPT_GIT_BLOB = "c218d1a31c60909d0ed4f510968bedefc46e27d2"
HG005_PATH = Path("research/hg005-d001-result-v1.json")
HG005_GIT_BLOB = "2dbbc3055d1aacec8a37dd510a1a75a3c7868006"
RAW_ROOT = Path("research/hg007/anantraj-july2026-originals/raw/sha256")
SOURCES = {
    "july20_subsidiary_rights_proposal": {
        "sha256": "04fb51cbaa2a31a0c6fa22e06611feee5bef547b43bed9504f191c7e36326d02",
        "page_count": 3,
    },
    "july21_completed_subscription": {
        "sha256": "efdc1f96962e381d432890161fe7c006df6288a3c602dd5a62d9f3209999c906",
        "page_count": 1,
    },
    "july21_conditional_demerger_press": {
        "sha256": "ec20ee9bc46f66668ca9ce350bf9fb7f0ef87d3c557aaa759826e8e0f421f771",
        "page_count": 4,
    },
}
PRE_SUBSCRIPTION_PARENT_ASHOK_SHARES = 250_000
ADDITIONAL_SUBSCRIBED_SHARES = 374_322_553
PARENT_RETAINED_SHARES_AFTER_SUBSCRIPTION = 374_572_553
PARENT_CASH_SUBSCRIPTION_RUPEES = 748_645_106
OLD_POSSIBLE_PARENT_FD_SHARE_COUNT = 359_876_930
ORIGINAL_REFERENCE_PRICE_INR = 577.85
ORIGINAL_REFERENCE_FD_CAP_CRORE = 20_795.48840005
INR_CRORE = 10_000_000
SHARE_FACE_VALUE = 2


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _pdf_pages(raw: bytes, count: int) -> list[str]:
    if not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-2048:]:
        raise ValueError("original Anant Raj PDF envelope corrupted")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if len(reader.pages) != count:
            raise ValueError("source PDF page count differs from original")
        texts = [p.extract_text() or "" for p in reader.pages]
    except (PdfReadError, OSError, TypeError, ValueError, KeyError) as exc:
        raise ValueError("original NSE July issuer PDF not parseable") from exc
    if any(len(t.strip()) < 50 for t in texts):
        raise ValueError("original issuer PDF page text sparse")
    return texts


def _assert_text(page: str, terms: tuple[str, ...], label: str) -> None:
    normalized = re.sub(r"\s+", " ", page).casefold()
    for term in terms:
        if term.casefold() not in normalized:
            raise ValueError(f"original {label} missing issuer term: {term}")


def load_original_ownership_sources(root: Path) -> tuple[dict, dict, dict]:
    receipt_raw = (root / RECEIPT_PATH).read_bytes()
    old_raw = (root / HG005_PATH).read_bytes()
    if _git_blob(receipt_raw) != RECEIPT_GIT_BLOB or _git_blob(old_raw) != HG005_GIT_BLOB:
        raise ValueError("pinned July/HG005 source Git blob was modified")
    receipts = json.loads(receipt_raw)
    market = json.loads(old_raw)
    if not isinstance(receipts, dict) or not isinstance(market, dict):
        raise TypeError("original receipt/HG005 market context must be JSON object")
    if (
        receipts.get("source_batch_id")
        != "HG007-P021-ANANTRAJ-ORIGINAL-JULY2026-SCHEME-SOURCES-v1"
        or receipts.get("source_completion_state")
        != "THREE_ORIGINAL_ISSUER_FILINGS_VERIFIED"
        or receipts.get("original_verified_count") != 3
        or receipts.get("original_scheme_transaction_effective_verified") is not False
        or receipts.get("live_capital_allowed") is not False
    ):
        raise ValueError("original three-source receipt invalid or promoted")
    rows = receipts.get("source_receipts")
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError("original source receipt list incomplete")
    row_map = {row["source_role"]: row for row in rows}
    if set(row_map) != set(SOURCES) or len(row_map) != len(rows):
        raise ValueError("ANANTRAJ original source roles missing/duplicated")
    documents: dict[str, list[str]] = {}
    provenance: dict[str, Any] = {
        "original_nse_source_batch_path": str(RECEIPT_PATH),
        "original_source_receipt_git_blob": RECEIPT_GIT_BLOB,
        "original_source_receipt_raw_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "legacy_hg005_path": str(HG005_PATH),
        "legacy_hg005_git_blob": HG005_GIT_BLOB,
        "original_documents": {},
    }
    for key, contract in SOURCES.items():
        receipt = row_map[key]
        meta = receipt.get("verified_original")
        if (
            receipt.get("state") != "OFFICIAL_PDF_SOURCE_PAGES_VERIFIED_NOT_TRANSACTION_CLOSE"
            or receipt.get("http_status") != 200
            or receipt.get("official_nclt_effective_demerger_order_verified") is not False
            or receipt.get("live_capital_allowed") is not False
            or not isinstance(meta, dict)
            or meta.get("original_pdf_sha256") != contract["sha256"]
            or meta.get("original_pdf_page_count") != contract["page_count"]
        ):
            raise ValueError(f"{key}: original NSE receipt/status changed")
        pdf_path = RAW_ROOT / f"{contract['sha256']}.pdf"
        raw = (root / pdf_path).read_bytes()
        if (
            hashlib.sha256(raw).hexdigest() != contract["sha256"]
            or len(raw) != meta.get("original_pdf_bytes")
        ):
            raise ValueError(f"{key}: actual NSE original PDF changed")
        pages = _pdf_pages(raw, contract["page_count"])
        if [hashlib.sha256(p.encode("utf-8")).hexdigest() for p in pages] != meta[
            "page_text_sha256"
        ]:
            raise ValueError(f"{key}: source-bound PDF page text drifted")
        documents[key] = pages
        provenance["original_documents"][key] = {
            "official_issuer_url": receipt["official_url"],
            "issuer_filing_date": receipt["issuer_filing_date"],
            "original_pdf_sha256": contract["sha256"],
            "original_pdf_byte_count": len(raw),
            "pdf_page_count": len(pages),
            "original_pdf_path": str(pdf_path),
            "page_text_sha256": meta["page_text_sha256"],
        }
    return documents, market, provenance


def _issuer_page_claims(docs: dict[str, list[str]]) -> None:
    # The exact original page locations are independently checked.
    july20 = docs["july20_subsidiary_rights_proposal"]
    july21 = docs["july21_completed_subscription"]
    press = docs["july21_conditional_demerger_press"]
    _assert_text(
        july20[0],
        (
            "37,43,22,553", "37,45,72,553", "2,50,000", "74,86,45,106",
            "wholly owned subsidiary",
        ),
        "July20 subscription proposal page 1",
    )
    _assert_text(
        july21[0],
        ("completed", "37,43,22,553", "74,86,45,106"),
        "July21 completed subscription page 1",
    )
    _assert_text(
        press[3],
        (
            "one fully paid-up", "for every one fully paid-up",
            "scheme will not result in the cancellation",
            "continue to remain a subsidiary", "subject to receipt",
        ),
        "July21 scheme press page 4",
    )


def _historical_share_proxy(market: dict[str, Any]) -> dict[str, Any]:
    if (
        market.get("context_id") != "HG005-D001-v1"
        or market.get("price_session") != "2026-10-01"
        or market.get("return_outcomes_opened") is not False
        or market.get("live_capital_allowed") is not False
    ):
        raise ValueError("historical HG005 Anant Raj share reference altered")
    value = market.get("key_mechanical_context", {}).get("ANANTRAJ")
    if not isinstance(value, dict):
        raise TypeError("historical ANANTRAJ market denominator must be object")
    price, market_cap = value.get("close_price_inr"), value.get(
        "reported_fd_market_cap_inr_crore"
    )
    if (
        type(price) not in (int, float)
        or type(market_cap) not in (int, float)
        or not math.isclose(price, ORIGINAL_REFERENCE_PRICE_INR, abs_tol=1e-9)
        or not math.isclose(market_cap, ORIGINAL_REFERENCE_FD_CAP_CRORE, abs_tol=1e-6)
    ):
        raise ValueError("source HG005 original frozen share denominator changed")
    observed_fd = market_cap * INR_CRORE / price
    if not math.isclose(
        observed_fd, OLD_POSSIBLE_PARENT_FD_SHARE_COUNT, abs_tol=1e-6
    ):
        raise ValueError("original 359876930-share HG005 implied count changed")
    return {
        "source_price_session": "2026-10-01",
        "legacy_price_inr_not_current": price,
        "legacy_fd_market_cap_inr_crore_not_current": market_cap,
        "legacy_implied_fully_diluted_share_count": OLD_POSSIBLE_PARENT_FD_SHARE_COUNT,
        "is_independently_verified_future_record_date_basic_share_count": False,
        "the_source_fd_count_does_not_prove_future_basic_count": True,
    }


def build_conditional_ownership_lookthrough(
    docs: dict[str, list[str]],
    market: dict[str, Any],
    *,
    original_source_provenance: dict[str, Any],
) -> dict[str, Any]:
    _issuer_page_claims(docs)
    baseline = _historical_share_proxy(market)
    if (
        PRE_SUBSCRIPTION_PARENT_ASHOK_SHARES + ADDITIONAL_SUBSCRIBED_SHARES
        != PARENT_RETAINED_SHARES_AFTER_SUBSCRIPTION
        or ADDITIONAL_SUBSCRIBED_SHARES * SHARE_FACE_VALUE
        != PARENT_CASH_SUBSCRIPTION_RUPEES
    ):
        raise ValueError("subsidiary capital subscription exact-source arithmetic mismatch")
    # This is not a record-date assertion. It is a frozen single scenario:
    # *if* future ARL eligible/basic shares equal the earlier HG005 FD proxy.
    assumed_new_issue = OLD_POSSIBLE_PARENT_FD_SHARE_COUNT
    newco_parent_shares = PARENT_RETAINED_SHARES_AFTER_SUBSCRIPTION
    newco_total_if_scheme = newco_parent_shares + assumed_new_issue
    parent_fraction = newco_parent_shares / newco_total_if_scheme
    direct_fraction = assumed_new_issue / newco_total_if_scheme
    parent_indirect_shares_per_parent_share = newco_parent_shares / assumed_new_issue
    direct_newco_shares_per_parent_share = 1.0
    aggregate_newco_equity_fraction_for_one_original_share = (
        parent_indirect_shares_per_parent_share + direct_newco_shares_per_parent_share
    ) / newco_total_if_scheme
    assert math.isclose(
        aggregate_newco_equity_fraction_for_one_original_share,
        1.0 / assumed_new_issue,
        abs_tol=1e-18,
    )
    assert math.isclose(parent_fraction + direct_fraction, 1.0, abs_tol=1e-14)
    return {
        "schema_version": 1,
        "review_id": AUDIT_ID,
        "classification": "HYPOTHETICAL_TWO_LAYER_OWNERSHIP_NOT_SCHEME_APPROVAL_OR_STOCK_RETURN",
        "symbol": "ANANTRAJ",
        "scheme_resultant_company": "Ashok Cloud Private Limited",
        "original_source_provenance": original_source_provenance,
        "original_rights_subscription": {
            "old_parent_owned_newco_ordinary_shares": PRE_SUBSCRIPTION_PARENT_ASHOK_SHARES,
            "completed_additional_newco_shares": ADDITIONAL_SUBSCRIBED_SHARES,
            "face_value_inr_per_share": SHARE_FACE_VALUE,
            "completed_parent_cash_subscription_inr_crore": (
                PARENT_CASH_SUBSCRIPTION_RUPEES / INR_CRORE
            ),
            "parent_newco_shares_after_july21_subscription": newco_parent_shares,
            "source_original_pdf_roles": [
                "july20_subsidiary_rights_proposal",
                "july21_completed_subscription",
            ],
            "underlying_newco_asset_ownership_completed_from_demerger": False,
        },
        "proposed_scheme": {
            "one_newco_share_per_one_eligible_ARL_share": True,
            "parent_existing_newco_shares_not_cancelled": True,
            "parent_subsidiary_status_will_remain_per_issuer_statement": True,
            "source_original_pdf_role": "july21_conditional_demerger_press",
            "effective_nclt_scheme_verified": False,
            "shareholder_approval_verified": False,
            "scheme_record_date_verified": False,
            "eligible_parent_share_count_as_of_record_date_verified": False,
        },
        "historical_share_count_proxy": baseline,
        "illustrative_no_other_newco_share_events_scenario": {
            "assumption": (
                "FUTURE_RECORD_DATE_ELIGIBLE_PARENT_BASIC_SHARES_EQUAL_HISTORICAL_HG005_"
                "FULLY_DILUTED_PROXY_359876930_AND_NEWCO_ONLY_HAS_JULY_PARENT_SHARES_"
                "PLUS_1_FOR_1_DIRECT_ISSUE_ALL_SAME_CLASS"
            ),
            "record_date_parent_eligible_shares_NOT_VERIFIED": assumed_new_issue,
            "newco_parent_retained_shares_IF_NOT_CANCELLED": newco_parent_shares,
            "newco_direct_new_shares_if_1_to_1": assumed_new_issue,
            "total_newco_shares_if_effective": newco_total_if_scheme,
            "hypothetical_parent_retained_newco_equity_fraction": parent_fraction,
            "hypothetical_direct_ARL_shareholder_newco_fraction": direct_fraction,
            "direct_newco_share_per_original_ARL_share": 1.0,
            "parent_lookthrough_newco_share_per_original_ARL_share": (
                parent_indirect_shares_per_parent_share
            ),
            "two_layer_lookthrough_equivalent_newco_shares_per_original_ARL_share": (
                parent_indirect_shares_per_parent_share
                + direct_newco_shares_per_parent_share
            ),
            "two_layer_equity_claim_fraction_per_original_ARL_share": (
                aggregate_newco_equity_fraction_for_one_original_share
            ),
            "combined_fraction_equals_preexisting_pro_rata_fraction_algebra_only": True,
            "newco_voting_rights_classes_and_indirect_control_verified": False,
            "realized_shareholder_distribution_or_value_creation_verified": False,
        },
        "valuation_double_counting_guard": {
            "mechanical_1to1_newco_distribution_itself_does_not_create_new_asset": True,
            "cannot_add_100pct_newco_val_to_unchanged_parent_business_value": True,
            "parent_cross_holding_must_be_removed_or_consistently_attributed": True,
            "parent_retained_interest_and_direct_minorities_must_be_reconciled": True,
            "transferred_net_liabilities_and_operating_cashflows_known": False,
            "cumulative_return_at_ex_date_or_effective_date_known": False,
            "possible_revaluation_from_separate_listing_empirically_verified": False,
            "stock_price_target_or_probability_authorized": False,
        },
        "required_independent_evidence": [
            "FINAL_APPROVED_SCHEME_SCHEDULES_AND_NCLT_EFFECTIVE_DATE",
            "RECORD_DATE_ARL_ELIGIBLE_BASIC_AND_DILUTED_SHARES",
            "ACTUAL_NEWCO_TOTAL_ISSUED_SHARES_AND_VOTING_CLASS",
            "ASSETS_LIABILITIES_AND_CASH_TRANSFERS_BETWEEN_ENTITIES",
            "CARVED_OUT_AUDITED_CLOUD_DATA_CENTER_EBITDA_CAPEX_AND_FCF",
            "CASH_FUNDING_RIGHTS_CROSSHOLDING_ELIMINATIONS_AND_MINORITY_CLAIMS",
            "CUM_AND_EX_OLD_PARENT_SHARE_PRICE_AND_NEWCO_OPEN_AFTER_LISTING",
            "CURRENT_MARKET_VALUATION_COSTS_TAXES_AND_RESTRICTED_FLOAT",
        ],
        "new_company_fair_value_or_distribution_price_calculated": False,
        "stock_expected_returns_calculated": False,
        "transaction_completion_probabilities_published": False,
        "prospective_return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
