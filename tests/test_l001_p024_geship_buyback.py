"""Synthetic original-PDF controls for L001 P024 GESHIP cap-table evidence."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.l001_p024_geship_buyback import (
    EVIDENCE,
    build_geship_capital_bridge,
    make_source_receipt,
    validate_bridge,
    validate_issuer_document,
    verify_source_receipt,
)
from scripts.archive_l001_p024_geship import _run

SEP = b"%PDF-" + b"synthetic-september-source" * 18
OCT = b"%PDF-" + b"synthetic-october-source" * 18
SEP_TEXT = """
The Great Eastern Shipping Company Limited
October 13, 2026
NSE Symbol GESHIP
Sub: Intimation regarding extinguishment of equity shares
paid up Equity Share Capital (Prior to buyback) 14,27,67,161
Shares being extinguished 18,58,941
Paid up share capital (Post Extinguishment) 14,09,08,220
NSDL ISIN INE017A01032
"""
OCT_TEXT = """
The Great Eastern Shipping Company Limited
October 19, 2026
NSE Symbol GESHIP
Kotak Securities Limited
Number bought back 1,94,000
Cumulative as on yesterday 29,01,660
Total Shares bought back 30,95,660
Average price 1516.7498
"""


def _stub_pdfs(monkeypatch):
    monkeypatch.setattr(
        "marketlab.l001_p024_geship_buyback._pdf_text",
        lambda raw: (5, SEP_TEXT) if raw == SEP else (2, OCT_TEXT),
    )


def _receipts():
    return {
        "SEPT_CANCELLATION": make_source_receipt(
            "SEPT_CANCELLATION", SEP, retrieved_at_utc="2026-10-21T00:01:00Z"
        ),
        "OCT19_DAILY": make_source_receipt(
            "OCT19_DAILY", OCT, retrieved_at_utc="2026-10-21T00:02:00Z"
        ),
    }


def test_distinguish_legally_extinguished_from_daily_purchased(monkeypatch):
    _stub_pdfs(monkeypatch)
    sources = {"SEPT_CANCELLATION": SEP, "OCT19_DAILY": OCT}
    receipts = _receipts()
    report = build_geship_capital_bridge(sources, receipts)
    assert report["certified_paidup_shares_before_september_buyback"] == 142767161
    assert report["certified_september_shares_extinguished"] == 1858941
    assert report["certified_post_september_paidup_shares"] == 140908220
    assert report["oct19_issuer_report_total_cumulative_purchased"] == 3095660
    assert report["oct19_issuer_report_daily_shares_purchased"] == 194000
    assert report["purchased_since_september_certificate_not_in_this_certificate"] == 1236719
    assert report["only_under_assumption_no_issuance_or_other_cancellation"][
        "if_all_later_repurchased_shares_legal_extinguished"
    ] == 139671501
    assert report["later_legal_cancellation_since_september_verified"] is False
    assert report["oct19_current_paidup_or_fully_diluted_shares_verified"] is False
    assert report["oct19_current_paidup_shares"] is None
    assert report["company_valuation_or_1y_3y_expected_return"] is None
    assert report["live_capital_allowed"] is False
    validate_bridge(report, originals=sources, receipts=receipts)


def test_cancellation_requires_original_page_count_issuer_and_isin(monkeypatch):
    _stub_pdfs(monkeypatch)
    receipt = _receipts()["SEPT_CANCELLATION"]
    verify_source_receipt("SEPT_CANCELLATION", SEP, receipt)
    with pytest.raises(AlphaContractError, match="source receipt/PDF different|receipt hash altered"):
        altered = copy.deepcopy(receipt)
        altered["original_pdf_sha256"] = "a" * 64
        verify_source_receipt("SEPT_CANCELLATION", SEP, altered)
    monkeypatch.setattr(
        "marketlab.l001_p024_geship_buyback._pdf_text",
        lambda raw: (5, SEP_TEXT.replace("INE017A01032", "INE999A01099")),
    )
    with pytest.raises(AlphaContractError, match="ISIN absent"):
        validate_issuer_document("SEPT_CANCELLATION", SEP)
    monkeypatch.setattr(
        "marketlab.l001_p024_geship_buyback._pdf_text",
        lambda raw: (4, SEP_TEXT),
    )
    with pytest.raises(AlphaContractError, match="page count"):
        validate_issuer_document("SEPT_CANCELLATION", SEP)


def test_dynamic_daily_report_cannot_be_reused_after_newer_date(monkeypatch):
    _stub_pdfs(monkeypatch)
    assert "dailyreport.pdf" in EVIDENCE["OCT19_DAILY"]["url"]
    monkeypatch.setattr(
        "marketlab.l001_p024_geship_buyback._pdf_text",
        lambda raw: (2, OCT_TEXT.replace("October 19, 2026", "October 21, 2026")),
    )
    with pytest.raises(AlphaContractError, match="missing October 19, 2026"):
        validate_issuer_document("OCT19_DAILY", OCT)


def test_actual_capture_clock_is_proven_and_cannot_predate_issuer(monkeypatch):
    _stub_pdfs(monkeypatch)
    with pytest.raises(AlphaContractError, match="backdate"):
        make_source_receipt(
            "SEPT_CANCELLATION", SEP, retrieved_at_utc="2026-10-12T23:59:59Z"
        )
    with pytest.raises(AlphaContractError, match="timezone-aware"):
        make_source_receipt(
            "SEPT_CANCELLATION", SEP, retrieved_at_utc="2026-10-21T00:00:00"
        )


def test_issuer_original_archive_script_source_or_failure(monkeypatch, tmp_path: Path):
    _stub_pdfs(monkeypatch)
    urls = {
        EVIDENCE["SEPT_CANCELLATION"]["url"]: SEP,
        EVIDENCE["OCT19_DAILY"]["url"]: OCT,
    }
    monkeypatch.setattr(
        "scripts.archive_l001_p024_geship._download",
        lambda url: (200, urls[url]),
    )
    made = _run(tmp_path, "unit-1")
    assert made["state"] == "NEW_ORIGINAL_GESHIP_SOURCE_BRIDGE_SEALED"
    path = tmp_path / "research/l001/l001-p024-geship-buyback-capital-bridge-v1.json"
    obj = json.loads(path.read_text("utf-8"))
    assert obj["issuer_source_custody"]["OCT19_DAILY"]["original_pdf_sha256"] == (
        hashlib.sha256(OCT).hexdigest()
    )
    assert _run(tmp_path, "unit-1")["state"] == "SEALED_SOURCE_ALREADY_REPLAYABLE"
    monkeypatch.setattr(
        "scripts.archive_l001_p024_geship._download",
        lambda url: (403, None),
    )
    blocked = _run(tmp_path / "failure", "unit-2")
    assert blocked["state"] == "PENDING_ORIGINAL_BUYBACK_CUSTODY"
    assert len(blocked["missing"]) == 2
    assert not (tmp_path / "failure" / path.relative_to(tmp_path)).exists()


def test_report_hash_change_cannot_produce_investable_alpha(monkeypatch):
    _stub_pdfs(monkeypatch)
    originals = {"SEPT_CANCELLATION": SEP, "OCT19_DAILY": OCT}
    receipts = _receipts()
    packet = build_geship_capital_bridge(originals, receipts)
    packet["oct19_current_paidup_shares"] = 139671501
    with pytest.raises(AlphaContractError, match="research SHA modified"):
        validate_bridge(packet, originals=originals, receipts=receipts)
