from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.hg007_promoter_net_ownership import (
    AUDIT_ID,
    GROUP_SHARES,
    JUNE_BASIC,
    JUNE_FD,
    LEDGER_FILES,
    PLEDGED_SEPT,
    QIP_NEW_SHARES,
    SEPT_BASIC,
    SEPT_FD,
    SOURCE_FILES,
    build_primary_promoter_reconciliation,
)


def test_two_original_xbrls_prove_same_net_promoter_share_count() -> None:
    result = build_primary_promoter_reconciliation(Path("."))
    assert result["review_id"] == AUDIT_ID
    assert result["original_report_dates"] == ["2026-06-30", "2026-09-29"]
    assert result["promoter_group_reported_shares_june"] == GROUP_SHARES
    assert result["promoter_group_reported_shares_sept29"] == GROUP_SHARES
    assert result["net_change_in_reported_promoter_group_shares_between_filings"] == 0
    assert result["total_issued_basic_shares_june"] == JUNE_BASIC
    assert result["total_issued_basic_shares_sept29"] == SEPT_BASIC
    assert result["qip_issued_basic_share_increase"] == QIP_NEW_SHARES
    assert result["june_original"]["issuer_fully_diluted_shares"] == JUNE_FD
    assert result["september_special_original"]["issuer_fully_diluted_shares"] == SEPT_FD
    assert result["published_promoter_percentage_change_explained_by_denominator_within_rounding"] is True
    assert result["published_june_promoter_pct"] == pytest.approx(56.12)
    assert result["published_sept29_promoter_pct"] == pytest.approx(53.70)
    assert result["percentage_point_change_from_fixed_promoter_shares_and_new_issued_base"] == pytest.approx(
        result["published_percentage_point_change"], abs=0.01
    )
    assert result["gross_promoter_sales_and_purchases_during_interval_excluded"] is False


def test_pledged_promoter_shares_are_new_snapshot_not_verified_creation_date() -> None:
    result = build_primary_promoter_reconciliation(Path("."))
    assert result["promoter_group_pledge_boolean_june"] is False
    assert result["promoter_group_pledge_boolean_sept29"] is True
    assert result["promoter_group_pledged_shares_reported_sept29"] == PLEDGED_SEPT
    assert result["first_public_sept29_filing_utc"] == "2026-10-08T13:24:47Z"
    assert result["oct4_research_could_use_sept29_filing"] is False
    for field in (
        "new_pledge_creation_date_verified",
        "pledge_borrowing_cost_security_and_lender_verified",
        "official_sept29_pledge_and_shareholding_current_as_of_oct12_verified",
        "company_current_fd_and_net_debt_verified",
        "stock_expected_returns_calculated",
        "case_completion_probability_published",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert result[field] is False


def test_original_june_and_september_xbrl_hash_tampering_rejected(tmp_path: Path) -> None:
    for path, _sha, _date, _url in SOURCE_FILES.values():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(path).read_bytes())
    for path, _sha in LEDGER_FILES.values():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(path).read_bytes())
    assert build_primary_promoter_reconciliation(tmp_path)["promoter_group_reported_shares_june"] == GROUP_SHARES
    june = tmp_path / SOURCE_FILES["june_original"][0]
    june.write_bytes(june.read_bytes() + b"hidden change")
    with pytest.raises(ValueError, match="original NSE XBRL content SHA changed"):
        build_primary_promoter_reconciliation(tmp_path)


def test_first_publication_timeline_source_integrity(tmp_path: Path) -> None:
    for path, _sha, _date, _url in SOURCE_FILES.values():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(path).read_bytes())
    for path, _sha in LEDGER_FILES.values():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(path).read_bytes())
    amended = tmp_path / LEDGER_FILES["first_seen_chronology"][0]
    amended.write_bytes(amended.read_bytes() + b"post hoc")
    with pytest.raises(ValueError, match="immutable source-ledger Git blob drifted"):
        build_primary_promoter_reconciliation(tmp_path)


def test_cli_reproduces_without_fetch_or_share_reclassification(tmp_path: Path) -> None:
    output = tmp_path / "original-promoter-net-shares.json"
    command = [
        sys.executable,
        "scripts/reconcile_hg007_promoter_net_ownership.py",
        "--output",
        str(output),
    ]
    first = subprocess.run(command, check=True, capture_output=True, text=True)
    summary = json.loads(first.stdout)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result == build_primary_promoter_reconciliation(Path("."))
    assert summary["net_reported_change"] == 0
    assert summary["qip_issued_shares"] == QIP_NEW_SHARES
    assert summary["capital_authorized"] is False
    subprocess.run(
        command + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    output.write_text(output.read_text(encoding="utf-8") + "changed", encoding="utf-8")
    failed = subprocess.run(
        command + ["--verify-existing"],
        check=False, capture_output=True, text=True,
    )
    assert failed.returncode != 0
    assert "result was altered" in failed.stderr
