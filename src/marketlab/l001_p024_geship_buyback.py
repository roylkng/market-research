"""L001 P024: distinguish legally extinguished GESHIP buybacks from purchases.

Only archived first-party, date/ISIN matched issuer filings qualify. A daily
purchase filing cannot prove a new legal post-September cancellation or a
current share count. No direct alpha, current fleet NAV, or trading advice.
"""

from __future__ import annotations

import copy
import hashlib
import io
import re
from datetime import UTC, datetime
from typing import Any

from pypdf import PdfReader

from marketlab.alpha import AlphaContractError, digest

REPORT_ID = "L001-P024-GESHIP-LEGAL-CANCELLATION-VS-PURCHASE-v1"
ISIN = "INE017A01032"
EVIDENCE = {
    "SEPT_CANCELLATION": {
        "url": "https://greatship.com/upload/investors/buyback_2026/1st_Lot_Buyback_Extinguishment_Certificate.pdf",
        "issuer_document_date": "2026-10-13",
        "pages": 5,
        "required": (
            "October 13, 2026",
            "18,58,941",
            "14,27,67,161",
            "14,09,08,220",
            "IN E017A01032",  # rechecked as contiguous after whitespace removal
            "extinguishment",
        ),
    },
    "OCT19_DAILY": {
        # This issuer URL is a *mutable* daily-report endpoint. It can only
        # qualify while its raw bytes still identify the exact Oct 19 date.
        "url": "https://greatship.com/upload/investors/buyback_2026/dailyreport.pdf",
        "issuer_document_date": "2026-10-19",
        "pages": 2,
        "required": (
            "October 19, 2026",
            "1,94,000",
            "29,01,660",
            "30,95,660",
            "1516.7498",
            "Kotak Securities",
        ),
    },
}
SHARES_PRE_SEPT = 142_767_161
SEPT_CERTIFIED_EXTINGUISHED = 1_858_941
SHARES_POST_SEPT_CERTIFICATE = 140_908_220
OCT19_PURCHASED_CUMULATIVE = 3_095_660
OCT19_DAILY_PURCHASED = 194_000
OCT18_CUMULATIVE = 2_901_660
OCT19_PURCHASE_PRICE_INR = 1516.7498
ORIGINAL_NAV_DATE = "2026-06-30"
NAV_ISSUER_REPORTED_JUNE_2026_INR = 1886.0
DATED_NSE_PRICE_OCT19 = 1519.30
PRIOR_HAIRCUT_THRESHOLD_PCT = 27.74


def _pdf_text(raw: bytes) -> tuple[int, str]:
    if not raw.startswith(b"%PDF") or len(raw) < 100 or len(raw) > 5_000_000:
        raise AlphaContractError("P024 original PDF size/type mismatch")
    try:
        pdf = PdfReader(io.BytesIO(raw), strict=False)
        return len(pdf.pages), " ".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        raise AlphaContractError("P024 original issuer PDF unreadable") from exc


def validate_issuer_document(kind: str, raw: bytes) -> dict[str, Any]:
    spec = EVIDENCE.get(kind)
    if spec is None:
        raise AlphaContractError("P024 unknown first-party document type")
    count, text = _pdf_text(raw)
    if count != spec["pages"]:
        raise AlphaContractError("P024 original issuer PDF page count changed")
    lowered = re.sub(r"\s+", " ", text).casefold()
    compact = re.sub(r"\s+", "", text).casefold()
    for token in spec["required"]:
        if token == "IN E017A01032":
            # The NSDL original ISIN is often split over lines by PDF tables.
            if "ine017a01032" not in compact:
                raise AlphaContractError("P024 original GESHIP ISIN absent")
        elif token.casefold() not in lowered:
            raise AlphaContractError(f"P024 original issuer PDF missing {token}")
    if kind == "SEPT_CANCELLATION" and (
        str(SHARES_PRE_SEPT).replace("142767161", "14,27,67,161") not in lowered
        or SEPT_CERTIFIED_EXTINGUISHED != SHARES_PRE_SEPT - SHARES_POST_SEPT_CERTIFICATE
    ):
        raise AlphaContractError("P024 certified share-capital arithmetic fails")
    if kind == "OCT19_DAILY" and (
        OCT18_CUMULATIVE + OCT19_DAILY_PURCHASED != OCT19_PURCHASED_CUMULATIVE
    ):
        raise AlphaContractError("P024 issuer buyback reported cumulative mismatch")
    return {
        "evidence_kind": kind,
        "issuer_document_date": spec["issuer_document_date"],
        "original_source_url": spec["url"],
        "original_pdf_pages": count,
        "original_pdf_bytes": len(raw),
        "original_pdf_sha256": hashlib.sha256(raw).hexdigest(),
        "issuer_symbol": "GESHIP",
        "issuer_isin": ISIN,
        "original_issuer_document_not_stock_return": True,
        "live_capital_allowed": False,
    }


