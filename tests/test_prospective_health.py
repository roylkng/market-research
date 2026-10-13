from datetime import UTC, date, datetime

import pytest

from marketlab.alpha import digest
from marketlab.alpha_prospective_futures_sources import (
    new_futures_source_ledger,
)
from marketlab.alpha_prospective_sources import new_source_ledger
from marketlab.alpha_sc003_preopen import new_sc003_ledger
from marketlab.alpha_t004_readiness import build_t004_readiness
from marketlab.calendar_snapshot import build_calendar_snapshot
from marketlab.prospective_health import (
    _latest_expected_session,
    _sc001_state,
    build_prospective_health_summary,
    health_clock_markers,
)
from marketlab.rm001_c002 import new_forecast_ledger, new_outcome_ledger
from marketlab.rm001_industry_timing import new_industry_source_ledger
from marketlab.rm001_size_timing import new_size_source_ledger


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
        start_date=date(2026, 9, 30),
        end_date=date(2026, 10, 20),
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


def _t004_warmup():
    return build_t004_readiness(
        session_date="2026-10-01",
        state="DELIVERY_SOURCE_WARMUP_BLOCKED",
        sc001_attempt_sha256="a" * 64,
        support_market_panel_sha256="b" * 64,
        support_delivery_panel_sha256="c" * 64,
        delivery_warmup={
            "state": "WARMUP_BLOCKED",
            "required_prior_sessions": 20,
            "prior_session_count": 20,
            "blocking_session_count": 1,
            "blocking_sessions": [
                {
                    "session_date": "2026-09-11",
                    "status": "EXCLUDE_SESSION_INTERNAL_FIELD_INCONSISTENCY",
                    "raw_sha256": "d" * 64,
                }
            ],
            "consecutive_clean_prior_sessions": 12,
            "additional_clean_prior_sessions_needed": 8,
            "first_prior_session": "2026-09-02",
            "last_prior_session": "2026-09-30",
            "feature_eligibility_changed": False,
            "live_capital_allowed": False,
        },
    )


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
        rm001_sc001_size_ledger=new_size_source_ledger(),
        rm001_sc002_industry_ledger=new_industry_source_ledger(),
        t004_decision_ledger=t004_d,
        t004_outcome_ledger=t004_o,
        t004_readiness=_t004_warmup(),
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
        summary["components"]["RM001_SC001_SIZE"]["state"]
        == "WAITING_FOR_SIZE_TIMING_EVIDENCE"
    )
    assert (
        summary["components"]["RM001_SC002_INDUSTRY"]["state"]
        == "BEFORE_FROZEN_START"
    )
    assert (
        summary["components"]["T006"]["state"]
        == "BLOCKED_BY_SC002_SAME_DAY_FUTURES_TIMING"
    )
    assert (
        summary["components"]["T005_PREOPEN_SUCCESSOR"]["state"]
        == "WAITING_FOR_SC003_TIMING_EVIDENCE"
    )
    assert (
        summary["components"]["T005_PREOPEN_SUCCESSOR"][
            "additional_ready_sessions_needed"
        ]
        == 3
    )
    assert summary["components"]["T004"]["state"] == "DELIVERY_SOURCE_WARMUP_BLOCKED"
    assert summary["components"]["T004"]["delivery_warmup"][
        "additional_clean_prior_sessions_needed"
    ] == 8
    assert summary["components"]["T004"]["eligibility_projection"][
        "projected_first_possible_decision_session"
    ] == "2026-10-14"
    assert summary["components"]["T004"]["eligibility_projection"][
        "guaranteed"
    ] is False
    assert summary["components"]["T006"]["source_timing_feasibility"][
        "state"
    ] == "ACCUMULATING_EVIDENCE"
    assert summary["components"]["T006"]["source_timing_feasibility"][
        "expected_sessions"
    ] == [
        "2026-09-30",
        "2026-10-01",
        "2026-10-05",
        "2026-10-06",
        "2026-10-07",
    ]
    assert summary["components"]["RM001_C002"]["state"] == "BEFORE_FROZEN_START"
    assert "T004_DELIVERY_WARMUP" in summary["blockers"]
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
        rm001_sc001_size_ledger=new_size_source_ledger(),
        rm001_sc002_industry_ledger=new_industry_source_ledger(),
        t004_decision_ledger=t004_d,
        t004_outcome_ledger=t004_o,
        t004_readiness=_t004_warmup(),
        t006_decision_ledger=t006_d,
        t006_outcome_ledger=t006_o,
        c002_forecast_ledger=new_forecast_ledger(),
        c002_outcome_ledger=new_outcome_ledger(),
        h024_summary={"primary_classification": "INSUFFICIENT_COVERAGE"},
    )
    assert summary["latest_expected_market_session"] == "2026-10-05"
    assert summary["components"]["SC001"]["state"] == "STALE"
    assert (
        summary["components"]["RM001_SC002_INDUSTRY"]["state"]
        == "WAITING_FOR_INDUSTRY_TIMING_EVIDENCE"
    )
    assert "SC001_STALE" in summary["blockers"]



