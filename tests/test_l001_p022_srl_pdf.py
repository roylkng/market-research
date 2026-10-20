"""Original UK scanned PDF custody never creates fictitious verified cashflows."""

from __future__ import annotations

import copy
import hashlib
import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pypdf import PdfWriter

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p022_srl_pdf import (
    PDF_DIR,
    SOURCE_URL,
    capture_pdf,
    validate_original_pdf,
)

UTC_INSTANT = datetime(2026, 10, 20, 15, 45, tzinfo=UTC)


def _fixture(*, pages: int = 24) -> bytes:
    w = PdfWriter()
    for i in range(pages):
        w.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    w.write(output)
    return output.getvalue()


def test_scanned_original_pdf_custody_records_pages_not_fake_ocr():
    raw = _fixture()
    evidence = validate_original_pdf(raw)
    assert evidence["pdf_pages"] == 24
    assert evidence["manual_visual_review_page_indices"] == [
        5, 12, 14, 15, 16, 18
    ]
    assert evidence["manual_source_facts_machine_ocr_verified"] is False
    assert evidence["archival_proves_reported_cash_rows_independently"] is False
    assert evidence["full_original_pdf_sha256"] == hashlib.sha256(raw).hexdigest()


def test_true_original_receipt_is_content_addressed(tmp_path: Path):
    raw = _fixture()
    receipt = capture_pdf(
        fetch=lambda url: (200, raw),
        root=tmp_path,
        actual_capture_utc=UTC_INSTANT,
    )
    assert receipt["source_url"] == SOURCE_URL
    assert receipt["source_state"] == "ARCHIVED_FULL_ORIGINAL_UNAUDITED_OCR"
    assert receipt["original_bytes_archived"] is True
    filename = tmp_path / receipt["original_full_pdf_path"]
    assert filename.is_file()
    assert filename.read_bytes() == raw
    assert receipt["receipt_sha256"] == digest({
        k: v for k, v in receipt.items() if k != "receipt_sha256"
    })
    assert receipt["parent_owner_cash_verified"] is False
    assert receipt["live_capital_allowed"] is False


def test_missing_or_invalid_pdf_is_never_accepted(tmp_path: Path):
    missing = capture_pdf(
        fetch=lambda url: (403, None),
        root=tmp_path,
        actual_capture_utc=UTC_INSTANT,
    )
    assert missing["source_state"] == "BLOCKED_ISSUER_SOURCE_UNAVAILABLE"
    assert missing["original_bytes_archived"] is False
    assert missing["original_full_pdf_sha256"] is None

    wrong = capture_pdf(
        fetch=lambda url: (200, _fixture(pages=23)),
        root=tmp_path,
        actual_capture_utc=UTC_INSTANT,
    )
    assert wrong["source_state"] == "BLOCKED_UNVERIFIED_OR_INVALID_PDF"
    assert wrong["original_full_pdf_path"] is None
    assert wrong["source_inspection"] if "source_inspection" in wrong else True
    assert wrong["original_full_pdf_sha256"] is None
    assert wrong["live_capital_allowed"] is False


def test_original_pdf_immutability_and_clock_controls(tmp_path: Path):
    raw = _fixture()
    first = capture_pdf(
        fetch=lambda url: (200, raw),
        root=tmp_path,
        actual_capture_utc=UTC_INSTANT,
    )
    same = capture_pdf(
        fetch=lambda url: (200, raw),
        root=tmp_path,
        actual_capture_utc=UTC_INSTANT,
    )
    assert same["original_full_pdf_sha256"] == first["original_full_pdf_sha256"]
    stored = tmp_path / first["original_full_pdf_path"]
    stored.write_bytes(b"tampered")
    with pytest.raises(AlphaContractError, match="hash path collision"):
        capture_pdf(
            fetch=lambda url: (200, raw),
            root=tmp_path,
            actual_capture_utc=UTC_INSTANT,
        )
    with pytest.raises(AlphaContractError, match="aware UTC"):
        capture_pdf(
            fetch=lambda url: (200, raw),
            root=tmp_path,
            actual_capture_utc=datetime(2026, 10, 20),
        )


def test_receipt_failure_preserves_no_shareholder_return_claim(tmp_path: Path):
    def unavailable(_url: str):
        raise ConnectionError("synthetic transport failure")

    out = capture_pdf(
        fetch=unavailable,
        root=tmp_path,
        actual_capture_utc=UTC_INSTANT,
    )
    assert out["source_state"] == "BLOCKED_ISSUER_SOURCE_UNAVAILABLE"
    assert out["parent_owner_cash_verified"] is False
    assert out["prospective_oct15_source_signal"] is False
    assert out["live_capital_allowed"] is False
