"""A1 synthetic PDF tests: original 2026 HG009 calendar is immutable."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p004_a1_muhurat import (
    AMENDMENT_ID,
    CAS_LAST_TRADE_UTC,
    FIRST_TRADE_UTC,
    NONCAS_LAST_TRADE_UTC,
    ORIGINAL_CALENDAR_SHA,
    ORIGINAL_HG009_CLOCK_SHA,
    PDF_DIR,
    SAFE_AFTER_ALL_SESSIONS_UTC,
    SOURCE_URL,
    build_amendment,
    validate_circular_receipt,
    validate_original_nse_circular,
)

ROOT = Path(__file__).resolve().parents[1]
RAW = b"%PDF-" + b"synthetic-test-not-an-exchange-document-" * 6
SAMPLE_TEXT = """
National Stock Exchange of India Limited
Department CAPITAL MARKET SEGMENT
Download Ref No NSE/CMTR/76941 Date: October 19, 2026
Circular Ref No 149/2026
Sunday, November 08, 2026 Muhurat Trading
Preopen order entry 14:05
Normal Market Continuous Trading 14:20
Closing Auction Session CAS normal close 15:15
CAS matching 15:30 to 15:35
Normal Market Close time for Non-CAS securities 15:30
Trade Modification cut-off time 16:15
All trades executed in this Diwali Muhurat session result in
settlement obligations
"""


def _source(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "marketlab.hg009_p004_a1_muhurat._pdf_text",
        lambda raw: (2, SAMPLE_TEXT),
    )
    proof = validate_original_nse_circular(RAW)
    receipt = {
        "schema_version": 1,
        "receipt_id": "HG009-P004-A1-NSE-CIRCULAR-RECEIPT-v1",
        "source_url": SOURCE_URL,
        "captured_at_utc": "2026-10-20T15:31:02Z",
        "source_state": "ORIGINAL_CIRCULAR_ARCHIVED",
        "actual_http_status": 200,
        "error_class": None,
        "original_pdf_sha256": hashlib.sha256(RAW).hexdigest(),
        "original_pdf_repo_path": str(
            PDF_DIR / f"CMTR76941-{hashlib.sha256(RAW).hexdigest()}.pdf"
        ),
        "original_circular_proof": proof,
        "live_capital_allowed": False,
    }
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def test_oct19_exchange_paper_proves_sunday_Nov08_without_rewriting_Oct15():
    from marketlab.hg009_p004_clock import load_p004_inputs

    calendar, _, _, _ = load_p004_inputs(ROOT)
    assert calendar.sha256 == ORIGINAL_CALENDAR_SHA
    assert "2026-11-08" in calendar.unresolved_special_dates
    assert "2026-11-08" not in {
        s.session_date for s in calendar.sessions
    }
    assert "2026-10-20" not in {
        s.session_date for s in calendar.sessions
    }
    assert FIRST_TRADE_UTC == "2026-11-08T08:50:00+00:00"
    assert CAS_LAST_TRADE_UTC == "2026-11-08T10:05:00+00:00"
    assert NONCAS_LAST_TRADE_UTC == "2026-11-08T10:00:00+00:00"
    assert SAFE_AFTER_ALL_SESSIONS_UTC == "2026-11-08T10:45:00+00:00"


def test_calendar_amendment_moves_H20_to_Nov12_and_retains_H1_H5(
    monkeypatch: pytest.MonkeyPatch,
):
    receipt = _source(monkeypatch)
    output = build_amendment(
        root=ROOT, receipt=receipt, original_pdf=RAW
    )
    assert output["amendment_id"] == AMENDMENT_ID
    assert output["original_oct14_P004_clock_sha256"] == ORIGINAL_HG009_CLOCK_SHA
    assert output["h1_existing_original_dates_unchanged"] == ["2026-10-15"]
    assert output["h5_existing_original_dates_unchanged"] == [
        "2026-10-15", "2026-10-16", "2026-10-19",
        "2026-10-21", "2026-10-22",
    ]
    h20 = output["amended_H20_20_exact_sessions"]
    assert len(h20) == 20
    assert h20.count("2026-11-08") == 1
    assert h20[-1] == "2026-11-12"
    assert "2026-11-10" not in h20
    assert output["original_H20_state_retained"] == (
        "UNRESOLVED_EXCHANGE_SPECIAL_SESSION_BLOCKS_RESULT"
    )
    assert output["H20_new_outcomes_observed_or_calculated"] is False
    assert output["H60_still_requires_official_2027_calendar"] is True
    assert output["live_capital_allowed"] is False
    unsigned = copy.deepcopy(output)
    assert output["amendment_sha256"] == digest({
        k: v for k, v in unsigned.items() if k != "amendment_sha256"
    })


def test_two_page_pdf_source_requires_original_exact_semantics(
    monkeypatch: pytest.MonkeyPatch,
):
    _source(monkeypatch)
    monkeypatch.setattr(
        "marketlab.hg009_p004_a1_muhurat._pdf_text",
        lambda raw: (2, SAMPLE_TEXT.replace("15:35", "15:15")),
    )
    with pytest.raises(AlphaContractError, match="missing mandatory evidence"):
        validate_original_nse_circular(RAW)
    monkeypatch.setattr(
        "marketlab.hg009_p004_a1_muhurat._pdf_text",
        lambda raw: (1, SAMPLE_TEXT),
    )
    with pytest.raises(AlphaContractError, match="exact 2 pages"):
        validate_original_nse_circular(RAW)


def test_official_source_receipt_cannot_be_backdated_or_tampered(
    monkeypatch: pytest.MonkeyPatch,
):
    receipt = _source(monkeypatch)
    validate_circular_receipt(receipt, raw=RAW)
    altered = copy.deepcopy(receipt)
    altered["captured_at_utc"] = "2026-11-09T12:00:00Z"
    altered.pop("receipt_sha256")
    altered["receipt_sha256"] = digest(altered)
    with pytest.raises(AlphaContractError, match="not captured prospectively"):
        validate_circular_receipt(altered, raw=RAW)

    wrong = copy.deepcopy(receipt)
    wrong["source_url"] = "https://example.invalid/muhurat.pdf"
    wrong.pop("receipt_sha256")
    wrong["receipt_sha256"] = digest(wrong)
    with pytest.raises(AlphaContractError, match="not admissible"):
        validate_circular_receipt(wrong, raw=RAW)

    changed = copy.deepcopy(receipt)
    changed["original_circular_proof"]["non_auction_continuous_market_close_ist"] = (
        "15:15"
    )
    changed.pop("receipt_sha256")
    changed["receipt_sha256"] = digest(changed)
    with pytest.raises(AlphaContractError, match="source page proof differs"):
        validate_circular_receipt(changed, raw=RAW)


def test_original_pdf_byte_change_rejected_without_ghost_admission(
    monkeypatch: pytest.MonkeyPatch,
):
    receipt = _source(monkeypatch)
    with pytest.raises(AlphaContractError, match="not admissible"):
        validate_circular_receipt(receipt, raw=RAW + b"tampered")