def _sc002_all_late_ready():
    ledger = new_futures_source_ledger()
    sessions = [
        "2026-09-30",
        "2026-10-01",
        "2026-10-05",
        "2026-10-06",
        "2026-10-07",
    ]
    attempts = []
    for index, session in enumerate(sessions, start=1):
        attempt = {
            "seq": index,
            "session_date": session,
            "captured_at_utc": f"{session}T15:30:00+00:00",
            "decision_cutoff_utc": f"{session}T13:00:00+00:00",
            "captured_before_or_at_cutoff": False,
            "futures": {"status": "READY"},
            "eligible_before_cutoff": False,
            "live_capital_allowed": False,
        }
        attempt["attempt_sha256"] = digest(attempt)
        attempts.append(attempt)
    ledger["attempts"] = attempts
    ledger["attempt_count"] = len(attempts)
    return _rehash(ledger)


def test_health_confirms_t006_timing_infeasible_only_after_five_late_ready_sessions():
    t004_d, t004_o = _empty_trial("T004")
    t006_d, t006_o = _empty_trial("T006")
    summary = build_prospective_health_summary(
        as_of_date="2026-10-07",
        after_market_close=True,
        calendar=_calendar(),
        sc001_ledger=_sc001_ready(),
        sc002_ledger=_sc002_all_late_ready(),
        sc003_ledger=new_sc003_ledger(),
        rm001_sc001_size_ledger=new_size_source_ledger(),
        rm001_sc002_industry_ledger=new_industry_source_ledger(),
        t004_decision_ledger=t004_d,
        t004_outcome_ledger=t004_o,
        t004_readiness=_t004_warmup(),
        t006_decision_ledger=t006_d,
        t006_outcome_ledger=t006_o,
        c002_forecast_ledger=new_forecast_ledger(),
        c002_outcome_ledger=new_outcome_ledger(),
        h024_summary={"primary_classification": "INSUFFICIENT_COVERAGE"},
    )
    feasibility = summary["components"]["T006"]["source_timing_feasibility"]
    assert feasibility["state"] == "TIMING_INFEASIBLE_FOR_FROZEN_T006"
    assert feasibility["ready_after_cutoff_session_count"] == 5
    assert feasibility["eligible_before_cutoff_session_count"] == 0
    assert (
        summary["components"]["T006"]["state"]
        == "BLOCKED_BY_CONFIRMED_SC002_TIMING_INFEASIBILITY"
    )


def test_2026_oct13_morning_health_does_not_prematurely_expect_today_sc001() -> None:
    # 09:50 IST is 04:20Z, long before today's NSE market close and
    # independently before the SC001 official market/delivery 18:30 cutoff.
    morning = health_clock_markers("2026-10-13T04:20:00Z")
    assert morning == {
        "as_of_date": "2026-10-13",
        "after_market_close": False,
        "sc001_source_cutoff_passed": False,
    }
    calendar = _calendar()
    expected = _latest_expected_session(
        calendar,
        as_of_date=date.fromisoformat(str(morning["as_of_date"])),
        after_market_close=bool(morning["sc001_source_cutoff_passed"]),
    )
    assert expected == "2026-10-12"

    source = _sc001_ready()
    source["attempts"][0]["session_date"] = "2026-10-12"
    source["attempts"][0]["captured_at_utc"] = "2026-10-12T12:00:00+00:00"
    source["attempts"][0]["decision_cutoff_utc"] = "2026-10-12T13:00:00+00:00"
    source["attempts"][0]["attempt_sha256"] = digest(
        {k: v for k, v in source["attempts"][0].items() if k != "attempt_sha256"}
    )
    _rehash(source)
    assert _sc001_state(source, expected_session=expected)["state"] == "HEALTHY"
    assert _sc001_state(source, expected_session="2026-10-13")["state"] == "STALE"


