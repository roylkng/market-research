from __future__ import annotations

from dataclasses import replace

import pytest

from marketlab.execution import (
    ExecutionError,
    PriceBar,
    TradingCalendar,
    TradingSession,
    build_paper_position,
)
from marketlab.h002 import H002SignalResult, PriceReference


def _session(day: str) -> TradingSession:
    return TradingSession(
        session_date=day,
        open_timestamp_utc=f"{day}T03:45:00+00:00",
        close_timestamp_utc=f"{day}T10:00:00+00:00",
    )


def _calendar() -> TradingCalendar:
    # Explicit sessions. 2026-09-15 is intentionally absent despite being a weekday.
    days = [
        "2026-09-03",
        "2026-09-04",
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


def _signal(
    bucket: str = "POSITIVE", *, scored_at: str = "2026-09-06T06:31:00+00:00"
) -> H002SignalResult:
    return H002SignalResult(
        schema_version=1,
        rule_id="H002-R001",
        signal_version="ue_price_normalized_v1",
        event_id="event-1",
        event_version_id="event-version-1",
        expectation_id="expectation-1",
        symbol="TESTCO",
        scored_at_utc=scored_at,
        actual_basic_eps=12.0,
        expected_eps=10.0,
        surprise_eps=2.0,
        price_day_minus_2=100.0 if bucket != "NO_SIGNAL" else None,
        ue=0.02 if bucket != "NO_SIGNAL" else None,
        bucket=bucket,
        no_signal_reason="missing_baseline_basic_eps" if bucket == "NO_SIGNAL" else None,
    )


def _reference(day: str = "2026-09-03", *, value: float = 100.0) -> PriceReference:
    return PriceReference(
        symbol="TESTCO",
        role="price_day_minus_2",
        trading_date=day,
        close_timestamp_utc=f"{day}T10:00:00+00:00",
        close_price=value,
        source="TEST-REFERENCE",
        corporate_action_version="CA-v1",
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
        corporate_action_version=corporate_action_version,
        tradable_at_close=tradable_at_close,
    )


def _completed_bars():
    stock = [
        _bar(
            "TESTCO",
            "2026-09-08",
            open_price=100.0,
            close_price=101.0,
            source="ENTRY-SRC",
        ),
        _bar(
            "TESTCO",
            "2026-10-06",
            open_price=119.0,
            close_price=120.0,
            source="EXIT-SRC",
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
    signal=None,
    stock=None,
    benchmarks=None,
    as_of="2026-10-07T12:00:00+00:00",
    reference=None,
    **kwargs,
):
    return build_paper_position(
        _signal() if signal is None else signal,
        exchange_published_at_utc="2026-09-06T06:30:00+00:00",
        calendar=_calendar(),
        stock_bars=[] if stock is None else stock,
        benchmark_bars=[] if benchmarks is None else benchmarks,
        as_of_utc=as_of,
        price_reference=_reference() if reference is None else reference,
        **kwargs,
    )


def test_calendar_uses_explicit_sessions_and_frozen_holding_convention():
    entry, exit_session = _calendar().schedule("2026-09-06T06:30:00+00:00")
    assert entry.session_date == "2026-09-08"
    assert exit_session.session_date == "2026-10-06"
    assert "2026-09-15" not in {session.session_date for session in _calendar().sessions}


def test_publication_local_date_not_utc_date_controls_schedule():
    entry, _ = _calendar().schedule("2026-09-06T19:00:00+00:00")
    assert entry.session_date == "2026-09-09"


def test_calendar_has_content_digest_and_records_it_in_position():
    calendar = _calendar()
    assert len(calendar.sha256) == 64
    assert calendar.sha256 == _calendar().sha256
    position = build_paper_position(
        _signal("NO_SIGNAL"),
        exchange_published_at_utc="2026-09-06T06:30:00+00:00",
        calendar=calendar,
        stock_bars=[],
        benchmark_bars=[],
        as_of_utc="2026-09-06T07:00:00+00:00",
    )
    assert position.calendar_snapshot_sha256 == calendar.sha256
    assert position.schema_version == 3


def test_reference_is_second_session_strictly_before_publication_local_date():
    assert (
        _calendar().reference_session("2026-09-06T06:30:00+00:00").session_date
        == "2026-09-03"
    )
    with pytest.raises(ExecutionError, match="second trading session"):
        _build(
            as_of="2026-09-06T07:00:00+00:00",
            reference=_reference("2026-09-04"),
        )


def test_reference_close_timestamp_and_value_must_match_scored_signal():
    bad_timestamp = replace(
        _reference(), close_timestamp_utc="2026-09-03T09:59:59+00:00"
    )
    with pytest.raises(ExecutionError, match="reference session close"):
        _build(as_of="2026-09-06T07:00:00+00:00", reference=bad_timestamp)
    with pytest.raises(ExecutionError, match="does not match the scored signal"):
        _build(
            as_of="2026-09-06T07:00:00+00:00", reference=_reference(value=101.0)
        )


def test_no_signal_is_skipped_without_reference_or_market_data():
    position = build_paper_position(
        _signal("NO_SIGNAL"),
        exchange_published_at_utc="2026-09-06T06:30:00+00:00",
        calendar=_calendar(),
        stock_bars=[],
        benchmark_bars=[],
        as_of_utc="2026-09-06T07:00:00+00:00",
    )
    assert position.status == "SKIPPED"
    assert position.entry_session_date is None
    assert position.live_order_created is False


def test_non_no_signal_requires_scored_price_reference():
    with pytest.raises(ExecutionError, match="requires the scored price reference"):
        build_paper_position(
            _signal(),
            exchange_published_at_utc="2026-09-06T06:30:00+00:00",
            calendar=_calendar(),
            stock_bars=[],
            benchmark_bars=[],
            as_of_utc="2026-09-06T07:00:00+00:00",
        )


def test_before_entry_open_is_pending():
    position = _build(as_of="2026-09-08T03:00:00+00:00")
    assert position.status == "PENDING"
    assert position.skip_or_pending_reason == "entry_not_due"


def test_missing_entry_before_session_close_remains_pending():
    position = _build(as_of="2026-09-08T05:00:00+00:00")
    assert position.status == "PENDING"
    assert position.skip_or_pending_reason == "missing_entry_bar_before_entry_session_close"


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
def test_unavailable_or_nontradable_entry_skips_only_after_session_close(
    entry_bar, reason
):
    stock = [] if entry_bar is None else [entry_bar]
    position = _build(stock=stock, as_of="2026-09-08T13:00:00+00:00")
    assert position.status == "SKIPPED"
    assert position.skip_or_pending_reason == f"{reason}_after_entry_session_close"


def test_late_signal_decision_is_never_backfilled_at_entry_open():
    with pytest.raises(ExecutionError, match="strictly precede scheduled entry open"):
        _build(
            signal=_signal(scored_at="2026-09-08T04:00:00+00:00"),
            as_of="2026-09-08T05:00:00+00:00",
        )


def test_missing_exit_is_pending_before_close_and_unresolved_after_close():
    stock = [_bar("TESTCO", "2026-09-08", open_price=100.0)]
    before_due = _build(stock=stock, as_of="2026-10-06T09:00:00+00:00")
    after_due = _build(stock=stock, as_of="2026-10-06T11:00:00+00:00")
    assert before_due.status == "PENDING"
    assert before_due.skip_or_pending_reason == "exit_not_due"
    assert after_due.status == "UNRESOLVED_EXIT"
    assert after_due.skip_or_pending_reason == "missing_exit_bar_after_due_close"


def test_exit_tradability_must_be_confirmed():
    stock, benchmarks = _completed_bars()
    stock[1] = replace(stock[1], tradable_at_close=False)
    position = _build(stock=stock, benchmarks=benchmarks)
    assert position.status == "UNRESOLVED_EXIT"
    assert position.skip_or_pending_reason == "exit_not_confirmed_tradable_after_due_close"


def test_completed_position_uses_exact_window_benchmarks_costs_and_separate_sources():
    stock, benchmarks = _completed_bars()
    position = _build(stock=stock, benchmarks=benchmarks)
    assert position.status == "COMPLETED"
    assert position.reference_session_date == "2026-09-03"
    assert position.entry_session_date == "2026-09-08"
    assert position.exit_session_date == "2026-10-06"
    assert position.entry_price == 100.0
    assert position.exit_price == 120.0
    assert position.entry_price_source == "ENTRY-SRC"
    assert position.exit_price_source == "EXIT-SRC"
    assert position.entry_price_source_timestamp_utc is not None
    assert position.exit_price_source_timestamp_utc is not None
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
    assert by_id["nifty_50"].entry_source is not None
    assert by_id["nifty_50"].exit_source is not None
    assert position.live_order_created is False


def test_entry_exit_corporate_action_version_mismatch_is_rejected():
    stock, benchmarks = _completed_bars()
    stock[1] = replace(stock[1], corporate_action_version="CA-v2")
    with pytest.raises(ExecutionError, match="corporate-action versions differ"):
        _build(stock=stock, benchmarks=benchmarks)


def test_duplicate_market_bars_are_rejected_instead_of_last_write_wins():
    duplicate = _bar("TESTCO", "2026-09-08")
    with pytest.raises(ExecutionError, match="duplicate market bar"):
        _build(stock=[duplicate, duplicate], as_of="2026-09-08T13:00:00+00:00")


def test_market_data_source_timestamp_cannot_predate_value_it_contains():
    stock, benchmarks = _completed_bars()
    stock[1] = replace(
        stock[1], source_timestamp_utc="2026-10-06T09:00:00+00:00"
    )
    with pytest.raises(ExecutionError, match="predates close value"):
        _build(stock=stock, benchmarks=benchmarks)


def test_future_market_data_relative_to_evaluation_is_unavailable_not_consumed():
    bar = _bar(
        "TESTCO",
        "2026-09-08",
        open_price=100.0,
        close_price=None,
        source_timestamp_utc="2026-09-08T05:00:00+00:00",
    )
    position = _build(stock=[bar], as_of="2026-09-08T04:00:00+00:00")
    assert position.status == "PENDING"
    assert position.skip_or_pending_reason == "missing_entry_bar_before_entry_session_close"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, 0.0, True, "100"])
