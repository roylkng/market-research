"""Original source prices refresh thesis hurdles, not future stock predictions."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p017_reverse_falsification import (
    build_l001_p017,
    load_source_packets,
    materialize_l001_p017,
    validate_l001_p017,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/l001/l001-p017-three-reverse-value-gates-v1.json"


def _source_report():
    return materialize_l001_p017(ROOT)


def test_official_nse_oct15_oct19_company_isins_and_actual_prices():
    report = _source_report()
    by = {
        row["symbol"]: row
        for row in report["dated_original_close_observations"]
    }
    assert set(by) == {"GESHIP", "ZUARIIND", "DATAMATICS"}
    assert by["GESHIP"]["frozen_isin"] == "INE017A01032"
    assert by["GESHIP"]["oct15_original_NSE_EQ_close_inr"] == 1484.1
    assert by["GESHIP"]["oct19_original_NSE_EQ_close_inr"] == 1519.3
    assert by["ZUARIIND"]["oct15_original_NSE_EQ_close_inr"] == 267.55
    assert by["ZUARIIND"]["oct19_original_NSE_EQ_close_inr"] == 259.1
    assert by["DATAMATICS"]["oct15_original_NSE_EQ_close_inr"] == 793
    assert by["DATAMATICS"]["oct19_original_NSE_EQ_close_inr"] == 777.75
    assert all(row["economic_dividend_and_share_adjusted_return"] is None for row in by.values())
    assert all(row["actual_fill_price"] is None for row in by.values())
    assert all(row["prospective_strategy_signal"] is False for row in by.values())


def test_geship_old_nav_residual_stress_is_smaller_at_oct19_price():
    report = _source_report()
    geship = report["company_diagnostics"]["GESHIP"]
    assert geship["issuer_NAV_per_share_inr_stale"] == 1886
    assert geship["issuer_reported_net_cash_cr_stale"] == 8056
    assert geship["dated_Oct15_discount_to_issuer_NAV_percent_not_margin_safety"] == pytest.approx(
        21.31, abs=0.01
    )
    assert geship["dated_Oct19_discount_to_issuer_NAV_percent_not_margin_safety"] == pytest.approx(
        19.44, abs=0.02
    )
    assert geship["break_even_haircut_noncash_NAV_Oct15_percent"] > geship[
        "break_even_haircut_noncash_NAV_Oct19_percent"
    ]
    assert geship["break_even_haircut_noncash_NAV_Oct19_percent"] == pytest.approx(
        27.75, abs=0.15
    )
    assert geship["issuer_buyback_cumulative_purchased_as_of_2026_10_16"] == 2901660
    assert geship["issuer_buyback_September_legally_extinguished_lot"] == 1858941
    assert geship["current_Oct19_fully_diluted_share_count_verified"] is False
    assert geship["shipping_fleet_cycle_normalized_NAV"] is None


def test_zuari_apparent_equity_gap_cannot_be_recomputed_with_old_underlying_prices():
    report = _source_report()
    z = report["company_diagnostics"]["ZUARIIND"]
    assert z["original_listed_holdings_mark_at_Oct15_cr"] == pytest.approx(3820.124826)
    assert z["borrowing_net_of_cash_as_of_2026_03_31_cr_not_current"] == pytest.approx(
        2519.4245
    )
    assert z["Oct15_repriced_stakes_less_stale_March_debt_cr"] == pytest.approx(
        1300.7003, abs=0.0002
    )
    assert z["further_listed_holding_discount_erasing_Oct15_apparent_gap_pct"] == pytest.approx(
        13.19, abs=0.03
    )
    assert z["Oct19_current_repriced_listed_holdings_cr"] is None
    assert z["Oct19_contemporaneous_debt_and_pledge_covenants_cr"] is None
    assert z["Oct19_actual_attributable_SOTP_value_cr"] is None
    assert z["Oct19_cheapness_inferred_from_price_drop"] is False
    assert z["Oct19_debt_pledged_value_double_counted"] is False


def test_datamatics_fy26_owner_cash_hurdle_does_not_assume_investment_assets():
    report = _source_report()
    d = report["company_diagnostics"]["DATAMATICS"]
    assert d["historical_basic_share_count_as_of_2026_03_31"] == 59106389
    assert d["FY26_CFO_less_PPE_CR_not_normalized_owner_cash"] == 284.42
    assert d["Oct19_price_times_historical_basic_shares_cr"] == pytest.approx(
        4597.0, abs=0.02
    )
    assert d["annual_owner_cash_needed_for_16x_Oct19_basic_share_parity_cr"] == pytest.approx(
        287.3, abs=0.2
    )
    assert d["annual_owner_cash_needed_for_50pct_gross_at_16x_cr"] > 430
    assert d["cash_proxy_required_growth_for_50pct_gross_at_16x_pct"] > 50
    assert d["FY26_209_69_cr_acquisition_payable_fully_reconciled"] is False
    assert d["verified_equity_fair_value"] is None


def test_original_market_input_tampering_blocks_research():
    source, receipts = load_source_packets(ROOT)
    modified = copy.deepcopy(source)
    stock = next(
        item for item in modified["oct19"]["source_identity_rows"]
        if item["symbol"] == "GESHIP"
    )
    stock["ohlcv"]["close_inr"] = 100000
    with pytest.raises(AlphaContractError, match="tampered source packet"):
        build_l001_p017(modified, receipts)
    modified = copy.deepcopy(source)
    modified["zuari"] = modified["zuari"].replace("13.19%", "99.99%")
    with pytest.raises(AlphaContractError, match="audit baseline memo mismatch"):
        build_l001_p017(modified, receipts)


def test_posthoc_company_hurdles_must_not_turn_into_buy_signals():
    report = _source_report()
    assert report["risk_adjusted_expected_return_for_any_company"] is None
    assert report["rank_stocks_as_buy"] is False
    assert report["live_capital_allowed"] is False
    assert report["price_date_change_is_posthoc_not_oct15_preregistered_alpha"] is True
    assert report["different_timing_of_NAV_listed_assets_and_debt_explicit"] is True
    assert report["uncalibrated_multiples_and_NAV_are_not_fair_values"] is True
    assert report["share_buyback_purchases_not_equal_to_legal_cancellations"] is True


def test_deterministic_original_source_replay_and_cli_are_read_only():
    report = _source_report()
    assert report == json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["report_sha256"] == digest({
        k: v for k, v in report.items() if k != "report_sha256"
    })
    validate_l001_p017(report, root=ROOT)
    run = subprocess.run(
        [sys.executable, "scripts/materialize_l001_p017.py", "--check"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    status = json.loads(run.stdout)
    assert status["state"] == "VERIFIED"
    assert status["priced_dated_companies"] == 3
    assert status["live_capital_allowed"] is False
