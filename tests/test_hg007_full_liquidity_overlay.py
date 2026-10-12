from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_full_liquidity_overlay import (
    SOURCE_BLOBS,
    build_liquidity_readiness,
    load_source_packets,
)


def _inputs() -> tuple[dict, dict, dict, dict]:
    return load_source_packets(Path("."))


def _report() -> dict:
    a, b, c, receipts = _inputs()
    return build_liquidity_readiness(a, b, c, provenance=receipts)


def test_all_28_original_cases_and_twenty_day_equity_coverage() -> None:
    report = _report()
    assert report["original_hg002_selected_count_preserved"] == 28
    assert len(report["company_cases"]) == 28
    assert len({x["symbol"] for x in report["company_cases"]}) == 28
    assert report["twenty_session_EQ_complete_company_count"] == 26
    assert report["twenty_session_EQ_partial_BE_verified_company_count"] == 2
    counts = {
        key: len(values)
        for key, values in report[
            "historical_cash_turnover_bands_not_investment_ranks"
        ].items()
    }
    assert counts == {
        "MEDIAN_DAILY_VALUE_BELOW_0_1_CR": 3,
        "MEDIAN_DAILY_VALUE_0_1_TO_BELOW_1_CR": 7,
        "MEDIAN_DAILY_VALUE_1_TO_BELOW_10_CR": 4,
        "MEDIAN_DAILY_VALUE_AT_LEAST_10_CR": 12,
        "INCOMPLETE_EQ_SERIES_WITH_SEPARATE_BE_OBSERVATIONS": 2,
    }
    assert report["direct_or_procedural_with_median_daily_turnover_below_one_crore"] == [
        "AXITA", "DEVX", "SANDESH", "SUVIDHAA", "TREL"
    ]
    assert report["original_case_economics_prices_and_selection_unmodified"] is True
    assert report["investment_recommendations_generated"] is False
    assert report["alpha_discovery_or_forward_returns_calculated"] is False
    assert report["live_capital_allowed"] is False
    assert report["portfolio_eligibility_allowed"] is False
    for company in report["company_cases"]:
        assert company["live_capital_allowed"] is False
        assert company["portfolio_eligibility_allowed"] is False
        assert company["company_expected_returns_calculated"] is False


def test_true_original_nse_turnover_not_orderbook_capacity() -> None:
    by_symbol = {row["symbol"]: row for row in _report()["company_cases"]}
    checks = {
        "DEVX": (0.40847033, 24.48158229754411),
        "SUVIDHAA": (0.0202446025, 493.95882186375354),
        "SANDESH": (0.04973082, 201.082507),
        "ANANTRAJ": (88.72696000750001, 0.11270531526330563),
        "INOXGREEN": (26.6312475355, 0.37549874397246297),
        "SAMBHV": (47.8594882545, 0.208944),
    }
    for symbol, (expected_median, expected_factor) in checks.items():
        reading = by_symbol[symbol]["historical_eq_source_readiness"]
        assert reading["source_eq_session_count"] == 20
        assert reading["median_daily_cash_market_value_traded_inr_crore"] == pytest.approx(
            expected_median
        )
        assert reading[
            "illustrative_ticket_to_one_percent_historical_median_ratios"
        ]["1000000"] == pytest.approx(expected_factor)
        assert reading["ticket_quotients_predict_trading_days_or_fills"] is False
        assert reading["current_bid_ask_depth_spread_slippage_verified"] is False
    assert by_symbol["INOXGREEN"]["capital_basis_correction"][
        "status"
    ] == "STALE_MARCH_FD_DENOMINATOR_AFTER_SEPTEMBER_QIP"


def test_orbtexp_and_retail_be_series_does_not_fill_eq_days() -> None:
    by_symbol = {row["symbol"]: row for row in _report()["company_cases"]}
    for sym, eq_count, be_count in [("ORBTEXP", 9, 11), ("RETAIL", 15, 5)]:
        reading = by_symbol[sym]["historical_eq_source_readiness"]
        assert reading["state"] == "PARTIAL_EQ_SESSIONS_WITH_SEPARATELY_VERIFIED_BE_SERIES"
        assert reading["source_eq_session_count"] == eq_count
        assert reading["source_be_series_sessions_not_imputed"] == be_count
        assert reading["source_be_series_tags"] == ["BE"]
        assert reading["full_20day_eq_median_value_traded_inr_crore"] is None
        assert reading["illustrative_ticket_to_one_percent_historical_median_ratios"] is None
        assert reading["zero_trading_days_proven"] is False
        assert reading["be_series_order_execution_and_settlement_verified"] is False


def test_source_tamper_and_scope_change_are_rejected(tmp_path: Path) -> None:
    for path, _sha in SOURCE_BLOBS.values():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(path).read_bytes())
    casework, all28, series, receipts = load_source_packets(tmp_path)
    assert build_liquidity_readiness(
        casework, all28, series, provenance=receipts
    )["original_hg002_selected_count_preserved"] == 28
    path = tmp_path / SOURCE_BLOBS["NSE_EQ_SERIES_ABSENCE_REVIEW"][0]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="source blob changed"):
        load_source_packets(tmp_path)

    original, all28, series, receipts = _inputs()
    changed = deepcopy(all28)
    changed["casework"][0]["turnover_statistics_if_complete"][
        "median_daily_traded_value_inr_crore"
    ] = 2.0
    with pytest.raises(ValueError, match="ratio changed"):
        build_liquidity_readiness(original, changed, series, provenance=receipts)
    changed = deepcopy(series)
    changed["findings"][0]["missing_eq_day_count"] = 0
    with pytest.raises(ValueError, match="inconsistent original EQ/BE"):
        build_liquidity_readiness(original, all28, changed, provenance=receipts)
    changed = deepcopy(original)
    changed["casework_with_capital_readiness"][0]["symbol"] = "FAKE"
    with pytest.raises(ValueError, match="original 28 companies differ"):
        build_liquidity_readiness(changed, all28, series, provenance=receipts)


def test_no_source_or_decision_mutated() -> None:
    original, all28, series, receipts = _inputs()
    prior = deepcopy((original, all28, series))
    build_liquidity_readiness(original, all28, series, provenance=receipts)
    assert (original, all28, series) == prior


def test_cli_materialization_is_exactly_reproducible(tmp_path: Path) -> None:
    output = tmp_path / "all28-liquidity.json"
    command = [
        sys.executable, "scripts/build_hg007_28_liquidity_risk.py",
        "--out", str(output)
    ]
    first = subprocess.run(
        command, check=True, text=True, capture_output=True
    )
    short = json.loads(first.stdout)
    assert short["company_count"] == 28
    assert short["complete_EQ_20days"] == 26
    assert json.loads(output.read_text(encoding="utf-8")) == _report()
    subprocess.run(
        command + ["--verify-existing"], check=True, text=True, capture_output=True
    )
    output.write_text(output.read_text(encoding="utf-8") + "{}")
    bad = subprocess.run(
        command + ["--verify-existing"], check=False, text=True, capture_output=True
    )
    assert bad.returncode != 0
    assert "overlay drifted" in bad.stderr
