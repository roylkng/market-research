"""Original signed Zuari 2026 annual security notes stay historical, not current NAV."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p026_zuari_annual import (
    SECURITY_NOTES,
    URL,
    _page_texts,
    _validate_original_texts,
    validated_receipt,
    verify_receipt,
)
from scripts import archive_l001_p026_zuari_annual as archive

FAKE_RAW = b"%PDF-1.7\n" + b"SYNTHETIC_TEST_NOT_THE_REAL_COMPANY\n" * 2000
CAPTURE = "2026-10-21T17:31:05+00:00"


def _example_pages() -> list[str]:
    pages = ["No financial note on this fixture page"] * 155
    pages[0] = (
        "ZUARI INDUSTRIES LIMITED 24 August 2026 "
        "ANNUAL REPORT 2025-26"
    )
    pages[120] = (
        "17.1 (a) ICICI BANK ltd first charge 12,00,000 "
        "shares CHAMBAL Fertilisers"
    )
    pages[121] = (
        "17.1 (b) CANARA BANK 8,00,000 shares of CHAMBAL Fertilisers"
    )
    pages[122] = (
        "17.2 BAJAJ FINANCE lender pledge of 3,974,979 "
        "CHAMBAL Fertilisers shares"
    )
    pages[123] = (
        "17.3 Unlisted NCD 20,000.00 lakhs secured against "
        "4,818,333 CHAMBAL Fertilisers shares"
    )
    return pages


def test_2026_annual_original_pages_and_multiple_lender_security_records():
    pages = _example_pages()
    result = _validate_original_texts(pages)
    assert result["original_issuer_and_fy26_detected"] is True
    assert result["page_count"] == 155
    assert result["matched_independent_note_count"] == 4
    assert set(result["debt_lien_page_evidence"]) == set(SECURITY_NOTES)
    assert result["pledged_stake_units_summable_without_overlap_audit"] is False
    assert result["september_2026_debenture_redemption_verified"] is False
    assert all(
        item["has_current_2026_10_21_lien_or_redemption_proof"] is False
        for item in result["debt_lien_page_evidence"].values()
    )


def test_old_NCD_security_missing_same_page_stays_unverified():
    pages = _example_pages()
    pages[123] = pages[123].replace("4,818,333", "1,111,111")
    result = _validate_original_texts(pages)
    assert result["matched_independent_note_count"] == 3
    ncd = result["debt_lien_page_evidence"][
        "SEPT30_NCD_4818333_CFCL_SHARES"
    ]
    assert ncd["status"] == "NOT_FULLY_RECONCILED_IN_EXTRACTED_PDF_TEXT"
    assert ncd["pdf_page_zero_based"] is None


def test_original_issuer_or_year_incorrect_fails_source_admission():
    pages = _example_pages()
    pages[0] = pages[0].replace("ZUARI INDUSTRIES", "ZUARI AGRO CHEMICALS")
    with pytest.raises(AlphaContractError, match="wrong issuer"):
        _validate_original_texts(pages)
    with pytest.raises(AlphaContractError, match="page range"):
        _validate_original_texts(pages[:20])
    with pytest.raises(AlphaContractError, match="header/size"):
        _page_texts(b"not a real original annual")


def test_exact_pdf_byte_archive_and_receipt_capture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
):
    monkeypatch.setattr(
        "marketlab.l001_p026_zuari_annual._page_texts",
        lambda raw: _example_pages(),
    )
    original = validated_receipt(FAKE_RAW, observed_utc=CAPTURE)
    assert original["issuer_symbol"] == "ZUARIIND"
    assert original["issuer_isin"] == "INE217A01012"
    assert original["original_raw_pdf_sha256"] == hashlib.sha256(FAKE_RAW).hexdigest()
    assert original["source_evidence"]["matched_independent_note_count"] == 4
    assert original["financial_institution_security_may_limit_free_sale"] is True
    assert original["company_attributable_fair_value"] is None
    assert original["live_capital_allowed"] is False
    verify_receipt(FAKE_RAW, original)

    monkeypatch.setattr(archive, "_download", lambda url: (200, FAKE_RAW, None))
    result = archive.run(tmp_path, attempt_id="p026-fake-1")
    assert result["state"] == "ORIGINAL_FY26_ANNUAL_PDF_ARCHIVED"
    assert result["source_original_raw_sha256"] == original["original_raw_pdf_sha256"]
    assert (tmp_path / result["source_original_raw_path"]).read_bytes() == FAKE_RAW
    checked = archive.check(tmp_path)
    assert checked["state"] == "FY26_ORIGINAL_ANNUAL_SOURCE_REPLAYED"
    assert checked["source_receipt_count"] == 1
    assert checked["loan_security_same_page_note_matches"] == 4
    assert checked["october_2026_lien_clearance_verified"] is False


def test_modified_pdf_or_receipt_cannot_be_passed_to_original_source_validator(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "marketlab.l001_p026_zuari_annual._page_texts",
        lambda raw: _example_pages(),
    )
    record = validated_receipt(FAKE_RAW, observed_utc=CAPTURE)
    changed = copy.deepcopy(record)
    changed["source_evidence"]["september_2026_debenture_redemption_verified"] = True
    with pytest.raises(AlphaContractError, match="receipt hash changed"):
        verify_receipt(FAKE_RAW, changed)
    with pytest.raises(AlphaContractError, match="original bytes/notes differ"):
        verify_receipt(record["original_raw_pdf_sha256"].encode(), record)


def test_403_or_wrong_issuer_receipt_cannot_prove_debt_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
):
    monkeypatch.setattr(archive, "_download", lambda url: (403, None, None))
    result = archive.run(tmp_path, attempt_id="p026-no-pdf")
    assert result["state"] == "ORIGINAL_ISSUER_ANNUAL_SOURCE_NOT_AVAILABLE"
    assert result["source_original_raw_path"] is None
    assert result["live_capital_allowed"] is False
    raw = json.loads(
        (tmp_path / "research/l001/originals/zuari_fy26_annual/attempts/"
         "p026-no-pdf.json").read_text("utf-8")
    )
    signed = raw.pop("attempt_sha256")
    assert digest(raw) == signed
    assert archive.check(tmp_path)["source_receipt_count"] == 0
    assert archive.URL == URL
