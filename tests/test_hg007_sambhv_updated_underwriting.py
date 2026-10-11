from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_sambhv_update import (
    AUDIT_ID,
    ORIGINAL_JULY_BOARD,
    SOURCES,
    build_latest_underwriting,
    load_pinned_latest,
)


def _study() -> dict:
    inputs, receipts = load_pinned_latest(Path("."))
    return build_latest_underwriting(inputs, receipts)


def test_five_company_original_case_membership_and_no_alpha_change() -> None:
    packet = _study()
    assert packet["overlay_id"] == AUDIT_ID
    assert packet["original_five_case_count"] == 5
    assert tuple(row["symbol"] for row in packet["casework"]) == (
        "ANANTRAJ", "DEVX", "INOXGREEN", "NPST", "SAMBHV"
    )
    assert packet["original_five_case_names_and_order_unchanged"] is True
    assert packet["source_case_count_with_new_sambhv_data"] == 1
    assert packet["source_probabilities_or_expected_returns_published"] == 0
    assert packet["latest_sambhv_warrant_cash_received_independently_verified"] is False
    assert packet["latest_sambhv_q2_incremental_ebitda_verified"] is False
    assert packet["current_five_company_FD_and_EV_verified"] is False
    assert packet["stock_selection_or_investment_rankings_changed"] is False
    assert packet["portfolio_eligibility_allowed"] is False
    assert packet["live_capital_allowed"] is False
    assert all(x["current_price_target"] is None for x in packet["casework"])


def test_sambhv_cash_tranches_and_q2_volume_never_substitute_ebitda() -> None:
    rows = {row["symbol"]: row for row in _study()["casework"]}
    p = rows["SAMBHV"]
    evidence = p["newer_original_sambhv_cash_and_volume_evidence"]
    assert evidence is not None
    assert evidence["source_July15_proposed_issue_total_cr"] == 99.9971
    assert evidence["if_100pct_allotted_25pct_advance_cr_not_bank_cash"] == (
        pytest.approx(24.999275)
    )
    assert evidence["if_100pct_exercised_75pct_later_cr_not_bank_cash"] == (
        pytest.approx(74.997825)
    )
    assert evidence["actual_allotment_or_cash_receipt_verified"] is False
    assert evidence["actual_exercise_or_new_shares_verified"] is False
    assert evidence["actual_allotment_date_unknown"] is True
    assert evidence["proposed_18_month_window_starts_on_actual_allotment_date"] is True
    assert evidence["proposed_anjaneya_76pct_concentration"] == pytest.approx(
        76.00110403201693
    )
    assert evidence["q2_fy27_sales_volume_tonnes"] == 122662
    assert evidence["q2_fy27_sales_tonnes_yoy_pct"] == pytest.approx(
        24.192046006803825
    )
    assert evidence["q2_sales_growth_proves_new_plant_or_ebitda"] is False
    assert evidence["steel_plus_power_gross_capex_cr"] == 935
    assert evidence["hypothetical_full_gross_warrants_over_combined_capex"] == (
        pytest.approx(99.9971 / 935)
    )
    assert evidence["hypothetical_25pct_advance_over_combined_capex"] == (
        pytest.approx(24.999275 / 935)
    )
    assert evidence["actual_funding_gap_verifiable"] is False
    assert evidence["historical_hg005_or_p030_repriced"] is False
    assert evidence["valuation_ready"] is False
    assert p["original_hg005_hurdle_unmodified"]["state"] == "SENSITIVITY_READY"
    assert p["primary_source_economic_cashflow_sufficient"] is False
    assert p["probability_weighted_equity_expected_return"] is None
    assert p["portfolio_eligibility_allowed"] is False
    assert p["live_capital_allowed"] is False
    for symbol in ("ANANTRAJ", "DEVX", "INOXGREEN", "NPST"):
        assert rows[symbol]["newer_original_sambhv_cash_and_volume_evidence"] is None


def test_all_four_original_research_documents_remain_immutable() -> None:
    originals, receipt = load_pinned_latest(Path("."))
    before = deepcopy(originals)
    build_latest_underwriting(originals, receipt)
    assert originals == before


def test_prevent_promotion_of_25pct_bank_cash_without_evidence() -> None:
    originals, receipt = load_pinned_latest(Path("."))
    altered = deepcopy(originals)
    altered["p032"]["first_25pct_subscription_cash_received_verified"] = True
    with pytest.raises(ValueError, match="cannot be promoted"):
        build_latest_underwriting(altered, receipt)
    altered = deepcopy(originals)
    altered["p031"]["warrant_proceeds_are_verified_current_cash"] = True
    with pytest.raises(ValueError, match="realized warrant cash"):
        build_latest_underwriting(altered, receipt)
    altered = deepcopy(originals)
    altered["p031"]["q2_vs_q1_vs_prior_year_sales_tonnes"][
        "all_product_sales_tonnes"
    ]["q2_fy27_tonnes"] = 220_000
    with pytest.raises(ValueError, match="volume, not EBITDA"):
        build_latest_underwriting(altered, receipt)


def test_exact_companion_sources_and_issuer_pdf_cannot_be_rewritten(
    tmp_path: Path,
) -> None:
    for relative, _ in SOURCES.values():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(relative).read_bytes())
    original = tmp_path / ORIGINAL_JULY_BOARD
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(Path(ORIGINAL_JULY_BOARD).read_bytes())
    load_pinned_latest(tmp_path)
    original.write_bytes(original.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="SHA changed"):
        load_pinned_latest(tmp_path)
    original.write_bytes(Path(ORIGINAL_JULY_BOARD).read_bytes())
    changed = tmp_path / SOURCES["p032"][0]
    changed.write_bytes(changed.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Git blob drifted"):
        load_pinned_latest(tmp_path)


def test_cli_idempotent_original_only_research(tmp_path: Path) -> None:
    dest = tmp_path / "latest-sambhv.json"
    cmd = [
        sys.executable, "scripts/build_hg007_sambhv_updated_underwriting.py",
        "--out", str(dest)
    ]
    summary = subprocess.run(cmd, check=True, capture_output=True, text=True)
    assert json.loads(summary.stdout)["original_case_count"] == 5
    assert json.loads(summary.stdout)["case_expected_returns_published"] == 0
    assert json.loads(dest.read_text(encoding="utf-8")) == _study()
    subprocess.run(
        cmd + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    dest.write_text(dest.read_text(encoding="utf-8") + "tamper", encoding="utf-8")
    failed = subprocess.run(
        cmd + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "overlay altered" in failed.stderr
