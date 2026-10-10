from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.hg007_ownership_gap import (
    EVIDENCE_ID,
    QIP_PATH,
    RAW_PATH,
    RAW_SHA256,
    build_original_empty_api_evidence,
)


def test_original_oct10_nse_no_data_response_is_hash_pinned() -> None:
    source = RAW_PATH.read_bytes()
    assert source == b'{"data":[],"msg":"no data found"}'
    assert len(source) == 33
    assert hashlib.sha256(source).hexdigest() == RAW_SHA256
    report = build_original_empty_api_evidence(Path("."))
    assert report["evidence_id"] == EVIDENCE_ID
    assert report["source"]["original_raw_sha256"] == RAW_SHA256
    assert report["source"]["original_data_array_length"] == 0
    assert report["source"]["original_message"] == "no data found"
    assert report["source"]["http_status"] == 200
    assert report["source"]["github_workflow_run_id"] == 38055817025
    assert report["classification"] == "OFFICIAL_EXACT_ENDPOINT_NO_DATA_NOT_NO_FILING_EXISTS"
    assert report["current_official_september_ownership_filings_verified"] is False
    assert report["current_promoter_pledged_share_quantity_verified"] is False
    assert report["investment_governance_risk_score_calculated"] is False
    assert report["live_capital_allowed"] is False


def test_qip_arithmetic_does_not_prove_september_pledge_or_option_count() -> None:
    report = build_original_empty_api_evidence(Path("."))
    june = report["original_june_2026_snapshot"]
    sep = report["september_2026_qip_original_verified"]
    assert june["issued_basic_shares"] == 401492045
    assert june["outstanding_esop_shares"] == 2467620
    assert june["promoter_pledge_disclosed"] is False
    assert june["promoter_percent_original_rounded"] == 56.12
    assert sep["issued_basic_shares_after_allotment"] == 419602518
    assert sep["additional_qip_shares"] == 18110473
    assert sep["unchanged_promoter_shares_mechanical_post_qip_percent"] == pytest.approx(
        53.69779287168148
    )
    assert sep["september_original_reg31_shares_and_pledge_verified"] is False
    claim = report["unverified_secondary_pledge_claim"]
    assert claim["reported_pledged_shares_not_officially_source_verified"] == 4900000
    assert claim["current_promoter_pledge_status"] == "UNKNOWN_PENDING_ORIGINAL_FILING"
    assert claim["treat_as_governance_risk_pending_review_not_confirmed"] is True
    assert report["current_employee_option_issued_outstanding_reverified"] is False
    assert report["company_expected_returns_calculated"] is False


def test_altered_raw_official_response_or_prior_qip_denominator_rejected(
    tmp_path: Path,
) -> None:
    for item in (RAW_PATH, QIP_PATH):
        dest = tmp_path / item
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(item.read_bytes())
    assert build_original_empty_api_evidence(tmp_path)["live_capital_allowed"] is False
    master = tmp_path / RAW_PATH
    master.write_bytes(b'{"data":[{"symbol":"INOXGREEN"}]}')
    with pytest.raises(ValueError, match="raw bytes drifted"):
        build_original_empty_api_evidence(tmp_path)
    master.write_bytes(RAW_PATH.read_bytes())
    qip = tmp_path / QIP_PATH
    qip.write_bytes(qip.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="upstream drifted"):
        build_original_empty_api_evidence(tmp_path)


def test_cli_is_reproducible_without_network_or_investment_promotion(tmp_path: Path) -> None:
    target = tmp_path / "source-ledger.json"
    cmd = [
        sys.executable, "scripts/audit_hg007_nse_empty_source.py",
        "--out", str(target),
    ]
    first = subprocess.run(cmd, check=True, capture_output=True, text=True)
    observed = json.loads(first.stdout)
    assert observed["record_count_for_this_api_request"] == 0
    assert observed["september_original_shareholding_confirmed"] is False
    assert observed["pledged_shares_confirmed"] is False
    assert observed["live_capital_allowed"] is False
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload == build_original_empty_api_evidence(Path("."))
    subprocess.run(
        cmd + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    target.write_text(target.read_text(encoding="utf-8") + "altered", encoding="utf-8")
    failed = subprocess.run(
        cmd + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "was altered" in failed.stderr
