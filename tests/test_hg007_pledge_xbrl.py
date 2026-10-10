from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_pledge_xbrl import (
    AUDIT_ID,
    SOURCE_PATH,
    SOURCE_SHA,
    build_sept29_promoter_pledge_audit,
    load_original_source,
)


def _actual() -> tuple[bytes, dict, dict]:
    return load_original_source(Path("."))


def test_original_asof_promoter_pledge_and_dilution_exact() -> None:
    original, sept, june = _actual()
    assert hashlib.sha256(original).hexdigest() == SOURCE_SHA
    result = build_sept29_promoter_pledge_audit(original, sept, june)
    assert result["audit_id"] == AUDIT_ID
    assert result["issuer_asof_date"] == "2026-09-29"
    assert result["original_filing_public_broadcast_utc"] == (
        "2026-10-08T13:24:47Z"
    )
    assert result["source_pledging_named_promoter"] == "Inox Wind Limited"
    assert result["named_promoter_held_shares"] == 205_274_791
    assert result["named_promoter_pledged_shares"] == 4_900_000
    assert result["promoter_group_total_shares"] == 225_317_291
    assert result["promoter_group_total_pledged_shares"] == 4_900_000
    assert result["listed_company_total_basic_shares"] == 419_602_518
    assert result["listed_company_total_fully_diluted_shares"] == 422_070_138
    assert result["dilutive_instruments_share_difference"] == 2_467_620
    assert result["reference_june_original_pledge_boolean"] is False
    assert result["sept29_original_pledge_boolean"] is True
    assert result["pledged_percent_of_promoter_group"] == pytest.approx(
        100*4_900_000/225_317_291
    )
    assert result["pledged_percent_of_all_issued"] == pytest.approx(
        100*4_900_000/419_602_518
    )
    assert result["pledged_percent_of_named_promoter_holding"] == pytest.approx(
        100*4_900_000/205_274_791
    )
    assert result["current_oct11_fd_capitalization_verified"] is False
    assert result["exact_date_pledge_created_verified"] is False
    assert result["no_post_sep29_pledge_changes_verified"] is False
    assert result["issuer_target_price_or_expected_return_calculated"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False


def test_original_source_blob_change_and_baseline_swap_refused(tmp_path: Path) -> None:
    from marketlab.hg007_pledge_xbrl import (
        P010_JUNE_PATH,
        SOURCE_RECEIPT_PATH,
    )

    for relative in (SOURCE_PATH, P010_JUNE_PATH, SOURCE_RECEIPT_PATH):
        dest = tmp_path / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(relative.read_bytes())
    load_original_source(tmp_path)
    dest = tmp_path / SOURCE_PATH
    dest.write_bytes(dest.read_bytes() + b"x")
    with pytest.raises(ValueError, match="original NSE XBRL SHA"):
        load_original_source(tmp_path)


def test_tampered_pledge_number_does_not_pass_even_if_raw_sha_is_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import marketlab.hg007_pledge_xbrl as module

    raw, sept, june = _actual()
    corrupted = raw.replace(b">4900000<", b">4800000<")
    assert corrupted != raw
    sha = hashlib.sha256(corrupted).hexdigest()
    monkeypatch.setattr(module, "SOURCE_SHA", sha)
    amended = deepcopy(sept)
    amended["source_original_xbrl_sha256"] = sha
    with pytest.raises(ValueError, match="pledged/FD/holding totals mismatch"):
        build_sept29_promoter_pledge_audit(corrupted, amended, june)


def test_qip_asof_source_not_evidence_of_oct11_current_capital() -> None:
    raw, sept, june = _actual()
    report = build_sept29_promoter_pledge_audit(raw, sept, june)
    blocked_fields = [
        "exact_date_pledge_created_verified",
        "pledge_security_and_recourse_terms_verified",
        "no_post_sep29_pledge_changes_verified",
        "no_post_sep29_issuance_or_esop_exercises_verified",
        "current_oct11_fd_capitalization_verified",
        "issuer_target_price_or_expected_return_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ]
    assert all(report[field] is False for field in blocked_fields)
    assert report["governance_risk_marker"] == (
        "NEW_AS_OF_SEPT29_PROMOTER_PLEDGE_VERSUS_JUNE_REPORT"
    )
