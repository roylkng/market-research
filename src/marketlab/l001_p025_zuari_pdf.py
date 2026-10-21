"""Original first-party Zuari Q1FY27 30-page PDF custody, no valuation claim.

A source URL that resolves today is not proof of what an investor saw earlier.
Original PDF bytes, actual retrieval UTC and page-specific issuer/P&L values
must be independently checked before archiving. Changed/blocked pages fail closed.
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
from marketlab.l001_p025_zuari_falsification import SOURCE

RECEIPT_ID = "L001-P025-ZUARI-ORIGINAL-Q1-ISSUER-PDF-CUSTODY-v1"
REQUIRED_PAGE_LINES = {
    0: ("ZUARI INDUSTRIES LIMITED", "14 August 2026", "ZUARIIND"),
    19: ("Strategic Investments", "4,223", "3,681", "Chambal"),
    24: ("Profit & Loss Statement", "61.54", "34.37", "0.57", "519.69"),
    25: ("Segment Information", "8.05", "61.54", "13.74", "39.75"),
}
PDF_PAGE_COUNT = 30
URL = SOURCE["original_issuer_url"]


def _pages(raw: bytes) -> list[str]:
    if (
        not isinstance(raw, bytes)
        or not raw.startswith(b"%PDF")
        or not 1_000 <= len(raw) <= 20_000_000
    ):
        raise AlphaContractError("P025 original issuer file PDF header/size invalid")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        return [page.extract_text(extraction_mode="plain") or "" for page in reader.pages]
    except Exception as exc:
        raise AlphaContractError("P025 original 30-page issuer PDF unreadable") from exc


def _content_check(raw: bytes) -> dict[str, Any]:
    texts = _pages(raw)
    if len(texts) != PDF_PAGE_COUNT:
        raise AlphaContractError("P025 original Zuari PDF page count drift")
    proof = {}
    for index, tokens in REQUIRED_PAGE_LINES.items():
        text = re.sub(r"\s+", " ", texts[index]).casefold()
        for token in tokens:
            term = token.casefold()
            if term[0].isdigit() and term[-1].isdigit():
                # "8.05" must not match "88.05" or "8.050".
                matched = re.search(
                    rf"(?<![0-9.]){re.escape(term)}(?![0-9.])", text
                ) is not None
            else:
                matched = term in text
            if not matched:
                raise AlphaContractError(
                    f"P025 original issuer PDF page {index} missing: {token}"
                )
        proof[str(index)] = hashlib.sha256(texts[index].encode("utf-8")).hexdigest()
    return {
        "pdf_page_count": len(texts),
        "matched_page_text_sha256": proof,
        "numeric_validation_page_scoped_not_new_valuation": True,
    }


def validated_original_receipt(
    raw: bytes, *, retrieved_at_utc: str
) -> dict[str, Any]:
    try:
        parsed = datetime.fromisoformat(str(retrieved_at_utc))
    except ValueError as exc:
        raise AlphaContractError("P025 PDF retrieval time invalid") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError("P025 PDF retrieval must be timezone-aware")
    captured = parsed.astimezone(UTC)
    if captured.date().isoformat() < SOURCE["source_publication_date"]:
        raise AlphaContractError("P025 issuer document cannot be retrieved before publication")
    content = _content_check(raw)
    sha = hashlib.sha256(raw).hexdigest()
    receipt = {
        "schema_version": 1,
        "receipt_id": RECEIPT_ID,
        "issuer": "ZUARIIND",
        "issuer_isin": "INE217A01012",
        "source_document_date": SOURCE["source_publication_date"],
        "source_url": URL,
        "actual_retrieved_at_utc": captured.isoformat(),
        "raw_pdf_size_bytes": len(raw),
        "raw_pdf_sha256": sha,
        "original_file_path": (
            f"research/l001/originals/zuari_q1/sha256/{sha}.pdf"
        ),
        **content,
        "pdf_original_source_archived": True,
        "financial_stake_haircut_is_investable_fair_value": False,
        "market_announcement_first_seen_in_2026_08": False,
        "company_expected_total_return_proven": False,
        "live_capital_allowed": False,
    }
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def verify_original_receipt(receipt: dict[str, Any], raw: bytes) -> None:
    unsigned = copy.deepcopy(receipt)
    stored = unsigned.pop("receipt_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("P025 original issuer PDF receipt hash altered")
    expected = validated_original_receipt(
        raw, retrieved_at_utc=receipt["actual_retrieved_at_utc"]
    )
    if expected != receipt:
        raise AlphaContractError("P025 original issuer PDF bytes no longer match receipt")
