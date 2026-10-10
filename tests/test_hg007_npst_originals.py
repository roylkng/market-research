from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import acquire_hg007_npst_originals as src


def _fake_pdf() -> bytes:
    return b"%PDF-1.7\n" + b"0" * 800 + b"%%EOF\n"


def _fake_page_evidence(raw: bytes) -> dict:
    assert raw == _fake_pdf()
    return {
        "page_count": 3,
        "page_text_sha256": ["a" * 64, "b" * 64, "c" * 64],
        "page_text_nonempty_count": 3,
        "issuer_name_mentioned_in_extracted_text": True,
        "june_2026_reporting_date_text_found": True,
        "march_2026_reporting_date_text_found": True,
        "original_document_full_economic_review_complete": False,
    }


class Response:
    def __init__(
        self, status: int, content: bytes, url: str
    ) -> None:
        self.status_code = status
        self.content = content
        self.url = url


def _fake_get(
    monkeypatch: pytest.MonkeyPatch, status: int, *, source_id: str, data: bytes,
) -> list:
    seen = []
    original = src.FILINGS[source_id]["url"]

    def download(url: str, **kwargs: object) -> Response:
        seen.append((url, kwargs))
        return Response(status, data, url=original)

    monkeypatch.setattr(src.requests, "get", download)
    return seen


@pytest.mark.parametrize("kind,reporting,prior_monitoring", [
    ("2026-08-11-investor-presentation", "2026-06-30", False),
    ("2026-08-11-june-reg32-use-of-funds", "2026-06-30", False),
    ("2026-08-11-march-monitoring-agency", "2026-03-31", True),
])
def test_exact_bse_original_source_receipt_distinguishes_reporting_period(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str,
    reporting: str, prior_monitoring: bool,
) -> None:
    monkeypatch.setattr(src, "_pdf_page_evidence", _fake_page_evidence)
    seen = _fake_get(monkeypatch, 200, source_id=kind, data=_fake_pdf())
    receipt, data = src.acquire_original(kind, attempts=3, sleep_seconds=0)
    assert receipt["status"] == "ORIGINAL_PDF_BYTE_AND_PAGE_STRUCTURE_CAPTURED"
    assert receipt["source_kind"] == kind
    assert receipt["source_declared_reporting_period"] == reporting
    assert receipt["monitoring_march_is_not_q1_june_evidence"] is prior_monitoring
    assert receipt["source_issuer_text_reconciled"] is True
    assert receipt["source_reporting_period_text_reconciled"] is True
    assert receipt["original_pdf_text_economic_facts_approved"] is False
    assert receipt["unutilized_proceeds_reported_value_verified"] is False
    assert receipt["original_q1fy27_ebitda_verified"] is False
    assert receipt["company_expected_returns_calculated"] is False
    assert receipt["portfolio_eligibility_allowed"] is False
    assert receipt["live_capital_allowed"] is False
    assert data == _fake_pdf()
    assert len(seen) == 1
    assert seen[0][0] == src.FILINGS[kind]["url"]
    assert seen[0][1]["allow_redirects"] is False
    out = tmp_path / kind
    src.save_original(out, receipt, data)
    pdf = out / "raw" / "sha256" / f"{receipt['original_raw_sha256']}.pdf"
    assert pdf.read_bytes() == data
    src.save_original(out, receipt, data)


def test_real_pdf_envelope_and_no_fake_html() -> None:
    assert src._pdf_envelope(_fake_pdf()) is True
    assert src._pdf_envelope(b"<html>CAPTCHA</html>") is False
    assert src._pdf_envelope(b"%PDF-1.7\n") is False
    assert src._pdf_envelope(b"%PDF-1.7" + b"0" * 1500) is False
    assert src._pdf_envelope(b"") is False


