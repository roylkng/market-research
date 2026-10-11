from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import probe_hg007_anantraj_june_qip_nse_original as probe


def _pdf() -> bytes:
    return b"%PDF-1.7\n" + b"0" * 3000 + b"\n%%EOF\n"


def _details() -> dict:
    return {
        "original_issuer": "Anant Raj Limited",
        "monitoring_agency_named_in_original": "Infomerics Valuation and Rating Limited",
        "reported_quarter_end": "2026-06-30",
        "page_count": 21,
        "page_text_sha256": ["a" * 64] * 21,
        "all_pages_semantically_or_visually_approved": False,
    }


class Response:
    def __init__(self, status_code: int, content: bytes) -> None:
        self.status_code = status_code
        self.content = content
        self.url = probe.NSE_ORIGINAL_URL


def test_nse_original_custody_tracks_exact_sha_and_rejects_cash_promotion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    seen: list[dict] = []

    def fake_get(url: str, **kwargs: object) -> Response:
        seen.append({"url": url, **kwargs})
        return Response(200, _pdf())

    monkeypatch.setattr(probe.requests, "get", fake_get)
    monkeypatch.setattr(probe, "_inspect_original_pdf", lambda raw: _details())
    packet, raw = probe.acquire_nse_original(attempts=3, sleep_seconds=0)
    assert raw == _pdf()
    assert packet["state"] == probe.CAPTURED
    assert packet["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert len(seen) == 1
    assert seen[0]["url"] == probe.NSE_ORIGINAL_URL
    assert seen[0]["allow_redirects"] is False
    for field in (
        "all_object_values_page_visually_checked",
        "monitoring_report_is_independent_financial_audit",
        "cloud_capex_deployment_confirmed_from_balances",
        "cash_transferred_to_ashok_cloud_ascertained",
        "liabilities_transferred_to_ashok_cloud_ascertained",
        "company_completion_probability_published",
        "equity_expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert packet[field] is False
    probe.save_original(tmp_path, packet, raw)
    assert (
        tmp_path / "raw" / "sha256" / f"{packet['source_sha256']}.pdf"
    ).read_bytes() == raw
    assert json.loads((tmp_path / "attempt.json").read_text(encoding="utf-8")) == packet


def test_nse_403_does_not_retry_or_imply_cash_verified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    requests = []

    def fake_get(url: str, **kwargs: object) -> Response:
        requests.append(url)
        return Response(403, b"access blocked")

    monkeypatch.setattr(probe.requests, "get", fake_get)
    packet, raw = probe.acquire_nse_original(attempts=3, sleep_seconds=0)
    assert raw is None
    assert len(requests) == 1
    assert packet["state"] == "NSE_ACCESS_BLOCKED"
    assert packet["source_sha256"] is None
    probe.save_original(tmp_path, packet, raw)
    assert not (tmp_path / "raw").exists()
    assert packet["cash_transferred_to_ashok_cloud_ascertained"] is False


def test_html_200_and_wrong_pdf_pages_are_not_originals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        probe.requests, "get",
        lambda url, **kwargs: Response(200, b"<html>blocked</html>"),
    )
    result, raw = probe.acquire_nse_original(attempts=1)
    assert result["state"] == "NSE_DOCUMENT_REJECTED"
    assert raw is None

    monkeypatch.setattr(probe, "_inspect_original_pdf", lambda raw: {
        **_details(), "page_count": 22
    })
    monkeypatch.setattr(
        probe.requests, "get",
        lambda url, **kwargs: Response(200, _pdf()),
    )
    result, raw = probe.acquire_nse_original(attempts=1)
    assert result["state"] == "NSE_DOCUMENT_REJECTED"
    assert raw is None
    assert "expected 21" in result["reason"]


def test_exact_issuer_report_and_date_schema_reconciliation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(probe, "_inspect_original_pdf", lambda raw: _details())
    packet = probe._receipt(
        probe.CAPTURED, http_code=200, original=_pdf(),
        identity=_details(), error="source captured"
    )
    packet["source_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="sha mismatch"):
        probe.save_original(tmp_path, packet, _pdf())


def test_nse_source_retry_limit_and_fake_completion_rejected() -> None:
    with pytest.raises(ValueError, match="1, 2, or 3"):
        probe.acquire_nse_original(attempts=0)
    with pytest.raises(ValueError, match="retry delay"):
        probe.acquire_nse_original(sleep_seconds=-1)
    with pytest.raises(ValueError, match="unrecognized"):
        probe._receipt(
            "EVERYTHING_IS_APPROVED", http_code=200,
            original=None, identity=None, error="none"
        )
