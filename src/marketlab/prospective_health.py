from __future__ import annotations

import copy
from datetime import date
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_prospective_futures_sources import validate_futures_source_ledger
from marketlab.alpha_prospective_sources import validate_source_ledger
from marketlab.alpha_sc003_preopen import preopen_readiness_summary, validate_sc003_ledger
from marketlab.alpha_t004_readiness import validate_t004_readiness
from marketlab.calendar_snapshot import CalendarSnapshot
from marketlab.rm001_c002 import validate_forecast_ledger, validate_outcome_ledger

HEALTH_ID = "MARKETLAB-PROSPECTIVE-HEALTH-v1"
C002_START = date(2026, 10, 5)


def _canonical_hash(payload: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(payload)
    unsigned.pop("summary_sha256", None)
    return digest(unsigned)


def _count_records(payload: dict[str, Any]) -> int:
    for count_field, list_field in (
        ("decision_count", "decisions"),
        ("outcome_count", "outcomes"),
        ("entry_count", "entries"),
        ("record_count", "records"),
    ):
        if count_field in payload or list_field in payload:
            rows = payload.get(list_field, [])
            if not isinstance(rows, list):
                raise AlphaContractError(
                    f"prospective health expected list field: {list_field}"
                )
            declared = int(payload.get(count_field, len(rows)) or 0)
            if declared != len(rows):
                raise AlphaContractError(
                    f"prospective health count mismatch: {count_field}"
                )
            return len(rows)
    raise AlphaContractError("prospective health cannot infer record count")


def _latest_expected_session(
    calendar: CalendarSnapshot,
    *,
    as_of_date: date,
    after_market_close: bool,
) -> str | None:
    eligible = []
    for session in calendar.sessions:
        session_day = date.fromisoformat(session.session_date)
        if (
            session_day < as_of_date
            or session_day == as_of_date
            and after_market_close
        ):
            eligible.append(session.session_date)
    return max(eligible) if eligible else None


def _sc001_state(
    ledger: dict[str, Any],
    *,
    expected_session: str | None,
) -> dict[str, Any]:
    validate_source_ledger(ledger)
    eligible = [
        row
        for row in ledger["attempts"]
        if row.get("eligible_before_cutoff") is True
    ]
    eligible.sort(
        key=lambda row: (
            str(row["session_date"]),
            str(row["captured_at_utc"]),
            int(row["seq"]),
        )
    )
    distinct_sessions = sorted(
        {str(row["session_date"]) for row in eligible}
    )
    latest = distinct_sessions[-1] if distinct_sessions else None
    if expected_session is None:
        state = "NO_EXPECTED_SESSION"
    elif latest is None:
        state = "NO_ELIGIBLE_CAPTURE"
    elif latest == expected_session:
        state = "HEALTHY"
    elif latest < expected_session:
        state = "STALE"
    else:
        state = "AHEAD_OF_EXPECTED_CALENDAR"
    return {
        "state": state,
        "ledger_sha256": ledger["ledger_sha256"],
        "eligible_session_count": len(distinct_sessions),
        "latest_eligible_session": latest,
        "expected_latest_session": expected_session,
    }


def _sc002_state(ledger: dict[str, Any]) -> dict[str, Any]:
    validate_futures_source_ledger(ledger)
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list):
        raise AlphaContractError("SC002 attempts must be a list")
    declared = int(ledger.get("attempt_count", len(attempts)) or 0)
    if declared != len(attempts):
        raise AlphaContractError("SC002 attempt count mismatch")
    ready_sessions = sorted(
        {
            str(row["session_date"])
            for row in attempts
            if row.get("futures", {}).get("status") == "READY"
        }
    )
    eligible_sessions = sorted(
        {
            str(row["session_date"])
            for row in attempts
            if row.get("eligible_before_cutoff") is True
        }
    )
    late_ready = sorted(set(ready_sessions) - set(eligible_sessions))
    if eligible_sessions:
        state = "SAME_DAY_FUTURES_TIMING_READY"
    elif ready_sessions:
        state = "BLOCKED_SAME_DAY_FUTURES_TIMING"
    else:
        state = "WAITING_FOR_FUTURES_SOURCE"
    return {
        "state": state,
        "ledger_sha256": ledger.get("ledger_sha256"),
        "attempt_count": len(attempts),
        "ready_session_count": len(ready_sessions),
        "eligible_before_1830_session_count": len(eligible_sessions),
        "late_ready_session_count": len(late_ready),
        "latest_ready_session": ready_sessions[-1] if ready_sessions else None,
    }


