from datetime import UTC, date, datetime

from marketlab.alpha import digest
from marketlab.alpha_prospective_futures_sources import (
    new_futures_source_ledger,
)
from marketlab.alpha_prospective_sources import new_source_ledger
from marketlab.alpha_sc003_preopen import new_sc003_ledger
from marketlab.calendar_snapshot import build_calendar_snapshot
from marketlab.prospective_health import build_prospective_health_summary
from marketlab.rm001_c002 import new_forecast_ledger, new_outcome_ledger


def _rehash(ledger, field="ledger_sha256"):
    unsigned = dict(ledger)
    unsigned.pop(field, None)
    ledger[field] = digest(unsigned)
    return ledger


def _calendar():
    payload = {
        "CM": [
            {
                "tradingDate": "02-Oct-2026",
                "description": "Mahatma Gandhi Jayanti",
            }
        ]
    }
    raw = b'{"CM":[{"tradingDate":"02-Oct-2026","description":"Mahatma Gandhi Jayanti"}]}'
    return build_calendar_snapshot(
        payload,
        raw_holiday_bytes=raw,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 6),
        captured_at=datetime(2026, 9, 1, tzinfo=UTC),
        version="TEST-CALENDAR-v1",
    )


def _sc001_ready():
    ledger = new_source_ledger()
    attempt = {
        "seq": 1,
        "session_date": "2026-10-01",
        "captured_at_utc": "2026-10-01T12:00:00+00:00",
        "decision_cutoff_utc": "2026-10-01T13:00:00+00:00",
        "captured_before_or_at_cutoff": True,
        "market": {"status": "READY"},
        "delivery": {"status": "READY"},
        "eligible_before_cutoff": True,
        "live_capital_allowed": False,
    }
    attempt["attempt_sha256"] = digest(attempt)
    ledger["attempts"] = [attempt]
    ledger["attempt_count"] = 1
    return _rehash(ledger)


def _sc002_late_ready():
    ledger = new_futures_source_ledger()
    attempt = {
        "seq": 1,
        "session_date": "2026-10-01",
        "captured_at_utc": "2026-10-01T17:20:00+00:00",
        "decision_cutoff_utc": "2026-10-01T13:00:00+00:00",
        "captured_before_or_at_cutoff": False,
        "futures": {"status": "READY"},
        "eligible_before_cutoff": False,
        "live_capital_allowed": False,
    }
    attempt["attempt_sha256"] = digest(attempt)
    ledger["attempts"] = [attempt]
    ledger["attempt_count"] = 1
    return _rehash(ledger)


def _empty_trial(prefix):
    decision = {
        "schema_version": 1,
        "ledger_id": f"{prefix}-DECISION",
        "decision_count": 0,
        "decisions": [],
        "ledger_sha256": "d" * 64,
        "live_capital_allowed": False,
    }
    outcome = {
        "schema_version": 1,
        "ledger_id": f"{prefix}-OUTCOME",
        "outcome_count": 0,
        "outcomes": [],
        "ledger_sha256": "o" * 64,
        "live_capital_allowed": False,
    }
    return decision, outcome


def test_health_surfaces_t006_source_timing_blocker_and_c002_prestart():
    t004_d, t004_o = _empty_trial("T004")
    t006_d, t006_o = _empty_trial("T006")
    summary = build_prospective_health_summary(
        as_of_date="2026-10-02",
        after_market_close=True,
        calendar=_calendar(),
        sc001_ledger=_sc001_ready(),
        sc002_ledger=_sc002_late_ready(),
        sc003_ledger=new_sc003_ledger(),
        t004_decision_ledger=t004_d,
        t004_outcome_ledger=t004_o,
        t006_decision_ledger=t006_d,
        t006_outcome_ledger=t006_o,
        c002_forecast_ledger=new_forecast_ledger(),
        c002_outcome_ledger=new_outcome_ledger(),
        h024_summary={
            "primary_classification": "INSUFFICIENT_COVERAGE",
            "current_primary_event_count": 0,
            "market_data_cutoff_session": "2026-09-16",
            "summary_sha256": "h" * 64,
        },
    )
    assert summary["latest_expected_market_session"] == "2026-10-01"
    assert summary["components"]["SC001"]["state"] == "HEALTHY"
    assert (
        summary["components"]["SC002"]["state"]
        == "BLOCKED_SAME_DAY_FUTURES_TIMING"
    )
    assert (
        summary["components"]["T006"]["state"]
        == "BLOCKED_BY_SC002_SAME_DAY_FUTURES_TIMING"
    )
    assert summary["components"]["RM001_C002"]["state"] == "BEFORE_FROZEN_START"
    assert "T006_SOURCE_TIMING" in summary["blockers"]
    assert len(summary["summary_sha256"]) == 64


def test_health_marks_sc001_stale_when_expected_session_is_missing():
    t004_d, t004_o = _empty_trial("T004")
    t006_d, t006_o = _empty_trial("T006")
    summary = build_prospective_health_summary(
        as_of_date="2026-10-05",
        after_market_close=True,
        calendar=_calendar(),
        sc001_ledger=_sc001_ready(),
        sc002_ledger=new_futures_source_ledger(),
        sc003_ledger=new_sc003_ledger(),
        t004_decision_ledger=t004_d,
        t004_outcome_ledger=t004_o,
        t006_decision_ledger=t006_d,
        t006_outcome_ledger=t006_o,
        c002_forecast_ledger=new_forecast_ledger(),
        c002_outcome_ledger=new_outcome_ledger(),
        h024_summary={"primary_classification": "INSUFFICIENT_COVERAGE"},
    )
    assert summary["latest_expected_market_session"] == "2026-10-05"
    assert summary["components"]["SC001"]["state"] == "STALE"
    assert "SC001_STALE" in summary["blockers"]
