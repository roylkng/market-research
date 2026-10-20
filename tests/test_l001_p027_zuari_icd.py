"""P027 original Zuari Agro September 2026 ICD evidence, no double-counted NAV."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.l001_p027_zuari_icd import (
    EVIDENCE,
    build_parent_icd_cash_bridge,
    make_receipt,
    validate_bridge,
    validate_issuer_pdf,
    verify_receipt,
)
from scripts.archive_l001_p027_zuari_icd import (
    FRONTIER_PATH,
    _run,
)

ROOT = Path(__file__).resolve().parents[1]
A = b"%PDF-1.4 " + b"A" * 590
B = b"%PDF-1.4 " + b"B" * 590
SEP18 = """
ZUARI AGRO CHEMICALS LIMITED
18th September, 2026
National Stock Exchange of India Ltd NSE Symbol: ZUARI
Under SEBI Regulation 30
Inter Corporate Deposits Rs.258.50 Crore availed by the Company
from Zuari Industries Limited
today 18th September, 2026 repaid ICDs amounting to Rs. 214.50 Crore
"""
SEP30 = """
ZUARI AGRO CHEMICALS LIMITED
30th September, 2026
National Stock Exchange of India Ltd NSE Symbol: ZUARI
With reference to 18 September earlier repayment Rs. 214.50 Crore
total ICDs Rs.258.50 Crore from Zuari Industries Limited
today repaid the balance ICDs amounting to Rs. 44 Crore
Consequently outstanding ICDs from Zuari Industries Limited stand Nil.
"""


def _fake_pdfs(monkeypatch):
    monkeypatch.setattr(
        "marketlab.l001_p027_zuari_icd._read_pdf",
        lambda raw: (1, SEP18) if raw == A else (1, SEP30),
    )


def _frontier():
    return json.loads((ROOT / FRONTIER_PATH).read_text(encoding="utf-8"))


def _receipts():
    return {
        "SEPT18": make_receipt(
            "SEPT18", A, captured_at_utc="2026-10-21T00:00:00Z",
        ),
        "SEPT30": make_receipt(
            "SEPT30", B, captured_at_utc="2026-10-21T00:01:00Z",
        ),
    }


def test_original_zuari_agro_issuer_is_not_zuari_industries(monkeypatch):
    _fake_pdfs(monkeypatch)
    assert "zuari.in" in EVIDENCE["SEPT18"]["url"]
    assert validate_issuer_pdf("SEPT18", A)["issuer_symbol_ZUARI_NOT_PARENT"] == "ZUARI"
    assert validate_issuer_pdf("SEPT30", B)["parent_creditor_symbol"] == "ZUARIIND"


def test_two_filed_repayments_are_258_50_not_new_equity(monkeypatch):
    _fake_pdfs(monkeypatch)
    originals = {"SEPT18": A, "SEPT30": B}
    receipts = _receipts()
    report = build_parent_icd_cash_bridge(
        originals, receipts, earlier_frontier=_frontier()
    )
    facts = report["issuer_published_ICD_parent_creditor_cash_event"]
    assert facts["sep18_deposit_principal_repayment_cr"] == 214.50
    assert facts["sep30_final_deposit_principal_repayment_cr"] == 44
    assert facts["total_principal_icd_repaid_cr"] == 258.50
    assert facts["reported_icd_from_parent_outstanding_after_sep30_cr"] == 0
    assert facts["incremental_parent_net_asset_value_from_repayment_alone_cr"] == 0
    assert facts["incremental_new_group_profit_from_principal_repayment_cr"] == 0
    assert facts["unverified_parent_cash_increase_reconciled_cr"] is None
    assert facts["unverified_parent_beginning_loan_receivable_decrease_cr"] is None
    assert report["consolidation_group_and_intragroup_elimination_reconciled"] is False
    assert report["parent_creditor_lender_waterfall_known"] is False
    assert report["pledged_shares_original_sep30_depository_source_verified"] is False
    assert report["fully_diluted_parent_equity_current"] is None
    assert report["buy_rating_or_price_target"] is None
    assert report["live_capital_allowed"] is False
    validate_bridge(report, originals=originals, receipts=receipts, earlier_frontier=_frontier())


def test_bad_date_issuer_and_number_are_rejected(monkeypatch):
    _fake_pdfs(monkeypatch)
    monkeypatch.setattr(
        "marketlab.l001_p027_zuari_icd._read_pdf",
        lambda _: (1, SEP30.replace("44 Crore", "55 Crore")),
    )
    with pytest.raises(AlphaContractError, match="repayment proof missing"):
        validate_issuer_pdf("SEPT30", B)
    monkeypatch.setattr(
        "marketlab.l001_p027_zuari_icd._read_pdf",
        lambda _: (1, SEP30.replace("NSE Symbol: ZUARI", "NSE Symbol: ZUARIIND")),
    )
    with pytest.raises(AlphaContractError, match="wrong issuer"):
        validate_issuer_pdf("SEPT30", B)
    monkeypatch.setattr("marketlab.l001_p027_zuari_icd._read_pdf", lambda _: (2, SEP30))
    with pytest.raises(AlphaContractError, match="page count"):
        validate_issuer_pdf("SEPT30", B)


def test_source_clock_and_receipt_hash_prohibit_retrospective_repair(monkeypatch):
    _fake_pdfs(monkeypatch)
    with pytest.raises(AlphaContractError, match="backdated"):
        make_receipt("SEPT30", B, captured_at_utc="2026-09-10T00:00:00Z")
    with pytest.raises(AlphaContractError, match="lacks offset"):
        make_receipt("SEPT18", A, captured_at_utc="2026-10-21T12:00:00")
    a = _receipts()["SEPT18"]
    a["raw_pdf_sha256"] = "f" * 64
    with pytest.raises(AlphaContractError, match="receipt hash modified"):
        verify_receipt("SEPT18", A, a)


def test_original_source_archive_script_fail_closed_and_idempotent(monkeypatch, tmp_path):
    _fake_pdfs(monkeypatch)
    original_frontier = ROOT / FRONTIER_PATH
    dst = tmp_path / FRONTIER_PATH
    dst.parent.mkdir(parents=True)
    dst.write_bytes(original_frontier.read_bytes())
    specs = {EVIDENCE["SEPT18"]["url"]: A, EVIDENCE["SEPT30"]["url"]: B}
    monkeypatch.setattr(
        "scripts.archive_l001_p027_zuari_icd._download",
        lambda url: (200, specs[url]),
    )
    result = _run(tmp_path, run_id="test1")
    assert result["state"] == "ORIGINAL_ZUARI_258_50CR_PRINCIPAL_REPAYMENT_VERIFIED"
    assert result["new_parent_equity_value_from_existing_loan_repayment_cr"] == 0
    report_path = tmp_path / (
        "research/l001/l001-p027-zuari-original-icd-cash-bridge-v1.json"
    )
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["original_issuer_source_documents"]["SEPT30"][
        "raw_pdf_sha256"
    ] == hashlib.sha256(B).hexdigest()
    again = _run(tmp_path, run_id="test1")
    assert again["state"] == "ORIGINAL_ZUARI_ICD_SOURCE_ALREADY_REPLAY_VERIFIED"
    monkeypatch.setattr(
        "scripts.archive_l001_p027_zuari_icd._download",
        lambda url: (403, None),
    )
    failure_dir = tmp_path / "failure"
    result = _run(failure_dir, run_id="test2")
    assert result["state"] == "ORIGINAL_ZUARI_ISSUER_SOURCE_INCOMPLETE"
    assert result["source_completed_count"] == 0
    assert not (
        failure_dir / "research/l001/l001-p027-zuari-original-icd-cash-bridge-v1.json"
    ).exists()


def test_signed_source_report_cannot_be_turn_into_buy_rating(monkeypatch):
    _fake_pdfs(monkeypatch)
    originals = {"SEPT18": A, "SEPT30": B}
    receipts = _receipts()
    report = build_parent_icd_cash_bridge(
        originals, receipts, earlier_frontier=_frontier()
    )
    corrupted = copy.deepcopy(report)
    corrupted["buy_rating_or_price_target"] = 450
    with pytest.raises(AlphaContractError, match="cashbridge changed"):
        validate_bridge(
            corrupted,
            originals=originals,
            receipts=receipts,
            earlier_frontier=_frontier(),
        )