def test_invalid_market_prices_never_become_returns(bad):
    bar = _bar("TESTCO", "2026-09-08", open_price=bad)
    with pytest.raises(ExecutionError, match="finite positive number"):
        _build(stock=[bar], as_of="2026-09-08T13:00:00+00:00")


def test_cost_scenarios_are_frozen_and_cannot_be_optimized_after_outcomes():
    with pytest.raises(ExecutionError, match="cost scenarios are frozen"):
        _build(
            as_of="2026-09-06T07:00:00+00:00", cost_scenarios_bps=(0, 10, 20)
        )


def test_missing_benchmark_is_reported_not_imputed():
    stock, benchmarks = _completed_bars()
    benchmarks = [
        bar for bar in benchmarks if bar.instrument_id != "nifty_200_momentum_30"
    ]
    position = _build(stock=stock, benchmarks=benchmarks)
    by_id = {result.benchmark_id: result for result in position.benchmarks}
    assert by_id["nifty_200_momentum_30"].status == "MISSING"
    assert by_id["nifty_200_momentum_30"].return_pct is None
    assert by_id["nifty_200_momentum_30"].reason == "missing_benchmark_bar"


def test_sector_benchmark_requires_pre_registered_mapping_evidence():
    with pytest.raises(ExecutionError, match="pre-registered mapping version"):
        _build(as_of="2026-09-06T07:00:00+00:00", sector_benchmark_id="nifty_it")
    with pytest.raises(ExecutionError, match="registered before publication"):
        _build(
            as_of="2026-09-06T07:00:00+00:00",
            sector_benchmark_id="nifty_it",
            sector_benchmark_mapping_version="SECTOR-v1",
            sector_benchmark_mapping_sha256="a" * 64,
            sector_benchmark_assigned_at_utc="2026-09-06T06:30:00+00:00",
        )


def test_pre_registered_sector_benchmark_is_carried_into_observation():
    stock, benchmarks = _completed_bars()
    benchmarks.extend(
        [
            _bar("nifty_it", "2026-09-08", open_price=500.0),
            _bar("nifty_it", "2026-10-06", close_price=550.0),
        ]
    )
    position = _build(
        stock=stock,
        benchmarks=benchmarks,
        sector_benchmark_id="nifty_it",
        sector_benchmark_mapping_version="SECTOR-v1",
        sector_benchmark_mapping_sha256="a" * 64,
        sector_benchmark_assigned_at_utc="2026-09-05T12:00:00+00:00",
    )
    assert position.sector_benchmark_id == "nifty_it"
    assert position.sector_benchmark_mapping_version == "SECTOR-v1"
    assert position.sector_benchmark_mapping_sha256 == "a" * 64
    by_id = {result.benchmark_id: result for result in position.benchmarks}
    assert by_id["nifty_it"].return_pct == pytest.approx(10.0)


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
