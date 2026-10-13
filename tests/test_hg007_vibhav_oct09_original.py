from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import probe_hg007_vibhav_oct09_original as module


def _fake_pdf() -> bytes:
    return b"%PDF-1.7\n" + b"X" * 1150 + b"\n%%EOF\n"


def _pages() -> list[str]:
    return [
        (
            "IGESL: NOI: 2026 9th October, 2026 "
            "NSE Symbol: INOXGREEN Vibhav Energy "
            "ICDs aggregating to Rs. 150 Crore into shares "
            "5 Crore shares to Company against Rs. 50 Crore "
            "10 Crore shares to Authum against Rs. 100 Crore "
            "Consequent shareholding stands at 75% and Authum 25%. "
            "Vibhav ceased to be a wholly-owned subsidiary but remains subsidiary."
        ),
        (
            "Annexure A. Vibhav after conversion paid-up is Rs. 400.01 Crore. "
            "The conversion does not involve any fresh cash outflow. "
            "The acquisition is completed. 50 Crore of ICD is converted."
        ),
    ]


def test_original_oct9_conversion_math_without_business_transfer_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_pdf_pages", lambda raw: _pages())
    data = module.verify_original_oct9(_fake_pdf())
    assert data["total_existing_icds_converted_inr_crore"] == 150
    assert data["inoxgreen_icd_converted_inr_crore"] == 50
    assert data["authum_icd_converted_inr_crore"] == 100
    assert data["reported_issuer_vibhav_ownership_pct"] == 75
    assert data["reported_authum_vibhav_ownership_pct"] == 25
    assert data["subsidiary_paid_up_cap_after_conversion_inr_crore"] == 400.01
    assert data["post_conversion_vibhav_wholly_owned"] is False
    assert data["conversion_is_noncash"] is True
    assert data["original_wwil_bta_legal_transfer_verified_by_this_notice"] is False
    assert data["stock_expected_returns_calculated"] is False


def test_document_identity_mismatch_blocks_promotion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = _pages()
    pages[0] = pages[0].replace("10 Crore shares", "1 Crore shares")
    monkeypatch.setattr(module, "_pdf_pages", lambda raw: pages)
    with pytest.raises(ValueError, match="page 1 missing"):
        module.verify_original_oct9(_fake_pdf())


def test_403_has_no_access_bypass_or_followed_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Forbidden:
        status_code = 403
        url = module.OFFICIAL_URL
        content = b"Forbidden"

    calls: list = []

    def get(url: str, **kwargs: object) -> Forbidden:
        calls.append((url, kwargs))
        return Forbidden()

    monkeypatch.setattr(module.requests, "get", get)
    receipt, body = module.acquire_oct9(attempts=3, sleep_seconds=0)
    assert receipt["source_state"] == module.BLOCKED
    assert receipt["source_http_status"] == 403
    assert body is None
    assert len(calls) == 1
    assert calls[0][0] == module.OFFICIAL_URL
    assert calls[0][1]["allow_redirects"] is False


def test_source_retained_with_sha_and_no_capital(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_pdf_pages", lambda raw: _pages())
    receipt = module._receipt(
        module.OK, 200, _fake_pdf(),
        module.verify_original_oct9(_fake_pdf()), "SOURCE_OK"
    )
    module.retain_source(tmp_path, receipt, _fake_pdf())
    sha = hashlib.sha256(_fake_pdf()).hexdigest()
    assert (tmp_path / "raw" / "sha256" / f"{sha}.pdf").read_bytes() == _fake_pdf()
    stored = json.loads((tmp_path / "source-receipt-v1.json").read_text())
    assert stored["original_pdf_sha256"] == sha
    assert stored["source_first_public_timestamp_verified"] is False
    assert stored["wwil_undertaking_transfer_completed"] is False
    assert stored["live_capital_allowed"] is False
    module.retain_source(tmp_path, receipt, _fake_pdf())
    altered = dict(receipt, observed_at_utc="2026-10-13T00:00:00Z")
    with pytest.raises(ValueError, match="overwrite refused"):
        module.retain_source(tmp_path, altered, _fake_pdf())


def test_html_login_is_not_original_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status_code = 200
        url = module.OFFICIAL_URL
        content = b"<html>sign in</html>"

    monkeypatch.setattr(module.requests, "get", lambda url, **kwargs: Response())
    receipt, raw = module.acquire_oct9(attempts=2, sleep_seconds=0)
    assert raw is None
    assert receipt["source_state"] == module.NOT_PDF


def test_invalid_retry_configuration() -> None:
    with pytest.raises(ValueError, match="bounded"):
        module.acquire_oct9(attempts=0)
    with pytest.raises(ValueError, match="retry spacing"):
        module.acquire_oct9(attempts=1, sleep_seconds=-2)
