from __future__ import annotations

from datetime import date, timedelta

import pytest

from marketlab.analyst import seal_decision
from marketlab.attribution import (
    advance_attribution,
    new_attribution_state,
    summarize_attribution,
)
from marketlab.paperfund import (
    hard_invalidation_exit,
    mark_session,
    new_fund,
    process_entry_batch,
)

POLICY_FROZEN_AT = "2026-09-11T18:46:13Z"


def make_decision(symbol: str = "AAA") -> dict:
    return seal_decision(
        {
            "schema_version": 1,
            "object_type": "ANALYST_DECISION",
            "live_capital_allowed": False,
            "decision_timestamp": "2026-09-13T18:00:00+05:30",
            "symbol": symbol,
            "isin": "INE000A01001",
            "company_name": f"{symbol} Ltd",
            "sector": "Industrials",
            "benchmark": "NIFTY 500",
            "horizon_sessions": 60,
            "validation_role": "PROSPECTIVE_VALIDATION",
            "business_thesis": "Frozen attribution test thesis.",
            "thesis_evidence": [
                {
                    "source_ref": "repo://test-evidence.json",
                    "available_at": "2026-09-13T17:00:00+05:30",
                }
            ],
            "valuation_assumptions": {"status": "ACCEPTABLE"},
            "signal_states": {
                "h019": {"state": "MISSING", "evidence_ref": None},
                "h021": {"state": "MISSING_EXPECTATION_SIGNAL", "evidence_ref": None},
                "h013": {"state": "NOT_DUE", "evidence_ref": None},
                "h020": {
                    "state": "PAPER_ENTRY_ELIGIBLE_TREND",
                    "evidence_ref": "repo://h020.json",
                },
            },
            "market_regime": "BEARISH",
            "sector_regime": "NEUTRAL",
            "catalysts": [],
            "invalidations": [
                {"condition": "guidance withdrawn", "severity": "HARD"}
            ],
            "scenarios": {
                "bear": {"narrative": "Bear.", "benchmark_relative_return_pct": None},
                "base": {"narrative": "Base.", "benchmark_relative_return_pct": None},
                "bull": {"narrative": "Bull.", "benchmark_relative_return_pct": None},
            },
            "forecast": {
                "expected_benchmark_relative_return_pct": None,
                "p10_benchmark_relative_return_pct": None,
                "p50_benchmark_relative_return_pct": None,
                "p90_benchmark_relative_return_pct": None,
                "probability_beat_benchmark": None,
                "expected_mae_pct": None,
                "calibration_status": "UNAVAILABLE",
            },
            "missing_information": [],
            "analyst_action": "PORTFOLIO_ELIGIBLE",
        }
    )


def entered_fund() -> tuple[dict, dict]:
    decision = make_decision()
    fund = new_fund(
        book="PROSPECTIVE_VALIDATION",
        policy_frozen_at=POLICY_FROZEN_AT,
    )
    fund = process_entry_batch(
        fund,
        [decision],
        session_date="2026-09-14",
        open_prices={"AAA": 100.0},
    )
    fund = mark_session(
        fund,
        session_date="2026-09-14",
        bars={"AAA": {"close": 102.0, "high": 103.0, "low": 99.0}},
    )
    return fund, decision


def make_attribution(fund: dict) -> dict:
    return new_attribution_state(
        fund,
        benchmark_name="NIFTY 500",
        benchmark_basis="PRICE",
        benchmark_source_ref="fixture://official-nifty500-price",
    )


def test_first_session_links_entry_and_benchmark_shadow_nav() -> None:
    fund, _ = entered_fund()
    attribution = make_attribution(fund)
    attribution = advance_attribution(
        attribution,
        fund,
        session_date="2026-09-14",
        benchmark_bar={"open": 200.0, "close": 202.0},
    )

    assert attribution["first_session_date"] == "2026-09-14"
    assert attribution["benchmark_start_open"] == 200.0
    assert attribution["nav_history"][0]["benchmark_nav"] == pytest.approx(1_010_000.0)
    decision_id = next(iter(attribution["position_benchmarks"]))
    assert attribution["position_benchmarks"][decision_id]["benchmark_entry_open"] == 200.0
    assert attribution["benchmark"]["dividend_mismatch"] is True


