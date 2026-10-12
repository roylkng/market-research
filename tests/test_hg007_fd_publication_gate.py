from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_fd_publication_gate import (
    AUDIT_ID,
    FD_SHARES,
    FROZEN_SOURCES,
    SEPT_ORIGINAL_SHA256,
    SEPT_ORIGINAL_XBRL,
    build_publication_safe_fd_reference,
    load_time_bound_sources,
)


def _inputs() -> tuple[dict, dict, dict, dict]:
    return load_time_bound_sources(Path("."))


def _report() -> dict:
    p008, p040, original_counts, receipts = _inputs()
    return build_publication_safe_fd_reference(
        p008, p040, original_counts, source_receipts=receipts
    )


def test_original_sept29_xbrl_vs_p008_march_options_hypothesis() -> None:
    report = _report()
    assert report["audit_id"] == AUDIT_ID
    assert report["original_september_29_issued_basic_shares"] == 419_602_518
    assert report["original_september_29_reported_fully_diluted_shares"] == FD_SHARES
    assert report["september_report_dilutive_difference_vs_basic_shares"] == 2_467_620
    assert report["official_nse_first_public_timestamp_utc"] == "2026-10-08T13:24:47Z"
    assert report["original_september_29_reported_fully_diluted_shares"] == 422_070_138
    assert report["september_report_group_promoter_shares"] == 225_317_291
    assert report["september_report_group_pledged_shares"] == 4_900_000
    assert report["total_promoter_net_reported_share_change_june_to_sept29"] == 0
    assert report["pledge_origin_effective_date_or_current_balance_verified"] is False
    assert report["exact_instrument_class_breakdown_revalidated_under_this_audit"] is False
    assert report["independently_verified_current_october_13_fully_diluted_count"] is False
    assert report["post_qip_current_cash_or_enterprise_value_verified"] is False
    assert report["company_specific_expected_return_calculated"] is False
    assert report["live_capital_allowed"] is False


def test_oct1_filing_not_public_and_oct9_public_but_not_current_fd_certification() -> None:
    report = _report()
    oct1 = report["dated_price_and_original_fd_count_reference"]["2026-10-01"]
    oct9 = report["dated_price_and_original_fd_count_reference"]["2026-10-09"]
    assert oct1["raw_official_nse_close_inr"] == 159
    assert oct1["september_source_publication_at_this_price_close"] == (
        "NOT_PUBLIC_AT_MARKET_CLOSE"
    )
    assert oct1["could_original_sep29_fd_count_have_been_used_as_knowable_input"] is False
    assert oct1["dated_market_cap_inr_crore_if_issued_count_unmodified_since_sep29"] == (
        pytest.approx(6710.9151942)
    )
    assert oct9["raw_official_nse_close_inr"] == 128.92
    assert oct9["september_source_publication_at_this_price_close"] == (
        "PUBLIC_BEFORE_MARKET_CLOSE"
    )
    assert oct9["could_original_sep29_fd_count_have_been_used_as_knowable_input"] is True
    assert oct9["dated_market_cap_inr_crore_if_issued_count_unmodified_since_sep29"] == (
        pytest.approx(5441.328219096)
    )
    assert oct9["any_interim_new_securities_or_exercises_checked"] is False
    assert oct9["this_is_a_verified_current_day_fully_diluted_market_cap"] is False
    assert oct1["this_is_an_executable_price_or_forward_return"] is False
    assert oct9["this_is_an_executable_price_or_forward_return"] is False


def test_changed_nse_public_disclosure_date_fails_closed() -> None:
    p008, p040, counts, receipts = _inputs()
    tampered = deepcopy(p040)
    tampered["first_public_sept29_filing_utc"] = "2026-09-29T13:24:47Z"
    with pytest.raises(ValueError, match="first-public"):
        build_publication_safe_fd_reference(
            p008, tampered, counts, source_receipts=receipts
        )


def test_mislabeling_reported_issuer_shares_or_cash_ev_fails_closed() -> None:
    p008, p040, counts, receipts = _inputs()
    fake = deepcopy(counts)
    fake["fully_diluted_shares"] -= 10_000
    with pytest.raises(ValueError, match="reconciliation mismatch"):
        build_publication_safe_fd_reference(
            p008, p040, fake, source_receipts=receipts
        )
    fake = deepcopy(p008)
    fake["post_qip_fully_diluted_market_cap_authorized"] = True
    with pytest.raises(ValueError, match="original P008"):
        build_publication_safe_fd_reference(
            fake, p040, counts, source_receipts=receipts
        )


def test_source_blobs_and_nse_original_bytes_are_pinned(tmp_path: Path) -> None:
    for relative, _sha in FROZEN_SOURCES.values():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Path(relative).read_bytes())
    xbrl = tmp_path / SEPT_ORIGINAL_XBRL
    xbrl.parent.mkdir(parents=True, exist_ok=True)
    xbrl.write_bytes(Path(SEPT_ORIGINAL_XBRL).read_bytes())
    _, _, counts, _ = load_time_bound_sources(tmp_path)
    assert counts["fully_diluted_shares"] == FD_SHARES
    assert len(SEPT_ORIGINAL_SHA256) == 64

    xbrl.write_bytes(xbrl.read_bytes() + b" ")
    with pytest.raises(ValueError, match="XBRL SHA mismatch"):
        load_time_bound_sources(tmp_path)

    xbrl.write_bytes(Path(SEPT_ORIGINAL_XBRL).read_bytes())
    p008 = tmp_path / FROZEN_SOURCES["P008_OCT_CAP"][0]
    p008.write_bytes(p008.read_bytes() + b" ")
    with pytest.raises(ValueError, match="source Git blob drift"):
        load_time_bound_sources(tmp_path)


def test_original_source_objects_are_not_mutated() -> None:
    p008, p040, counts, receipts = _inputs()
    original = deepcopy((p008, p040, counts))
    build_publication_safe_fd_reference(
        p008, p040, counts, source_receipts=receipts
    )
    assert (p008, p040, counts) == original


def test_deterministic_cli_and_immutable_result(tmp_path: Path) -> None:
    target = tmp_path / "dated-fd.json"
    command = [
        sys.executable, "scripts/reconcile_hg007_fd_publication.py",
        "--out", str(target)
    ]
    out = subprocess.run(command, capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    assert data["original_fully_diluted_shares_asof_2026_09_29"] == FD_SHARES
    assert data["oct1_source_first_public_after_close"] is True
    assert data["oct9_source_first_public_before_close"] is True
    assert data["live_capital_allowed"] is False
    assert json.loads(target.read_text(encoding="utf-8")) == _report()
    subprocess.run(
        command + ["--verify-existing"], capture_output=True, text=True, check=True
    )
    target.write_text(target.read_text(encoding="utf-8") + "altered")
    failed = subprocess.run(
        command + ["--verify-existing"],
        capture_output=True, text=True, check=False
    )
    assert failed.returncode != 0
    assert "source packet drifted" in failed.stderr
