from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_wwil_synergy_hurdle import (
    MANAGEMENT_REPORTED_FY26_TURNOVER_CRORE,
    PRESS_SHA,
    build_wwil_management_hurdle,
    load_original_press,
)


def _result() -> dict:
    raw, receipt, provenance = load_original_press(Path("."))
    return build_wwil_management_hurdle(raw, receipt, provenance)


def test_original_oct7_press_source_and_page_bound_management_claim() -> None:
    result = _result()
    assert result["source_provenance"]["original_pdf_sha256"] == PRESS_SHA
    assert result["source_provenance"]["original_pdf_byte_count"] == 459650
    assert 1 <= result["original_pdf_page_count"] <= 10
    pages = result["issuer_reported_claim_source_pages"]
    assert set(pages) == {
        "management_2x_post_synergy_multiple",
        "reported_580cr_fy26_turnover",
        "management_synergies_future_year",
        "contract_5pct_escalation",
    }
    for row in pages.values():
        assert row["page_number"] in range(1, result["original_pdf_page_count"] + 1)
        assert row["source_pdf_sha256"] == PRESS_SHA
        assert row["page_text_sha256"] in result["original_pdf_page_text_sha256"]
    assert result["management_reported_consideration_inr_crore"] == 550
    assert result["management_reported_fy26_business_turnover_approx_inr_crore"] == 580
    assert result["management_claimed_post_synergy_consideration_ebitda_multiple_approx"] == 2


def test_management_2x_implies_future_hurdle_not_trailing_earnings() -> None:
    result = _result()
    assert result[
        "reverse_implied_future_annual_ebitda_inr_crore_if_quote_basis_comparable"
    ] == 275
    assert result["reverse_implied_ebitda_margin_on_older_fy26_turnover_pct"] == (
        pytest.approx(100 * 275 / 580)
    )
    assert result["note_forward_ebitda_vs_prior_fy26_turnover_are_not_same_period"] is True
    assert result[
        "reported_contract_price_escalation_pct_not_guaranteed_total_revenue_growth"
    ] == 5.0
    stress = result["nonforecast_illustrative_margin_stress"]
    assert len(stress) == 5
    by_margin = {
        round(item["illustrative_ebitda_margin_pct_of_reported_fy26_turnover"], 4): item
        for item in stress
    }
    assert by_margin[15.0]["arithmetic_annual_ebitda_inr_crore"] == pytest.approx(87)
    assert by_margin[15.0]["headline_550cr_cash_consideration_divided_by_ebitda"] == pytest.approx(550/87)
    assert by_margin[25.0]["headline_550cr_cash_consideration_divided_by_ebitda"] == pytest.approx(550/145)
    assert by_margin[35.0]["headline_550cr_cash_consideration_divided_by_ebitda"] == pytest.approx(550/203)
    assert by_margin[40.0]["headline_550cr_cash_consideration_divided_by_ebitda"] == pytest.approx(550/232)
    assert all(item["is_earnings_observation"] is False for item in stress)
    assert all(item["is_fair_value_enterprise_multiple"] is False for item in stress)


def test_full_source_authority_and_stock_probability_remain_blocked() -> None:
    result = _result()
    for flag in (
        "acquired_business_historical_normalized_ebitda_verified",
        "post_synergy_ebitda_achieved",
        "full_wwil_business_transfer_completed_verified",
        "third_party_debt_minority_and_group_eliminations_verified",
        "wwil_maintenance_capex_and_cash_conversion_verified",
        "fully_diluted_parent_equity_count_verified",
        "stock_target_price_authorized",
        "company_completion_probability_published",
        "company_expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert result[flag] is False
    assert result["illustrative_multiple_is_issuer_claim_not_audited_transaction_ev_ebitda"] is True


def test_original_pdf_raw_bytes_and_receipt_hash_cannot_be_replaced(tmp_path: Path) -> None:
    from marketlab.hg007_wwil_synergy_hurdle import PDF_RELATIVE, RECEIPT_RELATIVE

    for path in (PDF_RELATIVE, RECEIPT_RELATIVE):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    raw, receipt, provenance = load_original_press(tmp_path)
    assert hashlib.sha256(raw).hexdigest() == PRESS_SHA
    original = deepcopy(receipt)
    build_wwil_management_hurdle(raw, receipt, provenance)
    assert receipt == original

    edited = tmp_path / PDF_RELATIVE
    edited.write_bytes(edited.read_bytes() + b"fraud")
    with pytest.raises(ValueError, match="SHA or byte"):
        load_original_press(tmp_path)


def test_market_press_review_can_be_reproduced_from_exact_original(tmp_path: Path) -> None:
    dest = tmp_path / "management-press-hurdle.json"
    command = [
        sys.executable, "scripts/review_hg007_wwil_original_synergy.py",
        "--out", str(dest)
    ]
    cli = subprocess.run(command, check=True, capture_output=True, text=True)
    summary = json.loads(cli.stdout)
    assert summary["original_pdf_sha256"] == PRESS_SHA
    assert summary["future_ebitda_hurdle_crore_not_a_historical_observation"] == 275
    assert summary["historical_normalized_ebitda_verified"] is False
    assert summary["capital_authorized"] is False
    assert json.loads(dest.read_text(encoding="utf-8")) == _result()
    subprocess.run(
        command + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    dest.write_text(dest.read_text(encoding="utf-8") + "modified", encoding="utf-8")
    fail = subprocess.run(
        command + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert fail.returncode != 0
    assert "packet drifted" in fail.stderr


def test_revenue_is_previous_fy26_not_same_period_post_synergy() -> None:
    result = _result()
    assert MANAGEMENT_REPORTED_FY26_TURNOVER_CRORE == 580
    assert result["note_forward_ebitda_vs_prior_fy26_turnover_are_not_same_period"] is True
    assert "SOURCE" in result["classification"] or "MANAGEMENT" in result["classification"]
