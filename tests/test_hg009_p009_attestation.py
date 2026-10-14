"""P009 signed replay controls against issuer file, receipt and row tampering."""

from __future__ import annotations

import copy
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p009_attestation import (
    SOURCES,
    build_original_attestation,
    validate_original_attestation,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/hg009/hg009-p009-original-fy26-attestation-v1.json"


def _staged_root(tmp_path: Path) -> Path:
    from marketlab.hg009_p008_underwriting import PINNED

    for filename, _ in PINNED.values():
        destination = tmp_path / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / filename).read_bytes())
    for original in SOURCES.values():
        receipt = ROOT / original["receipt_path"]
        target = tmp_path / original["receipt_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(receipt.read_bytes())
        data = json.loads(receipt.read_text("utf-8"))
        source = ROOT / data["original_raw_repo_path"]
        destination = tmp_path / data["original_raw_repo_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    return tmp_path


def test_all_three_original_filings_replay_from_first_signed_receipt():
    attestation = build_original_attestation(ROOT)
    assert attestation["issuer_byte_attestation_successful_count"] == 3
    assert attestation["original_statement_financial_fields_replayed_count"] == 27
    assert attestation["historical_fiscal_period_end"] == "2026-03-31"
    assert [r["symbol"] for r in attestation["original_nse_filing_sources"]] == [
        "ACE", "ACUTAAS", "TRAVELFOOD",
    ]
    assert all(
        row["source_field_count_replayed"] == 9
        and row["field_values_are_not_normalized_owner_cash"] is True
        and row["capital_allowed"] is False
        for row in attestation["original_nse_filing_sources"]
    )
    assert attestation["all_ten_original_issuer_source_proofs_complete"] is False
    assert attestation["normalized_parent_owner_fcf_valuations_complete"] == 0
    assert attestation["risk_adjusted_expected_return_valuations_complete"] == 0
    assert attestation["paper_investment_eligible_count"] == 0
    assert attestation["live_capital_allowed"] is False
    validate_original_attestation(attestation, root=ROOT)


def test_changed_signed_receipt_rejected(tmp_path: Path):
    root = _staged_root(tmp_path)
    pin = SOURCES["ACUTAAS"]
    receipt_path = root / pin["receipt_path"]
    data = json.loads(receipt_path.read_text("utf-8"))
    data["captured_at_utc"] = "2026-10-10T09:00:00Z"
    receipt_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AlphaContractError, match="receipt hash changed"):
        build_original_attestation(root)


def test_original_archived_exchange_bytes_cannot_be_modified(tmp_path: Path):
    root = _staged_root(tmp_path)
    receipt = json.loads(
        (root / SOURCES["ACE"]["receipt_path"]).read_text("utf-8")
    )
    original_path = root / receipt["original_raw_repo_path"]
    raw = gzip.decompress(original_path.read_bytes())
    altered = raw.replace(b"41,727.00", b"11,727.00", 1)
    assert altered != raw
    original_path.write_bytes(gzip.compress(altered, mtime=0))
    with pytest.raises(AlphaContractError, match="raw file hash changed"):
        build_original_attestation(root)


def test_receipt_target_cannot_repoint_to_another_issuer(tmp_path: Path):
    root = _staged_root(tmp_path)
    receipt_path = root / SOURCES["TRAVELFOOD"]["receipt_path"]
    data = json.loads(receipt_path.read_text("utf-8"))
    data["symbol"] = "ACE"
    data.pop("receipt_sha256")
    data["receipt_sha256"] = digest(data)
    receipt_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AlphaContractError, match="receipt hash changed"):
        build_original_attestation(root)


def test_unchanged_source_snapshot_has_identical_signed_output_and_cli():
    attestation = build_original_attestation(ROOT)
    assert attestation == json.loads(OUTPUT.read_text("utf-8"))
    done = subprocess.run(
        [sys.executable, "scripts/materialize_hg009_p009.py", "--check"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    meta = json.loads(done.stdout)
    assert meta["issuers"] == 3
    assert meta["replayed_fields"] == 27
    assert meta["attestation_sha256"] == attestation["attestation_sha256"]
    assert meta["completed_valuations"] == 0