def test_forbidden_source_does_not_retry_or_invent_proceeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    kind = "2026-08-11-june-reg32-use-of-funds"
    seen = _fake_get(monkeypatch, 403, source_id=kind, data=b"Forbidden")
    result, raw = src.acquire_original(kind, attempts=3, sleep_seconds=0)
    assert result["status"] == "ORIGINAL_SOURCE_ACCESS_BLOCKED"
    assert result["failure_or_review_reason"] == "HTTP_403_NO_BYPASS"
    assert result["original_raw_sha256"] is None
    assert result["original_pdf_page_evidence"] is None
    assert raw is None
    assert len(seen) == 1
    src.save_original(tmp_path, result, raw)
    assert (tmp_path / "original-receipt-v1.json").exists()
    assert not (tmp_path / "raw").exists()


def test_200_html_fake_original_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    kind = "2026-08-11-investor-presentation"
    seen = _fake_get(
        monkeypatch, 200, source_id=kind, data=b"<html><body>not a PDF</body></html>"
    )
    result, raw = src.acquire_original(kind, attempts=2, sleep_seconds=0)
    assert result["status"] == "ORIGINAL_PDF_NOT_VERIFIABLE"
    assert result["original_raw_sha256"] is None
    assert raw is None
    assert len(seen) == 1


def test_url_substitution_and_redirect_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kind = "2026-08-11-investor-presentation"
    original = src.FILINGS[kind]["url"]

    def redirected(url: str, **kwargs: object) -> Response:
        assert kwargs["allow_redirects"] is False
        return Response(302, b"", url=original)

    monkeypatch.setattr(src.requests, "get", redirected)
    result, raw = src.acquire_original(kind, attempts=1)
    assert result["status"] == "ORIGINAL_SOURCE_REDIRECT_UNFOLLOWED"
    assert raw is None

    def wrong_host(url: str, **kwargs: object) -> Response:
        return Response(200, _fake_pdf(), url="https://example.invalid/fake.pdf")

    monkeypatch.setattr(src.requests, "get", wrong_host)
    result, raw = src.acquire_original(kind, attempts=1)
    assert result["status"] == "ORIGINAL_SOURCE_REDIRECT_UNFOLLOWED"
    assert raw is None


def test_mutated_pdf_or_false_source_receipt_cannot_anchor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(src, "_pdf_page_evidence", _fake_page_evidence)
    kind = "2026-08-11-investor-presentation"
    _fake_get(monkeypatch, 200, source_id=kind, data=_fake_pdf())
    receipt, raw = src.acquire_original(kind, attempts=1)
    assert raw is not None
    invalid = deepcopy(receipt)
    invalid["original_raw_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="content mismatch"):
        src.save_original(tmp_path / "invalid", invalid, raw)
    invalid = deepcopy(receipt)
    invalid["original_bse_url"] = "https://not-exchange.invalid/data"
    with pytest.raises(ValueError, match="substituted"):
        src.save_original(tmp_path / "changed", invalid, raw)
    src.save_original(tmp_path / "good", receipt, raw)
    altered = deepcopy(receipt)
    altered["captured_at_utc"] = "2026-10-11T00:00:00Z"
    with pytest.raises(ValueError, match="cannot be overwritten"):
        src.save_original(tmp_path / "good", altered, raw)


def test_invalid_sources_and_retry_configuration_rejected() -> None:
    with pytest.raises(ValueError, match="predeclared"):
        src.acquire_original("unlisted-attachment", attempts=1)
    with pytest.raises(ValueError, match="1-3"):
        src.acquire_original("2026-08-11-investor-presentation", attempts=4)
    with pytest.raises(ValueError, match="retry delay"):
        src.acquire_original(
            "2026-08-11-investor-presentation", attempts=1, sleep_seconds=-1
        )
    assert len(src.FILINGS) == 3
    assert len({data["url"] for data in src.FILINGS.values()}) == 3


def test_receipt_sha_only_if_original_bytes_captured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(src, "_pdf_page_evidence", _fake_page_evidence)
    kind = "2026-08-11-june-reg32-use-of-funds"
    _fake_get(monkeypatch, 200, source_id=kind, data=_fake_pdf())
    result, raw = src.acquire_original(kind, attempts=1)
    assert result["original_raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["original_raw_byte_count"] == len(raw)
    assert json.dumps(result, allow_nan=False)
