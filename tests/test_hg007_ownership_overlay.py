from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_ownership_overlay import (
    ID,
    P009_PATH,
    P011_PATH,
    build_ownership_case_overlay,
    load_exact_case_sources,
)


def _base() -> tuple[dict, dict, dict]:
    return load_exact_case_sources(Path("."))


def _result() -> dict:
    p009, p011, receipt = _base()
    return build_ownership_case_overlay(p009, p011, receipt)


def test_no_company_left_behind_and_reported_reg31_vintage_is_explicit() -> None:
    report = _result()
    assert report["casebook_id"] == ID
    assert report["original_hg007_28_member_count"] == 28
    assert len(report["casework"]) == 28
    assert len({r["symbol"] for r in report["casework"]}) == 28
    assert report["source_verified_new_dilution_pledge_cases"] == ["INOXGREEN"]
    assert report["unreviewed_company_count"] == 27
    by_symbol = {item["symbol"]: item for item in report["casework"]}
    known = by_symbol["INOXGREEN"]["additional_post_qip_original_ownership_review"]
    assert known["evidence_state"] == (
        "OFFICIAL_SEP29_REPORTED_FD_AND_PROMOTER_PLEDGE_RECONCILED"
    )
    assert known["fully_paid_issued_shares_asof_report"] == 419_602_518
    assert known["fully_diluted_shares_including_esop_asof_report"] == 422_070_138
    assert known["outstanding_esop_shares_asof_report"] == 2_467_620
    assert known["promoter_reported_percentage"] == 53.7
    assert known["promoter_pledged_shares_asof_report"] == 4_900_000
    assert known["promoter_pledged_shares_percentage_of_promoter_holdings"] == 2.17
    assert known["promoter_pledge_is_a_diligence_risk_not_an_auto_sell_signal"] is True
    assert known["oct1_source_not_yet_published"] is True
    assert known["current_oct12_fd_shares_verified"] is False
    assert known["pledge_lender_and_effective_dates_verified"] is False
    assert known["risk_adjusted_shareholder_expected_return_published"] is False
    assert all(
        by_symbol[s]["additional_post_qip_original_ownership_review"]["evidence_state"]
        == "NOT_REVIEWED_UNDER_P012"
        for s in by_symbol if s != "INOXGREEN"
    )
    assert all(
        item["portfolio_eligibility_allowed"] is False
        and item["live_capital_allowed"] is False
        and item["current_buy_recommendation_authorized"] is False
        for item in report["casework"]
    )
    assert report["stock_level_alpha_trials_claimed"] == 0
    assert report["live_capital_allowed"] is False


def test_september_report_is_not_fake_october1_point_in_time_data() -> None:
    report = _result()
    ino = next(r for r in report["casework"] if r["symbol"] == "INOXGREEN")
    source = ino["additional_post_qip_original_ownership_review"]
    assert source["source_broadcast_at_utc"] == "2026-10-08T13:24:47Z"
    assert source["dated_oct1_reported_fd_cap_inr_crore_retrospective"] == pytest.approx(
        6710.9151942
    )
    assert source["dated_oct9_reported_fd_cap_inr_crore_not_current_12oct"] == pytest.approx(
        5441.328219096
    )
    assert source["issuer_live_transaction_close_verified"] is False


def test_mutating_input_cannot_silently_rewrite_historical_research() -> None:
    prev, new, receipts = _base()
    original = deepcopy((prev, new))
    build_ownership_case_overlay(prev, new, receipts)
    assert (prev, new) == original

    altered = deepcopy(new)
    altered["reported_promoter_pledged_shares"] = 0
    with pytest.raises(ValueError, match="issuer Sep29 shareholdings"):
        build_ownership_case_overlay(prev, altered, receipts)

    altered = deepcopy(prev)
    row = next(r for r in altered["casework_with_capital_readiness"]
               if r["symbol"] == "INOXGREEN")
    row["capital_basis_correction"]["status"] = "CURRENT_FD_APPROVED"
    with pytest.raises(ValueError, match="stale March reference"):
        build_ownership_case_overlay(altered, new, receipts)

    altered = deepcopy(prev)
    altered["casework_with_capital_readiness"][0]["symbol"] = "INOXGREEN"
    with pytest.raises(ValueError, match="duplicate/invalid"):
        build_ownership_case_overlay(altered, new, receipts)


def test_original_p009_p011_blob_drift_rejected(tmp_path: Path) -> None:
    for path in (P009_PATH, P011_PATH):
        dest = tmp_path / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())
    load_exact_case_sources(tmp_path)
    copied = tmp_path / P011_PATH
    copied.write_bytes(copied.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="original archived research source changed"):
        load_exact_case_sources(tmp_path)


def test_reproducible_cli_28_cases(tmp_path: Path) -> None:
    dest = tmp_path / "issuer-risk.json"
    cmd = [
        sys.executable, "scripts/build_hg007_ownership_overlay.py",
        "--out", str(dest),
    ]
    run = subprocess.run(cmd, check=True, capture_output=True, text=True)
    assert json.loads(dest.read_text(encoding="utf-8")) == _result()
    assert json.loads(run.stdout)["original_28_preserved"] == 28
    subprocess.run(
        cmd + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    dest.write_text(dest.read_text(encoding="utf-8") + "bad", encoding="utf-8")
    failed = subprocess.run(
        cmd + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "diligence view changed" in failed.stderr
