from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from marketlab import h022_p001_outcomes as outcomes
from marketlab import h022_prospective as prospective

UNIVERSE_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")
CALENDAR_PATH = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json"
)
IST = ZoneInfo("Asia/Kolkata")


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _signal(
    *,
    source_char: str,
    published: str,
    frozen: str,
    primary_signal: float = 5.0,
    symbol: str = "ABB",
) -> dict:
    source_id = source_char * 64
    record = {
        "schema_version": 1,
        "protocol_id": prospective.PROTOCOL_ID,
        "hypothesis_id": prospective.HYPOTHESIS_ID,
        "feature_version": prospective.FEATURE_VERSION,
        "cohort_id": prospective.COHORT_ID,
        "cohort_sha256": prospective.COHORT_SHA256,
        "context_gate_sha256": "c" * 64,
        "source_id": source_id,
        "symbol": symbol,
        "exchange_published_at_utc": published,
        "source_record_id": "d" * 64,
        "raw_sha256": "e" * 64,
        "text_sha256": "f" * 64,
        "source_disposition": "PROSPECTIVE_SIGNAL_ELIGIBLE",
        "prior_source_id": "a" * 64,
        "prior_exchange_published_at_utc": "2026-09-10T03:00:00Z",
        "prior_source_disposition": "CONTEXT_ONLY_PRE_START",
        "prior_group_source_ids": ["a" * 64],
        "current": {},
        "prior": {},
        "primary_signal": primary_signal,
        "secondary_features": {},
        "deltas": {"forward_commitment_density_delta": primary_signal},
        "signal_status": "SIGNAL",
        "signal_frozen_at_utc": frozen,
        "outcome_data_attached": False,
    }
    record["signal_record_sha256"] = prospective._signal_record_hash(record)
    prospective.validate_signal_record(record)
    return record


def _ledger(*signals: dict) -> dict:
    ledger = prospective.new_signal_ledger()
    for signal in signals:
        ledger = prospective.append_signal_record(ledger, signal)
    return ledger


def _synthetic_calendar(session_count: int = 130) -> dict:
    sessions: list[dict[str, str]] = []
    cursor = date(2026, 9, 15)
    while len(sessions) < session_count:
        if cursor.weekday() < 5:
            opened = datetime.combine(
                cursor,
                datetime.min.time().replace(hour=9, minute=15),
                tzinfo=IST,
            ).astimezone(UTC)
            closed = datetime.combine(
                cursor,
                datetime.min.time().replace(hour=15, minute=30),
                tzinfo=IST,
            ).astimezone(UTC)
            sessions.append(
                {
                    "session_date": cursor.isoformat(),
                    "open_timestamp_utc": opened.isoformat().replace("+00:00", "Z"),
                    "close_timestamp_utc": closed.isoformat().replace("+00:00", "Z"),
                }
            )
        cursor += timedelta(days=1)
    return {
        "version": "TEST-CALENDAR-V1",
        "start_date": sessions[0]["session_date"],
        "end_date": sessions[-1]["session_date"],
        "sessions": sessions,
        "unresolved_special_dates": [],
    }


def _abb_identity() -> tuple[str, str]:
    universe = _load(UNIVERSE_PATH)
    member = next(row for row in universe["members"] if row["symbol"] == "ABB")
    return str(member["isin"]), str(member.get("series") or "EQ")


def _stock_bar(session_date: str, *, open_price: float, close_price: float) -> dict:
    isin, series = _abb_identity()
    return {
        "session_date": session_date,
        "symbol_requested": "ABB",
        "symbol_observed": "ABB",
        "isin_requested": isin,
        "isin_observed": isin,
        "series": series,
        "identity_mode": "EXACT_CURRENT_U001_ISIN",
        "open": open_price,
        "close": close_price,
        "source_url": f"https://nsearchives.nseindia.com/{session_date}.zip",
    }


def _benchmark_bar(session_date: str, *, open_price: float, close_price: float) -> dict:
    return {
        "session_date": session_date,
        "open": open_price,
        "close": close_price,
        "source_url": f"https://nsearchives.nseindia.com/nifty500-{session_date}.csv",
    }


def _evaluation_after(calendar: dict, session_index: int) -> str:
    session = calendar["sessions"][session_index]
    close = datetime.fromisoformat(session["close_timestamp_utc"])
    return (close + timedelta(minutes=5)).astimezone(UTC).isoformat().replace("+00:00", "Z")


def test_actual_reviewed_calendar_retains_unresolved_special_date() -> None:
    sessions, unresolved = outcomes.load_reviewed_sessions(_load(CALENDAR_PATH))
    assert sessions[0].session_date == "2026-09-01"
    assert sessions[-1].session_date == "2026-12-31"
    assert tuple(item.isoformat() for item in unresolved) == ("2026-11-08",)


def test_late_signal_freeze_never_receives_first_open_outcome() -> None:
    calendar = _synthetic_calendar()
    signal = _signal(
        source_char="1",
        published="2026-09-14T18:30:00Z",
        frozen="2026-09-15T04:00:00Z",
    )
    report = outcomes.build_prospective_outcome_report(
        _ledger(signal),
        universe_snapshot=_load(UNIVERSE_PATH),
        calendar=calendar,
        market_data_cutoff_session=calendar["sessions"][-1]["session_date"],
        evaluation_frozen_at_utc=_evaluation_after(calendar, -1),
        stock_bars={},
        benchmark_bars={},
        corporate_actions={},
    )
    row = report["records"][0]
    assert row["execution_status"] == "LATE_SIGNAL_FREEZE"
    assert all(
        row["horizons"][str(horizon)]["status"] == "LATE_SIGNAL_FREEZE"
        for horizon in outcomes.HORIZONS
    )
    summary = outcomes.summarize_prospective_outcomes(report)
    assert summary["primary_classification"] == "INSUFFICIENT_COVERAGE"
    assert summary["horizons"]["60"]["late_signal_freeze_count"] == 1
    assert summary["horizons"]["60"]["challenge_signal_count"] == 0


