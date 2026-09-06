from __future__ import annotations

from dataclasses import replace

import pytest

from marketlab.execution import (
    ExecutionError,
    PriceBar,
    TradingCalendar,
    TradingSession,
    build_paper_position,
    load_and_validate_execution_rule,
)
from marketlab.h002 import H002SignalResult


def _session(day: str) -> TradingSession:
    return TradingSession(
        session_date=day,
        open_timestamp_utc=f"{day}T03:45:00+00:00",
        close_timestamp_utc=f"{day}T10:00:00+00:00",
    )


def _session_days() -> list[str]:
    # 2026-09-15 is intentionally absent despite being a weekday.
    return [
        "2026-09-07",
        "2026-09-08",
        "2026-09-09",
        "2026-09-10",
        "2026-09-11",
        "2026-09-14",
        "2026-09-16",
        "2026-09-17",
        "2026-09-18",
        "2026-09-21",
        "2026-09-22",
        "2026-09-23",
        "2026-09-24",
        "2026-09-25",
        "2026-09-28",
        "2026-09-29",
        "2026-09-30",
        "2026-10-01",
        "2026-10-02",
        "2026-10-05",
        "2026-10-06",
        "2026-10-07",
        "2026-10-08",
        "2026-10-09",
        "2026-10-12",
    ]


def _calendar(*, version: str = "NSE-CALENDAR-TEST-v1") -> TradingCalendar:
    return TradingCalendar([_session(day) for day in _session_days()], version=version)


def _signal(bucket: str = "POSITIVE") -> H002SignalResult:
    return H002SignalResult(
        schema_version=1,
        rule_id="H002-R001",
        signal_version="ue_price_normalized_v1",
        event_id="event-1",
        event_version_id="event-version-1",
        expectation_id="expectation-1",
        symbol="TESTCO",
        scored_at_utc="2026-09-06T06:31:00+00:00",
        actual_basic_eps=12.0,
        expected_eps=10.0,
        surprise_eps=2.0,
        price_day_minus_2=100.0,
        ue=0.02 if bucket != "NO_SIGNAL" else None,
        bucket=bucket,
        no_signal_reason="missing_baseline_basic_eps" if bucket == "NO_SIGNAL" else None,
    )


def _bar(
    instrument: str,
    day: str,
    *,
    open_price: float | None = 100.0,
    close_price: float | None = 100.0,
    tradable_at_open: bool | None = True,
    tradable_at_close: bool | None = True,
    corporate_action_version: str | None = "CA-v1",
    source: str = "TEST-MARKET-DATA",
    source_timestamp_utc: str | None = None,
) -> PriceBar:
    return PriceBar(
        instrument_id=instrument,
        session_date=day,
        open_price=open_price,
        close_price=close_price,
        source=source,
        source_timestamp_utc=source_timestamp_utc or f"{day}T12:00:00+00:00",
        tradable_at_open=tradable_at_open,
        tradable_at_close=tradable_at_close,
        corporate_action_version=corporate_action_version,
    )


def _completed_bars():
    stock = [
        _bar(
            "TESTCO",
            "2026-09-08",
            open_price=100.0,
            close_price=101.0,
            source="ENTRY-SOURCE",
        ),
        _bar(
            "TESTCO",
            "2026-10-06",
            open_price=119.0,
            close_price=120.0,
            source="EXIT-SOURCE",
        ),
    ]
    benchmarks = [
        _bar("nifty_50", "2026-09-08", open_price=200.0),
        _bar("nifty_50", "2026-10-06", close_price=210.0),
        _bar("nifty_200_momentum_30", "2026-09-08", open_price=300.0),
        _bar("nifty_200_momentum_30", "2026-10-06", close_price=306.0),
    ]
    return stock, benchmarks


def _build(
    *,
    signal: H002SignalResult | None = None,
    stock_bars: list[PriceBar] | None = None,
    benchmark_bars: list[PriceBar] | None = None,
    as_of_utc: str = "2026-10-07T12:00:00+00:00",
):
    return build_paper_position(
        signal or _signal(),
        exchange_published_at_utc="2026-09-06T06:30:00+00:00",
        calendar=_calendar(),
        stock_bars=[] if stock_bars is None else stock_bars,
        benchmark_bars=[] if benchmark_bars is None else benchmark_bars,
        as_of_utc=as_of_utc,
    )


def test_execution_rule_hash_validates():
    document = load_and_validate_execution_rule("registry/h002_execution_rule.yaml")
    assert document["id"] == "H002-X001"
    assert document["live_capital"] is False


