from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import probe_ss002_polycab_original_stay as module


def _pdf() -> bytes:
    return b"%PDF-1.7\n" + b"x" * 3000 + b"\n%%EOF\n"


def _pages() -> list[str]:
    return [
        (
            "Polycab India Limited Date: October 09, 2026 "
            "NCLAT Principal Bench New Delhi against corporate insolvency "
            "admission under Section 9 IBC. The matter concerns Asier Metals "
            "and alleged operational debt 2.79 crore. "
            "The NCLAT order stayed and kept in abeyance the prior CIRP order. "
        ),
        "National Company Law Appellate Tribunal Company Appeal (AT) Insolvency 1940 2026. " * 2,
        "The hearing relates to prior order dated 07.10.2026 and dispute between parties. " * 2,
        (
            "The impugned order is stayed and be kept in abeyance till further orders. "
            "The appeal is next listed on 26.10.2026 within the first five cases. "
        ) * 2,
    ]


def _fake_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    class Page:
        def __init__(self, value: str) -> None:
            self.value = value

        def extract_text(self) -> str:
            return self.value

    class Reader:
        def __init__(self, source, strict: bool) -> None:
            self.pages = [Page(p) for p in _pages()]

    monkeypatch.setattr(module, "PdfReader", Reader)


def test_recovered_oct9_official_event_is_not_reclassified_as_current_cirp() -> None:
    event = module.original_announcement_identity(Path("."))
    assert event["source_event_seq"] == "106813081"
    assert event["source_event_category"] == "INSOLVENCY_RESOLUTION"
    assert len(event["source_event_id"]) == 64
    assert event["source_capture_payload_sha256"] == module.CAPTURE_PAYLOAD_SHA
    assert event["source_capture_git_blob_sha"] == module.CAPTURE_GIT_BLOB_SHA


def test_original_page_text_proves_stay_and_hearing_but_not_future_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_reader(monkeypatch)
    verified = module._pdf_identity(_pdf())
    assert verified["page_count"] == 4
    assert verified["disputed_claim_approx_inr_crore"] == 2.79
    assert verified["nclat_stay_order_date_ist"] == "2026-10-09"
    assert verified["nclt_prior_admission_order_date_ist"] == "2026-10-07"
    assert verified["next_hearing_reported_date_ist"] == "2026-10-26"
    assert verified["issuer_or_court_exact_text_reflects_stay"] is True
    assert verified["post_9oct_further_court_status_verified"] is False


def test_original_pdf_without_court_stay_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Page:
        def extract_text(self) -> str:
            return "Generic insolvency announcement without case context or order. " * 3

    class Reader:
        def __init__(self, source, strict: bool) -> None:
            self.pages = [Page() for _ in range(4)]

    monkeypatch.setattr(module, "PdfReader", Reader)
    with pytest.raises(ValueError, match="court stay and exact-date"):
        module._pdf_identity(_pdf())
    with pytest.raises(ValueError, match="PDF envelope invalid"):
        module._pdf_identity(b"<html>403 Forbidden</html>")


def test_no_redirect_or_bypass_on_access_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls = []

    class Response:
        status_code = 403
        url = module.ORIGINAL_URL
        content = b"Forbidden"

    def fake_get(url: str, **kwargs: object) -> Response:
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(module.requests, "get", fake_get)
    receipt, raw = module.probe_official(Path("."), attempts=3, pause_seconds=0)
    assert raw is None
    assert receipt["source_capture_state"] == "SOURCE_ACCESS_BLOCKED"
    assert receipt["issuer_currently_in_unstayed_cirp_proven"] is False
    assert receipt["market_expected_returns_calculated"] is False
    assert receipt["live_capital_allowed"] is False
    assert len(calls) == 1
    assert calls[0][0] == module.ORIGINAL_URL
    assert calls[0][1]["allow_redirects"] is False
    module.retain_original(tmp_path, receipt, raw)
    assert not (tmp_path / "raw").exists()


def test_original_extraction_and_source_custody(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _fake_reader(monkeypatch)

    class Response:
        status_code = 200
        url = module.ORIGINAL_URL
        content = _pdf()

    monkeypatch.setattr(module.requests, "get", lambda url, **kwargs: Response())
    receipt, raw = module.probe_official(Path("."), attempts=1, pause_seconds=0)
    assert receipt["source_capture_state"] == "ORIGINAL_NSE_PDF_TEXT_IDENTITY_VALIDATED"
    assert receipt["original_pdf_text_identity"]["page_count"] == 4
    assert receipt["original_pdf_text_identity"][
        "legal_inference"
    ] == "ADMISSION_ORDER_STAYED_PENDING_FURTHER_COURT_PROCESS_AS_OF_OCT09"
    assert receipt["issuer_currently_in_unstayed_cirp_proven"] is False
    assert receipt["court_order_post_oct9_updates_checked"] is False
    assert receipt["market_expected_returns_calculated"] is False
    assert receipt["portfolio_eligibility_allowed"] is False
    assert receipt["live_capital_allowed"] is False
    module.retain_original(tmp_path, receipt, raw)
    sha = hashlib.sha256(raw).hexdigest()
    assert (tmp_path / "raw" / "sha256" / f"{sha}.pdf").read_bytes() == raw
    assert json.loads((tmp_path / "source-receipt-v1.json").read_text()) == receipt
    module.retain_original(tmp_path, receipt, raw)
    changed = dict(receipt, issuer_currently_in_unstayed_cirp_proven=True)
    with pytest.raises(ValueError, match="cannot be rewritten"):
        module.retain_original(tmp_path, changed, raw)


def test_original_nse_candidate_id_is_immutable(tmp_path: Path) -> None:
    original = Path(module.CAPTURE_FILE)
    target = tmp_path / original
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(original.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Git blob drifted"):
        module.original_announcement_identity(tmp_path)
