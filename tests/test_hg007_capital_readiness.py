from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_capital_readiness import (
    QIP_REPORT_GIT_BLOB,
    QIP_REPORT_PATH,
    build_capital_readiness_overlay,
    load_casework_with_qip,
)


def _output() -> dict:
    board, qip, receipts = load_casework_with_qip(Path("."))
    return build_capital_readiness_overlay(board, qip, source_receipts=receipts)


def test_full_frozen_cohort_retained_and_only_inoxgreen_stale() -> None:
    result = _output()
    assert result["original_hg007_cohort_count_preserved"] == 28
    assert len(result["casework_with_capital_readiness"]) == 28
    assert result["capital_denominator_stale_case_count"] == 1
    assert result["capital_denominator_stale_symbols"] == ["INOXGREEN"]
    assert result["capital_denominator_unreviewed_others"] == 27
    assert result["company_probabilities_published"] == 0
    assert result["investment_opportunities_ranked"] is False
    assert result["live_capital_allowed"] is False
    assert result["company_expected_returns_calculated"] is False
    assert result["source_receipts"]["qip_audit_git_blob_sha"] == QIP_REPORT_GIT_BLOB
    by_symbol = {row["symbol"]: row for row in result["casework_with_capital_readiness"]}
    assert len(by_symbol) == 28
    case = by_symbol["INOXGREEN"]
    assert case["reported_fd_cap_reference_inr_cr_not_current"] == pytest.approx(
        6422.9586735
    )
    assert case["capital_basis_correction"]["status"] == (
        "STALE_MARCH_FD_DENOMINATOR_AFTER_SEPTEMBER_QIP"
    )
    assert case["capital_basis_correction"][
        "legacy_current_fd_reference_may_be_used_for_new_underwriting"
    ] is False
    assert case["capital_basis_correction"][
        "oct1_same_price_post_qip_basic_cap_reference_inr_crore"
    ] == pytest.approx(6671.6800362)
    assert case["capital_basis_correction"][
        "oct9_price_post_qip_basic_cap_reference_inr_crore"
    ] == pytest.approx(5409.515662056)
    assert case["capital_basis_correction"][
        "corrected_oct9_basic_reference_is_proven_current_fd"
    ] is False
    assert all(
        row["capital_basis_correction"]["status"] == "NOT_REEVALUATED_UNDER_HG007_P009"
        for symbol, row in by_symbol.items() if symbol != "INOXGREEN"
    )


def test_original_28_source_values_remain_immutable() -> None:
    board, qip, receipts = load_casework_with_qip(Path("."))
    originals = deepcopy((board, qip))
    overlay = build_capital_readiness_overlay(board, qip, source_receipts=receipts)
    assert (board, qip) == originals
    assert overlay["original_stock_selection_or_payoff_inputs_modified"] is False


def test_downstream_cannot_override_frozen_legacy_or_current_qip_evidence() -> None:
    board, qip, receipts = load_casework_with_qip(Path("."))
    fake = deepcopy(board)
    entry = next(x for x in fake["casework"] if x["symbol"] == "INOXGREEN")
    entry["reported_fd_cap_reference_inr_cr_not_current"] = 6671.6800362
    with pytest.raises(ValueError, match="original INOXGREEN"):
        build_capital_readiness_overlay(fake, qip, source_receipts=receipts)

    fake = deepcopy(qip)
    fake["post_qip_fully_diluted_market_cap_authorized"] = True
    with pytest.raises(ValueError, match="cannot claim current FD"):
        build_capital_readiness_overlay(board, fake, source_receipts=receipts)

    fake = deepcopy(qip)
    fake["post_qip_basic_share_capital_sensitivities"]["2026-10-09"][
        "implied_post_qip_basic_market_cap_inr_crore"
    ] = 8000
    with pytest.raises(ValueError, match="exact source-derived"):
        build_capital_readiness_overlay(board, fake, source_receipts=receipts)


def test_pinned_qip_report_source_drift_rejected(tmp_path: Path) -> None:
    from marketlab.hg007_casework import SOURCE_BLOBS

    for name, _sha in SOURCE_BLOBS.values():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(name).read_bytes())
    dest = tmp_path / QIP_REPORT_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(QIP_REPORT_PATH.read_bytes())
    board, _, _ = load_casework_with_qip(tmp_path)
    assert board["source_membership_count"] == 28
    dest.write_bytes(dest.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="capitalization changed"):
        load_casework_with_qip(tmp_path)


def test_overlay_cli_reproduces_source_pinned_report(tmp_path: Path) -> None:
    dest = tmp_path / "capital-state.json"
    cmd = [
        sys.executable,
        "scripts/build_hg007_capital_readiness.py",
        "--out", str(dest),
    ]
    r = subprocess.run(cmd, check=True, capture_output=True, text=True)
    out = json.loads(dest.read_text(encoding="utf-8"))
    assert out == _output()
    assert json.loads(r.stdout)["newly_flagged_stale_share_denominator"] == [
        "INOXGREEN"
    ]
    subprocess.run(
        cmd + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    dest.write_text(dest.read_text(encoding="utf-8") + "extra", encoding="utf-8")
    failed = subprocess.run(
        cmd + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "overlay altered" in failed.stderr
