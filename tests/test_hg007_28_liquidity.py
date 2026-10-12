from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from marketlab.alpha_market import DailyEquityObservation
from marketlab.hg007_28_liquidity import (
    AUDIT_ID,
    ORIGINAL_COHORT_BLOB,
    ORIGINAL_COHORT_PATH,
    ORIGINAL_FIVE,
    ORIGINAL_FIVE_HISTORY_BLOB,
    ORIGINAL_FIVE_HISTORY_PATH,
    _one_day,
    _pinned_json,
    _valid_bar,
    build_twenty_day_all_28,
    validate_twenty_day_all_28,
)
from marketlab.hg007_liquidity_history import (
    LAST_SESSION,
    REQUIRED_SESSIONS,
    pinned_window_and_context,
)


def test_28_frozen_names_and_twenty_original_nse_sessions() -> None:
    result = build_twenty_day_all_28(Path("."))
    validate_twenty_day_all_28(result)
    prior, _ = _pinned_json(
        Path("."), ORIGINAL_COHORT_PATH, ORIGINAL_COHORT_BLOB
    )
    assert result["audit_id"] == AUDIT_ID
    assert result["original_selected_symbol_order"] == prior["symbols"]
    assert len(result["casework"]) == 28
    assert result["original_completed_sessions"] == 20
    assert result["source_window_first_session"] == "2026-09-10"
    assert result["source_window_last_session"] == LAST_SESSION
    assert len(result["twenty_original_nse_whole_market_source_receipts"]) == 20
    assert {
        row["symbol"] for row in result["casework"]
    } == set(prior["symbols"])
    assert result["complete_20_session_equity_company_count"] >= len(ORIGINAL_FIVE)
    assert result["complete_20_session_equity_company_count"] + result[
        "incomplete_or_changed_identity_company_count"
    ] == 28
    assert result["measurement_is_posthoc_historical_not_prospective"] is True
    assert result["selection_or_hg005_payoff_amended"] is False
    assert result["source_returns_or_alpha_computed"] is False
    assert result["investment_recommendations_generated"] is False
    assert result["live_capital_allowed"] is False


def test_five_original_liquidity_statistics_reproduced_for_all_20_sessions() -> None:
    all_28 = build_twenty_day_all_28(Path("."))
    p036, _ = _pinned_json(
        Path("."), ORIGINAL_FIVE_HISTORY_PATH, ORIGINAL_FIVE_HISTORY_BLOB
    )
    cases = {item["symbol"]: item for item in all_28["casework"]}
    for old in p036["company_distribution"]:
        symbol = old["symbol"]
        assert symbol in ORIGINAL_FIVE
        newer = cases[symbol]
        assert newer["exact_20_session_coverage_complete"] is True
        stat = newer["turnover_statistics_if_complete"]
        assert stat is not None
        assert stat["median_daily_traded_value_inr_crore"] == pytest.approx(
            old["twenty_session_traded_value_median_inr_crore"]
        )
        assert stat["p10_daily_traded_value_inr_crore"] == pytest.approx(
            old["twenty_session_traded_value_p10_nearest_rank_inr_crore"]
        )
        assert stat["p25_daily_traded_value_inr_crore"] == pytest.approx(
            old["twenty_session_traded_value_p25_nearest_rank_inr_crore"]
        )
        assert stat["oct09_daily_traded_value_inr_crore"] == pytest.approx(
            old["oct9_day_traded_value_inr_crore"]
        )
        assert stat["ticket_to_one_percent_of_median_turnover"]["1000000"] == (
            pytest.approx(
                old["ten_lakh_ticket_divided_by_one_pct_of_historical_median"]
            )
        )
        assert stat["quotients_are_fill_days_or_slippage_predictions"] is False
        assert newer["current_real_position_capacity_verified"] is False


def test_every_28_company_has_a_20_day_status_not_missing_as_zero() -> None:
    report = build_twenty_day_all_28(Path("."))
    for company in report["casework"]:
        rows = company["daily_source_rows"]
        assert len(rows) == REQUIRED_SESSIONS
        assert rows[-1]["session"] == "2026-10-09"
        assert rows[0]["session"] == "2026-09-10"
        assert all(record["symbol"] == company["symbol"] for record in rows)
        if company["exact_20_session_coverage_complete"] is False:
            assert company["turnover_statistics_if_complete"] is None
            assert company["state"] in {
                "MULTIPLE_IDENTITIES_CORPORATE_ACTION_REVIEW_REQUIRED",
                "NO_VERIFIED_EQ_TRADING_ROWS",
                "PARTIAL_OR_INVALID_TWENTY_SESSION_EQUITY_HISTORY",
            }
        else:
            assert company["state"] == "EXACT_20_SESSION_OFFICIAL_HISTORICAL_TURNOVER_OBSERVED"
            assert len(company["observed_isins"]) == 1
            assert company["missing_or_invalid_session_rows"] == []
            assert all(
                row["traded_value_inr"] > 0 and row["traded_shares"] > 0
                for row in rows
            )


