"""P049 is a reverse cashflow hurdle, never a calibrated equity fair value."""

from __future__ import annotations

import copy
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.hg007_p049_datamatics_cash import (
    AUDIT_ID,
    AUDITED_CASH_FACTS,
    EXPLORATORY_FCF_MULTIPLES,
    PRICE_PACKET_PATH,
    Q1_MANAGEMENT_FACTS,
    build_datamatics_reverse_hurdle,
    materialize_datamatics_cash_hurdle,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/hg007/hg007-p049-datamatics-cash-hurdle-v1.json"


def test_fy26_vs_fy25_operating_cash_less_fixed_asset_cash_proxy():
    analysis = materialize_datamatics_cash_hurdle(ROOT)
    assert analysis["audit_id"] == AUDIT_ID
    assert analysis["market_source"]["symbol"] == "DATAMATICS"
    assert analysis["market_source"]["isin"] == "INE365B01017"
    assert analysis["market_source"][
        "official_EQ_close_inr_not_current_quote"
    ] == 777.9
    assert analysis[
        "fy26_cfo_less_fixed_asset_cash_spending_inr_crore_not_normalized_fcf"
    ] == pytest.approx(284.42)
    assert analysis["fy25_comparable_cashflow_proxy_inr_crore"] == pytest.approx(
        187.81
    )
    assert analysis[
        "historical_cashflow_proxy_growth_percent_not_next_year_forecast"
    ] == pytest.approx(51.44)
    assert analysis["estimated_basic_shares_using_mar31_paidup_not_oct13_current"] == (
        59106389
    )
    assert analysis[
        "estimated_oct13_cross_date_basic_market_cap_inr_crore"
    ] == pytest.approx(4597.886)
    assert analysis["observed_cashflow_proxy_yield_percent"] == pytest.approx(6.19)
    assert analysis[
        "basic_reference_market_cap_to_fy26_cashflow_proxy_multiple"
    ] == pytest.approx(16.166)
    assert analysis[
        "fy26_financial_borrowings_less_cash_inr_crore_excluding_lease"
    ] == pytest.approx(-0.06)
    assert analysis[
        "fy26_consolidated_total_lease_liabilities_inr_crore"
    ] == pytest.approx(78.57)
    assert analysis[
        "cash_proxy_required_for_50pct_gross_share_value_at_16x_inr_crore"
    ] == pytest.approx(431.052)
    assert analysis[
        "cash_proxy_increase_required_for_50pct_at_16x_percent_not_forecast"
    ] == pytest.approx(51.55)


def test_multiple_scenarios_not_targets_or_probabilities():
    analysis = materialize_datamatics_cash_hurdle(ROOT)
    scenarios = analysis["scenarios_are_price_equivalents_not_targets"]
    assert [row["exploratory_multiple_on_fy26_cash_proxy"] for row in scenarios] == (
        list(EXPLORATORY_FCF_MULTIPLES)
    )
    assert [row["price_equivalent_inr_not_target"] for row in scenarios] == [
        577.44, 769.92, 962.4,
    ]
    assert all(row["probability"] is None for row in scenarios)
    for key in (
        "current_oct13_fully_diluted_shares_verified",
        "normalized_sustainable_fcf_verified",
        "shareholder_cost_of_capital_estimated",
        "corporate_action_adjusted_total_return_estimated",
        "live_capital_allowed",
        "portfolio_eligibility_allowed",
        "investment_recommendation_generated",
        "source_financial_pdf_raw_archived_and_replayable",
    ):
        assert analysis[key] is False
    assert analysis["probability_weighted_fair_value_inr"] is None
    assert analysis["expected_future_total_return"] is None
    assert analysis["no_net_cash_or_investment_adjustment_applied"] is True
    assert analysis["cashflow_proxy_excludes_acquisition_investment_and_financing_outflows"]


def test_q1_yoy_momentum_is_descriptive_not_a_future_extrapolation():
    analysis = materialize_datamatics_cash_hurdle(ROOT)
    assert analysis["q1fy27_yoy_revenue_growth_percent_source_only"] == pytest.approx(
        9.9, abs=0.02
    )
    # Source headline may use unrounded internal data. Numbers here are
    # reconstructed strictly from publicly rounded ₹ crore table cells.
    assert analysis["q1fy27_yoy_ebitda_growth_percent_source_only"] == pytest.approx(
        33.20, abs=0.02
    )
    assert analysis[
        "q1fy27_sequential_revenue_growth_percent_source_only"
    ] < 0
    assert analysis["source_page_refs"]["audited_exchange_fy26"][
        "raw_pdf_bytes_archived"
    ] is False


def test_p049_refuses_negative_cashflow_or_share_capital_discrepancy():
    normal = materialize_datamatics_cash_hurdle(ROOT)
    cash = copy.deepcopy(AUDITED_CASH_FACTS)
    cash["fy26_cfo_inr_crore"] = math.nan
    with pytest.raises(ValueError, match="nonnegative and finite"):
        build_datamatics_reverse_hurdle(
            oct13_close_inr=777.9,
            frozen_source_packet_sha256=normal["market_source"][
                "frozen_original_28_case_packet_sha256"
            ],
            frozen_source_raw_sha256=normal["market_source"][
                "frozen_original_28_case_file_sha256"
            ],
            cash_facts=cash,
            q1_facts=Q1_MANAGEMENT_FACTS,
        )
    cash = copy.deepcopy(AUDITED_CASH_FACTS)
    cash["fy26_paid_up_equity_share_capital_exact_inr"] -= 1
    with pytest.raises(ValueError, match="cannot be reconstructed"):
        build_datamatics_reverse_hurdle(
            oct13_close_inr=777.9,
            frozen_source_packet_sha256=normal["market_source"][
                "frozen_original_28_case_packet_sha256"
            ],
            frozen_source_raw_sha256=normal["market_source"][
                "frozen_original_28_case_file_sha256"
            ],
            cash_facts=cash,
        )


def test_market_source_cannot_be_replaced_after_oct13(tmp_path: Path):
    destination = tmp_path / PRICE_PACKET_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = (ROOT / PRICE_PACKET_PATH).read_bytes()
    destination.write_bytes(source.replace(b"DATAMATICS", b"COUNTERFEIT", 1))
    with pytest.raises(ValueError, match="frozen October 13 NSE source blob"):
        materialize_datamatics_cash_hurdle(tmp_path)


def test_frozen_report_reproduces_without_crossing_date_line():
    observed = materialize_datamatics_cash_hurdle(ROOT)
    assert observed == json.loads(REPORT.read_text(encoding="utf-8"))
    run = subprocess.run(
        [
            sys.executable, "scripts/materialize_hg007_p049.py",
            "--repo-root", ".",
            "--output", str(REPORT), "--check",
        ],
        capture_output=True, text=True, check=True,
    )
    status = json.loads(run.stdout)
    assert status["status"] == "VERIFIED"
    assert status["packet_sha256"] == observed["packet_sha256"]