def test_calendar_uses_explicit_sessions_and_records_deterministic_hash():
    calendar = _calendar()
    entry, exit_session = calendar.schedule("2026-09-06T06:30:00+00:00")
    assert entry.session_date == "2026-09-08"
    assert exit_session.session_date == "2026-10-06"
    assert "2026-09-15" not in {session.session_date for session in calendar.sessions}
    assert len(calendar.sha256) == 64
    assert calendar.sha256 == _calendar().sha256
    assert calendar.sha256 != _calendar(version="NSE-CALENDAR-TEST-v2").sha256


def test_publication_local_date_not_utc_date_controls_schedule():
    entry, _ = _calendar().schedule("2026-09-06T19:00:00+00:00")
    assert entry.session_date == "2026-09-09"


def test_no_signal_is_skipped_without_market_data():
    position = _build(
        signal=_signal("NO_SIGNAL"),
        as_of_utc="2026-09-06T07:00:00+00:00",
    )
    assert position.status == "SKIPPED"
    assert position.entry_session_date is None
    assert position.calendar_snapshot_sha256 == _calendar().sha256
    assert position.live_order_created is False


def test_signal_decision_must_strictly_precede_entry_open():
    signal = replace(_signal(), scored_at_utc="2026-09-08T03:45:00+00:00")
    with pytest.raises(ExecutionError, match="strictly precede scheduled entry open"):
        _build(signal=signal, as_of_utc="2026-09-08T04:00:00+00:00")


def test_before_entry_open_is_pending():
    position = _build(as_of_utc="2026-09-08T03:00:00+00:00")
    assert position.status == "PENDING"
    assert position.skip_or_pending_reason == "entry_not_due"


def test_missing_entry_stays_pending_until_session_close_then_skips():
    before_close = _build(as_of_utc="2026-09-08T09:00:00+00:00")
    after_close = _build(as_of_utc="2026-09-08T10:01:00+00:00")
    assert before_close.status == "PENDING"
    assert before_close.skip_or_pending_reason == "missing_entry_bar_before_entry_session_close"
    assert after_close.status == "SKIPPED"
    assert after_close.skip_or_pending_reason == "missing_entry_bar_after_entry_session_close"


def test_future_market_data_is_unavailable_not_consumed():
    future_bar = _bar(
        "TESTCO",
        "2026-09-08",
        open_price=100.0,
        source_timestamp_utc="2026-09-08T12:00:00+00:00",
    )
    position = _build(
        stock_bars=[future_bar],
        as_of_utc="2026-09-08T09:00:00+00:00",
    )
    assert position.status == "PENDING"
    assert position.skip_or_pending_reason == "missing_entry_bar_before_entry_session_close"


def test_source_timestamp_cannot_predate_open_value():
    impossible = _bar(
        "TESTCO",
        "2026-09-08",
        open_price=100.0,
        source_timestamp_utc="2026-09-08T03:00:00+00:00",
    )
    with pytest.raises(ExecutionError, match="source predates open value"):
        _build(stock_bars=[impossible], as_of_utc="2026-09-08T09:00:00+00:00")


def test_duplicate_market_bars_are_rejected():
    bar = _bar("TESTCO", "2026-09-08")
    with pytest.raises(ExecutionError, match="duplicate market bar"):
        _build(stock_bars=[bar, bar])


def test_nonfinite_market_price_is_rejected():
    bar = _bar("TESTCO", "2026-09-08", open_price=float("nan"))
    with pytest.raises(ExecutionError, match="finite positive number"):
        _build(stock_bars=[bar])


def test_completed_position_records_calendar_entry_exit_provenance_and_benchmarks():
    stock, benchmarks = _completed_bars()
    position = _build(stock_bars=stock, benchmark_bars=benchmarks)
    assert position.status == "COMPLETED"
    assert position.schema_version == 2
    assert position.entry_session_date == "2026-09-08"
    assert position.exit_session_date == "2026-10-06"
    assert position.calendar_snapshot_sha256 == _calendar().sha256
    assert position.entry_price == 100.0
    assert position.exit_price == 120.0
    assert position.entry_price_source == "ENTRY-SOURCE"
    assert position.exit_price_source == "EXIT-SOURCE"
    assert position.entry_corporate_action_version == "CA-v1"
    assert position.exit_corporate_action_version == "CA-v1"
    assert position.gross_return_pct == pytest.approx(20.0)
    assert position.cost_stressed_return_pct == {
        "0": pytest.approx(20.0),
        "25": pytest.approx(19.75),
        "50": pytest.approx(19.5),
    }
    by_id = {result.benchmark_id: result for result in position.benchmarks}
    assert by_id["nifty_50"].return_pct == pytest.approx(5.0)
    assert by_id["nifty_50"].excess_return_pct == pytest.approx(15.0)
    assert by_id["nifty_200_momentum_30"].return_pct == pytest.approx(2.0)
    assert by_id["nifty_200_momentum_30"].excess_return_pct == pytest.approx(18.0)
    assert position.live_order_created is False


