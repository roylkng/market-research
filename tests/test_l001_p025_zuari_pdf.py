"""Zuari source custody guards: mock PDFs are never misrepresented as NSE originals."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p025_zuari_pdf import (
    PDF_PAGE_COUNT,
    RECEIPT_ID,
    _pages,
    validated_original_receipt,
    verify_original_receipt,
)
from scripts import archive_l001_p025_zuari_pdf as archive

RAW = b"%PDF-1.7\n" + b"TEST_ONLY_NOT_REAL_ISSUER_PDF\n" * 300
STAMP = "2026-10-21T15:30:12+00:00"


def _synthetic_page_texts() -> list[str]:
    p = ["test only fixture"] * PDF_PAGE_COUNT
    p[0] = "ZUARI INDUSTRIES LIMITED 14 August 2026 NSE Symbol: ZUARIIND"
    p[19] = "Strategic Investments 4,223 3,681 Chambal Fertilisers"
    p[24] = "Profit & Loss Statement 61.54 34.37 (0.57) 519.69"
    p[25] = "Segment Information Total Segment EBITDA 8.05 finance 61.54 " \
            "Net Unallocable 13.74 (39.75)"
    return p


def _patch_page_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "marketlab.l001_p025_zuari_pdf._pages",
        lambda raw: _synthetic_page_texts(),
    )


def test_original_pdf_validator_rejects_blank_or_fake_pdf_header():
    with pytest.raises(AlphaContractError, match="header/size"):
        _pages(b"not a PDF")
    with pytest.raises(AlphaContractError, match="header/size"):
        _pages(b"%PDF-tiny")


def test_original_source_pages_validate_number_date_and_identity(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_page_extraction(monkeypatch)
    data = validated_original_receipt(RAW, retrieved_at_utc=STAMP)
    assert data["receipt_id"] == RECEIPT_ID
    assert data["issuer"] == "ZUARIIND"
    assert data["issuer_isin"] == "INE217A01012"
    assert data["pdf_page_count"] == 30
    assert data["raw_pdf_size_bytes"] == len(RAW)
    assert data["raw_pdf_sha256"] == hashlib.sha256(RAW).hexdigest()
    assert set(data["matched_page_text_sha256"]) == {"0", "19", "24", "25"}
    assert data["pdf_original_source_archived"] is True
    assert data["company_expected_total_return_proven"] is False
    assert data["live_capital_allowed"] is False
    verify_original_receipt(data, RAW)


def test_issuer_numbers_must_match_on_their_original_page(
    monkeypatch: pytest.MonkeyPatch,
):
    text = _synthetic_page_texts()
    text[25] = text[25].replace("8.05", "88.05")
    monkeypatch.setattr(
        "marketlab.l001_p025_zuari_pdf._pages", lambda raw: text,
    )
    with pytest.raises(AlphaContractError, match="page 25 missing: 8.05"):
        validated_original_receipt(RAW, retrieved_at_utc=STAMP)
    text = _synthetic_page_texts()
    text[0] = "NOT ZUARI"
    monkeypatch.setattr(
        "marketlab.l001_p025_zuari_pdf._pages", lambda raw: text,
    )
    with pytest.raises(AlphaContractError, match="page 0 missing"):
        validated_original_receipt(RAW, retrieved_at_utc=STAMP)


def test_source_timestamp_and_receipt_mutation_blocked(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_page_extraction(monkeypatch)
    with pytest.raises(AlphaContractError, match="timezone-aware"):
        validated_original_receipt(
            RAW, retrieved_at_utc="2026-10-21T15:30:12"
        )
    with pytest.raises(AlphaContractError, match="before publication"):
        validated_original_receipt(
            RAW, retrieved_at_utc="2026-08-13T19:00:00Z"
        )
    data = validated_original_receipt(RAW, retrieved_at_utc=STAMP)
    compromised = copy.deepcopy(data)
    compromised["source_document_date"] = "2026-10-21"
    with pytest.raises(AlphaContractError, match="receipt hash altered"):
        verify_original_receipt(compromised, RAW)


def test_blocked_retrieval_is_append_only_and_not_silent_clearance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
):
    monkeypatch.setattr(archive, "_fetch", lambda: (403, None, None))
    result = archive._run(tmp_path, run_id="synthetic-123")
    assert result["status"] == "BLOCKED_ORIGINAL_ISSUER_PDF_HTTP_OR_NETWORK"
    assert result["original_pdf_archive_created"] is False
    assert result["original_pdf_raw_sha256"] is None
    assert result["live_capital_allowed"] is False
    file = (
        tmp_path / "research/l001/originals/zuari_q1/"
        "attempts/synthetic-123.json"
    )
    observed = json.loads(file.read_text(encoding="utf-8"))
    sig = observed.pop("attempt_sha256")
    assert sig == digest(observed)
    assert not list(
        (tmp_path / "research/l001/originals/zuari_q1").glob("sha256/*.pdf")
    )
    with pytest.raises(AlphaContractError, match="source collision"):
        archive._run(tmp_path, run_id="synthetic-123")


def test_synthetic_archive_is_content_addressed_and_replayable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
):
    _patch_page_extraction(monkeypatch)
    monkeypatch.setattr(archive, "_fetch", lambda: (200, RAW, None))
    result = archive._run(tmp_path, run_id="synthetic-456")
    assert result["status"] == "ORIGINAL_ISSUER_PDF_BYTES_ARCHIVED"
    assert result["original_pdf_archive_created"] is True
    sha = hashlib.sha256(RAW).hexdigest()
    assert result["original_pdf_raw_sha256"] == sha
    assert (
        tmp_path / f"research/l001/originals/zuari_q1/sha256/{sha}.pdf"
    ).read_bytes() == RAW
    ver = archive._check(tmp_path)
    assert ver["status"] == "ORIGINAL_ZUARI_ISSUER_PDF_REPLAYED"
    assert ver["sha256"] == [sha]
    assert ver["live_capital_allowed"] is False
