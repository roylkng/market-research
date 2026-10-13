from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_vibhav_conversion_stage import (
    ORIGINAL_OCT09_PDF_SHA,
    load_pinned_sources,
    reconcile_oct09_status,
)


def _inputs():
    return load_pinned_sources(Path("."))


def _result():
    sources, proofs = _inputs()
    return reconcile_oct09_status(sources, proofs)


def test_original_oct7_and_oct9_milestones_separated_and_28_names_frozen() -> None:
    result = _result()
    assert result["oct07_preconversion_state_preserved"][
        "vibhav_equity_parent_ownership_pct"
    ] == 100
    assert result["oct07_preconversion_state_preserved"][
        "funding_conversion_status"
    ] == "PROPOSED_OPTIONAL_FUTURE"
    milestone = result["oct09_completed_equity_milestone"]
    assert milestone["vepl_deposit_to_equity_conversion_completed"] is True
    assert milestone["total_converted_inr_crore"] == 150
    assert milestone["issuer_converted_inr_crore"] == 50
    assert milestone["authum_converted_inr_crore"] == 100
    assert milestone["post_conversion_vibhav_paid_up_capital_inr_crore"] == 400.01
    assert milestone["issuer_reported_vibhav_ownership_pct"] == 75
    assert milestone["authum_reported_vibhav_ownership_pct"] == 25
    assert milestone["new_cash_raised_in_vepl_from_conversion_inr_crore"] == 0
    assert milestone["wwil_underlying_business_transfer_closing_proven"] is False
    assert len(result["casework_with_current_vepl_milestone"]) == 28
    assert result["original_28_company_selection_changed"] is False
    assert result["expected_returns_calculated"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False


def test_current_ino_status_is_not_a_new_buy_signal_or_business_closing() -> None:
    r = _result()
    cells = {x["symbol"]: x for x in r["casework_with_current_vepl_milestone"]}
    ino = cells["INOXGREEN"]["latest_documented_vepl_milestone"]
    assert ino["equity_allotment"] == "COMPLETED_VIBHAV_ICD_TO_EQUITY"
    assert ino["minority_ownership"] == {"INOXGREEN_percent": 75, "AUTHUM_percent": 25}
    assert ino["vepl_legal_subsidiary_still_controlled"] is True
    assert ino["wwil_underlying_om_business_transfer_completed_verified"] is False
    assert ino["stock_or_portfolio_approval"] is False
    assert r["listed_issuer_current_oct13_fd_count_verified"] is False
    assert r["actual_parent_remaining_principal_accrued_interest_verified"] is False
    assert r["oct09_market_close_time_safe_use_verified"] is False
    assert all("latest_documented_vepl_milestone" not in cell
               for name, cell in cells.items() if name != "INOXGREEN")


def test_original_facts_not_mutated_and_late_decision_requires_source_time() -> None:
    originals, receipts = _inputs()
    prior = deepcopy(originals)
    result = reconcile_oct09_status(originals, receipts)
    assert originals == prior
    assert result["official_source_first_public_timestamp_verified"] is False
    assert result["listed_issuer_sep29_fd_shares_verified_then_not_current"] == 422_070_138
    assert result["source_receipts"]["new_oct09_pdf"]["raw_sha256"] == ORIGINAL_OCT09_PDF_SHA


def test_forged_completion_or_retroactive_oct7_ownership_is_rejected() -> None:
    a, receipts = _inputs()
    fake = deepcopy(a)
    fake["old_oct07"]["disclosed_terms"][
        "vibhav_parent_current_ordinary_equity_ownership_pct"
    ]["reported_value"] = 75
    with pytest.raises(ValueError, match="Oct7 issuer funding changed"):
        reconcile_oct09_status(fake, receipts)
    fake = deepcopy(a)
    fake["new_oct09"]["text_verified_disclosure_fields_not_investment_approval"][
        "reported_issuer_vibhav_ownership_pct"
    ] = 100
    with pytest.raises(ValueError, match="Oct9 postconversion issuer facts changed"):
        reconcile_oct09_status(fake, receipts)
    fake = deepcopy(a)
    fake["new_oct09"]["wwil_undertaking_transfer_completed"] = True
    with pytest.raises(ValueError, match="original Oct9 postconversion"):
        reconcile_oct09_status(fake, receipts)


def test_original_pdf_sha_mismatch_blocked(tmp_path: Path) -> None:
    import shutil

    original_root = Path(".")
    from marketlab.hg007_vibhav_conversion_stage import SOURCES

    for path, _hash in SOURCES.values():
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original_root / path, destination)
    relative = (
        "research/hg007/wwil-oct09-vibhav-conversion/raw/sha256/"
        + ORIGINAL_OCT09_PDF_SHA + ".pdf"
    )
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original_root / relative, target)
    load_pinned_sources(tmp_path)
    target.write_bytes(target.read_bytes() + b"forged")
    with pytest.raises(ValueError, match="original SHA mismatch"):
        load_pinned_sources(tmp_path)


def test_cli_builds_and_reverifies_same_report(tmp_path: Path) -> None:
    path = tmp_path / "stage.json"
    command = [
        sys.executable, "scripts/reconcile_hg007_oct09_vibhav_conversion.py",
        "--out", str(path),
    ]
    r = subprocess.run(command, check=True, capture_output=True, text=True)
    summary = json.loads(r.stdout)
    assert summary["post_conversion_parent_pct"] == 75
    assert summary["wwil_bta_legal_close_verified"] is False
    assert json.loads(path.read_text(encoding="utf-8")) == _result()
    subprocess.run(command + ["--verify-existing"], check=True, capture_output=True, text=True)
    path.write_text(path.read_text(encoding="utf-8") + "x", encoding="utf-8")
    failed = subprocess.run(
        command + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "overlay changed" in failed.stderr