@pytest.mark.parametrize(
    ("instant", "expected_market_close", "expected_sc001_due"),
    [
        ("2026-10-13T09:59:59Z", False, False),  # 15:29:59 IST
        ("2026-10-13T10:00:00Z", True, False),   # 15:30 IST
        ("2026-10-13T12:59:59Z", True, False),   # 18:29:59 IST
        ("2026-10-13T13:00:00Z", True, True),    # 18:30 IST
        ("2026-10-13T15:00:00Z", True, True),    # 20:30 IST
    ],
)
def test_market_close_and_source_cutoff_are_distinct(
    instant: str, expected_market_close: bool, expected_sc001_due: bool
) -> None:
    markers = health_clock_markers(instant)
    assert markers["as_of_date"] == "2026-10-13"
    assert markers["after_market_close"] is expected_market_close
    assert markers["sc001_source_cutoff_passed"] is expected_sc001_due
    expected = _latest_expected_session(
        _calendar(),
        as_of_date=date(2026, 10, 13),
        after_market_close=bool(markers["sc001_source_cutoff_passed"]),
    )
    assert expected == ("2026-10-13" if expected_sc001_due else "2026-10-12")


@pytest.mark.parametrize("invalid", [
    "2026-10-13T04:20:00",
    "2026-10-13",
    "2026-10-13T09:50:00+05:30",
    "not-a-timestamp",
])
def test_health_snapshot_utc_requires_real_timezone_specific_instant(invalid: str) -> None:
    with pytest.raises(ValueError):
        health_clock_markers(invalid)


def test_health_summary_uses_after_source_due_flag_for_sc001_expectation() -> None:
    t004_d, t004_o = _empty_trial("T004")
    t006_d, t006_o = _empty_trial("T006")
    params = {
        "as_of_date": "2026-10-05",
        "after_market_close": True,
        "calendar": _calendar(),
        "sc001_ledger": _sc001_ready(),
        "sc002_ledger": new_futures_source_ledger(),
        "sc003_ledger": new_sc003_ledger(),
        "rm001_sc001_size_ledger": new_size_source_ledger(),
        "rm001_sc002_industry_ledger": new_industry_source_ledger(),
        "t004_decision_ledger": t004_d,
        "t004_outcome_ledger": t004_o,
        "t004_readiness": _t004_warmup(),
        "t006_decision_ledger": t006_d,
        "t006_outcome_ledger": t006_o,
        "c002_forecast_ledger": new_forecast_ledger(),
        "c002_outcome_ledger": new_outcome_ledger(),
        "h024_summary": {"primary_classification": "INSUFFICIENT_COVERAGE"},
    }
    old = build_prospective_health_summary(**params)
    assert old["components"]["SC001"]["state"] == "STALE"
    assert old["sc001_source_cutoff_passed"] is True

    before_due = build_prospective_health_summary(
        **params, sc001_source_cutoff_passed=False
    )
    assert before_due["after_market_close"] is True
    assert before_due["sc001_source_cutoff_passed"] is False
    assert before_due["latest_expected_market_session"] == "2026-10-01"
    assert before_due["components"]["SC001"]["state"] == "HEALTHY"
    assert "SC001_STALE" not in before_due["blockers"]
    assert "T006_SOURCE_TIMING" in before_due["blockers"]

    with pytest.raises(ValueError, match="source cutoff cannot pass"):
        build_prospective_health_summary(
            **{**params, "after_market_close": False},
            sc001_source_cutoff_passed=True,
        )
