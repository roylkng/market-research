from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.hg007_original_pages import (
    CASE_ID,
    EXPECTED_SHA,
    ORIGINAL_PATH,
    PILOT_PATH,
    RECEIPT_PATH,
    build_original_pdf_page_packet,
    validate_original_pdf_page_packet,
)


def test_exact_original_bytes_and_previous_ss002_document_id() -> None:
    payload = build_original_pdf_page_packet(Path("."))
    validate_original_pdf_page_packet(payload)
    assert payload["document_review_id"] == CASE_ID
    assert payload["original_pdf_sha256"] == EXPECTED_SHA
    assert payload["original_pdf_byte_count"] == 354999
    assert payload["page_count"] == len(payload["pages"])
    assert all(item["source_document_sha256"] == EXPECTED_SHA for item in payload["pages"])
    assert all(item["page_visual_reviewed"] is False for item in payload["pages"])
    assert payload["ss002_pilot_semantic_review_pending"] is True
    assert payload["original_semantic_audit_complete"] is False
    assert payload["live_capital_allowed"] is False
    prior = json.loads(PILOT_PATH.read_text(encoding="utf-8"))
    original = next(
        row for row in prior["document_rows"]
        if row["symbol"] == "INOXGREEN"
    )
    assert original["document_id"] == payload["original_pdf_sha256"]
    assert original["semantic_audit_status"] == "PENDING_INDEPENDENT_SOURCE_REVIEW"
    assert "550" in "\n".join(item["extracted_text"] for item in payload["pages"])


def test_original_page_text_identity_provenance_is_immutable() -> None:
    payload = build_original_pdf_page_packet(Path("."))
    payload["pages"][0]["extracted_text"] += "FAKE PRICE TARGET"
    with pytest.raises(ValueError, match="SHA/page locator"):
        validate_original_pdf_page_packet(payload)


def test_exact_pdf_sha_tampering_is_rejected(tmp_path: Path) -> None:
    for path in (ORIGINAL_PATH, RECEIPT_PATH, PILOT_PATH):
        dest = tmp_path / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
    pdf = tmp_path / ORIGINAL_PATH
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == EXPECTED_SHA
    pdf.write_bytes(pdf.read_bytes() + b"altered")
    with pytest.raises(ValueError, match="original SHA"):
        build_original_pdf_page_packet(tmp_path)


def test_semantic_promotion_not_derived_from_structural_text() -> None:
    packet = build_original_pdf_page_packet(Path("."))
    for bad_flag in (
        "page_visual_review_complete",
        "original_semantic_audit_complete",
        "transfer_completed_verified",
        "funding_term_classes_verified",
        "normalized_ebitda_verified",
        "expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        copied = dict(packet)
        copied[bad_flag] = True
        with pytest.raises(ValueError, match="cannot authorize"):
            validate_original_pdf_page_packet(copied)


def test_original_pdf_cli_reproducibility(tmp_path: Path) -> None:
    out = tmp_path / "original-pages.json"
    base = [sys.executable, "scripts/extract_hg007_wwil_original_pages.py"]
    first = subprocess.run(
        base + ["--out", str(out)], check=True, capture_output=True, text=True
    )
    status = json.loads(first.stdout)
    assert status["original_pdf_sha256"] == EXPECTED_SHA
    assert status["original_semantic_audit_complete"] is False
    second = subprocess.run(
        base + ["--out", str(out), "--verify-existing"],
        check=True, capture_output=True, text=True,
    )
    assert json.loads(second.stdout) == status
    with out.open("a", encoding="utf-8") as handle:
        handle.write("{}")
    failed = subprocess.run(
        base + ["--out", str(out), "--verify-existing"],
        check=False, capture_output=True, text=True,
    )
    assert failed.returncode != 0
    assert "packet drifted" in failed.stderr
