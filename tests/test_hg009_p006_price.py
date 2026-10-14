"""Synthetic adversarial tests: HG009 P006 never opens real future NSE labels."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p004_clock import (
    build_hg009_outcome_clock,
    load_p004_inputs,
)
from marketlab.hg009_p006_price import (
    build_hg009_price_only_diagnostic,
    validate_hg009_price_only_diagnostic,
)

ROOT = Path(__file__).resolve().parents[1]
DATES = [
    "2026-10-15", "2026-10-16", "2026-10-19",
    "2026-10-21", "2026-10-22",
]


def _inputs():
    calendar, original, selected, controls = load_p004_inputs(ROOT)
    protocol = build_hg009_outcome_clock(
        calendar=calendar,
        original=original,
        selected=selected,
        controls=controls,
    )
    return {
        "protocol": protocol,
        "calendar": calendar,
        "original": original,
        "selected": selected,
        "controls": controls,
    }


def _packet(
    arguments: dict,
    day: str,
    *,
    missing: tuple[str, str] | None = None,
    benefit: bool = False,
) -> dict:
    members = {
        "SELECTED": arguments["selected"]["selected"],
        "ONE_LANE": arguments["controls"]["controls"]["ONE_LANE"],
        "ZERO_LANE": arguments["controls"]["controls"]["ZERO_LANE"],
    }
    day_index = DATES.index(day)
    bars = []
    coverage = {}
    for arm in ("SELECTED", "ONE_LANE", "ZERO_LANE"):
        for row in members[arm]:
            symbol, isin = row["symbol"], row["isin"]
            missing_row = missing == (symbol, isin)
            if missing_row:
                price = None
                state = "ISIN_CHANGED_REQUIRES_ORIGINAL_ACTION"
            else:
                baseline = 100.0
                increase = {
                    "SELECTED": 4.0,
                    "ONE_LANE": 2.0,
                    "ZERO_LANE": 1.0,
                }[arm]
                if benefit:
                    increase *= 2.0
                price = {
                    "open_inr": baseline,
                    "high_inr": baseline + increase * (day_index + 1) + 2.0,
                    "low_inr": baseline - 2.0,
                    "close_inr": baseline + increase * (day_index + 1),
                    "traded_value_inr": 1000000.0,
                    "traded_volume": 15000.0,
                    "trade_count": 100,
                }
                state = "ORIGINAL_NSE_EQ_OHLC_OBSERVED_NOT_FILL"
            bars.append({
                "arm": arm,
                "symbol": symbol,
                "frozen_isin": isin,
                "exchange_series": "EQ",
                "state": state,
                "ohlcv": price,
                "source_original_udiff_sha256": "a" * 64,
                "corporate_action_adjusted": False,
                "dividend_adjusted": False,
                "actual_trade_fill": False,
                "current_order_capacity_verified": False,
            })
        observed = sum(
            bar["arm"] == arm
            and bar["state"] == "ORIGINAL_NSE_EQ_OHLC_OBSERVED_NOT_FILL"
            for bar in bars
        )
        coverage[arm] = {
            "declared": 100,
            "observed_official_eq": observed,
            "missing_or_changed_identity": 100 - observed,
            "state_counts": {},
        }
    assert len(bars) == 300
    session = next(
        s for s in arguments["calendar"].sessions
        if s.session_date == day
    )
    close = datetime.fromisoformat(session.close_timestamp_utc).astimezone(UTC)
    original = {
        "schema_version": 1,
        "record_id": "HG009-P002-300-FROZEN-NSE-OFFICIAL-EQ-DAILY-v1",
        "date_ist": day,
        "observed_recorded_at_utc": f"{day}T12:00:00+00:00",
        "exchange_session_close_utc": close.isoformat(),
        "selected_manifest_sha256": arguments["selected"]["cohort_sha256"],
        "controls_manifest_sha256": arguments["controls"]["manifest_sha256"],
        "h021_original_daily_packet_sha256": "f" * 64,
        "original_market_source_sha256": "a" * 64,
        "original_index_source_sha256": "b" * 64,
        "original_source_market_captured_at_utc": f"{day}T11:00:00Z",
        "original_source_index_captured_at_utc": f"{day}T11:01:00Z",
        "benchmark": {
            "id": "nifty_500",
            "basis": "PRICE_INDEX_NOT_TOTAL_RETURN",
            "open": 20000.0,
            "close": 20020.0 + day_index * 20.0,
        },
        "source_identity_rows": bars,
        "arm_coverage": coverage,
        "corporate_actions_resolved": False,
        "dividends_adjusted": False,
        "gross_holding_period_returns_calculated": False,
        "benchmark_excess_returns_calculated": False,
        "live_capital_allowed": False,
        "portfolio_eligibility_allowed": False,
    }
    original["packet_sha256"] = digest(original)
    return original


def _evaluate(horizon: int, rows: list[dict], args: dict) -> dict:
    return build_hg009_price_only_diagnostic(
        horizon_sessions=horizon,
        market_snapshots=rows,
        evaluated_at_utc="2026-10-23T11:00:00Z",
        **args,
    )


def test_h1_same_session_open_to_close_no_invented_fills():
    args = _inputs()
    result = _evaluate(1, [_packet(args, DATES[0])], args)
    assert result["horizon_sessions"] == 1
    assert result["first_entry_date"] == result["official_exit_date"] == DATES[0]
    assert result["original_universe_size"] == 300
    assert len(result["original_symbol_isin_rows"]) == 300
    assert result["arm_descriptive_statistics"]["SELECTED"][
        "mean_price_change_pct_if_observed"
    ] == 4.0
    assert result["arm_descriptive_statistics"]["ONE_LANE"][
        "mean_price_change_pct_if_observed"
    ] == 2.0
    assert result["arm_descriptive_statistics"]["ZERO_LANE"][
        "mean_price_change_pct_if_observed"
    ] == 1.0
    assert result["observed_priced_only_arm_differences"][
        "SELECTED_MINUS_ONE_LANE"
    ]["mean_if_each_arm_observed_only_difference_pp"] == 2.0
    assert result["Nifty500_price_only_change_pct"] == 0.1
    for item in result["original_symbol_isin_rows"]:
        assert item["actual_trade_executed"] is False
        assert item["economic_total_return_calculated"] is False
    assert result["live_capital_allowed"] is False
    assert result["one_cross_section_demonstrates_replicable_alpha"] is False
    assert result["sector_size_beta_neutral_or_causal_inference_available"] is False
    validate_hg009_price_only_diagnostic(
        result, horizon_sessions=1,
        market_snapshots=[_packet(args, DATES[0])], **args
    )


def test_h5_requires_all_exact_frozen_market_sessions_and_no_fake_holidays():
    args = _inputs()
    originals = [_packet(args, day) for day in DATES]
    result = _evaluate(5, originals, args)
    assert result["official_exit_date"] == "2026-10-22"
    assert result["exact_frozen_holding_sessions"] == DATES
    assert "2026-10-20" not in result["exact_frozen_holding_sessions"]
    assert result["arm_descriptive_statistics"]["SELECTED"][
        "median_price_change_pct_if_observed"
    ] == 20.0
    assert len(result["official_source_evidence"]) == 5
    with pytest.raises(
        AlphaContractError, match="missing original intermediate"
    ):
        _evaluate(5, originals[:3] + originals[4:], args)
    altered = copy.deepcopy(originals)
    altered[2] = altered[3]
    with pytest.raises(
        AlphaContractError, match="missing/shifted/duplicate"
    ):
        _evaluate(5, altered, args)


def test_unpriceable_intermediate_stock_never_disappears_or_becomes_zero():
    args = _inputs()
    first = args["selected"]["selected"][0]
    identity = (first["symbol"], first["isin"])
    originals = [
        _packet(args, day, missing=identity if day == "2026-10-19" else None)
        for day in DATES
    ]
    result = _evaluate(5, originals, args)
    selected = result["arm_descriptive_statistics"]["SELECTED"]
    assert selected["original_fixed_denominator"] == 100
    assert selected["priced_observation_count"] == 99
    assert selected["missing_or_changed_source_count"] == 1
    row = next(
        x for x in result["original_symbol_isin_rows"]
        if (x["symbol"], x["frozen_isin"]) == identity
    )
    assert row["source_complete_all_intermediate_dates"] is False
    assert row["state"] == "INCOMPLETE_SOURCE_WINDOW_NO_PRICE_CHANGE"
    assert row["unadjusted_gross_stock_price_change_fraction"] is None
    assert row["original_missing_source_receipts"] == [{
        "session_date": "2026-10-19",
        "source_state": "ISIN_CHANGED_REQUIRES_ORIGINAL_ACTION",
    }]
    assert result["unobserved_issuers_count_as_zero_return"] is False


def test_no_h20_or_h60_without_official_special_and_next_calendar():
    args = _inputs()
    with pytest.raises(AlphaContractError, match="H20/H60"):
        _evaluate(20, [_packet(args, DATES[0])], args)
    with pytest.raises(AlphaContractError, match="H20/H60"):
        _evaluate(60, [_packet(args, DATES[0])], args)


def test_source_tampering_or_price_evaluation_before_market_close_fails_closed():
    args = _inputs()
    original = _packet(args, DATES[0])
    original["source_identity_rows"][0]["ohlcv"]["close_inr"] = 500000.0
    with pytest.raises(AlphaContractError, match="tampered source packet"):
        _evaluate(1, [original], args)

    normal = _packet(args, DATES[0])
    with pytest.raises(AlphaContractError, match="before exit session close"):
        build_hg009_price_only_diagnostic(
            horizon_sessions=1,
            market_snapshots=[normal],
            evaluated_at_utc="2026-10-15T09:59:59Z",
            **args,
        )
    altered = _evaluate(1, [_packet(args, DATES[0])], args)
    altered["arm_descriptive_statistics"]["SELECTED"][
        "mean_price_change_pct_if_observed"
    ] = 100000
    with pytest.raises(AlphaContractError, match="report hash altered"):
        validate_hg009_price_only_diagnostic(
            altered, horizon_sessions=1,
            market_snapshots=[_packet(args, DATES[0])], **args,
        )


def test_original_source_replay_cli_is_safe_before_future_market_source():
    run = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate_hg009_p006_price.py",
            "--check",
        ],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    result = json.loads(run.stdout)
    assert result["live_capital_allowed"] is False
    assert result["economic_total_returns_computed"] is False
    assert result["scientific_causal_alpha_claim"] is False
    assert not any(x["changed"] for x in result["ready"])