def test_one_day_missing_source_record_not_filled_from_other_names() -> None:
    _sessions, _five, _p035, oct9_bytes, _provenance = pinned_window_and_context(
        Path(".")
    )
    result, parsed = _one_day(
        oct9_bytes,
        session="2026-10-09",
        original_symbols=["DEVX", "NOTINORIGINALCOHORT"],
    )
    assert result["DEVX"]["state"] == "EXACT_NSE_EQ_OHLC_AND_TURNOVER_OBSERVED"
    assert parsed["DEVX"].symbol == "DEVX"
    assert result["NOTINORIGINALCOHORT"]["state"] == (
        "OFFICIAL_EQ_ROW_MISSING_NO_SUBSTITUTION"
    )
    assert result["NOTINORIGINALCOHORT"]["traded_value_inr"] is None
    assert result["NOTINORIGINALCOHORT"]["isin"] is None


def test_nontrading_or_bad_turnover_fields_not_interpreted_as_executable() -> None:
    bar = DailyEquityObservation(
        session_date="2026-10-09",
        symbol="EXAMPLE",
        isin="INE000000000",
        open_price=100.0,
        high_price=110.0,
        low_price=95.0,
        close_price=101.0,
        previous_close=100.0,
        volume=100.0,
        turnover_inr=10_100.0,
        trade_count=20.0,
    )
    assert _valid_bar(bar)
    assert not _valid_bar(replace(bar, volume=0))
    assert not _valid_bar(replace(bar, turnover_inr=0))
    assert not _valid_bar(replace(bar, turnover_inr=200_000.0))
    assert not _valid_bar(replace(bar, trade_count=2.5))


def test_source_modified_frozen_membership_and_packet_fail_closed(tmp_path: Path) -> None:
    original, _ = _pinned_json(
        Path("."), ORIGINAL_COHORT_PATH, ORIGINAL_COHORT_BLOB
    )
    temp_path = tmp_path / ORIGINAL_COHORT_PATH
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_bytes(ORIGINAL_COHORT_PATH.read_bytes() + b" ")
    with pytest.raises(ValueError, match="original research Git blob changed"):
        _pinned_json(tmp_path, ORIGINAL_COHORT_PATH, ORIGINAL_COHORT_BLOB)
    assert len(original["symbols"]) == 28

    pkt = build_twenty_day_all_28(Path("."))
    pkt["casework"][0]["symbol"] = "DIDNOTSELECT"
    from marketlab.hg007_28_liquidity import _digest
    pkt["packet_sha256"] = _digest({
        k: v for k, v in pkt.items() if k != "packet_sha256"
    })
    with pytest.raises(ValueError, match="membership was modified"):
        validate_twenty_day_all_28(pkt)

    pkt = build_twenty_day_all_28(Path("."))
    pkt["casework"][0]["daily_source_rows"][0]["traded_value_inr"] = 100
    with pytest.raises(ValueError, match="digest changed"):
        validate_twenty_day_all_28(pkt)


def test_no_capital_or_return_flags_may_be_toggled() -> None:
    pkt = build_twenty_day_all_28(Path("."))
    for field in (
        "selection_or_hg005_payoff_amended",
        "source_returns_or_alpha_computed",
        "future_liquidity_representativeness_proven",
        "spread_depth_and_price_impact_verified",
        "investment_recommendations_generated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        altered = deepcopy(pkt)
        altered[field] = True
        # Hash tampering alone already fails closed. A carefully rehashed
        # modified packet must still fail its explicit scientific gate.
        from marketlab.hg007_28_liquidity import _digest
        altered["packet_sha256"] = _digest({
            k: v for k, v in altered.items() if k != "packet_sha256"
        })
        with pytest.raises(ValueError, match="cannot authorize"):
            validate_twenty_day_all_28(altered)


def test_offline_cli_replays_sources_without_future_prices(tmp_path: Path) -> None:
    target = tmp_path / "all28.json"
    base = [
        sys.executable,
        "scripts/build_hg007_28_liquidity.py",
        "--output",
        str(target),
    ]
    first = subprocess.run(base, check=True, capture_output=True, text=True)
    note = json.loads(first.stdout)
    assert note["frozen_company_count"] == 28
    assert note["source_completed_sessions"] == 20
    assert note["investment_recommendations_generated"] is False
    assert note["historical_turnover_is_executable_capacity"] is False
    assert note["live_capital_allowed"] is False
    report = json.loads(target.read_text(encoding="utf-8"))
    validate_twenty_day_all_28(report)
    subprocess.run(
        base + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    target.write_text(
        target.read_text(encoding="utf-8") + "tampered", encoding="utf-8"
    )
    bad = subprocess.run(
        base + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert bad.returncode != 0
    assert "official liquidity source report changed" in bad.stderr
