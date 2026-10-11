from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import probe_hg007_anantraj_june_qip_monitor as source


def _details() -> dict:
    return {
        "original_issuer": "Anant Raj Limited",
        "monitoring_agency_named_in_original": "Infomerics Valuation and Rating Limited",
        "reported_quarter_end": "2026-06-30",
        "original_issuer_document_date": "2026-08-08",
        "page_count": 7,
        "page_text_sha256": ["a" * 64] * 7,
        "all_pages_semantically_or_visually_approved": False,
        "reported_qip_objects_amounts_issuer_independently_reconciled": False,
        "actual_cash_transferred_to_ashok_cloud_verified": False,
    }


def _sample_pdf() -> bytes:
    return b"%PDF-1.7\n" + b"0" * 3000 + b"\n%%EOF\n"


class Response:
    def __init__(self, status: int, content: bytes) -> None:
        self.status_code = status
        self.content = content
        self.url = source.SOURCE_URL


def test_https_official_original_retrieval_is_shabound_not_accounting_approval(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls = []

    def fake_get(url: str, **kwargs: object) -> Response:
        calls.append((url, kwargs))
        return Response(200, _sample_pdf())

    monkeypatch.setattr(source.requests, "get", fake_get)
    monkeypatch.setattr(source, "_inspect_original_pdf", lambda raw: _details())
    receipt, original = source.acquire_bse_original(attempts=2, sleep_seconds=0)
    assert len(calls) == 1
    assert calls[0][0] == source.SOURCE_URL
    assert calls[0][1]["allow_redirects"] is False
    assert original == _sample_pdf()
    assert receipt["state"] == source.CAPTURE_OK
    assert receipt["original_pdf_sha256"] == hashlib.sha256(original).hexdigest()
    for key in (
        "full_qip_utilization_table_audited",
        "cloud_scheme_cash_transfer_amount_audited",
        "cloud_scheme_loan_transfer_amount_audited",
        "anant_raj_debt_free_business_confirmed",
        "report_is_a_financial_statement_audit",
        "equity_expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert receipt[key] is False
    source.retain_original(tmp_path, receipt, original)
    assert (
        tmp_path / "raw" / "sha256" / f"{receipt['original_pdf_sha256']}.pdf"
    ).read_bytes() == original
    assert json.loads((tmp_path / "attempt.json").read_text()) == receipt


def test_original_access_denied_is_single_attempt_no_bypass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = []

    def fake_get(url: str, **kwargs: object) -> Response:
        calls.append((url, kwargs))
        return Response(403, b"access denied")

    monkeypatch.setattr(source.requests, "get", fake_get)
    receipt, data = source.acquire_bse_original(attempts=3, sleep_seconds=0)
    assert data is None
    assert len(calls) == 1
    assert receipt["state"] == "BSE_ACCESS_BLOCKED"
    assert receipt["reason"] == "HTTP_403_NO_ACCESS_BYPASS"
    source.retain_original(tmp_path, receipt, data)
    assert not (tmp_path / "raw").exists()
    assert receipt["live_capital_allowed"] is False


def test_bad_pdf_or_wrong_issuer_cannot_be_source_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        source.requests, "get",
        lambda url, **kwargs: Response(200, b"<html>login</html>"),
    )
    receipt, data = source.acquire_bse_original(attempts=1)
    assert receipt["state"] == "BSE_INVALID_PDF_OR_ISSUER"
    assert data is None
    with pytest.raises(ValueError, match="PDF byte envelope"):
        source._inspect_original_pdf(b"<html>not PDF</html>")


def test_changed_receipt_or_original_source_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(source, "_inspect_original_pdf", lambda raw: _details())
    raw = _sample_pdf()
    receipt = source._receipt(
        source.CAPTURE_OK, 200, raw=raw, details=_details(),
        reason="ORIGINAL_BYTES_RETAINED_AUDIT_STILL_PENDING"
    )
    receipt["original_pdf_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="content or page text"):
        source.retain_original(tmp_path, receipt, raw)


def test_bounded_network_settings_and_unsupported_source_state() -> None:
    with pytest.raises(ValueError, match="between 1 and 3"):
        source.acquire_bse_original(attempts=4)
    with pytest.raises(ValueError, match="retry delay"):
        source.acquire_bse_original(attempts=1, sleep_seconds=-1)
    with pytest.raises(ValueError, match="invalid official BSE"):
        source._receipt("READY_FOR_INVESTING", 200, raw=None, details=None, reason="")


def test_pdf_structural_schema_rejects_unreadable_pages(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    class BadReader:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.pages = []

    monkeypatch.setattr(source, "PdfReader", BadReader)
    with pytest.raises(ValueError, match="unreadable PDF pages"):
        source._inspect_original_pdf(_sample_pdf())
