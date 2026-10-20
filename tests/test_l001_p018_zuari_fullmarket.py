"""Original full-market NSE Oct19 has five invested issuers, beyond HG009 300."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p012_zuari_reprice import ORIGINAL_JUNE_HOLDINGS
from marketlab.l001_p018_zuari_fullmarket import (
    DATES,
    build_l001_p018,
    load_original_sources,
    materialize_l001_p018,
    validate_l001_p018,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/l001/l001-p018-oct19-five-stake-source-repricing-v1.json"


def test_both_original_full_nse_archives_validate_and_all_five_stakes_are_present():
    prices, receipts = load_original_sources(ROOT)
    assert set(prices) == set(DATES)
    assert set(receipts) == set(DATES)
    members = {
        (h.symbol, h.isin) for h in ORIGINAL_JUNE_HOLDINGS
    } | {("ZUARIIND", "INE217A01012")}
    for day in DATES:
        assert set(prices[day]) == members
        assert all(v > 0 for v in prices[day].values())
        assert len(receipts[day]["official_raw_udiff_sha256"]) == 64
        assert len(receipts[day]["official_original_index_sha256"]) == 64
        assert receipts[day]["source_is_trade_fill"] is False


def test_Oct19_five_underlying_prices_reprice_same_date_as_parent():
    report = materialize_l001_p018(ROOT)
    assert report["as_of_research_date"] == "2026-10-20"
    assert report["original_issuer_june_reported_portfolio_mark_cr"] == 4223.0
    assert report["source_rounded_five_stakes_total_cr"] == 4224
    assert report["stake_marks_by_date_cr"]["2026-10-15"] == pytest.approx(
        3820.124826, abs=0.000002
    )
    assert report["parent_Oct15_official_EQ_close_inr"] == 267.55
    assert report["parent_Oct19_official_EQ_close_inr"] == 259.1
    assert report["parent_original_share_count_historical_not_current"] == 29781184
    assert report["net_borrowings_as_of_2026_03_31_cr_not_current"] == pytest.approx(
        2519.4245
    )
    assert len(report["five_source_repriced_listed_holdings"]) == 5
    assert all(
        row["listed_share_count_still_unchanged_since_June_verified"] is False
        for row in report["five_source_repriced_listed_holdings"]
    )
    assert report["October20_is_official_NSE_Dussehra_holiday"] is True
    assert report["forecast_next_year_shareholder_return"] is None
    assert report["after_tax_liquidation_or_owner_equity_NAV_verified"] is False
    assert report["live_capital_allowed"] is False
    validate_l001_p018(report, root=ROOT)


def test_break_even_haircut_is_exact_crossdated_accounting_identity_not_nav():
    report = materialize_l001_p018(ROOT)
    portfolio = report["stake_marks_by_date_cr"]["2026-10-19"]
    cap = report["parent_Oct19_cap_from_old_basic_shares_cr_not_current_fd_cap"]
    old_debt = report["net_borrowings_as_of_2026_03_31_cr_not_current"]
    gap = portfolio - old_debt - cap
    assert report["Oct19_gross_hypothetical_residual_to_old_cap_cr"] == pytest.approx(
        gap, abs=0.0001
    )
    assert report["Oct19_further_markdown_erasing_apparent_gap_fraction"] == pytest.approx(
        gap / portfolio, abs=1e-7
    )
    assert report["additional_markdown_sensitivities"][0][
        "hypothetical_gap_to_Oct19_old_basic_equity_cap_cr"
    ] == pytest.approx(gap, abs=0.0001)
    assert report["current_oct19_entity_stake_units_verified"] is False
    assert report["March_to_Oct19_realized_cash_and_current_debt_verified"] is False
    assert report["pledged_asset_obligations_double_subtracted"] is False


def test_missing_original_stake_or_manufactured_quote_fails_closed():
    prices, receipts = load_original_sources(ROOT)
    replaced = copy.deepcopy(prices)
    h = ORIGINAL_JUNE_HOLDINGS[0]
    del replaced["2026-10-19"][(h.symbol, h.isin)]
    with pytest.raises(AlphaContractError, match="all five original"):
        build_l001_p018(replaced, receipts)

    replaced = copy.deepcopy(prices)
    replaced["2026-10-19"][(h.symbol, h.isin)] = -1
    with pytest.raises(AlphaContractError, match="not finite positive"):
        build_l001_p018(replaced, receipts)
    replaced = copy.deepcopy(prices)
    replaced["2026-10-15"][(h.symbol, h.isin)] = 600
    with pytest.raises(AlphaContractError, match="P012 Oct15 asset-mark drift"):
        build_l001_p018(replaced, receipts)


def test_report_original_source_and_posthoc_signatures_do_not_become_buys():
    report = materialize_l001_p018(ROOT)
    assert report["research_id"].startswith("L001-P018-20261020")
    assert report["june_deck_pdf_independently_reaudited_in_this_run"] is False
    assert report["source_prices_tradable_at_close_verified"] is False
    assert report["fresh_issuer_buy_signal_from_posthoc_original_close"] is False
    assert report["portfolio_eligible"] is False
    assert report["live_capital_allowed"] is False
    assert report["report_sha256"] == digest({
        k: v for k, v in report.items() if k != "report_sha256"
    })
    tampered = copy.deepcopy(report)
    tampered["five_source_repriced_listed_holdings"][0][
        "Oct19_pro_forma_stake_mark_cr"
    ] = 1e9
    with pytest.raises(AlphaContractError, match="report hash changed"):
        validate_l001_p018(tampered, root=ROOT)


def test_cli_replays_original_oct19_market_zip_and_index_without_network():
    report = materialize_l001_p018(ROOT)
    assert report == json.loads(REPORT.read_text("utf-8"))
    result = subprocess.run(
        [sys.executable, "scripts/materialize_l001_p018.py", "--check"],
        cwd=ROOT, check=True, text=True, capture_output=True,
    )
    status = json.loads(result.stdout)
    assert status["state"] == "VERIFIED"
    assert status["sha256"] == report["report_sha256"]
    assert status["live_capital_allowed"] is False
