from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_qip_capitalization import (
    MARCH_2026_BASIC_SHARES,
    MARCH_2026_FD_SHARES,
    MARCH_2026_REPORTED_ESOP,
    ORIGINAL_QIP_PDF_RELATIVE_PATH,
    ORIGINAL_QIP_PDF_SHA256,
    SEP29_ISSUED_SHARES,
    SOURCE_BLOBS,
    build_qip_denominator_audit,
    current_denominator_required,
    load_verified_source_references,
)


def _build() -> dict:
    a, b, c, s = load_verified_source_references(Path("."))
    return build_qip_denominator_audit(a, b, c, provenance=s)


def test_official_qip_pdf_and_march_share_convention() -> None:
    old, oct9, qip, receipts = load_verified_source_references(Path("."))
    assert MARCH_2026_BASIC_SHARES == 401_492_045
    assert MARCH_2026_REPORTED_ESOP == 2_467_620
    assert MARCH_2026_FD_SHARES == 403_959_665
    assert SEP29_ISSUED_SHARES == 419_602_518
    assert receipts["qip_original_pdf"]["sha256"] == ORIGINAL_QIP_PDF_SHA256
    original = Path(ORIGINAL_QIP_PDF_RELATIVE_PATH).read_bytes()
    assert hashlib.sha256(original).hexdigest() == ORIGINAL_QIP_PDF_SHA256
    assert len(original) == 309090
    assert qip["source_original_pdf_sha256"] == ORIGINAL_QIP_PDF_SHA256
    assert old["price_session"] == "2026-10-01"
    assert oct9["price_session"] == "2026-10-09"


def test_precise_1oct_and_9oct_post_allotment_issued_market_caps() -> None:
    result = _build()
    assert result["audit_id"] == "HG007-P008-INOXGREEN-QIP-DATED-CAPITALIZATION-v1"
    old = result["frozen_hg005_oct1_historical_result_not_modified"]
    new = result["post_qip_basic_share_capital_sensitivities"]
    assert old["reported_old_market_cap_inr_crore"] == pytest.approx(6422.9586735)
    assert old["march_fd_shares_used"] == 403_959_665
    assert old["current_fd_capitalization_label_is_stale_after_sep29_qip"] is True
    assert new["2026-10-01"]["implied_post_qip_basic_market_cap_inr_crore"] == (
        pytest.approx(6671.6800362)
    )
    assert new["2026-10-01"][
        "old_hg005_market_cap_shortfall_against_post_qip_basic_inr_crore"
    ] == pytest.approx(248.7213627)
    assert new["2026-10-01"][
        "old_hg005_denominator_understatement_vs_new_basic_pct"
    ] == pytest.approx(3.872379931793435)
    assert new["2026-10-09"]["raw_nse_close_inr"] == 128.92
    assert new["2026-10-09"]["implied_post_qip_basic_market_cap_inr_crore"] == (
        pytest.approx(5409.515662056)
    )
    assert new["2026-10-09"][
        "oct1_to_oct9_raw_unadjusted_reference_price_change_pct"
    ] == pytest.approx(-18.918238993710702)
    assert result["original_september_2026_nse_qip"]["qip_new_issued_shares"] == (
        18_110_473
    )
    assert result["original_september_2026_nse_qip"][
        "issuer_reported_gross_issue_proceeds_inr_crore"
    ] == pytest.approx(299.999985245)


