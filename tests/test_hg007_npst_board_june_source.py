from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import acquire_hg007_npst_board_june_original as module


def _fake_pdf() -> bytes:
    return b"%PDF-1.7\n" + b"X" * 1_300 + b"\n%%EOF\n"


def _fake_text_pages() -> list[str]:
    return [
        "Network People Services Technologies Limited ISIN INE0FFK01017 "
        "11.08.2026 NPST Board outcome approving June 30, 2026 results.",
        "The standalone and consolidated financial results for quarter ended "
        "June 30, 2026 attached with independent auditor limited review report.",
        "CARE Ratings Monitoring Agency Report for quarter ended June 30, 2026. "
        "Monitoring Agency June 30, 2026 result source scope.",
    ]


class FakePage:
    def __init__(self, content: str) -> None:
        self.content = content

    def extract_text(self) -> str:
        return self.content


class FakeReader:
    def __init__(self, _stream: object, strict: bool = False) -> None:
        self.pages = [FakePage(x) for x in _fake_text_pages()]


def test_original_npst_board_pdf_scope_and_page_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "PdfReader", FakeReader)
    result = module.original_page_evidence(_fake_pdf())
    assert result["issuer"] == "Network People Services Technologies Limited"
    assert result["isin"] == "INE0FFK01017"
    assert result["reporting_quarter"] == "2026-06-30"
    assert result["original_document_page_count"] == 3
    assert all(result["identity_gates"].values())
    assert "monitoring agency" in result["source_review_routing_pages"]
    assert result["source_review_routing_pages"]["monitoring agency"] == [3]
    assert all(
        value is False
        for name, value in result.items()
        if name.endswith("_verified") or name.endswith("_completed")
    )


def test_full_primary_june_document_cannot_be_confused_with_march(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def wrong_pages(_stream: object, strict: bool = False) -> FakeReader:
        out = FakeReader(_stream, strict=strict)
        out.pages[-1].content = out.pages[-1].content.replace(
            "June 30, 2026", "March 31, 2026"
        )
        return out

    monkeypatch.setattr(module, "PdfReader", wrong_pages)
    with pytest.raises(ValueError, match="june_monitoring"):
        module.original_page_evidence(_fake_pdf())


def test_plain_200_html_does_not_become_an_original_exchange_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status_code = 200
        url = module.SOURCE_URL

        def iter_content(self, chunk_size: int):
            yield b"<html>blocked by gateway</html>"

        def close(self):
            pass

    monkeypatch.setattr(module.requests, "get", lambda url, **kwargs: Response())
    receipt, raw = module.acquire_original_board_outcome(attempts=1)
    assert receipt["status"] == "ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_BAD_PDF_OR_IDENTITY"
    assert receipt["original_pdf_sha256"] is None
    assert raw is None


def test_genuine_pdf_capture_does_not_approve_june_economics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(module, "PdfReader", FakeReader)

    class Response:
        status_code = 200
        url = module.SOURCE_URL

        def iter_content(self, chunk_size: int):
            yield _fake_pdf()[:800]
            yield _fake_pdf()[800:]

        def close(self):
            pass

    seen = []

    def get(url: str, **kwargs: object) -> Response:
        seen.append((url, kwargs))
        return Response()

    monkeypatch.setattr(module.requests, "get", get)
    receipt, raw = module.acquire_original_board_outcome(attempts=2, sleep_seconds=0)
    assert raw is not None
    assert len(seen) == 1
    assert seen[0][0] == module.SOURCE_URL
    assert seen[0][1]["allow_redirects"] is False
    assert seen[0][1]["stream"] is True
    assert receipt["status"] == (
        "ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_CAPTURED_TEXT_IDENTITIES_PASSED"
    )
    assert receipt["original_pdf_sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["original_page_identity_evidence"]["original_document_page_count"] == 3
    assert receipt["independent_june_quarter_monitoring_cash_verification_complete"] is False
    assert receipt["financial_statement_limited_review_semantic_analysis_complete"] is False
    assert receipt["reported_reg32_unused_proceeds_are_bank_cash_verified"] is False
    assert receipt["investment_recommendation_authorized"] is False
    assert receipt["live_capital_allowed"] is False

    module.retain_source(tmp_path, receipt, raw)
    blob = tmp_path / "raw" / "sha256" / f"{hashlib.sha256(raw).hexdigest()}.pdf"
    assert blob.read_bytes() == raw
    assert json.loads((tmp_path / "source-receipt-v1.json").read_text()) == receipt
    module.retain_source(tmp_path, receipt, raw)


def test_blocked_exchange_original_is_not_automatically_bypassed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls = []

    class Response:
        status_code = 403
        url = module.SOURCE_URL

        def close(self):
            pass

    def get(url: str, **kwargs: object) -> Response:
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(module.requests, "get", get)
    receipt, raw = module.acquire_original_board_outcome(attempts=3, sleep_seconds=0)
    assert receipt["status"] == "ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_HTTP_BLOCKED"
    assert receipt["reason"] == "HTTP_403_NO_SOURCE_ACCESS_BYPASS"
    assert len(calls) == 1
    assert raw is None
    module.retain_source(tmp_path, receipt, raw)
    assert not (tmp_path / "raw").exists()


def test_bad_receipt_cannot_overwrite_pinned_original(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(module, "PdfReader", FakeReader)
    raw = _fake_pdf()
    details = module.original_page_evidence(raw)
    receipt = module._receipt(
        status="ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_CAPTURED_TEXT_IDENTITIES_PASSED",
        http=200,
        original_bytes=raw,
        evidence=details,
        reason="CAPTURED",
    )
    module.retain_source(tmp_path, receipt, raw)
    other = dict(receipt, captured_at_utc="2026-10-12T00:00:00Z")
    with pytest.raises(ValueError, match="immutable"):
        module.retain_source(tmp_path, other, raw)


def test_bounded_retry_configuration_and_redirect_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="1-3"):
        module.acquire_original_board_outcome(attempts=10)
    with pytest.raises(ValueError, match="0-30"):
        module.acquire_original_board_outcome(attempts=1, sleep_seconds=-1)

    class Response:
        status_code = 302
        url = module.SOURCE_URL

        def close(self):
            pass

    monkeypatch.setattr(module.requests, "get", lambda url, **kwargs: Response())
    receipt, raw = module.acquire_original_board_outcome(attempts=3, sleep_seconds=0)
    assert receipt["status"] == "ORIGINAL_NSE_BOARD_OUTCOME_SOURCE_UNFOLLOWED_REDIRECT"
    assert raw is None
