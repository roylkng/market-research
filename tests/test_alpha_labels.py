from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_labels import build_labels
from marketlab.alpha_market import DailyEquityObservation
from marketlab.marketdata import IndexDailyPrice


def _panels(sessions=70, isin="INE000000001"):
    start = date(2026, 1, 1)
    stocks = []
    benchmarks = []
    stock_close = 100.0
    benchmark_close = 20_000.0
    for index in range(sessions):
        day = (start + timedelta(days=index)).isoformat()
        stock_open = stock_close
        stock_close *= 1.001
        benchmark_open = benchmark_close
        benchmark_close *= 1.0005
        stocks.append(
            DailyEquityObservation(
                session_date=day,
                symbol="TEST",
                isin=isin,
                open_price=stock_open,
                high_price=max(stock_open, stock_close) * 1.01,
                low_price=min(stock_open, stock_close) * 0.99,
                close_price=stock_close,
                previous_close=stock_open,
                volume=100_000,
                turnover_inr=30_000_000,
                trade_count=1_000,
            )
        )
        benchmarks.append(
            IndexDailyPrice(
                benchmark_id="nifty_500",
                index_name="Nifty 500",
                session_date=day,
                open_price=benchmark_open,
                close_price=benchmark_close,
            )
        )
    return stocks, benchmarks


def test_labels_use_next_session_open_and_horizon_close():
    stocks, benchmarks = _panels()
    feature_session = benchmarks[0].session_date
    labels = build_labels(
        stocks,
        benchmarks,
        symbol="TEST",
        isin="INE000000001",
        feature_session=feature_session,
        evaluation_as_of_session=benchmarks[-1].session_date,
    )
    by_horizon = {row["horizon_sessions"]: row for row in labels["records"]}
    one = by_horizon[1]
    assert one["status"] == "COMPLETE"
    assert one["entry_session"] == benchmarks[1].session_date
    assert one["exit_session"] == benchmarks[1].session_date
    assert one["excess_return"] > 0

    twenty = by_horizon[20]
    assert twenty["entry_session"] == benchmarks[1].session_date
    assert twenty["exit_session"] == benchmarks[20].session_date


def test_labels_do_not_open_immature_horizons():
    stocks, benchmarks = _panels()
    labels = build_labels(
        stocks,
        benchmarks,
        symbol="TEST",
        isin="INE000000001",
        feature_session=benchmarks[0].session_date,
        evaluation_as_of_session=benchmarks[10].session_date,
    )
    by_horizon = {row["horizon_sessions"]: row for row in labels["records"]}
    assert by_horizon[1]["status"] == "COMPLETE"
    assert by_horizon[5]["status"] == "COMPLETE"
    assert by_horizon[20]["status"] == "NOT_MATURE"
    assert by_horizon[60]["status"] == "NOT_MATURE"
    assert by_horizon[20]["stock_return"] is None


def test_labels_fail_closed_on_identity_change():
    stocks, benchmarks = _panels()
    exit_day = benchmarks[20].session_date
    stocks = [
        (
            DailyEquityObservation(
                **{
                    **row.__dict__,
                    "isin": "INE999999999",
                }
            )
            if row.session_date == exit_day
            else row
        )
        for row in stocks
    ]
    labels = build_labels(
        stocks,
        benchmarks,
        symbol="TEST",
        isin="INE000000001",
        feature_session=benchmarks[0].session_date,
        evaluation_as_of_session=benchmarks[-1].session_date,
        horizons=(20,),
    )
    assert labels["records"][0]["status"] == "IDENTITY_MISMATCH"
    assert labels["records"][0]["excess_return"] is None


def test_labels_reject_future_or_unknown_evaluation_session():
    stocks, benchmarks = _panels()
    with pytest.raises(AlphaContractError, match="not a completed session"):
        build_labels(
            stocks,
            benchmarks,
            symbol="TEST",
            isin="INE000000001",
            feature_session=benchmarks[0].session_date,
            evaluation_as_of_session="2030-01-01",
        )
