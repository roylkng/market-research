"""L001 P026: archive original Zuari FY26 annual and locate secured-loan pages.

Original 2026-08-24 annual report is pre-existing disclosure, but its *actual*
model-source capture must be timestamped now. Loan notes are dated 31 Mar 2026,
so no September redemption or current lien status is inferred from the report.
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

ID = "L001-P026-ZUARI-FY26-ORIGINAL-ANNUAL-LOAN-COLLATERAL-v1"
URL = "https://www.zuariindustries.in/storage/uploads/images/1787553470.pdf"
ISSUER = "ZUARI INDUSTRIES LIMITED"
SYMBOL = "ZUARIIND"
ISIN = "INE217A01012"
FILING_DATE = "2026-08-24"
BALANCE_DATE = "2026-03-31"
SECURITY_NOTES = {
    "ICICI_1200000_CFCL_SHARES": ("icici bank", "12,00,000", "chambal"),
    "CANARA_800000_CFCL_SHARES": ("canara bank", "8,00,000", "chambal"),
    "BAJAJ_FINANCE_3974979_CFCL_SHARES": (
        "bajaj finance", "3,974,979", "chambal"
    ),
    "SEPT30_NCD_4818333_CFCL_SHARES": (
        "20,000.00", "4,818,333", "chambal"
    ),
}


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).casefold()


def _page_texts(raw: bytes) -> list[str]:
    if (
        not isinstance(raw, bytes)
        or not raw.startswith(b"%PDF")
        or not 50_000 <= len(raw) <= 70_000_000
    ):
        raise AlphaContractError("P026 original issuer annual PDF header/size invalid")
    try:
        pdf = PdfReader(io.BytesIO(raw), strict=False)
        if not 100 <= len(pdf.pages) <= 650:
            raise AlphaContractError("P026 issuer annual report page count invalid")
        return [page.extract_text(extraction_mode="plain") or "" for page in pdf.pages]
    except AlphaContractError:
        raise
    except Exception as exc:
        raise AlphaContractError("P026 original issuer annual PDF unreadable") from exc


def _validate_original_texts(texts: list[str]) -> dict[str, Any]:
    if not 100 <= len(texts) <= 650:
        raise AlphaContractError("P026 Zuari FY26 annual page range invalid")
    # A stand-alone signed annual report need not include its *exchange
    # cover-letter date* on the cover. Validate the actual issuer/fiscal year
    # that are printed in the report itself. Source publication is an
    # independent, earlier-dated exchange/issuer provenance assertion.
    front = _normalize(" ".join(texts[:30])).replace("–", "-").replace("—", "-")
    issuer_ok = "zuari industries" in front
    year_ok = (
        "2025-26" in front
        and any(tag in front for tag in (
            "annual report", "financial statements", "financial year"
        ))
    )
    if not issuer_ok or not year_ok:
        raise AlphaContractError(
            "P026 wrong issuer, annual period or source edition "
            f"(issuer={issuer_ok}, fiscal_year={year_ok})"
        )
    matches: dict[str, dict[str, Any]] = {}
    pages = [_normalize(s) for s in texts]
    for note_id, tokens in SECURITY_NOTES.items():
        candidates = [
            i for i, p in enumerate(pages)
            if all(token in p for token in tokens)
        ]
        # Co-location on one annual note page prevents cross-document
        # concatenation from manufacturing pledged loan support.
        if candidates:
            i = min(candidates)
            matches[note_id] = {
                "status": "ISSUER_ANNUAL_FY26_SAME_PAGE_TEXT_MATCH",
                "pdf_page_zero_based": i,
                "page_text_sha256": hashlib.sha256(
                    texts[i].encode("utf-8")
                ).hexdigest(),
                "balance_sheet_reference_date": BALANCE_DATE,
                "has_current_2026_10_21_lien_or_redemption_proof": False,
                "independently_distributable_stake_value_verified": False,
            }
        else:
            matches[note_id] = {
                "status": "NOT_FULLY_RECONCILED_IN_EXTRACTED_PDF_TEXT",
                "pdf_page_zero_based": None,
                "page_text_sha256": None,
                "balance_sheet_reference_date": BALANCE_DATE,
                "has_current_2026_10_21_lien_or_redemption_proof": False,
                "independently_distributable_stake_value_verified": False,
            }
    return {
        "page_count": len(texts),
        "original_issuer_and_fy26_detected": True,
        "debt_lien_page_evidence": matches,
        "matched_independent_note_count": sum(
            row["status"] == "ISSUER_ANNUAL_FY26_SAME_PAGE_TEXT_MATCH"
            for row in matches.values()
        ),
        "new_current_shareholder_NAV_estimated": False,
        "september_2026_debenture_redemption_verified": False,
        "pledged_stake_units_summable_without_overlap_audit": False,
    }


def validated_receipt(raw: bytes, *, observed_utc: str) -> dict[str, Any]:
    try:
        t = datetime.fromisoformat(observed_utc)
    except ValueError as exc:
        raise AlphaContractError("P026 invalid annual source retrieval time") from exc
    if t.tzinfo is None or t.astimezone(UTC).date().isoformat() < FILING_DATE:
        raise AlphaContractError("P026 source retrieval must be later than publication")
    pages = _page_texts(raw)
    evidence = _validate_original_texts(pages)
    sha = hashlib.sha256(raw).hexdigest()
    report = {
        "schema_version": 1,
        "receipt_id": ID,
        "issuer_symbol": SYMBOL,
        "issuer_isin": ISIN,
        "original_issuer_pdf_url": URL,
        "actual_retrieved_at_utc": t.astimezone(UTC).isoformat(),
        "official_issuer_document_date": FILING_DATE,
        "balance_sheet_facts_as_of": BALANCE_DATE,
        "original_raw_pdf_sha256": sha,
        "original_raw_pdf_bytes": len(raw),
        "original_raw_path": (
            f"research/l001/originals/zuari_fy26_annual/sha256/{sha}.pdf"
        ),
        "source_evidence": evidence,
        "original_issuer_document_not_current_loan_clearance": True,
        "financial_institution_security_may_limit_free_sale": True,
        "current_2026_10_share_pledges_verified": False,
        "source_not_a_2026_10_15_prospective_stock_selection_signal": True,
        "company_attributable_fair_value": None,
        "live_capital_allowed": False,
    }
    report["receipt_sha256"] = digest(report)
    return report


def verify_receipt(raw: bytes, receipt: dict[str, Any]) -> None:
    unsigned = copy.deepcopy(receipt)
    saved = unsigned.pop("receipt_sha256", None)
    if saved != digest(unsigned):
        raise AlphaContractError("P026 annual issuer receipt hash changed")
    replay = validated_receipt(
        raw, observed_utc=receipt["actual_retrieved_at_utc"]
    )
    if replay != receipt:
        raise AlphaContractError("P026 annual issuer original bytes/notes differ")