def _sc003_state(ledger: dict[str, Any]) -> dict[str, Any]:
    validate_sc003_ledger(ledger)
    summary = preopen_readiness_summary(ledger)
    return {
        "state": (
            "READY_FOR_SUCCESSOR_DESIGN"
            if summary["successor_preopen_design_ready"]
            else "WAITING_FOR_TIMING_EVIDENCE"
        ),
        "ledger_sha256": ledger["ledger_sha256"],
        "distinct_target_session_count": summary[
            "distinct_target_session_count"
        ],
        "ready_before_preopen_cutoff_session_count": summary[
            "distinct_ready_before_cutoff_session_count"
        ],
        "minimum_ready_sessions": summary[
            "minimum_ready_sessions_for_successor_design"
        ],
        "additional_ready_sessions_needed": summary[
            "additional_ready_sessions_needed"
        ],
    }


def _trial_state(
    *,
    decision_ledger: dict[str, Any],
    outcome_ledger: dict[str, Any],
    blocked_reason: str | None = None,
    warning_if_empty: str | None = None,
) -> dict[str, Any]:
    decisions = _count_records(decision_ledger)
    outcomes = _count_records(outcome_ledger)
    if outcomes > decisions:
        raise AlphaContractError(
            "prospective trial has more outcomes than decisions"
        )
    if decisions:
        state = "ACTIVE"
    elif blocked_reason:
        state = blocked_reason
    elif warning_if_empty:
        state = warning_if_empty
    else:
        state = "WAITING_FOR_FIRST_DECISION"
    return {
        "state": state,
        "decision_count": decisions,
        "outcome_count": outcomes,
        "mature_outcome_fraction": (
            None if decisions == 0 else outcomes / decisions
        ),
        "decision_ledger_sha256": decision_ledger.get("ledger_sha256"),
        "outcome_ledger_sha256": outcome_ledger.get("ledger_sha256"),
    }


def _c002_state(
    *,
    forecast_ledger: dict[str, Any],
    outcome_ledger: dict[str, Any],
    as_of_date: date,
) -> dict[str, Any]:
    validate_forecast_ledger(forecast_ledger)
    validate_outcome_ledger(outcome_ledger)
    forecasts = len(forecast_ledger["entries"])
    sealed = sum(
        row.get("status") == "SEALED"
        for row in forecast_ledger["entries"]
    )
    outcomes = len(outcome_ledger["entries"])
    scored = sum(
        row.get("status") == "SCORED"
        for row in outcome_ledger["entries"]
    )
    if as_of_date < C002_START:
        state = "BEFORE_FROZEN_START"
    elif sealed == 0:
        state = "WAITING_FOR_FIRST_FORECAST"
    elif scored < 20:
        state = "PROSPECTIVE_ACCUMULATION"
    else:
        state = "PRIMARY_SAMPLE_MINIMUM_REACHED"
    return {
        "state": state,
        "start_date": C002_START.isoformat(),
        "forecast_entry_count": forecasts,
        "sealed_forecast_count": sealed,
        "outcome_entry_count": outcomes,
        "scored_outcome_count": scored,
        "minimum_evaluated_dates": 20,
        "forecast_ledger_sha256": forecast_ledger["ledger_sha256"],
        "outcome_ledger_sha256": outcome_ledger["ledger_sha256"],
    }


