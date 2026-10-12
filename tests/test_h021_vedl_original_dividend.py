from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import acquire_h021_vedl_dividend_original as p012


def _original_stub() -> bytes:
    return b"%PDF-1.6\n" + b"x" * 750 + b"\n%%EOF\n"


def _pdf_page_stub(monkeypatch: pytest.MonkeyPatch, text: str | None = None) -> None:
    original_text = text or (
        "VEDL/Sec./SE/26-27/108 October 08, 2026\n"
        "Vedanta Limited Scrip Code: VEDL\n"
        "Board of Directors approved the First Interim Dividend 2026-27 "
        "of Rs 5/- per equity share. Further, as intimated, the record date "
        "for the payment is Wednesday, October 14, 2026.\n"
        "The approval has been accorded at 01:00 PM IST.\n"
    )

    class FakePage:
        def extract_text(self) -> str:
            return original_text

    class FakeReader:
        def __init__(self, _stream: object, *, strict: bool) -> None:
            self.pages = [FakePage()]

    monkeypatch.setattr(p012, "PdfReader", FakeReader)


def test_oct8_archived_announcement_proves_public_url_before_h021_entry() -> None:
    anchor = p012.verify_archived_preentry_event(Path("."))
    assert anchor["ss002_capture_id"] == "SS002-P001-2026-10-08-v1"
    assert anchor["ss002_capture_git_blob"] == (
        "123c858432d2f4af86d76792a85c727077ff7ec0"
    )
    assert anchor["source_public_broadcast_at_utc"] == "2026-10-08T07:41:56Z"
    assert anchor["source_was_public_before_oct12_planned_entry"] is True
    assert anchor["original_pdf_url_discovered_before_entry"] == p012.ORIGINAL_SOURCE_URL


def test_archived_nse_announcement_tamper_rejected(tmp_path: Path) -> None:
    raw = p012.FROZEN_ANNOUNCEMENT_PATH.read_bytes()
    target = tmp_path / p012.FROZEN_ANNOUNCEMENT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="archived announcement blob was modified"):
        p012.verify_archived_preentry_event(tmp_path)


def test_one_original_pdf_page_proves_only_issuer_record_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pdf_page_stub(monkeypatch)
    verified = p012.verify_original_dividend_pdf(_original_stub())
    assert verified["issuer_reported_dividend_per_share_inr"] == 5
    assert verified["issuer_reported_record_date_ist"] == "2026-10-14"
    assert verified["issuer_reported_board_declaration_date"] == "2026-10-08"
    assert verified["original_pdf_page_count"] == 1
    assert verified["ex_date_confirmed_by_this_pdf"] is False
    assert verified["cash_dividend_payable_or_received_proven"] is False
    assert verified["hypothetical_entry_holder_dividend_entitlement_proven"] is False


def test_malformed_original_pdf_or_changed_company_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pdf_page_stub(monkeypatch)
    with pytest.raises(ValueError, match="PDF byte envelope"):
        p012.verify_original_dividend_pdf(b"<html>Cloudflare challenge</html>")
    _pdf_page_stub(monkeypatch, text="Unrelated firm declares Rs 5 dividend" * 20)
    with pytest.raises(ValueError, match="missing source anchor"):
        p012.verify_original_dividend_pdf(_original_stub())


