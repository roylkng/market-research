from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts import acquire_hg007_anantraj_originals as module


def _fake_pdf(key: str) -> bytes:
    return b"%PDF-1.7\n" + key.encode() + b"f" * 800 + b"\n%%EOF\n"


def _text_page(count: int) -> list[str]:
    key = next(k for k, spec in module.PDF_SOURCES.items() if spec["pages"] == count)
    facts = " ".join(module.PDF_SOURCES[key]["tokens"])
    return [facts + (" Anant Raj Limited. Ashok Cloud Private Limited. " * 3)] + [
        "Official listed-company filing additional annexure page. " * 3
        for _ in range(count - 1)
    ]


def _patch_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        module, "_pdf_pages",
        lambda raw, *, expected_count: _text_page(expected_count),
    )


def test_exact_three_official_sources_with_original_bytes_and_audited_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _patch_pdf(monkeypatch)
    staged: dict[str, tuple[dict, bytes | None]] = {}
    for key, spec in module.PDF_SOURCES.items():
        raw = _fake_pdf(key)
        verified = module.verify_source_bytes(key, raw)
        assert verified["original_pdf_page_count"] == spec["pages"]
        assert verified["issuer_terms_original_text_located"] is True
        assert verified["original_pdf_sha256"] == hashlib.sha256(raw).hexdigest()
        assert verified["scheme_effective_date_verified"] is False
        receipt = module._receipt(
            key, "OFFICIAL_PDF_SOURCE_PAGES_VERIFIED_NOT_TRANSACTION_CLOSE",
            http_status=200, reason="TEST", verified=verified,
        )
        staged[key] = receipt, raw
    packet = module.retain_attempt(tmp_path, staged)
    assert packet["original_verified_count"] == 3
    assert packet["source_completion_state"] == "THREE_ORIGINAL_ISSUER_FILINGS_VERIFIED"
    assert packet["original_scheme_transaction_effective_verified"] is False
    assert packet["pro_forma_newco_ownership_completed_verified"] is False
    assert packet["live_capital_allowed"] is False
    for key, (_, raw) in staged.items():
        assert raw is not None
        digest = hashlib.sha256(raw).hexdigest()
        assert (tmp_path / "raw" / "sha256" / f"{digest}.pdf").read_bytes() == raw
        assert packet["source_receipts"][list(module.PDF_SOURCES).index(key)][
            "verified_original"
        ]["original_pdf_sha256"] == digest
    assert module.retain_attempt(tmp_path, staged) == packet


def test_early_source_invalid_or_modified_original_never_approved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _patch_pdf(monkeypatch)
    key = "july20_subsidiary_rights_proposal"
    raw = _fake_pdf(key)
    r = module._receipt(
        key, "OFFICIAL_PDF_SOURCE_PAGES_VERIFIED_NOT_TRANSACTION_CLOSE",
        http_status=200, reason="ORIGINAL", verified=module.verify_source_bytes(key, raw)
    )
    r["verified_original"]["original_pdf_sha256"] = "0" * 64
    rest = {
        name: (
            module._receipt(
                name, "OFFICIAL_SOURCE_ACCESS_BLOCKED",
                http_status=403, reason="HTTP_403_NO_ACCESS_BYPASS", verified=None,
            ),
            None,
        )
        for name in module.PDF_SOURCES if name != key
    }
    with pytest.raises(ValueError, match="receipt changed"):
        module.retain_attempt(tmp_path, {key: (r, raw), **rest})


def test_blocked_403_has_no_retry_or_alternative_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "july21_conditional_demerger_press"
    calls = []

    class Response:
        status_code = 403
        content = b"Forbidden"
        url = module.PDF_SOURCES[key]["url"]

    def fake(url: str, **kwargs: object) -> Response:
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(module.requests, "get", fake)
    receipt, raw = module.acquire_one(key, attempts=3, sleep_seconds=0)
    assert raw is None
    assert receipt["state"] == "OFFICIAL_SOURCE_ACCESS_BLOCKED"
    assert receipt["verified_original"] is None
    assert receipt["reason"] == "HTTP_403_NO_ACCESS_BYPASS"
    assert len(calls) == 1
    assert calls[0][0] == module.PDF_SOURCES[key]["url"]
    assert calls[0][1]["allow_redirects"] is False
    assert receipt["portfolio_eligibility_allowed"] is False


def test_html_200_and_redirect_are_not_source_custody(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "july21_completed_subscription"

    class Response:
        def __init__(self, state: int, raw: bytes):
            self.status_code = state
            self.content = raw
            self.url = module.PDF_SOURCES[key]["url"]

    monkeypatch.setattr(
        module.requests, "get",
        lambda url, **kwargs: Response(200, b"<html>Please sign in</html>"),
    )
    receipt, raw = module.acquire_one(key, attempts=3, sleep_seconds=0)
    assert raw is None
    assert receipt["state"] == "OFFICIAL_SOURCE_INVALID_PDF_OR_TEXT"

    monkeypatch.setattr(
        module.requests, "get", lambda url, **kwargs: Response(302, b"")
    )
    receipt, raw = module.acquire_one(key, attempts=3, sleep_seconds=0)
    assert raw is None
    assert receipt["state"] == "OFFICIAL_SOURCE_UNFOLLOWED_REDIRECT"


def test_exact_expected_source_identity_must_be_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def wrong_pages(raw: bytes, *, expected_count: int) -> list[str]:
        return ["Completely unrelated issuer and false transaction " * 4
                for _ in range(expected_count)]
    monkeypatch.setattr(module, "_pdf_pages", wrong_pages)
    with pytest.raises(ValueError, match="identity mismatch"):
        module.verify_source_bytes(
            "july21_conditional_demerger_press",
            _fake_pdf("july21_conditional_demerger_press"),
        )
    with pytest.raises(ValueError, match="not preregistered"):
        module.verify_source_bytes("another_vendor", _fake_pdf("alternative"))


def test_invalid_count_and_incomplete_three_doc_state_are_explicit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _patch_pdf(monkeypatch)
    with pytest.raises(ValueError, match="must be 1-3"):
        module.acquire_one("july20_subsidiary_rights_proposal", attempts=5, sleep_seconds=0)
    staged = {
        name: (
            module._receipt(
                name, "OFFICIAL_SOURCE_NOT_FOUND",
                http_status=404, reason="NOT_YET", verified=None,
            ), None
        )
        for name in module.PDF_SOURCES
    }
    staged["july21_completed_subscription"] = (
        module._receipt(
            "july21_completed_subscription",
            "OFFICIAL_PDF_SOURCE_PAGES_VERIFIED_NOT_TRANSACTION_CLOSE",
            http_status=200, reason="TEST",
            verified=module.verify_source_bytes(
                "july21_completed_subscription",
                _fake_pdf("july21_completed_subscription"),
            ),
        ),
        _fake_pdf("july21_completed_subscription"),
    )
    result = module.retain_attempt(tmp_path, staged)
    assert result["original_verified_count"] == 1
    assert result["source_completion_state"] == "INCOMPLETE_OR_BLOCKED_ORIGINAL_SOURCES"
    assert result["original_scheme_transaction_effective_verified"] is False
