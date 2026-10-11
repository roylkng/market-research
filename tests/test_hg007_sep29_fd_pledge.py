from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_sep29_fd_pledge import (
    AUDIT_ID,
    ESOP_OUTSTANDING,
    ORIGINAL_XML_SHA,
    PROMOTER_PLEDGED_SHARES,
    QIP_AUDIT_PATH,
    REPORT_PATH,
    SHARES_FD,
    SHARES_ISSUED,
    build_sep29_report,
    load_verified_reg31,
)


def _source() -> tuple[bytes, dict, dict]:
    return load_verified_reg31(Path("."))


def _result() -> dict:
    raw, receipt, prior = _source()
    return build_sep29_report(raw, receipt, prior)


def test_original_reported_sep29_fd_includes_exact_esop_not_unissued_warrants() -> None:
    report = _result()
    assert report["review_id"] == AUDIT_ID
    assert report["shareholding_report_date"] == "2026-09-29"
    assert report["shareholding_first_broadcast_utc"] == "2026-10-08T13:24:47Z"
    assert report["original_nse_raw_xbrl_sha256"] == ORIGINAL_XML_SHA
    assert report["reported_paid_issued_shares"] == SHARES_ISSUED == 419_602_518
    assert report["reported_fully_diluted_shares_including_esop"] == SHARES_FD == 422_070_138
    assert report["reported_outstanding_esop_shares"] == ESOP_OUTSTANDING == 2_467_620
    assert report["reported_fully_diluted_shares_including_esop"] - report[
        "reported_paid_issued_shares"
    ] == report["reported_outstanding_esop_shares"]
    assert report["no_other_convertibles_or_warrants_reported"] is True
    assert report["post_sep29_additional_issuance_or_pledge_change_excluded"] is False
    assert report["oct12_current_fd_share_count_independently_verified"] is False


def test_original_promoter_pledged_shares_and_percentages() -> None:
    report = _result()
    assert report["reported_promoter_shares"] == 225_317_291
    assert report["reported_promoter_ownership_pct"] == pytest.approx(53.7)
    assert report["reported_promoter_pledged_shares"] == PROMOTER_PLEDGED_SHARES
    assert PROMOTER_PLEDGED_SHARES == 4_900_000
    assert report["reported_promoter_pledge_pct_promoter_shares"] == pytest.approx(2.17)
    assert report["reported_promoter_pledge_pct_total_issued_shares"] == pytest.approx(1.17)
    assert report["pledge_lender_collateral_terms_and_creation_date_verified"] is False
    for flag in (
        "oct12_current_fd_share_count_independently_verified",
        "cash_adjusted_enterprise_value_authorized",
        "wwil_target_ebitda_and_free_cashflow_verified",
        "company_probability_weighted_return_published",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert report[flag] is False


def test_fd_market_cap_is_dated_sensitivity_not_approved_october_current_cap() -> None:
    report = _result()
    date_prices = report["original_cash_purchased_price_reference_dates"]
    assert set(date_prices) == {"2026-10-01", "2026-10-09"}
    assert date_prices["2026-10-01"][
        "sep29_reported_fd_market_cap_inr_crore"
    ] == pytest.approx(6710.9151942)
    assert date_prices["2026-10-09"][
        "sep29_reported_fd_market_cap_inr_crore"
    ] == pytest.approx(5441.328219096)
    assert date_prices["2026-10-01"][
        "sep29_reported_basic_market_cap_inr_crore"
    ] == pytest.approx(6671.6800362)
    assert date_prices["2026-10-09"][
        "sep29_reported_basic_market_cap_inr_crore"
    ] == pytest.approx(5409.515662056)
    assert date_prices["2026-10-01"]["source_reg31_filing_was_public_at_price_close"] is False
    assert date_prices["2026-10-09"]["source_reg31_filing_was_public_at_price_close"] is True
    assert all(
        row["share_count_freshness_at_price_session_proven"] is False
        and row["economic_wwil_enterprise_value_verified"] is False
        for row in date_prices.values()
    )


def test_malformed_or_changed_pinned_reg31_bytes_fail_closed(tmp_path: Path) -> None:
    from marketlab.hg007_sep29_fd_pledge import ORIGINAL_XML_PATH

    for source in (ORIGINAL_XML_PATH, REPORT_PATH, QIP_AUDIT_PATH):
        new = tmp_path / source
        new.parent.mkdir(parents=True, exist_ok=True)
        new.write_bytes(source.read_bytes())
    load_verified_reg31(tmp_path)
    raw_xml = tmp_path / ORIGINAL_XML_PATH
    raw_xml.write_bytes(raw_xml.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="sha256 changed"):
        load_verified_reg31(tmp_path)
    raw_xml.write_bytes(ORIGINAL_XML_PATH.read_bytes())
    receipt = tmp_path / REPORT_PATH
    receipt.write_bytes(receipt.read_bytes() + b" ")
    with pytest.raises(ValueError, match="receipt changed"):
        load_verified_reg31(tmp_path)


def test_source_report_rejects_forged_governance_and_changed_old_capital_context() -> None:
    raw, receipt, old_qip = _source()
    originals = deepcopy((receipt, old_qip))
    build_sep29_report(raw, receipt, old_qip)
    assert (receipt, old_qip) == originals

    bad_receipt = deepcopy(receipt)
    bad_receipt["reported_promoter_and_pledge_context"]["promoter_percentage"] = 58.0
    with pytest.raises(ValueError, match="governance parser"):
        build_sep29_report(raw, bad_receipt, old_qip)

    bad_old = deepcopy(old_qip)
    bad_old["post_qip_basic_share_capital_sensitivities"]["2026-10-01"][
        "post_sep29_issued_basic_shares"
    ] = 401_492_045
    with pytest.raises(ValueError, match="basic cap context drifted"):
        build_sep29_report(raw, receipt, bad_old)

    with pytest.raises(ValueError, match="SHA"):
        build_sep29_report(raw + b"extra", receipt, old_qip)


def test_cli_exact_original_replay_is_idempotent_and_stays_research_only(
    tmp_path: Path,
) -> None:
    output = tmp_path / "sep29-fd-pledge-v1.json"
    command = [
        sys.executable, "scripts/reconcile_hg007_sep29_fd_pledge.py",
        "--out", str(output),
    ]
    first = subprocess.run(command, check=True, capture_output=True, text=True)
    brief = json.loads(first.stdout)
    assert brief["reported_fd_shares"] == 422_070_138
    assert brief["reported_esop_shares"] == 2_467_620
    assert brief["reported_promoter_pledged_shares"] == 4_900_000
    assert brief["valuation_authorized"] is False
    assert json.loads(output.read_text(encoding="utf-8")) == _result()
    subprocess.run(
        command + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    output.write_text(output.read_text(encoding="utf-8") + "\n{}", encoding="utf-8")
    failure = subprocess.run(
        command + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failure.returncode != 0
    assert "has drifted" in failure.stderr
