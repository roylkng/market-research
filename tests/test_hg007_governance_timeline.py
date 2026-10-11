from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_governance_timeline import (
    ORIGINALS,
    REPORT_ID,
    load_original_source_states,
    reconcile_gov_publication_timeline,
)


def _build() -> dict:
    originals, receipts = load_original_source_states(Path("."))
    return reconcile_gov_publication_timeline(originals, receipts)


def test_exact_original_oct4_to_oct8_nse_lookahead_guard() -> None:
    report = _build()
    assert report["event_review_id"] == REPORT_ID
    assert report["original_outside_u001_28_count"] == 28
    assert report["historical_oct4_source_pledge_boolean_true_count"] == 0
    assert report["original_case_selection_modified"] is False
    before = report["oct4_lookahead_correct_source"]
    after = report["oct8_later_primary_governance_publication"]
    assert before["report_date"] == "2026-06-30"
    assert before["INOXGREEN_promoter_group_pct"] == pytest.approx(56.12)
    assert before["INOXGREEN_public_pct"] == pytest.approx(43.88)
    assert before["INOXGREEN_pledge_boolean"] is False
    assert before["knows_september29_exceptional_filing"] is False
    assert after["original_first_public_utc"] == "2026-10-08T13:24:47Z"
    assert after["issuer_capital_asof_date"] == "2026-09-29"
    assert after["regular_2026_sep30_quarter_filing"] is False
    assert after["INOXGREEN_promoter_group_pct"] == 53.7
    assert after["INOXGREEN_promoter_named_pledged_shares"] == 4_900_000
    assert after["INOXGREEN_promoter_pledge_boolean"] is True
    assert after["pledge_security_lender_loan_date_verified"] is False
    assert after["current_oct11_pledge_status_verified"] is False
    assert report["other_27_current_ownership_and_pledge_reviewed"] is False
    assert report["share_target_price_or_expected_return_calculated"] is False
    assert report["portfolio_eligibility_allowed"] is False
    assert report["live_capital_allowed"] is False


def test_percent_reduction_is_not_a_verified_promoter_sale() -> None:
    report = _build()["conditional_promoter_fraction_reconciliation"]
    assert report["june_old_basic_shares"] == 401_492_045
    assert report["sept29_qip_issued_basic_shares"] == 419_602_518
    assert report["june_reported_promoter_pct"] == pytest.approx(56.12)
    assert report["sept29_reported_promoter_pct"] == 53.7
    assert report["percentage_point_difference"] == pytest.approx(-2.42)
    assert report["consistent_with_issue_denominator_dilution_within_reported_pct_rounding"] is True
    assert report["promoter_sold_or_bought_shares_proven"] is False
    assert report["exact_june_promoter_share_count_source_verified_here"] is False


def test_later_issuer_source_cannot_be_backdated_to_oct4() -> None:
    originals, receipts = load_original_source_states(Path("."))
    tampered = deepcopy(originals)
    tampered["HG007_P013_POST_QIP_CASES"][
        "original_nse_xbrl_public_at_utc"
    ] = "2026-10-01T03:00:00Z"
    with pytest.raises(ValueError, match="timeline"):
        reconcile_gov_publication_timeline(tampered, receipts)


def test_wrong_original_pledge_quantity_not_passed_as_official() -> None:
    originals, receipts = load_original_source_states(Path("."))
    tampered = deepcopy(originals)
    tampered["HG007_P012_NAMED_PROMOTER_PLEDGE"][
        "named_promoter_pledged_shares"
    ] = 0
    with pytest.raises(ValueError, match="promoter pledged-share"):
        reconcile_gov_publication_timeline(tampered, receipts)


def test_march_style_zero_pledge_cannot_replace_sept29_update() -> None:
    originals, receipts = load_original_source_states(Path("."))
    tampered = deepcopy(originals)
    tampered["HG007_P011_NSE_SPECIAL_RECEIPT"][
        "parsed_special_facts"
    ]["promoter_pledge_boolean_as_of_report"] = False
    with pytest.raises(ValueError, match="September 29 NSE XBRL"):
        reconcile_gov_publication_timeline(tampered, receipts)


def test_mutation_of_exact_archived_source_file_rejected(tmp_path: Path) -> None:
    for location, _digest in ORIGINALS.values():
        original = Path(location)
        output = tmp_path / location
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(original.read_bytes())
    load_original_source_states(tmp_path)
    x = tmp_path / ORIGINALS["GF001_28_AS_OF_OCT04"][0]
    x.write_bytes(x.read_bytes() + b" ")
    with pytest.raises(ValueError, match="source Git blob changed"):
        load_original_source_states(tmp_path)


def test_cli_repeatability_without_market_network(tmp_path: Path) -> None:
    output = tmp_path / "review.json"
    cmd = [
        sys.executable,
        "scripts/reconcile_hg007_governance_timeline.py",
        "--out", str(output),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    note = json.loads(result.stdout)
    assert note["oct4_pledge_boolean"] is False
    assert note["oct8_pledged_shares_disclosed"] == 4_900_000
    assert note["promoter_shares_sold_proven"] is False
    assert json.loads(output.read_text(encoding="utf-8")) == _build()
    subprocess.run(
        cmd + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    output.write_text(output.read_text(encoding="utf-8") + "changed", encoding="utf-8")
    failed = subprocess.run(
        cmd + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "chronology changed" in failed.stderr