def make_source_receipt(
    kind: str, raw: bytes, *, retrieved_at_utc: str
) -> dict[str, Any]:
    parsed = validate_issuer_document(kind, raw)
    try:
        timestamp = datetime.fromisoformat(retrieved_at_utc)
    except (TypeError, ValueError) as exc:
        raise AlphaContractError("P024 invalid actual source timestamp") from exc
    if timestamp.tzinfo is None:
        raise AlphaContractError("P024 requires timezone-aware actual capture")
    captured = timestamp.astimezone(UTC)
    if captured.date().isoformat() < parsed["issuer_document_date"]:
        raise AlphaContractError("P024 cannot backdate issuer document capture")
    receipt: dict[str, Any] = {
        **parsed,
        "retrieved_at_utc": captured.isoformat(),
        "source_custody_state": "ORIGINAL_ISSUER_PDF_BYTES_REPLAYABLE",
        "original_raw_path": (
            f"research/l001/originals/geship_buyback/{kind.lower()}/"
            f"{parsed['original_pdf_sha256']}.pdf"
        ),
    }
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def verify_source_receipt(
    kind: str, raw: bytes, receipt: dict[str, Any]
) -> None:
    unsigned = copy.deepcopy(receipt)
    if unsigned.pop("receipt_sha256", None) != digest(unsigned):
        raise AlphaContractError("P024 issuer receipt hash altered")
    expected = make_source_receipt(
        kind, raw, retrieved_at_utc=receipt["retrieved_at_utc"]
    )
    if expected != receipt:
        raise AlphaContractError("P024 source receipt/PDF different")


def build_geship_capital_bridge(
    original_bytes: dict[str, bytes],
    source_receipts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if set(original_bytes) != set(EVIDENCE) or set(source_receipts) != set(EVIDENCE):
        raise AlphaContractError("P024 cannot bridge one-sided issuer evidence")
    for kind in EVIDENCE:
        verify_source_receipt(kind, original_bytes[kind], source_receipts[kind])
    # October 2026 purchased lots after September certificate. These purchases
    # are NOT proof of later legal share extinguishment, and original month-end
    # balances cannot be silently carried forward to October 19.
    post_sept_purchases = (
        OCT19_PURCHASED_CUMULATIVE - SEPT_CERTIFIED_EXTINGUISHED
    )
    if post_sept_purchases < 0:
        raise AlphaContractError("P024 impossible cumulative repurchases")
    illustrative_if_all_cancelled = (
        SHARES_POST_SEPT_CERTIFICATE - post_sept_purchases
    )
    output: dict[str, Any] = {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "issuer_symbol": "GESHIP",
        "issuer_isin": ISIN,
        "basis_date": "2026-10-19",
        "issuer_published_declaration_date": "2026-10-13",
        "issuer_source_custody": source_receipts,
        "certified_paidup_shares_before_september_buyback": SHARES_PRE_SEPT,
        "certified_september_shares_extinguished": SEPT_CERTIFIED_EXTINGUISHED,
        "certified_post_september_paidup_shares": SHARES_POST_SEPT_CERTIFICATE,
        "oct19_issuer_report_daily_shares_purchased": OCT19_DAILY_PURCHASED,
        "oct19_issuer_report_prior_cumulative_purchased": OCT18_CUMULATIVE,
        "oct19_issuer_report_total_cumulative_purchased": OCT19_PURCHASED_CUMULATIVE,
        "oct19_daily_avg_acquisition_price_inr_not_market_close": (
            OCT19_PURCHASE_PRICE_INR
        ),
        "purchased_since_september_certificate_not_in_this_certificate": (
            post_sept_purchases
        ),
        "later_legal_cancellation_since_september_verified": False,
        "oct19_current_paidup_or_fully_diluted_shares_verified": False,
        "oct19_current_paidup_shares": None,
        "only_under_assumption_no_issuance_or_other_cancellation": {
            "if_none_of_later_repurchased_shares_legal_extinguished": (
                SHARES_POST_SEPT_CERTIFICATE
            ),
            "if_all_later_repurchased_shares_legal_extinguished": (
                illustrative_if_all_cancelled
            ),
            "conditional_denominator_range_is_current_shares_proof": False,
        },
        "hypothetical_later_shares_if_cancelled_as_pct_of_post_sep": round(
            100 * post_sept_purchases / SHARES_POST_SEPT_CERTIFICATE, 4
        ),
        "old_june30_issuer_nav_per_share_inr_unreconciled": (
            NAV_ISSUER_REPORTED_JUNE_2026_INR
        ),
        "oct19_original_nse_eq_close_inr_not_an_entry_fill": (
            DATED_NSE_PRICE_OCT19
        ),
        "oct19_headline_discount_to_stale_june_nav_percent": round(
            100 * (1 - DATED_NSE_PRICE_OCT19 / NAV_ISSUER_REPORTED_JUNE_2026_INR),
            4,
        ),
        "historical_noncash_nav_haircut_erasing_price_gap_percent": (
            PRIOR_HAIRCUT_THRESHOLD_PCT
        ),
        "nav_not_marked_to_current_fleet_or_offshore_cycle": True,
        "issuer_june30_nav_not_revalued_from_buyback_only": True,
        "cash_paid_for_buyback_must_reduce_nav": True,
        "post_sep_certified_shares_not_actual_oct19_legal_count": True,
        "buyback_maximum_issuer_price_not_floor_for_investors": True,
        "company_valuation_or_1y_3y_expected_return": None,
        "investable_margin_of_safety_established": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["report_sha256"] = digest(output)
    return output


def validate_bridge(
    result: dict[str, Any], *,
    originals: dict[str, bytes],
    receipts: dict[str, dict],
) -> None:
    unsigned = copy.deepcopy(result)
    sig = unsigned.pop("report_sha256", None)
    if sig != digest(unsigned):
        raise AlphaContractError("P024 published buyback research SHA modified")
    if result != build_geship_capital_bridge(originals, receipts):
        raise AlphaContractError("P024 original source replay differs from report")