def test_source_acquisition_and_custody_without_return_approval(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _pdf_page_stub(monkeypatch)
    raw = _original_stub()
    calls = []

    class Response:
        status_code = 200
        content = raw
        url = p012.ORIGINAL_SOURCE_URL

    def get(url: str, **kwargs: object) -> Response:
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(p012.requests, "get", get)
    archive = p012.verify_archived_preentry_event(Path("."))
    receipt, pdf = p012.download_original(archive=archive, attempts=2, retry_delay=0)
    assert receipt["state"] == (
        "OFFICIAL_PDF_BYTES_AND_ISSUER_TEXT_CAPTURED_NOT_ENTITLEMENT_AUDITED"
    )
    assert receipt["first_original_announcement_provenance"] == archive
    assert receipt["source_url"] == p012.ORIGINAL_SOURCE_URL
    assert pdf == raw
    assert receipt["actual_ex_date_verified_by_board_letter"] is False
    assert receipt["h021_return_basis_total_return_certified"] is False
    assert receipt["actual_h021_trade_and_entitlement_proven"] is False
    assert receipt["live_capital_allowed"] is False
    assert len(calls) == 1
    assert calls[0][1]["allow_redirects"] is False
    p012.retain_capture(tmp_path, receipt, pdf)
    path = tmp_path / "original" / "sha256" / f"{receipt['original_pdf_sha256']}.pdf"
    assert path.read_bytes() == raw
    assert json.loads((tmp_path / "source-receipt-v1.json").read_text()) == receipt
    p012.retain_capture(tmp_path, receipt, pdf)


def test_http403_is_never_bypassed_or_retried(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempts = []

    class Response:
        status_code = 403
        content = b"Forbidden"
        url = p012.ORIGINAL_SOURCE_URL

    def get(url: str, **kwargs: object) -> Response:
        attempts.append(url)
        return Response()

    monkeypatch.setattr(p012.requests, "get", get)
    receipt, data = p012.download_original(
        archive={"source_was_public_before_oct12_planned_entry": True},
        attempts=3, retry_delay=0,
    )
    assert data is None
    assert receipt["state"] == "ACCESS_BLOCKED_NO_BYPASS"
    assert len(attempts) == 1
    assert receipt["original_pdf_sha256"] is None
    p012.retain_capture(tmp_path, receipt, data)
    assert not (tmp_path / "original").exists()


def test_invalid_pdf_http200_never_claims_source_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status_code = 200
        content = b"Access denied HTML response"
        url = p012.ORIGINAL_SOURCE_URL

    monkeypatch.setattr(p012.requests, "get", lambda url, **kwargs: Response())
    receipt, raw = p012.download_original(archive={}, attempts=1)
    assert receipt["state"] == "INVALID_OR_UNREADABLE_OFFICIAL_PDF"
    assert receipt["original_pdf_sha256"] is None
    assert raw is None


def test_forged_entitlement_and_receipt_change_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pdf_page_stub(monkeypatch)
    raw = _original_stub()
    event = p012.verify_archived_preentry_event(Path("."))
    receipt = p012._receipt(
        "OFFICIAL_PDF_BYTES_AND_ISSUER_TEXT_CAPTURED_NOT_ENTITLEMENT_AUDITED",
        http_status=200, raw=raw,
        original_text=p012.verify_original_dividend_pdf(raw), archive=event,
        error="DECLARATION_NOT_ENTITLEMENT",
    )
    receipt["actual_h021_trade_and_entitlement_proven"] = True
    with pytest.raises(ValueError, match="not authentic"):
        p012.verify_receipt(receipt, raw)
    receipt["packet_sha256"] = p012._canonical_hash(
        {k: v for k, v in receipt.items() if k != "packet_sha256"}
    )
    with pytest.raises(ValueError, match="may not authorize"):
        p012.verify_receipt(receipt, raw)


def test_redirection_and_retry_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status_code = 302
        content = b""
        url = p012.ORIGINAL_SOURCE_URL

    monkeypatch.setattr(p012.requests, "get", lambda url, **kwargs: Response())
    receipt, raw = p012.download_original(archive={}, attempts=1)
    assert receipt["state"] == "UNFOLLOWED_REDIRECT"
    assert raw is None
    with pytest.raises(ValueError, match="between 1 and 3"):
        p012.download_original(archive={}, attempts=4)
    with pytest.raises(ValueError, match="retry delay"):
        p012.download_original(archive={}, retry_delay=-1)



def test_exact_ordinal_1st_from_original_nse_pdf_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Visually verified original issuer PDF says '1st Interim Dividend';
    # earlier normalized sources spelled it out as 'First'.
    official = (
        "VEDL/Sec./SE/26-27/108 October 08, 2026 "
        "Vedanta Limited Scrip Code: VEDL "
        "Board of Directors approved the 1st Interim Dividend 2026-27 "
        "of Rs 5/- per equity share on face value of Rs 1/- per equity share. "
        "The record date shall be Wednesday, October 14, 2026. "
        "The approval has been accorded at 01:00 PM IST."
    )
    _pdf_page_stub(monkeypatch, text=official)
    result = p012.verify_original_dividend_pdf(_original_stub())
    assert result["issuer_reported_dividend_per_share_inr"] == 5.0
    assert result["issuer_reported_record_date_ist"] == "2026-10-14"
    assert result["ex_date_confirmed_by_this_pdf"] is False


def test_second_dividend_cannot_pass_original_first_dividend_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unrelated = (
        "VEDL/Sec./SE/26-27/108 October 08, 2026 "
        "Vedanta Limited Scrip Code: VEDL "
        "Board approved the 2nd Interim Dividend 2026-27 "
        "of Rs 5/- per equity share. The record date is "
        "Wednesday, October 14, 2026. "
        "The approval was at 01:00 PM IST."
    )
    _pdf_page_stub(monkeypatch, text=unrelated)
    with pytest.raises(ValueError, match="different numbered dividend"):
        p012.verify_original_dividend_pdf(_original_stub())



def test_original_pdf_still_verifies_when_text_parser_splits_ordinal_and_punctuation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Actual archived original PDF renders "1st", but PDF text parsers may
    # split its ordinal, fiscal-year dash, rupee suffix or record-date comma.
    extracted = (
        "VEDL/Sec./SE/26-27/108 October 08, 2026. "
        "Scrip Code: VEDL for Vedanta Limited. "
        "Board approved 1 st Interim Dividend 2026 - 27 "
        "of ₹ 5 /- per equity share. "
        "The record date for payment is Wednesday, October 14, 2026. "
        "Board approval was at 01:00 PM IST."
    )
    _pdf_page_stub(monkeypatch, text=extracted)
    evidence = p012.verify_original_dividend_pdf(_original_stub())
    assert evidence["issuer_reported_dividend_per_share_inr"] == 5.0
    assert evidence["issuer_reported_record_date_ist"] == "2026-10-14"
    assert evidence["cash_dividend_payable_or_received_proven"] is False


def test_missing_issuer_or_dividend_amount_remains_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other = (
        "Scrip Code: VEDL October 08, 2026. "
        "Board approved First Interim Dividend 2026-27 "
        "of Rs 5/- per equity share. "
        "record date Wednesday October 14, 2026, "
        "approved at 01:00 PM IST."
    )
    _pdf_page_stub(monkeypatch, text=other)
    with pytest.raises(ValueError, match="vedanta limited"):
        p012.verify_original_dividend_pdf(_original_stub())
    missing_amount = other.replace("Scrip Code: VEDL", "Vedanta Limited Scrip Code: VEDL").replace(
        "5/- per", "3/- per"
    )
    _pdf_page_stub(monkeypatch, text=missing_amount)
    with pytest.raises(ValueError, match="5 per equity share"):
        p012.verify_original_dividend_pdf(_original_stub())
