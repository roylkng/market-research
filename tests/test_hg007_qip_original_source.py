from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import probe_hg007_qip_nse_original as module


def _bytes() -> bytes:
    return b"%PDF-1.7\n" + b"x" * 1500 + b"\n%%EOF\n"


def _page_text() -> list[str]:
    return [
        (
            "IGESL 30th September, 2026 NSE Symbol: INOXGREEN\n"
            "Sub: Allotment of equity shares qualified institutions placement "
            "meeting held 29th September, 2026 approved allotment "
            "1,81,10,473 Equity Shares at issue price Rs. 165.65 "
            "paid-up capital from Rs. 401,49,20,450 to Rs. 419,60,25,180 "
            "consisting of 41,96,02,518 Equity Shares."
        ),
        "Qualified Institutions Placement 1,81,10,473 equity shares allotted.",
        "Annexure 1 of original QIP includes listing of allottees exceeding five percent.",
    ]


def test_original_capital_equation_and_page_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_extract_pdf_pages", lambda raw: _page_text())
    verified = module.verify_qip_original(_bytes())
    assert verified["page_count"] == 3
    assert verified["pre_qip_issued_shares"] == 401_492_045
    assert verified["post_qip_issued_shares"] == 419_602_518
    assert verified["qip_allotted_shares"] == 18_110_473
    assert verified["qip_issue_price_inr"] == 165.65
    assert verified["current_esop_outstanding_verified"] is False
    assert verified["current_fully_diluted_shares_verified"] is False
    assert len(verified["page_text_sha256"]) == 3


def test_qip_pdf_missing_identity_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "_extract_pdf_pages", lambda raw: [
        "unrelated company unrelated allotment" * 5,
        "allotted shares" * 30,
        "annexure" * 30,
    ])
    with pytest.raises(ValueError, match="date/capital terms"):
        module.verify_qip_original(_bytes())


def test_invalid_venue_bytes_cannot_become_exchange_pdf() -> None:
    with pytest.raises(ValueError, match="PDF byte envelope"):
        module.verify_qip_original(b"<html>Access denied</html>")
    assert module._pdf_envelope(b"%PDF-1.7\n") is False


def test_access_blocked_is_recorded_without_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = []

    class Response:
        status_code = 403
        content = b"Forbidden"
        url = module.ORIGINAL_URL

    def fetch(url: str, **kwargs: object) -> Response:
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(module.requests, "get", fetch)
    receipt, data = module.probe_nse_original(attempts=3, sleep_seconds=0)
    assert receipt["state"] == "ORIGINAL_NSE_QIP_ACCESS_BLOCKED"
    assert receipt["source_original_pdf_sha256"] is None
    assert data is None
    assert receipt["live_capital_allowed"] is False
    assert len(calls) == 1
    assert calls[0][0] == module.ORIGINAL_URL
    assert calls[0][1]["allow_redirects"] is False
    module.save_original(tmp_path, receipt, data)
    assert not (tmp_path / "raw").exists()


def test_html_http_200_does_not_claim_original_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status_code = 200
        content = b"<html>Unexpected response body</html>"
        url = module.ORIGINAL_URL

    monkeypatch.setattr(module.requests, "get", lambda url, **kwargs: Response())
    receipt, data = module.probe_nse_original(attempts=1)
    assert receipt["state"] == "ORIGINAL_NSE_QIP_INVALID_PDF_OR_IDENTITY"
    assert receipt["source_original_pdf_sha256"] is None
    assert data is None


def test_immutable_original_qip_pdf_hash_and_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(module, "_extract_pdf_pages", lambda raw: _page_text())

    class Response:
        status_code = 200
        content = _bytes()
        url = module.ORIGINAL_URL

    monkeypatch.setattr(module.requests, "get", lambda url, **kwargs: Response())
    receipt, raw = module.probe_nse_original(attempts=1)
    assert raw is not None
    assert receipt["state"] == "ORIGINAL_NSE_QIP_PDF_CAPTURED_TEXT_IDENTITY_PASSED"
    assert receipt["qip_original_document_allotment_identity_confirmed"] is True
    assert receipt["current_fully_diluted_share_count_verified"] is False
    module.save_original(tmp_path, receipt, raw)
    document = tmp_path / "raw" / "sha256" / f"{hashlib.sha256(raw).hexdigest()}.pdf"
    assert document.read_bytes() == raw
    assert json.loads((tmp_path / "capture-receipt-v1.json").read_text()) == receipt
    module.save_original(tmp_path, receipt, raw)
    with pytest.raises(ValueError, match="receipt overwrite refused"):
        amended = dict(receipt, source_access_date_utc="2026-10-11T00:00:00Z")
        module.save_original(tmp_path, amended, raw)


def test_unknown_redirect_and_invalid_retry_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status_code = 302
        content = b""
        url = module.ORIGINAL_URL

    monkeypatch.setattr(module.requests, "get", lambda url, **kwargs: Response())
    receipt, raw = module.probe_nse_original(attempts=1)
    assert receipt["state"] == "ORIGINAL_NSE_QIP_UNFOLLOWED_REDIRECT"
    assert raw is None
    with pytest.raises(ValueError, match="between 1 and 3"):
        module.probe_nse_original(attempts=4)
    with pytest.raises(ValueError, match="retry spacing"):
        module.probe_nse_original(attempts=1, sleep_seconds=-1)
