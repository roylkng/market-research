"""Retain real SunRisers Leeds original UK scanned statutory report or fail closed.

No OCR. PDF identity/byte custody is independent of a human's visual audit.
Only the actual issuer original may supply facts, never a synthesized scan.
"""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from pypdf import PdfReader

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p021_srl_uk import SOURCE_URL

PAGE_COUNT = 24
PAGES_VISUALLY_AUDITED = (5, 12, 14, 15, 16, 18)
MAX_RETAINED_BYTES = 12_000_000
PDF_DIR = Path("research/l001/originals/srl_uk_fy26")


def validate_original_pdf(raw: bytes) -> dict[str, Any]:
    if (
        not isinstance(raw, bytes)
        or not raw.startswith(b"%PDF-")
        or len(raw) < 2000
        or len(raw) > 40_000_000
    ):
        raise AlphaContractError("L001 P022 original scanned PDF invalid size or header")
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if len(reader.pages) != PAGE_COUNT:
        raise AlphaContractError("L001 P022 scanned statutory PDF page count changed")
    for i in PAGES_VISUALLY_AUDITED:
        page = reader.pages[i]
        if (
            float(page.mediabox.width) < 100
            or float(page.mediabox.height) < 100
        ):
            raise AlphaContractError("L001 P022 original UK statement page absent")
    return {
        "pdf_pages": PAGE_COUNT,
        "manual_visual_review_page_indices": list(PAGES_VISUALLY_AUDITED),
        "manual_source_facts_machine_ocr_verified": False,
        "archival_proves_reported_cash_rows_independently": False,
        "full_original_pdf_byte_count": len(raw),
        "full_original_pdf_sha256": hashlib.sha256(raw).hexdigest(),
    }


def capture_pdf(
    *,
    fetch: Callable[[str], tuple[int | None, bytes | None]],
    root: Path,
    actual_capture_utc: datetime,
) -> dict[str, Any]:
    if actual_capture_utc.tzinfo is None:
        raise AlphaContractError("L001 P022 original-source capture needs aware UTC")
    instant = actual_capture_utc.astimezone(UTC).isoformat()
    try:
        status, raw = fetch(SOURCE_URL)
    except Exception as exc:
        status, raw = None, None
        failure = type(exc).__name__
    else:
        failure = None
    report: dict[str, Any] = {
        "schema_version": 1,
        "receipt_id": "L001-P022-UK-SRL-ORIGINAL-PDF-RECEIPT-v1",
        "source_url": SOURCE_URL,
        "actual_capture_utc": instant,
        "http_status": status,
        "error_class": failure,
        "original_full_pdf_path": None,
        "original_bytes_archived": False,
        "original_full_pdf_sha256": None,
        "original_source_visual_row_replay_machine_verified": False,
        "parent_owner_cash_verified": False,
        "prospective_oct15_source_signal": False,
        "live_capital_allowed": False,
    }
    if status == 200 and isinstance(raw, bytes):
        try:
            inspection = validate_original_pdf(raw)
        except Exception as exc:
            report.update({
                "source_state": "BLOCKED_UNVERIFIED_OR_INVALID_PDF",
                "error_class": type(exc).__name__,
                "received_raw_sha256_for_audit_not_accepted": hashlib.sha256(raw).hexdigest(),
            })
        else:
            report["source_inspection"] = inspection
            sha = inspection["full_original_pdf_sha256"]
            report["original_full_pdf_sha256"] = sha
            if len(raw) <= MAX_RETAINED_BYTES:
                target = root / PDF_DIR / f"srl-uk-fy26-original-{sha}.pdf"
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and target.read_bytes() != raw:
                    raise AlphaContractError("L001 P022 source PDF hash path collision")
                target.write_bytes(raw)
                report["original_full_pdf_path"] = str(target.relative_to(root))
                report["original_bytes_archived"] = True
                report["source_state"] = "ARCHIVED_FULL_ORIGINAL_UNAUDITED_OCR"
            else:
                report["source_state"] = "BLOCKED_TOO_LARGE_FOR_FULL_SOURCE_CUSTODY"
    else:
        report["source_state"] = "BLOCKED_ISSUER_SOURCE_UNAVAILABLE"
    report["receipt_sha256"] = digest(report)
    return report
