from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import acquire_hg007_devx_originals as module


def _fake_pages() -> list[str]:
    pages = ["Example DEV ACCELERATOR DEVX 20th May, 2026 public market statement"] * 34
    pages[5] = "Cash EBIT 36.55 ₹ 103.46 FY26 EBITDA margin 60.5 percent"
    pages[27] = ("Standalone Financial Metrics FY26 170.91 103.46 36.55 "
                 "Lease Liabilities Rent Out Flow 66.92 Interest on Lease Liabilities")
    pages[22] = "Winston signed in Q4. 450,000 square feet straight lease space."
    return pages


def _raw_nse() -> bytes:
    return b"%PDF-1.7\n" + b"A" * 10000 + b"\n%%EOF\n"


def _raw_acuite() -> bytes:
    return (
        b"<!DOCTYPE html><html><body><h1>DEV ACCELERATOR LIMITED</h1>"
        b"<h2>October 08, 2026</h2><p>ACUITE BBB Stable "
        b"non convertible debentures lease liabilities 3.11 "
        b"adjusted 1.32 Ahmedabad "
        + b"Lease liabilities Debt EBITDA NCD" * 175
        + b"</p></body></html>"
    )


def test_official_original_validation_requires_exact_issuer_and_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_pdf_pages", lambda raw: _fake_pages())
    pdf = module.validate_original("nse_pdf", _raw_nse())
    html = module.validate_original("acuite_html", _raw_acuite())
    assert pdf["page_count"] == 34
    assert len(pdf["page_text_sha256"]) == 34
    assert html["rating"] == "ACUITE BBB / Stable"
    assert pdf["winston_signed_not_recognized_as_current_cash_flow"] is True
    assert html["no_issuer_audit_or_equity_investment_approval"] is True


def test_missing_lease_outflow_or_credit_ratios_blocks_source_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad = _fake_pages()
    bad[27] = bad[27].replace("66.92", "99.00")
    monkeypatch.setattr(module, "_pdf_pages", lambda raw: bad)
    with pytest.raises(ValueError, match="66.92"):
        module.validate_original("nse_pdf", _raw_nse())
    with pytest.raises(ValueError, match="3.11"):
        module.validate_original(
            "acuite_html", _raw_acuite().replace(b"3.11", b"6.11")
        )


def test_exact_403_access_denial_without_redirect_or_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class Response:
        status_code = 403
        content = b"Forbidden"
        url = module.NSE_PDF_URL

    def fetch(url: str, **kwargs: object) -> Response:
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(module.requests, "get", fetch)
    blocked, raw = module.acquire_source("nse_pdf", attempts=3, sleep_seconds=0)
    assert blocked["status"] == "ACCESS_BLOCKED"
    assert blocked["raw_sha256"] is None
    assert raw is None
    assert len(calls) == 1
    assert calls[0][0] == module.NSE_PDF_URL
    assert calls[0][1]["allow_redirects"] is False
    assert blocked["live_capital_allowed"] is False


def test_bad_http200_document_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status_code = 200
        content = b"<html>log in to view</html>"
        url = module.NSE_PDF_URL

    monkeypatch.setattr(module.requests, "get", lambda url, **kw: Response())
    receipt, raw = module.acquire_source("nse_pdf", attempts=1)
    assert receipt["status"] == "INVALID_DOCUMENT"
    assert receipt["structural_evidence"] is None
    assert raw is None


def test_mismatched_url_cannot_promote_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status_code = 200
        content = _raw_acuite()
        url = "https://connect.acuite.in.evil.invalid/fake"

    monkeypatch.setattr(module.requests, "get", lambda url, **kw: Response())
    receipt, raw = module.acquire_source("acuite_html", attempts=3, sleep_seconds=0)
    assert receipt["status"] == "UNFOLLOWED_REDIRECT"
    assert raw is None


def test_hashed_originals_retained_without_alpha_or_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(module, "_pdf_pages", lambda raw: _fake_pages())
    receipts = {}
    for kind, raw in (("nse_pdf", _raw_nse()), ("acuite_html", _raw_acuite())):
        valid = module.validate_original(kind, raw)
        receipts[kind] = ({
            "source_id": module.SOURCE_ID,
            "source_kind": kind,
            "status": "SOURCE_CAPTURED_IDENTITY_CHECKED",
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "raw_byte_count": len(raw),
            "structural_evidence": valid,
            "live_capital_allowed": False,
        }, raw)
    packet = module.retain_sources(tmp_path, receipts)
    assert packet["both_independent_originals_available"] is True
    assert packet["company_expected_returns_calculated"] is False
    assert packet["total_return_outcomes_opened"] is False
    assert packet["live_capital_allowed"] is False
    for kind, (_receipt, raw) in receipts.items():
        ext = ".pdf" if kind == "nse_pdf" else ".html"
        saved = tmp_path / "raw" / "sha256" / f"{hashlib.sha256(raw).hexdigest()}{ext}"
        assert saved.read_bytes() == raw
    module.retain_sources(tmp_path, receipts)
    assert json.loads((tmp_path / "bundle-attempt.json").read_text()) == packet
    altered = dict(receipts)
    old, old_raw = altered["nse_pdf"]
    altered["nse_pdf"] = (dict(old, raw_sha256="f" * 64), old_raw)
    with pytest.raises(ValueError, match="source receipt"):
        module.retain_sources(tmp_path, altered)


def test_retry_configuration_refuses_unbounded_and_invented_sources() -> None:
    with pytest.raises(ValueError, match="1-3"):
        module.acquire_source("nse_pdf", attempts=0)
    with pytest.raises(ValueError, match="invalid source retry"):
        module.acquire_source("acuite_html", sleep_seconds=-1)
    with pytest.raises(ValueError, match="unknown original DEVX"):
        module.acquire_source("unapproved_pdf")



def test_acuite_original_fragment_or_bom_prefix_may_be_valid() -> None:
    original = _raw_acuite()
    fragment = b"<!-- provider HTML wrapper -->\n" + original
    bom = b"\xef\xbb\xbf" + original
    assert module.validate_original("acuite_html", fragment)["rating"] == (
        "ACUITE BBB / Stable"
    )
    assert module.validate_original("acuite_html", bom)["rating"] == (
        "ACUITE BBB / Stable"
    )


def test_acuite_200_login_page_and_plain_text_cannot_be_credit_evidence() -> None:
    login = b"<html><body><p>Sign in to continue</p></body></html>"
    with pytest.raises(ValueError, match="unusually short"):
        module.validate_original("acuite_html", login)
    nonsensical = (
        b"<html><body><p>" + b"completely unrelated issuer " * 300 + b"</p></body></html>"
    )
    with pytest.raises(ValueError, match="identity/credit clause"):
        module.validate_original("acuite_html", nonsensical)
    with pytest.raises(ValueError, match="lacks HTML"):
        module.validate_original("acuite_html", b"rating notice " * 600)