def test_complete_20_session_return_reuses_frozen_h022_math() -> None:
    calendar = _synthetic_calendar()
    signal = _signal(
        source_char="2",
        published="2026-09-14T18:30:00Z",
        frozen="2026-09-15T03:30:00Z",
    )
    entry_date = calendar["sessions"][0]["session_date"]
    exit_20 = calendar["sessions"][19]["session_date"]
    report = outcomes.build_prospective_outcome_report(
        _ledger(signal),
        universe_snapshot=_load(UNIVERSE_PATH),
        calendar=calendar,
        market_data_cutoff_session=exit_20,
        evaluation_frozen_at_utc=_evaluation_after(calendar, 19),
        stock_bars={
            (entry_date, "ABB"): _stock_bar(entry_date, open_price=100.0, close_price=101.0),
            (exit_20, "ABB"): _stock_bar(exit_20, open_price=109.0, close_price=110.0),
        },
        benchmark_bars={
            entry_date: _benchmark_bar(entry_date, open_price=200.0, close_price=201.0),
            exit_20: _benchmark_bar(exit_20, open_price=209.0, close_price=210.0),
        },
        corporate_actions={"ABB": {"status": "READY", "actions": []}},
    )
    row = report["records"][0]
    assert row["execution_status"] == "EXECUTABLE_AT_H022_X001_ENTRY"
    result = row["horizons"]["20"]
    assert result["status"] == "COMPLETE"
    assert result["stock_return_pct"] == pytest.approx(10.0)
    assert result["benchmark_return_pct"] == pytest.approx(5.0)
    assert result["gross_excess_pp"] == pytest.approx(5.0)
    assert result["cost_adjusted_excess_pp"] == pytest.approx(4.5)
    assert result["beat_benchmark"] is True
    assert row["horizons"]["60"]["status"] == "NOT_MATURE"


def test_unresolved_november_special_session_blocks_primary_60_session_exit() -> None:
    calendar = _load(CALENDAR_PATH)
    signal = _signal(
        source_char="3",
        published="2026-09-14T18:30:00Z",
        frozen="2026-09-15T03:30:00Z",
    )
    report = outcomes.build_prospective_outcome_report(
        _ledger(signal),
        universe_snapshot=_load(UNIVERSE_PATH),
        calendar=calendar,
        market_data_cutoff_session="2026-12-31",
        evaluation_frozen_at_utc="2026-12-31T10:05:00Z",
        stock_bars={},
        benchmark_bars={},
        corporate_actions={},
    )
    row = report["records"][0]
    assert row["horizons"]["20"]["status"] == "MISSING_ENTRY_STOCK_BAR"
    assert row["horizons"]["60"]["status"] == "CALENDAR_UNRESOLVED_SPECIAL_SESSION"
    assert row["horizons"]["60"]["unresolved_special_dates"] == ["2026-11-08"]
    assert row["horizons"]["120"]["status"] == "CALENDAR_COVERAGE_INSUFFICIENT"
    summary = outcomes.summarize_prospective_outcomes(report)
    assert summary["horizons"]["60"]["calendar_pending_count"] == 1
    assert summary["horizons"]["60"]["mature_signal_count"] == 0


def test_corporate_action_blocks_mature_horizon_without_return() -> None:
    calendar = _synthetic_calendar()
    signal = _signal(
        source_char="4",
        published="2026-09-14T18:30:00Z",
        frozen="2026-09-15T03:30:00Z",
    )
    entry_date = calendar["sessions"][0]["session_date"]
    exit_20 = calendar["sessions"][19]["session_date"]
    report = outcomes.build_prospective_outcome_report(
        _ledger(signal),
        universe_snapshot=_load(UNIVERSE_PATH),
        calendar=calendar,
        market_data_cutoff_session=exit_20,
        evaluation_frozen_at_utc=_evaluation_after(calendar, 19),
        stock_bars={(entry_date, "ABB"): _stock_bar(entry_date, open_price=100, close_price=100)},
        benchmark_bars={entry_date: _benchmark_bar(entry_date, open_price=200, close_price=200)},
        corporate_actions={
            "ABB": {
                "status": "READY",
                "actions": [
                    {
                        "ex_date": calendar["sessions"][5]["session_date"],
                        "subject": "Stock Split",
                    }
                ],
            }
        },
    )
    horizon = report["records"][0]["horizons"]["20"]
    assert horizon["status"] == "CORPORATE_ACTION_BLOCKED"
    assert "gross_excess_pp" not in horizon
    summary = outcomes.summarize_prospective_outcomes(report)
    assert summary["horizons"]["20"]["mature_signal_count"] == 1
    assert summary["horizons"]["20"]["complete_count"] == 0


def test_evaluation_refuses_cutoff_session_that_has_not_closed() -> None:
    calendar = _synthetic_calendar()
    signal = _signal(
        source_char="5",
        published="2026-09-14T18:30:00Z",
        frozen="2026-09-15T03:30:00Z",
    )
    first = calendar["sessions"][0]
    open_time = first["open_timestamp_utc"]
    with pytest.raises(outcomes.H022P001OutcomeError, match="had not completed"):
        outcomes.build_prospective_outcome_report(
            _ledger(signal),
            universe_snapshot=_load(UNIVERSE_PATH),
            calendar=calendar,
            market_data_cutoff_session=first["session_date"],
            evaluation_frozen_at_utc=open_time,
            stock_bars={},
            benchmark_bars={},
            corporate_actions={},
        )
