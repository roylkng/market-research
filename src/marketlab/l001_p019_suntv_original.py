"""Verify and optionally retain Sun TV FY26 original issuer annual-report proof.

The publisher PDF's complete SHA is the source identity. Retaining an excerpt
does NOT prove a full original was archived. Calendar/source dates are real
retrieval times, never backdated to historical forecast dates.
"""

from __future__ import annotations

import hashlib
import io
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p019_suntv_rights import ANNUAL_REPORT_URL

PDF_PAGE_INDICES = (77, 78, 160, 184, 228)
PAGE_REQUIRED_TEXT = {
    77: (
        "standalone statement of cash flows",
        "1736.10",
        "938.51",
    ),
    78: (
        "payment towards investment in subsidiary",
        "1190.88",
    ),
    160: (
        "consolidated statement of cash flows",
        "1801.64",
        "83.91",
        "2130.31",
    ),
    184: (
        "intangible assets",
        "franchise rights",
        "1190.88",
        "57.39",
        "1248.27",
    ),
    228: (
        "sunrisers leeds",
        "100.5",
        "1184.99",
        "asset acquisition",
    ),
}


def _normal(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def verify_annual_source_pages(page_texts: dict[int, str]) -> dict[str, Any]:
    if set(page_texts) != set(PDF_PAGE_INDICES):
        raise AlphaContractError("P019 incomplete issuer PDF page evidence")
    result = []
    for index in PDF_PAGE_INDICES:
        original = page_texts[index]
        if not isinstance(original, str) or len(original) < 90:
            raise AlphaContractError(f"P019 original page {index} missing text")
        clean = _normal(original)
        for phrase in PAGE_REQUIRED_TEXT[index]:
            if _normal(phrase) not in clean:
                raise AlphaContractError(
                    f"P019 original page {index} missing source term: {phrase}"
                )
        result.append({
            "zero_based_pdf_page": index,
            "required_source_terms_verified": list(PAGE_REQUIRED_TEXT[index]),
            "extracted_page_text_sha256": hashlib.sha256(
                original.encode("utf-8")
            ).hexdigest(),
        })
    return {
        "page_count": len(result),
        "source_page_checks": result,
        "full_original_cash_receipts_independently_verified": False,
        "conditional_owner_cash_proxy_is_verified_owner_cash": False,
    }


def archive_pdf_receipt(
    original_pdf: bytes,
    *,
    captured_at_utc: datetime,
    root: Path,
) -> dict[str, Any]:
    from pypdf import PdfReader, PdfWriter

    if (
        captured_at_utc.tzinfo is None
        or not original_pdf.startswith(b"%PDF")
        or len(original_pdf) < 30_000
        or len(original_pdf) > 35_000_000
    ):
        raise AlphaContractError("P019 invalid real annual report or capture clock")
    reader = PdfReader(io.BytesIO(original_pdf), strict=True)
    if len(reader.pages) < 229:
        raise AlphaContractError("P019 original annual report missing pages")
    pages = {
        i: reader.pages[i].extract_text()
        for i in PDF_PAGE_INDICES
    }
    inspection = verify_annual_source_pages(pages)
    rootdir = root / "research/l001/originals/suntv_fy26"
    rootdir.mkdir(parents=True, exist_ok=True)
    full_sha = hashlib.sha256(original_pdf).hexdigest()
    raw_retained = len(original_pdf) <= 8_000_000
    original_path = None
    if raw_retained:
        path = rootdir / f"suntv-fy26-full-{full_sha}.pdf"
        if path.exists() and path.read_bytes() != original_pdf:
            raise AlphaContractError("P019 original PDF SHA file collision")
        path.write_bytes(original_pdf)
        original_path = str(path.relative_to(root))
    else:
        # Store actual pages from the retrieved original, with a full-PDF hash
        # receipt and truthful flag that original *full* bytes aren't archived.
        writer = PdfWriter()
        for i in PDF_PAGE_INDICES:
            writer.add_page(reader.pages[i])
        writer.add_metadata({
            "/Title": "Sun TV FY26 selected original annual-report pages",
            "/Subject": (
                "Source excerpts, not a replacement for full issuer PDF. "
                f"Original full PDF SHA-256 {full_sha}"
            ),
        })
        buf = io.BytesIO()
        writer.write(buf)
        excerpt = buf.getvalue()
        excerpt_sha = hashlib.sha256(excerpt).hexdigest()
        path = rootdir / f"suntv-fy26-pages-{excerpt_sha}.pdf"
        if path.exists() and path.read_bytes() != excerpt:
            raise AlphaContractError("P019 original PDF excerpt collision")
        path.write_bytes(excerpt)
        original_path = str(path.relative_to(root))
    report = {
        "schema_version": 1,
        "receipt_id": "L001-P019-SUNTV-ISSUER-ANNUAL-FY26-RECEIPT-v1",
        "full_original_issuer_pdf_url": ANNUAL_REPORT_URL,
        "actual_retrieval_utc": captured_at_utc.astimezone(UTC).isoformat(),
        "full_original_pdf_byte_count": len(original_pdf),
        "full_original_pdf_sha256": full_sha,
        "full_original_pdf_archived": raw_retained,
        "stored_pdf_path": original_path,
        "stored_pdf_contains_original_full_document": raw_retained,
        "original_pages_source_verified": inspection,
        "franchise_rights_cashline_bank_allocation_proven": False,
        "economic_owner_cash_estimate_accepted": False,
        "prospective_oct15_alpha_approved": False,
        "live_capital_allowed": False,
    }
    report["receipt_sha256"] = digest(report)
    return report
