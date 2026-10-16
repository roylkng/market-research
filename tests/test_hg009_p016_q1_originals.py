"""P016 original NSE source checks are auditable, never an investment signal."""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p016_q1_originals import (
    ARCHIVE_DIR,
    SOURCE_PATH,
    capture_one_q1,
    original_q1_registry,
    validate_q1_html,
    verify_q1_receipt,
)
from scripts.capture_hg009_p016_q1 import verify_all

ROOT = Path(__file__).resolve().parents[1]


def _issuer(symbol="ACE"):
    j, _ = original_q1_registry(ROOT)
    return next(x for x in j["issuer_rows"] if x["symbol"] == symbol)


def _synthetic_html(issuer, *, change: str | None = None) -> bytes:
    values = issuer["amounts_in_lakh"]
    table = [
        ("NSE Symbol", issuer["symbol"]),
        ("ISIN", issuer["isin"]),
        ("Nature of report standalone or consolidated", "Standalone"),
        ("Whether results are audited or unaudited for the quarter ended",
         "Unaudited"),
    ]
    labels = {
        "paid_up_equity_capital": "Paid-up equity share capital",
        "face_value_per_share_inr": "Face value of equity share capital",
        "revenue": "Revenue from operations",
        "other_income": "Other income",
        "pbt": "Total profit before tax",
        "pat": "Net Profit Loss for the period from continuing operations",
    }
    for key, label in labels.items():
        value = values[key]
        if change == key:
            value = value + 100
        table.append((label, f"{value:,.2f}"))
    return (
        "<html><body><h2>Integrated Filing — IndAS</h2>"
        "<p>Amount in (Lakhs), 30-06-2026 Q1 FY27</p>"
        "<table>" + "".join(
            f"<tr><td>{label}</td><td>{value}</td></tr>"
            for label, value in table
        ) + "</table></body></html>"
    ).encode("utf-8")


def test_two_original_q1_issuer_indas_filing_identities_pinned():
    registry, raw_sha = original_q1_registry(ROOT)
    assert len(raw_sha) == 64
    assert [x["symbol"] for x in registry["issuer_rows"]] == [
        "ACE", "ACUTAAS"
    ]
    assert registry["retained_original_HTML_bytes"] is False
    assert _issuer("ACE")["isin"] == "INE731H01025"
    assert _issuer("ACUTAAS")["isin"] == "INE00FF01025"


def test_original_q1_must_replay_each_amount_and_reporting_basis():
    for symbol in ("ACE", "ACUTAAS"):
        issuer = _issuer(symbol)
        original = _synthetic_html(issuer)
        record = validate_q1_html(
            original, issuer,
            recorded_at_utc="2026-10-16T06:00:00+00:00",
        )
        assert record["symbol"] == symbol
        assert record["isin"] == issuer["isin"]
        assert record["original_raw_sha256"] == hashlib.sha256(original).hexdigest()
        assert len(record["verified_statement_fields"]) == 6
        assert all(
            row["original_row_value_verified"]
            for row in record["verified_statement_fields"].values()
        )
        assert record["original_shares_are_june_basic_not_oct_diluted"] is True
        assert record["live_capital_allowed"] is False


def test_wrong_amount_issuer_isin_or_standalone_basis_rejected():
    issuer = _issuer()
    with pytest.raises(AlphaContractError, match="financial cell not matched"):
        validate_q1_html(
            _synthetic_html(issuer, change="pbt"), issuer,
            recorded_at_utc="2026-10-16T06:00:00Z",
        )
    other = copy.deepcopy(issuer)
    other["isin"] = "INE000000000"
    with pytest.raises(AlphaContractError, match="issuer/ISIN"):
        validate_q1_html(
            _synthetic_html(issuer), other,
            recorded_at_utc="2026-10-16T06:00:00Z",
        )
    other = _synthetic_html(issuer).replace(b"Unaudited", b"Audited")
    with pytest.raises(AlphaContractError, match="issuer/ISIN"):
        validate_q1_html(
            other, issuer, recorded_at_utc="2026-10-16T06:00:00Z",
        )


def test_real_original_success_is_archived_replayable_and_not_owner_fcf(
    tmp_path: Path,
):
    issuer = _issuer()
    raw = _synthetic_html(issuer)
    result = capture_one_q1(
        issuer,
        fetch=lambda url: (200, raw),
        observe_now=lambda: datetime(2026, 10, 16, 6, 1, tzinfo=UTC),
        root=tmp_path,
    )
    assert result["source_verified"] is True
    assert result["state"] == "ORIGINAL_NSE_Q1_FULL_HTML_REPLAY_VERIFIED"
    archive = tmp_path / result["archive_path"]
    assert archive.is_file()
    assert gzip.decompress(archive.read_bytes()) == raw
    assert str(ARCHIVE_DIR) in result["archive_path"]
    verify_q1_receipt(result, issuer=issuer, root=tmp_path)
    altered = copy.deepcopy(result)
    altered["original_raw_byte_count"] *= 2
    with pytest.raises(AlphaContractError, match="receipt signature altered"):
        verify_q1_receipt(altered, issuer=issuer, root=tmp_path)


def test_HTTP_failure_or_bad_html_never_certifies_original_or_cash(
    tmp_path: Path,
):
    issuer = _issuer()
    missing = capture_one_q1(
        issuer,
        fetch=lambda url: (403, None),
        observe_now=lambda: datetime(2026, 10, 16, 6, 2, tzinfo=UTC),
        root=tmp_path,
    )
    assert missing["state"] == "ORIGINAL_NSE_NOT_AVAILABLE"
    assert missing["archive_path"] is None
    verify_q1_receipt(missing, issuer=issuer, root=tmp_path)

    bad = capture_one_q1(
        issuer,
        fetch=lambda url: (200, b"<html>FAKE FILING</html>"),
        observe_now=lambda: datetime(2026, 10, 16, 6, 2, tzinfo=UTC),
        root=tmp_path,
    )
    assert bad["state"] == "ORIGINAL_NSE_ISSUER_OR_FINANCIAL_MISMATCH"
    assert bad["source_verified"] is False
    assert bad["untrusted_raw_sha256"] is not None
    assert bad["live_capital_allowed"] is False
    verify_q1_receipt(bad, issuer=issuer, root=tmp_path)


def test_source_archived_attestation_only_if_both_issuers_verified(
    tmp_path: Path,
):
    destination = tmp_path / SOURCE_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes((ROOT / SOURCE_PATH).read_bytes())
    incomplete = verify_all(tmp_path)
    assert incomplete["state"] == "INCOMPLETE_ORIGINAL_SOURCE_ATTESTATION"
    assert incomplete["verified_issuer_count"] == 0
    assert incomplete["live_capital_allowed"] is False


def test_standalone_verify_command_never_mutates_prior_sources():
    runner = subprocess.run(
        [
            sys.executable, "scripts/capture_hg009_p016_q1.py",
            "--run-id", "test-read-only", "--verify-only",
        ],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    result = json.loads(runner.stdout)
    assert result["not_current_diluted_equity"] is True
    assert result["live_capital_allowed"] is False
