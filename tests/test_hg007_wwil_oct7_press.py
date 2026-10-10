from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import probe_hg007_wwil_oct7_press as p


def _fake_pdf() -> bytes:
    return b"%PDF-1.7\n" + b"w" * 900 + b"\n%%EOF\n"


class MockResponse:
    def __init__(self, code: int, raw: bytes, url: str = p.ORIGINAL_BSE_PDF) -> None:
        self.status_code = code
        self.content = raw
        self.url = url


def test_exact_pdf_can_be_retained_without_claiming_ebitda_verification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original = _fake_pdf()
    calls = []

    def fake_get(url: str, **kw: object) -> MockResponse:
        calls.append((url, kw))
        return MockResponse(200, original)

    monkeypatch.setattr(p.requests, "get", fake_get)
    r, raw = p.acquire_original_press(attempts=2, delay_seconds=0)
    assert raw == original
    assert r["source_status"] == "BSE_ORIGINAL_PRESS_PDF_CAPTURED_UNREVIEWED"
    assert r["source_original_pdf_sha256"] == hashlib.sha256(original).hexdigest()
    assert r["all_pdf_pages_read_and_text_hash_verified"] is False
    assert r["management_2x_post_synergy_ebitda_multiple_semantically_approved"] is False
    assert r["wwil_historical_ebitda_source_verified"] is False
    assert r["wwil_legal_transfer_completed_verified"] is False
    assert r["stock_expected_returns_calculated"] is False
    assert r["live_capital_allowed"] is False
    assert len(calls) == 1
    assert calls[0][0] == p.ORIGINAL_BSE_PDF
    assert calls[0][1]["allow_redirects"] is False
    p.write_source(tmp_path, receipt=r, original=raw)
    expected=tmp_path/"raw"/"sha256"/f"{r['source_original_pdf_sha256']}.pdf"
    assert expected.read_bytes() == original
    assert json.loads((tmp_path/"source-receipt-v1.json").read_text()) == r


def test_403_is_not_bypassed_or_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_get(url: str, **kwargs: object) -> MockResponse:
        calls.append(url)
        return MockResponse(403, b"Forbidden")

    monkeypatch.setattr(p.requests, "get", fake_get)
    receipt, raw = p.acquire_original_press(attempts=3, delay_seconds=0)
    assert receipt["source_status"] == "BSE_OFFICIAL_DOCUMENT_ACCESS_BLOCKED"
    assert receipt["source_fetch_reason"] == "HTTP_403_NO_ACCESS_BYPASS"
    assert raw is None
    assert len(calls) == 1


def test_fake_html_200_and_unfollowed_redirect_cannot_promote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        p.requests,"get",lambda url, **kw: MockResponse(200,b"<html>login</html>")
    )
    receipt, raw=p.acquire_original_press(attempts=1)
    assert receipt["source_status"] == "BSE_NONPDF_SOURCE_BYTES"
    assert receipt["source_original_pdf_sha256"] is None
    assert raw is None
    monkeypatch.setattr(
        p.requests,"get",lambda url, **kw: MockResponse(302,b"")
    )
    receipt,raw=p.acquire_original_press(attempts=1)
    assert receipt["source_status"] == "BSE_UNFOLLOWED_REDIRECT"
    assert raw is None


def test_source_receipt_must_match_original_bytes(tmp_path: Path) -> None:
    original=_fake_pdf()
    receipt=p._receipt(
        "BSE_ORIGINAL_PRESS_PDF_CAPTURED_UNREVIEWED",
        http_status=200, original_raw=original, reason="SOURCE_ORIGINAL",
    )
    receipt["source_original_pdf_sha256"]="0"*64
    with pytest.raises(ValueError,match="byte or SHA"):
        p.write_source(tmp_path,receipt=receipt,original=original)


def test_bounded_attempt_settings() -> None:
    with pytest.raises(ValueError,match="1..3"):
        p.acquire_original_press(attempts=4)
    with pytest.raises(ValueError,match="delay"):
        p.acquire_original_press(delay_seconds=-1)
    assert p._pdf_envelope(b"%PDF-1.7\n") is False