def test_nontradable_entry_pending_before_close_then_skipped_after_close():
    bar = _bar(
        "TESTCO",
        "2026-09-08",
        open_price=100.0,
        tradable_at_open=False,
        source_timestamp_utc="2026-09-08T04:00:00+00:00",
    )
    before_close = _build(stock_bars=[bar], as_of_utc="2026-09-08T09:00:00+00:00")
    after_close = _build(stock_bars=[bar], as_of_utc="2026-09-08T10:01:00+00:00")
    assert before_close.status == "PENDING"
    assert "entry_not_confirmed_tradable" in before_close.skip_or_pending_reason
    assert after_close.status == "SKIPPED"
    assert "entry_not_confirmed_tradable" in after_close.skip_or_pending_reason


def test_missing_exit_before_due_is_pending_and_after_due_is_unresolved():
    entry = _bar("TESTCO", "2026-09-08", open_price=100.0)
    before_due = _build(stock_bars=[entry], as_of_utc="2026-10-06T09:00:00+00:00")
    after_due = _build(stock_bars=[entry], as_of_utc="2026-10-06T11:00:00+00:00")
    assert before_due.status == "PENDING"
    assert before_due.skip_or_pending_reason == "exit_not_due"
    assert after_due.status == "UNRESOLVED_EXIT"
    assert after_due.skip_or_pending_reason == "missing_exit_bar_after_due_close"


def test_exit_must_be_confirmed_tradable():
    stock, benchmarks = _completed_bars()
    stock[1] = replace(stock[1], tradable_at_close=False)
    position = _build(stock_bars=stock, benchmark_bars=benchmarks)
    assert position.status == "UNRESOLVED_EXIT"
    assert position.skip_or_pending_reason == "exit_not_confirmed_tradable_after_due_close"


def test_source_timestamp_cannot_predate_close_value():
    stock, benchmarks = _completed_bars()
    stock[1] = replace(
        stock[1],
        source_timestamp_utc="2026-10-06T09:00:00+00:00",
    )
    with pytest.raises(ExecutionError, match="source predates close value"):
        _build(stock_bars=stock, benchmark_bars=benchmarks)


def test_entry_exit_corporate_action_versions_must_match():
    stock, benchmarks = _completed_bars()
    stock[1] = replace(stock[1], corporate_action_version="CA-v2")
    with pytest.raises(ExecutionError, match="corporate-action versions differ"):
        _build(stock_bars=stock, benchmark_bars=benchmarks)


def test_benchmark_newer_than_as_of_is_missing_not_consumed():
    stock, benchmarks = _completed_bars()
    benchmarks[-1] = replace(
        benchmarks[-1],
        source_timestamp_utc="2026-10-08T12:00:00+00:00",
    )
    position = _build(
        stock_bars=stock,
        benchmark_bars=benchmarks,
        as_of_utc="2026-10-07T12:00:00+00:00",
    )
    by_id = {result.benchmark_id: result for result in position.benchmarks}
    assert by_id["nifty_200_momentum_30"].status == "MISSING"
    assert by_id["nifty_200_momentum_30"].reason == "missing_benchmark_bar"


def test_negative_cost_scenario_is_rejected():
    with pytest.raises(ExecutionError, match="non-negative integer basis points"):
        build_paper_position(
            _signal(),
            exchange_published_at_utc="2026-09-06T06:30:00+00:00",
            calendar=_calendar(),
            stock_bars=[],
            benchmark_bars=[],
            as_of_utc="2026-09-08T03:00:00+00:00",
            cost_scenarios_bps=(-1,),
        )


def test_calendar_rejects_session_with_wrong_timestamp_date():
    with pytest.raises(ExecutionError, match="session open date mismatch"):
        TradingCalendar(
            [
                TradingSession(
                    session_date="2026-09-08",
                    open_timestamp_utc="2026-09-07T03:45:00+00:00",
                    close_timestamp_utc="2026-09-08T10:00:00+00:00",
                )
            ],
            version="bad",
        )
