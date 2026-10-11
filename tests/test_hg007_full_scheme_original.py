from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import acquire_hg007_anantraj_full_scheme as module


def _pdf_fixture() -> bytes:
    return b"%PDF-1.7\n" + b"not a real PDF but a byte-envelope fixture" * 1000 + b"\n%%EOF\n"


class _FakePage:
    def __init__(self, index: int):
        self.index = index

    def extract_text(self) -> str:
        if self.index == 1:
            return (
                "COMPOSITE SCHEME OF ARRANGEMENT AMONGST ANANT RAJ LIMITED "
                "ANANT RAJ CLOUD PRIVATE LIMITED AND ASHOK CLOUD PRIVATE LIMITED "
                "amalgamation of ARCPL and demerger of undertaking"
            )
        return "Part III Transfer of Demerged Undertaking and its liabilities and assets"


def _mock_parser(monkeypatch: pytest.MonkeyPatch, *, count: int = 48) -> None:
    class Reader:
        def __init__(self, raw, strict: bool = False):
            self.pages = [_FakePage(i) for i in range(1, count + 1)]

    monkeypatch.setattr(module, "PdfReader", Reader)


def test_immutable_first_party_investor_listing_proves_exact_document_link() -> None:
    packet = module.load_verified_discovery(Path("."))
    assert packet["original_webpage_captured_count"] == 2
    official = next(
        p for p in packet["source_pages"]
        if p["source_page_id"] == "company_investor_scheme"
    )
    candidate = next(
        p for p in official["link_discovery"][
            "candidate_pdf_urls_not_original_verified"
        ]
        if p["pdf_url"] == module.EXACT_DISCOVERED_SOURCE
    )
    assert candidate["source_href_kind"] == "OFFICIAL_HTML_ANCHOR"
    assert candidate["actual_pdf_bytes_fetched_and_sha_verified"] is False


def test_exact_original_pdf_full_48_pages_is_still_not_a_legal_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_parser(monkeypatch)
    raw = _pdf_fixture()
    packet = module._extract_verified_scheme_pages(raw)
    assert packet["page_count"] == 48
    assert packet["pdf_sha256"] == hashlib.sha256(raw).hexdigest()
    assert len(packet["source_page_text_digest_provenance"]) == 48
    assert packet["original_pdf_page_visual_review_complete"] is False
    assert packet["all_source_terms_semantically_approved"] is False
    assert packet["source_page_text_digest_provenance"][2]["mentions_liabilities"] is True


def test_wrong_page_count_or_company_identity_blocks_source_promotion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_parser(monkeypatch, count=47)
    with pytest.raises(ValueError, match="unexpected original"):
        module._extract_verified_scheme_pages(_pdf_fixture())

    class WrongPage:
        def extract_text(self) -> str:
            return "Unrelated issuer restatement; no composite arrangement."

    class WrongReader:
        def __init__(self, raw, strict: bool = False):
            self.pages = [WrongPage() for _ in range(48)]

    monkeypatch.setattr(module, "PdfReader", WrongReader)
    with pytest.raises(ValueError, match="not the original"):
        module._extract_verified_scheme_pages(_pdf_fixture())


def test_only_original_source_captured_from_discovered_official_href() -> None:
    assert module._validate_pdf_location(module.EXACT_TRANSPORT_SOURCE)
    assert module._validate_pdf_location(module.EXACT_DISCOVERED_SOURCE)
    for url in (
        "https://blob.anantrajlimited.com.evil.invalid/anantraj/scheme.pdf",
        "http://blob.anantrajlimited.com/anantraj/1785759469838-Composite%20Scheme%20of%20Arrangement.pdf",
        "https://blob.anantrajlimited.com/anantraj/another-composite-scheme.pdf",
        "https://otherissuer.invalid/scheme.pdf",
        "https://user:pass@blob.anantrajlimited.com/anantraj/1785759469838-Composite%20Scheme%20of%20Arrangement.pdf",
    ):
        assert not module._validate_pdf_location(url)


def test_http403_remains_blocked_without_retry_or_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class Response:
        status_code = 403
        url = module.EXACT_TRANSPORT_SOURCE

        def close(self):
            pass

    def fake_get(url: str, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(module.requests, "get", fake_get)
    receipt, raw = module.acquire_exact_official_pdf()
    assert raw is None
    assert receipt["state"] == "OFFICIAL_ORIGINAL_PDF_ACCESS_BLOCKED"
    assert receipt["source_pdf"] is None
    assert receipt["liability_values_and_assets_transferred_current_verified"] is False
    assert receipt["portfolio_eligibility_allowed"] is False
    assert len(calls) == 1
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["stream"] is True


def test_successful_streamed_exact_official_pdf_original_retains_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _mock_parser(monkeypatch)
    original = _pdf_fixture()

    class Response:
        status_code = 200
        url = module.EXACT_TRANSPORT_SOURCE
        def __init__(self):
            self.headers = {"content-length": str(len(original))}

        def iter_content(self, chunk_size: int = 1_048_576):
            yield original[:5000]
            yield original[5000:]

        def close(self):
            pass

    monkeypatch.setattr(module.requests, "get", lambda url, **kwargs: Response())
    receipt, raw = module.acquire_exact_official_pdf()
    assert raw == original
    assert receipt["state"] == (
        "OFFICIAL_ISSUER_SCHEME_PDF_BYTES_IDENTITY_VERIFIED_NOT_LEGALLY_APPROVED"
    )
    assert receipt["source_pdf"]["page_count"] == 48
    assert receipt["full_scheme_liabilities_assets_semantic_review_completed"] is False
    assert receipt["regulatory_approvals_effective_date_verified"] is False
    module.retain_source(tmp_path, receipt, raw)
    destination = tmp_path / "raw" / "sha256" / (
        hashlib.sha256(raw).hexdigest() + ".pdf"
    )
    assert destination.read_bytes() == raw
    assert json.loads((tmp_path / "source-receipt-v1.json").read_text()) == receipt
    module.retain_source(tmp_path, receipt, raw)


def test_source_custody_detects_wrong_sha_or_receipt_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _mock_parser(monkeypatch)
    original = _pdf_fixture()
    metadata = module._extract_verified_scheme_pages(original)
    receipt = module._receipt(
        "OFFICIAL_ISSUER_SCHEME_PDF_BYTES_IDENTITY_VERIFIED_NOT_LEGALLY_APPROVED",
        http_status=200, evidence=metadata, reason="ORIGINAL",
    )
    forged = dict(receipt, source_pdf={**metadata, "pdf_sha256": "0" * 64})
    with pytest.raises(ValueError, match="content/page digest differed"):
        module.retain_source(tmp_path, forged, original)
    module.retain_source(tmp_path, receipt, original)
    rewritten = dict(receipt, retrieved_at_utc="2026-10-12T12:00:00Z")
    with pytest.raises(ValueError, match="append-only"):
        module.retain_source(tmp_path, rewritten, original)
