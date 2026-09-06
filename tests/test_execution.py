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


def _calendar() -> TradingCalendar:
    # Explicit sessions. 2026-09-15 is intentionally absent despite being a weekday.
    days = [
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
    return TradingCalendar([_session(day) for day in days], version="NSE-CALENDAR-TEST-v1")


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
    source_timestamp_utc: str | None = None,
    source: str = "TEST-MARKET-DATA",
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
    # Publication is Sunday Sep 6. Sep 7 is skipped, Sep 8 is entry. Because the
    # explicit calendar omits Sep 15, the 20th holding session is Oct 6.
    stock = [
        _bar(
            "TESTCO",
            "2026-09-08",
            open_price=100.0,
            close_price=101.0,
            source="STOCK-ENTRY-SOURCE",
        ),
        _bar(
            "TESTCO",
            "2026-10-06",
            open_price=119.0,
            close_price=120.0,
            source="STOCK-EXIT-SOURCE",
        ),
    ]
    benchmarks = [
        _bar("nifty_50", "2026-09-08", open_price=200.0),
        _bar("nifty_50", "2026-10-06", close_price=210.0),
        _bar("nifty_200_momentum_30", "2026-09-08", open_price=300.0),
        _bar("nifty_200_momentum_30", "2026-10-06", close_price=306.0),
    ]
    return stock, benchmarks


def _build(*, signal=None, stock_bars=None, benchmark_bars=None, as_of: str):
    return build_paper_position(
        signal or _signal(),
        exchange_published_at_utc="2026-09-06T06:30:00+00:00",
        calendar=_calendar(),
        stock_bars=[] if stock_bars is None else stock_bars,
        benchmark_bars=[] if benchmark_bars is None else benchmark_bars,
        evaluation_as_of_utc=as_of,
    )


def test_execution_rule_hash_validates():
    document = load_and_validate_execution_rule("registry/h002_execution_rule.yaml")
    assert document["id"] == "H002-X001"
    assert document["live_capital"] is False
    assert document["cost_scenarios_round_trip_bps"] == [0, 25, 50]


def test_calendar_uses_explicit_sessions_and_has_deterministic_hash():
    one = _calendar()
    two = _calendar()
    entry, exit_session = one.schedule("2026-09-06T06:30:00+00:00")
    assert entry.session_date == "2026-09-08"
    assert exit_session.session_date == "2026-10-06"
    assert "2026-09-15" not in {session.session_date for session in one.sessions}
    assert one.sha256 == two.sha256
    assert len(one.sha256) == 64


def test_publication_local_date_not_utc_date_controls_schedule():
    # 19:00 UTC on Sep 6 is 00:30 IST on Sep 7. Sep 7 is event local date,
    # so Sep 8 is the first subsequent session and Sep 9 is the entry.
    entry, _ = _calendar().schedule("2026-09-06T19:00:00+00:00")
    assert entry.session_date == "2026-09-09"


def test_no_signal_is_skipped_without_market_data():
    position = _build(
        signal=_signal("NO_SIGNAL"),
        as_of="2026-09-06T07:00:00+00:00",
    )
    assert position.status == "SKIPPED"
    assert position.entry_session_date is None
    assert position.live_order_created is False


def test_before_entry_open_is_pending_not_false_missing_entry():
    position = _build(as_of="2026-09-08T03:00:00+00:00")
    assert position.status == "PENDING"
    assert position.skip_or_pending_reason == "entry_not_due"
    assert position.entry_session_date == "2026-09-08"


def test_missing_entry_between_open_and_close_remains_pending():
    position = _build(as_of="2026-09-08T04:00:00+00:00")
    assert position.status == "PENDING"
    assert position.skip_or_pending_reason == "entry_market_data_not_final_as_of"


def test_future_entry_record_is_unavailable_not_leaked():
    future_record = _bar(
        "TESTCO",
        "2026-09-08",
        open_price=100.0,
        source_timestamp_utc="2026-09-08T12:00:00+00:00",
    )
    position = _build(
        stock_bars=[future_record],
        as_of="2026-09-08T04:00:00+00:00",
    )
    assert position.status == "PENDING"
    assert position.entry_price is None
    assert position.skip_or_pending_reason == "entry_market_data_not_final_as_of"


def test_signal_scored_after_entry_open_cannot_backfill_a_trade():
    late_signal = replace(_signal(), scored_at_utc="2026-09-08T04:00:00+00:00")
    position = _build(signal=late_signal, as_of="2026-09-08T04:01:00+00:00")
    assert position.status == "SKIPPED"
    assert position.skip_or_pending_reason == "signal_not_available_before_entry_open"


def test_completed_position_uses_exact_open_close_and_records_sources():
    stock, benchmarks = _completed_bars()
    position = _build(
        stock_bars=stock,
        benchmark_bars=benchmarks,
        as_of="2026-10-07T12:00:00+00:00",
    )
    assert position.status == "COMPLETED"
    assert position.entry_session_date == "2026-09-08"
    assert position.exit_session_date == "2026-10-06"
    assert position.entry_price == 100.0
    assert position.exit_price == 120.0
    assert position.entry_price_source == "STOCK-ENTRY-SOURCE"
    assert position.exit_price_source == "STOCK-EXIT-SOURCE"
    assert position.calendar_sha256 == _calendar().sha256
    assert position.gross_return_pct == pytest.approx(20.0)
    assert position.cost_stressed_return_pct == {
        "0": pytest.approx(20.0),
        "25": pytest.approx(19.75),
        "50": pytest.approx(19.5),
    }
    by_id = {result.benchmark_id: result for result in position.benchmarks}
    assert by_id["nifty_50"].return_pct == pytest.approx(5.0)
    assert by_id["nifty_50"].excess_return_pct == pytest.approx(15.0)
    assert by_id["nifty_50"].entry_source == "TEST-MARKET-DATA"
    assert by_id["nifty_200_momentum_30"].return_pct == pytest.approx(2.0)
    assert by_id["nifty_200_momentum_30"].excess_return_pct == pytest.approx(18.0)
    assert position.live_order_created is False


@pytest.mark.parametrize(
    ("entry_bar", "reason"),
    [
        (None, "missing_entry_bar"),
        (_bar("TESTCO", "2026-09-08", open_price=None), "missing_entry_open"),
        (
            _bar("TESTCO", "2026-09-08", tradable_at_open=False),
            "entry_not_confirmed_tradable",
        ),
        (
            _bar("TESTCO", "2026-09-08", corporate_action_version=None),
            "missing_entry_corporate_action_version",
        ),
    ],
)
def test_unavailable_or_nontradable_entry_after_close_is_skipped(entry_bar, reason):
    stock = [] if entry_bar is None else [entry_bar]
    position = _build(
        stock_bars=stock,
        as_of="2026-09-08T13:00:00+00:00",
    )
    assert position.status == "SKIPPED"
    assert position.skip_or_pending_reason == reason
    assert position.gross_return_pct is None


def test_future_exit_bar_is_not_consumed_before_scheduled_close():
    stock, _ = _completed_bars()
    position = _build(
        stock_bars=stock,
        as_of="2026-10-05T12:00:00+00:00",
    )
    assert position.status == "PENDING"
    assert position.skip_or_pending_reason == "exit_not_due"
    assert position.exit_price is None


def test_missing_exit_is_unresolved_after_due_close():
    stock = [_bar("TESTCO", "2026-09-08", open_price=100.0)]
    position = _build(
        stock_bars=stock,
        as_of="2026-10-06T11:00:00+00:00",
    )
    assert position.status == "UNRESOLVED_EXIT"
    assert position.skip_or_pending_reason == "missing_exit_bar_after_due"


def test_exit_source_newer_than_as_of_is_unavailable_not_leaked():
    stock, _ = _completed_bars()
    stock[1] = _bar(
        "TESTCO",
        "2026-10-06",
        close_price=120.0,
        source_timestamp_utc="2026-10-07T12:00:00+00:00",
    )
    position = _build(
        stock_bars=stock,
        as_of="2026-10-06T11:00:00+00:00",
    )
    assert position.status == "UNRESOLVED_EXIT"
    assert position.skip_or_pending_reason == "exit_data_not_available_as_of"
    assert position.exit_price is None


def test_circuit_locked_exit_is_not_invented():
    stock, _ = _completed_bars()
    stock[1] = _bar(
        "TESTCO",
        "2026-10-06",
        close_price=120.0,
        tradable_at_close=False,
    )
    position = _build(
        stock_bars=stock,
        as_of="2026-10-07T12:00:00+00:00",
    )
    assert position.status == "UNRESOLVED_EXIT"
    assert position.skip_or_pending_reason == "exit_not_confirmed_tradable"
    assert position.gross_return_pct is None


def test_market_record_cannot_claim_close_before_session_close():
    impossible = _bar(
        "TESTCO",
        "2026-09-08",
        close_price=101.0,
        source_timestamp_utc="2026-09-08T09:00:00+00:00",
    )
    with pytest.raises(ExecutionError, match="containing close predates"):
        _build(
            stock_bars=[impossible],
            as_of="2026-09-08T09:30:00+00:00",
        )


def test_duplicate_market_bars_are_rejected():
    bar = _bar("TESTCO", "2026-09-08")
    with pytest.raises(ExecutionError, match="duplicate market bar"):
        _build(
            stock_bars=[bar, bar],
            as_of="2026-09-08T13:00:00+00:00",
        )


def test_missing_benchmark_is_reported_not_imputed():
    stock, benchmarks = _completed_bars()
    benchmarks = [bar for bar in benchmarks if bar.instrument_id != "nifty_200_momentum_30"]
    position = _build(
        stock_bars=stock,
        benchmark_bars=benchmarks,
        as_of="2026-10-07T12:00:00+00:00",
    )
    by_id = {result.benchmark_id: result for result in position.benchmarks}
    assert by_id["nifty_200_momentum_30"].status == "MISSING"
    assert by_id["nifty_200_momentum_30"].return_pct is None
    assert by_id["nifty_200_momentum_30"].reason == "missing_benchmark_bar"


def test_future_benchmark_data_is_reported_missing_not_used():
    stock, benchmarks = _completed_bars()
    benchmarks[-1] = _bar(
        "nifty_200_momentum_30",
        "2026-10-06",
        close_price=306.0,
        source_timestamp_utc="2026-10-08T12:00:00+00:00",
    )
    position = _build(
        stock_bars=stock,
        benchmark_bars=benchmarks,
        as_of="2026-10-07T12:00:00+00:00",
    )
    by_id = {result.benchmark_id: result for result in position.benchmarks}
    assert by_id["nifty_200_momentum_30"].status == "MISSING"
    assert by_id["nifty_200_momentum_30"].reason == "benchmark_data_not_available_as_of"


def test_entry_exit_corporate_action_version_mismatch_is_rejected():
    stock, benchmarks = _completed_bars()
    stock[1] = _bar(
        "TESTCO",
        "2026-10-06",
        close_price=120.0,
        corporate_action_version="CA-v2",
    )
    with pytest.raises(ExecutionError, match="corporate-action versions differ"):
        _build(
            stock_bars=stock,
            benchmark_bars=benchmarks,
            as_of="2026-10-07T12:00:00+00:00",
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