def test_total_return_basis_is_rejected_without_genuine_open_series() -> None:
    fund = new_fund(
        book="PROSPECTIVE_VALIDATION",
        policy_frozen_at=POLICY_FROZEN_AT,
    )
    with pytest.raises(ValueError, match="requires PRICE basis"):
        new_attribution_state(
            fund,
            benchmark_name="NIFTY 500 TRI",
            benchmark_basis="TOTAL_RETURN",
            benchmark_source_ref="fixture://daily-tri-close-only",
        )


def test_position_exit_computes_same_interval_benchmark_excess() -> None:
    fund, decision = entered_fund()
    attribution = make_attribution(fund)
    attribution = advance_attribution(
        attribution,
        fund,
        session_date="2026-09-14",
        benchmark_bar={"open": 200.0, "close": 202.0},
    )

    fund = hard_invalidation_exit(
        fund,
        decision=decision,
        session_date="2026-09-15",
        exit_price=110.0,
        condition="guidance withdrawn",
    )
    fund = mark_session(fund, session_date="2026-09-15", bars={})
    attribution = advance_attribution(
        attribution,
        fund,
        session_date="2026-09-15",
        benchmark_bar={"open": 203.0, "close": 204.0},
    )

    row = attribution["closed_position_attribution"][0]
    assert row["benchmark_return"] == pytest.approx(0.02)
    assert row["stock_gross_return"] == pytest.approx(0.10)
    assert row["gross_excess_pp"] == pytest.approx(8.0)
    assert row["net_excess_pp"] < row["gross_excess_pp"]
    assert row["net_beat_benchmark"] is True


def test_attribution_fails_if_prior_entry_session_was_skipped() -> None:
    fund, _ = entered_fund()
    fund = mark_session(
        fund,
        session_date="2026-09-15",
        bars={"AAA": {"close": 103.0}},
    )
    attribution = make_attribution(fund)
    with pytest.raises(ValueError, match="missed prior-session ENTRY_FILLED"):
        advance_attribution(
            attribution,
            fund,
            session_date="2026-09-15",
            benchmark_bar={"open": 203.0, "close": 204.0},
        )


def test_summary_reports_cash_drawdown_and_information_ratio_after_20_sessions() -> None:
    fund = new_fund(
        book="PROSPECTIVE_VALIDATION",
        policy_frozen_at=POLICY_FROZEN_AT,
    )
    attribution = make_attribution(fund)
    start = date(2026, 9, 14)
    benchmark_open = 100.0
    prior_close = benchmark_open
    for offset in range(20):
        session = start + timedelta(days=offset)
        fund = mark_session(fund, session_date=session.isoformat(), bars={})
        close = prior_close * (1.002 if offset % 2 == 0 else 0.999)
        attribution = advance_attribution(
            attribution,
            fund,
            session_date=session.isoformat(),
            benchmark_bar={"open": prior_close, "close": close},
        )
        prior_close = close

    summary = summarize_attribution(attribution)
    assert summary["sessions"] == 20
    assert summary["current_cash_weight"] == pytest.approx(1.0)
    assert summary["average_cash_weight"] == pytest.approx(1.0)
    assert summary["information_ratio"] is not None
    assert summary["closed_positions"] == 0
    assert summary["net_benchmark_beat_rate"] is None


def test_benchmark_bar_must_be_positive_and_complete() -> None:
    fund = new_fund(
        book="PROSPECTIVE_VALIDATION",
        policy_frozen_at=POLICY_FROZEN_AT,
    )
    fund = mark_session(fund, session_date="2026-09-14", bars={})
    attribution = make_attribution(fund)
    with pytest.raises((TypeError, ValueError), match="benchmark close"):
        advance_attribution(
            attribution,
            fund,
            session_date="2026-09-14",
            benchmark_bar={"open": 100.0},
        )
