from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import discover_hg007_anantraj_full_scheme as module


def _company_html() -> bytes:
    return (
        b"<html><body><h1>Anant Raj Investor Center</h1>"
        b"<section><h2>Scheme of Arrangement</h2>"
        b'<a href="https://blob.anantrajlimited.com/anantraj/'
        b'full-composite-scheme.pdf">Composite Scheme of Arrangement</a>'
        b"</section><a href='https://evil.invalid/fake.pdf'>Scheme scam</a>"
        b"</body></html>"
    )


def _nse_html() -> bytes:
    return (
        b"<html><head><title>NSE Scheme Document</title></head>"
        b"<body><table><tr><td>Anant Raj Limited</td>"
        b"<td>Composite Scheme of Arrangement</td>"
        b"<td><a href='https://nsearchives.nseindia.com/corporates/"
        b"offerdocument/scheme/ANANTRAJ_published_draft.pdf'>"
        b"17-Aug-2026 (35.58 MB)</a></td></tr></table></body></html>"
    )


def _receipt(page_id: str, raw: bytes) -> dict:
    return {
        "source_page_id": page_id,
        "exact_official_page_url": module.PRIMARY_PAGES[page_id],
        "source_capture_at_utc": "2026-10-11T10:00:00Z",
        "source_state": "OFFICIAL_PAGE_HTML_CAPTURED",
        "http_status": 200,
        "blocked_reason": None,
        "raw_html_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_html_bytes": len(raw),
    }


def test_two_official_pages_identify_unverified_candidate_pdf_urls() -> None:
    c = module.discover_official_pdf_candidates(
        "company_investor_scheme",
        module.PRIMARY_PAGES["company_investor_scheme"],
        _company_html(),
    )
    n = module.discover_official_pdf_candidates(
        "official_nse_scheme_listing",
        module.PRIMARY_PAGES["official_nse_scheme_listing"],
        _nse_html(),
    )
    assert c["issuer_name_mentioned_in_current_html"] is True
    assert c["candidate_direct_pdf_url_count"] == 1
    assert n["candidate_direct_pdf_url_count"] == 1
    assert c["candidate_pdf_urls_not_original_verified"][0][
        "actual_pdf_bytes_fetched_and_sha_verified"
    ] is False
    assert "evil.invalid" not in json.dumps(c)
    assert n["composite_scheme_uploaded_aug17_original_pdf_acquired"] is False


def test_browser_substitution_and_unapproved_host_are_rejected() -> None:
    assert module._candidate_pdf(
        "https://nsearchives.nseindia.com/corporates/scheme.pdf",
        base=module.PRIMARY_PAGES["official_nse_scheme_listing"],
    )
    for candidate in (
        "https://nseindia.com.evil.invalid/arrangement.pdf",
        "http://nsearchives.nseindia.com/file.pdf",
        "https://evil.invalid/scheme.pdf",
        "javascript:alert(1)",
        "data:application/pdf;base64,ZmFrZQ==",
        "file:///tmp/scheme.pdf",
        "https://blob.anantrajlimited.com/foo.txt",
        "https://user:secret@blob.anantrajlimited.com/scheme.pdf",
    ):
        assert module._candidate_pdf(
            candidate, base=module.PRIMARY_PAGES["company_investor_scheme"]
        ) is None
    with pytest.raises(ValueError, match="exact approved"):
        module.discover_official_pdf_candidates(
            "company_investor_scheme",
            "https://thirdparty.invalid/reproduced-webpage",
            _company_html(),
        )


def test_html_source_and_candidate_is_sha_preserved_and_no_scheme_approval(
    tmp_path: Path,
) -> None:
    source = {
        "company_investor_scheme": (
            _receipt("company_investor_scheme", _company_html()), _company_html()
        ),
        "official_nse_scheme_listing": (
            _receipt("official_nse_scheme_listing", _nse_html()), _nse_html()
        ),
    }
    result = module.retain_discovery_run(tmp_path, source)
    assert result["original_webpage_captured_count"] == 2
    assert result["unique_candidate_pdf_url_count"] == 2
    assert result["aug17_35_58mb_scheme_pdf_original_bytes_retrieved"] is False
    assert result["scheme_schedules_assets_liabilities_reconciled"] is False
    assert result["nclt_effective_scheme_verified"] is False
    assert result["live_capital_allowed"] is False
    for row in result["source_pages"]:
        p = tmp_path / "raw" / "sha256" / f"{row['raw_html_sha256']}.html"
        assert p.exists()
        assert hashlib.sha256(p.read_bytes()).hexdigest() == row["raw_html_sha256"]
    assert json.loads((tmp_path / "discovery-v1.json").read_text()) == result
    assert module.retain_discovery_run(tmp_path, source) == result


def test_malformed_html_receipt_or_missing_official_source_fails_closed(
    tmp_path: Path,
) -> None:
    raw = _company_html()
    bad = _receipt("company_investor_scheme", raw)
    bad["raw_html_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="original byte SHA"):
        module.retain_discovery_run(
            tmp_path,
            {
                "company_investor_scheme": (bad, raw),
                "official_nse_scheme_listing": (
                    _receipt("official_nse_scheme_listing", _nse_html()), _nse_html()
                ),
            },
        )
    blocked = {
        "source_page_id": "official_nse_scheme_listing",
        "exact_official_page_url": module.PRIMARY_PAGES["official_nse_scheme_listing"],
        "source_capture_at_utc": "2026-10-11T10:00:00Z",
        "source_state": "OFFICIAL_PAGE_ACCESS_BLOCKED",
        "http_status": 403,
        "blocked_reason": "HTTP_403_NO_ACCESS_BYPASS",
        "raw_html_sha256": None,
        "raw_html_bytes": None,
    }
    result = module.retain_discovery_run(
        tmp_path,
        {
            "company_investor_scheme": (
                _receipt("company_investor_scheme", raw), raw
            ),
            "official_nse_scheme_listing": (blocked, None),
        },
    )
    assert result["original_webpage_captured_count"] == 1
    assert result["source_pages"][1]["link_discovery"] is None
    assert result["aug17_35_58mb_scheme_pdf_original_bytes_retrieved"] is False


def test_direct_official_page_fetch_never_bypasses_http_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class Response:
        status_code = 403
        content = b"Access denied"
        url = module.PRIMARY_PAGES["official_nse_scheme_listing"]

    def fake_get(url: str, **kwargs: object) -> Response:
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(module.requests, "get", fake_get)
    receipt, original = module.fetch_official_page("official_nse_scheme_listing")
    assert original is None
    assert receipt["source_state"] == "OFFICIAL_PAGE_ACCESS_BLOCKED"
    assert receipt["blocked_reason"] == "HTTP_403_NO_ACCESS_BYPASS"
    assert len(calls) == 1
    assert calls[0][1]["allow_redirects"] is False
    assert receipt["raw_html_sha256"] is None
