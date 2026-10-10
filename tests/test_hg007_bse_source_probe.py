from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import probe_hg007_bse_wwil_original as probe


def _pdf() -> bytes:
    # Byte-envelope-only fixture: no claim of a fully validated PDF.
    return b"%PDF-1.7\n" + b"0" * 700 + b"\n%%EOF\n"


class FakeResponse:
    def __init__(
        self, status_code: int, content: bytes, *, url: str = probe.ORIGINAL_BSE_URL
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.url = url


def _patched(monkeypatch: pytest.MonkeyPatch, response: FakeResponse) -> list:
    calls = []

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        calls.append((url, kwargs))
        return response

    monkeypatch.setattr(probe.requests, "get", fake_get)
    return calls


def test_capture_exact_bse_original_bytes_but_not_semantic_approval(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    body = _pdf()
    calls = _patched(monkeypatch, FakeResponse(200, body))
    receipt, raw = probe.acquire_original_bse_pdf(attempts=2, sleep_seconds=0)
    assert raw == body
    assert receipt["original_source_url"] == probe.ORIGINAL_BSE_URL
    assert receipt["original_pdf_sha256"] == hashlib.sha256(body).hexdigest()
    assert receipt["state"] == "PDF_SOURCE_BYTES_CAPTURED_NOT_SEMANTICALLY_AUDITED"
    assert receipt["source_byte_envelope_checked"] is True
    assert receipt["source_pdf_full_structure_validated"] is False
    for field in (
        "original_page_semantic_audit_approved",
        "wwil_transfer_conditions_precedent_verified_satisfied",
        "vibhav_actual_conversion_classes_and_prices_verified",
        "wwil_normalized_ebitda_verified",
        "completion_probability_calculated",
        "expected_return_calculated",
        "stock_price_target_authorized",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert receipt[field] is False
    assert len(calls) == 1
    assert calls[0][0] == probe.ORIGINAL_BSE_URL
    assert calls[0][1]["allow_redirects"] is False
    probe.retain_original_source(tmp_path, receipt, raw)
    retained = tmp_path / "original-raw" / "sha256" / f"{receipt['original_pdf_sha256']}.pdf"
    assert retained.read_bytes() == body
    assert json.loads((tmp_path / "receipt.json").read_text()) == receipt
    probe.retain_original_source(tmp_path, receipt, raw)


def test_access_denial_stops_without_cookie_or_host_bypass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls = _patched(monkeypatch, FakeResponse(403, b"Forbidden"))
    receipt, raw = probe.acquire_original_bse_pdf(attempts=3, sleep_seconds=0)
    assert raw is None
    assert receipt["state"] == "ORIGINAL_ATTACHMENT_ACCESS_BLOCKED"
    assert receipt["reason"] == "HTTP_403_NO_ACCESS_BYPASS"
    assert len(calls) == 1
    probe.retain_original_source(tmp_path, receipt, raw)
    assert not (tmp_path / "original-raw").exists()
    assert json.loads((tmp_path / "receipt.json").read_text())["original_pdf_sha256"] is None


def test_html_200_cannot_masquerade_as_original_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patched(
        monkeypatch, FakeResponse(200, b"<html><body>login</body></html>")
    )
    receipt, raw = probe.acquire_original_bse_pdf(attempts=3, sleep_seconds=0)
    assert receipt["state"] == "NOT_A_VERIFIABLE_PDF_BYTE_ENVELOPE"
    assert receipt["original_pdf_sha256"] is None
    assert raw is None
    assert len(calls) == 1


def test_redirect_is_never_followed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patched(monkeypatch, FakeResponse(302, b"", url=probe.ORIGINAL_BSE_URL))
    receipt, raw = probe.acquire_original_bse_pdf(attempts=2, sleep_seconds=0)
    assert receipt["state"] == "UNFOLLOWED_REDIRECT"
    assert raw is None
    assert len(calls) == 1
    assert calls[0][1]["allow_redirects"] is False


def test_source_url_change_without_redirect_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched(monkeypatch, FakeResponse(
        200, _pdf(), url="https://www.bseindia.com.evil.invalid/wwil.pdf"
    ))
    receipt, raw = probe.acquire_original_bse_pdf(attempts=2, sleep_seconds=0)
    assert receipt["state"] == "UNFOLLOWED_REDIRECT"
    assert raw is None


def test_corrupted_receipt_cannot_anchor_false_original(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _patched(monkeypatch, FakeResponse(200, _pdf()))
    receipt, raw = probe.acquire_original_bse_pdf(attempts=1, sleep_seconds=0)
    receipt["original_pdf_sha256"] = "x" * 64
    with pytest.raises(ValueError, match="envelope/bytes disagree"):
        probe.retain_original_source(tmp_path, receipt, raw)


def test_invalid_fetch_settings_or_fake_source_signature_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="between 1 and 3"):
        probe.acquire_original_bse_pdf(attempts=4, sleep_seconds=0)
    with pytest.raises(ValueError, match="retry pause"):
        probe.acquire_original_bse_pdf(attempts=1, sleep_seconds=-1)
    assert not probe._pdf_byte_envelope(b"%PDF-1.7\n")
    assert not probe._pdf_byte_envelope(b"%PDF-1.7" + b"a" * 600)
    _patched(monkeypatch, FakeResponse(200, b"%PDF-1.7" + b"a" * 800))
    receipt, raw = probe.acquire_original_bse_pdf(attempts=1, sleep_seconds=0)
    assert receipt["state"] == "NOT_A_VERIFIABLE_PDF_BYTE_ENVELOPE"
    assert raw is None