def build_prospective_health_summary(
    *,
    as_of_date: str,
    after_market_close: bool,
    calendar: CalendarSnapshot,
    sc001_ledger: dict[str, Any],
    sc002_ledger: dict[str, Any],
    sc003_ledger: dict[str, Any],
    t004_decision_ledger: dict[str, Any],
    t004_outcome_ledger: dict[str, Any],
    t004_readiness: dict[str, Any],
    t006_decision_ledger: dict[str, Any],
    t006_outcome_ledger: dict[str, Any],
    c002_forecast_ledger: dict[str, Any],
    c002_outcome_ledger: dict[str, Any],
    h024_summary: dict[str, Any],
) -> dict[str, Any]:
    day = date.fromisoformat(as_of_date)
    expected_session = _latest_expected_session(
        calendar,
        as_of_date=day,
        after_market_close=after_market_close,
    )
    sc001 = _sc001_state(
        sc001_ledger,
        expected_session=expected_session,
    )
    sc002 = _sc002_state(sc002_ledger)
    sc003 = _sc003_state(sc003_ledger)

    validate_t004_readiness(t004_readiness)
    t004_decisions = _count_records(t004_decision_ledger)
    if t004_decisions:
        t004 = _trial_state(
            decision_ledger=t004_decision_ledger,
            outcome_ledger=t004_outcome_ledger,
        )
    else:
        readiness_state = str(t004_readiness["state"])
        if readiness_state == "DELIVERY_SOURCE_WARMUP_BLOCKED":
            t004 = _trial_state(
                decision_ledger=t004_decision_ledger,
                outcome_ledger=t004_outcome_ledger,
                blocked_reason="DELIVERY_SOURCE_WARMUP_BLOCKED",
            )
        elif readiness_state == "SESSION_EXCLUDED":
            t004 = _trial_state(
                decision_ledger=t004_decision_ledger,
                outcome_ledger=t004_outcome_ledger,
                warning_if_empty="LATEST_ELIGIBLE_SESSION_EXCLUDED",
            )
        elif readiness_state in {"SEALED", "ALREADY_SEALED"}:
            raise AlphaContractError(
                "T004 readiness says sealed but decision ledger is empty"
            )
        else:
            t004 = _trial_state(
                decision_ledger=t004_decision_ledger,
                outcome_ledger=t004_outcome_ledger,
                warning_if_empty="WAITING_FOR_FIRST_DECISION",
            )
    t004["readiness_sha256"] = t004_readiness["readiness_sha256"]
    t004["latest_readiness_session"] = t004_readiness["session_date"]
    t004["readiness_state"] = t004_readiness["state"]
    if t004_readiness["state"] == "DELIVERY_SOURCE_WARMUP_BLOCKED":
        warmup = t004_readiness["delivery_warmup"]
        t004["delivery_warmup"] = {
            "blocking_sessions": warmup["blocking_sessions"],
            "consecutive_clean_prior_sessions": warmup[
                "consecutive_clean_prior_sessions"
            ],
            "additional_clean_prior_sessions_needed": warmup[
                "additional_clean_prior_sessions_needed"
            ],
            "required_prior_sessions": warmup["required_prior_sessions"],
        }

    t006_block = None
    if sc002["eligible_before_1830_session_count"] == 0:
        t006_block = "BLOCKED_BY_SC002_SAME_DAY_FUTURES_TIMING"
    t006 = _trial_state(
        decision_ledger=t006_decision_ledger,
        outcome_ledger=t006_outcome_ledger,
        blocked_reason=t006_block,
    )

    c002 = _c002_state(
        forecast_ledger=c002_forecast_ledger,
        outcome_ledger=c002_outcome_ledger,
        as_of_date=day,
    )

    h024_primary = str(
        h024_summary.get("primary_classification") or "UNKNOWN"
    )
    h024 = {
        "state": h024_primary,
        "current_primary_event_count": int(
            h024_summary.get("current_primary_event_count") or 0
        ),
        "market_data_cutoff_session": h024_summary.get(
            "market_data_cutoff_session"
        ),
        "summary_sha256": h024_summary.get("summary_sha256"),
    }

    blockers = []
    if sc001["state"] == "STALE":
        blockers.append("SC001_STALE")
    if sc002["state"] == "BLOCKED_SAME_DAY_FUTURES_TIMING":
        blockers.append("SC002_SAME_DAY_FUTURES_TIMING")
    if t004["state"] == "DELIVERY_SOURCE_WARMUP_BLOCKED":
        blockers.append("T004_DELIVERY_WARMUP")
    if t006["state"].startswith("BLOCKED_"):
        blockers.append("T006_SOURCE_TIMING")

    summary: dict[str, Any] = {
        "schema_version": 1,
        "health_id": HEALTH_ID,
        "as_of_date": day.isoformat(),
        "after_market_close": after_market_close,
        "calendar_version": calendar.version,
        "calendar_sha256": calendar.sha256,
        "latest_expected_market_session": expected_session,
        "components": {
            "SC001": sc001,
            "SC002": sc002,
            "SC003": sc003,
            "T004": t004,
            "T006": t006,
            "RM001_C002": c002,
            "H024": h024,
        },
        "blockers": blockers,
        "blocker_count": len(blockers),
        "live_capital_allowed": False,
    }
    summary["summary_sha256"] = _canonical_hash(summary)
    return summary