def test_fd_options_same_march_balance_is_hypothesis_not_current() -> None:
    result = _build()
    options = result["non_authoritative_same_march_esop_count_scenario"]
    assert options["assumed_qip_plus_march_options_shares"] == 422_070_138
    assert options["oct1_hypothetical_fd_market_cap_inr_crore"] == pytest.approx(
        6710.9151942
    )
    assert options["oct9_hypothetical_fd_market_cap_inr_crore"] == pytest.approx(
        5441.328219096
    )
    assert options["scenario_is_a_verified_current_fd_market_cap"] is False
    assert result["current_esop_and_option_balance_reverified"] is False
    assert result["current_issued_shares_as_of_oct9_independently_reverified"] is False
    assert result["post_qip_fully_diluted_market_cap_authorized"] is False
    assert result["cash_adjusted_enterprise_value_authorized"] is False
    assert result["valuation_multiple_or_target_price_authorized"] is False
    assert result["stock_expected_returns_calculated"] is False
    assert result["prospective_return_outcomes_opened"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False
    with pytest.raises(ValueError, match="source-blocked"):
        current_denominator_required(result)


def test_original_hg005_and_nse_sources_never_modified() -> None:
    old, oct9, qip, receipts = load_verified_source_references(Path("."))
    prior = deepcopy((old, oct9, qip))
    build_qip_denominator_audit(old, oct9, qip, provenance=receipts)
    assert (old, oct9, qip) == prior


def test_forged_valuation_or_qip_allotment_fails_closed() -> None:
    old, oct9, qip, receipts = load_verified_source_references(Path("."))
    old["key_mechanical_context"]["INOXGREEN"][
        "reported_fd_market_cap_inr_crore"
    ] += 100.0
    with pytest.raises(ValueError, match="old market denominator"):
        build_qip_denominator_audit(old, oct9, qip, provenance=receipts)
    old, oct9, qip, receipts = load_verified_source_references(Path("."))
    qip["source_page_text_provenance"]["post_qip_issued_shares"] = (
        MARCH_2026_FD_SHARES
    )
    with pytest.raises(ValueError, match="issuer QIP"):
        build_qip_denominator_audit(old, oct9, qip, provenance=receipts)
    old, oct9, qip, receipts = load_verified_source_references(Path("."))
    oct9["case_prices_inr"]["INOXGREEN"] = 159.0
    with pytest.raises(ValueError, match="official Oct 9"):
        build_qip_denominator_audit(old, oct9, qip, provenance=receipts)


def test_pinned_source_byte_mutations_cannot_pass(tmp_path: Path) -> None:
    paths = [
        source for source, _ in SOURCE_BLOBS.values()
    ] + [ORIGINAL_QIP_PDF_RELATIVE_PATH]
    for name in paths:
        dest = tmp_path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(Path(name).read_bytes())
    load_verified_source_references(tmp_path)

    altered = tmp_path / ORIGINAL_QIP_PDF_RELATIVE_PATH
    altered.write_bytes(altered.read_bytes() + b"appended")
    with pytest.raises(ValueError, match="immutable hash"):
        load_verified_source_references(tmp_path)

    altered.write_bytes(Path(ORIGINAL_QIP_PDF_RELATIVE_PATH).read_bytes())
    old = tmp_path / SOURCE_BLOBS["hg005_original_2026_10_01"][0]
    old.write_bytes(old.read_bytes() + b" ")
    with pytest.raises(ValueError, match="original source drifted"):
        load_verified_source_references(tmp_path)


def test_cli_rebuild_is_deterministic_and_does_not_create_capital(
    tmp_path: Path,
) -> None:
    output = tmp_path / "review.json"
    base = [
        sys.executable,
        "scripts/reconcile_hg007_post_qip_capitalization.py",
        "--out",
        str(output),
    ]
    done = subprocess.run(
        base, check=True, capture_output=True, text=True
    )
    brief = json.loads(done.stdout)
    assert brief["corrected_oct1_post_qip_basic_cap_cr"] == pytest.approx(6671.6800362)
    assert brief["corrected_oct9_post_qip_basic_cap_cr"] == pytest.approx(5409.515662056)
    assert brief["live_capital_allowed"] is False
    assert brief["verified_current_fully_diluted_cap"] is False
    assert json.loads(output.read_text(encoding="utf-8")) == _build()
    subprocess.run(
        base + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    output.write_text(
        output.read_text(encoding="utf-8") + "{}",
        encoding="utf-8",
    )
    failed = subprocess.run(
        base + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "denominator result was modified" in failed.stderr
