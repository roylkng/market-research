from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_sc003_preopen import (
    SC003_P1_PROTOCOL,
    next_frozen_trading_session,
    preopen_cutoff_utc,
    validate_sc003_ledger,
)
from marketlab.calendar_snapshot import CalendarSnapshot

DESIGN_ID = "AE001-T005-PREOPEN-SUCCESSOR-READINESS-v1"
CANDIDATE_TRIAL_ID = "AE001-T012"
MIN_READY_TARGETS = 3


def _utc(value: object, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise AlphaContractError(
            f"pre-open successor invalid timestamp: {field}"
        ) from exc
    if parsed.tzinfo is None:
        raise AlphaContractError(
            f"pre-open successor timestamp must be timezone-aware: {field}"
        )
    return parsed.astimezone(UTC)


def _validate_ready_attempt(
    attempt: dict[str, Any],
    *,
    calendar: CalendarSnapshot,
) -> None:
    if attempt.get("ready_before_preopen_cutoff") is not True:
        raise AlphaContractError(
            "pre-open successor received a non-ready SC003 attempt"
        )
    if attempt.get("source_status") != "READY":
        raise AlphaContractError(
            "pre-open successor requires READY SC003 source"
        )

    target = str(attempt.get("target_session_date") or "")
    if not target:
        raise AlphaContractError(
            "pre-open successor SC003 target session is missing"
        )
    target_close, cutoff_session = next_frozen_trading_session(
        calendar,
        target_session_date=target,
    )
    expected_cutoff = preopen_cutoff_utc(cutoff_session)
    observed_cutoff = _utc(
        attempt.get("preopen_cutoff_utc"),
        field="preopen_cutoff_utc",
    )
    if observed_cutoff != expected_cutoff:
        raise AlphaContractError(
            f"{target}: SC003 pre-open cutoff does not match frozen calendar"
        )

    protocol = str(attempt.get("protocol") or "AE001-SC003-v1")
    if protocol == SC003_P1_PROTOCOL:
        if attempt.get("cutoff_session_date") != cutoff_session:
            raise AlphaContractError(
                f"{target}: SC003-P1 cutoff session differs from frozen calendar"
            )
        if attempt.get("frozen_calendar_sha256") != calendar.sha256:
            raise AlphaContractError(
                f"{target}: SC003-P1 calendar SHA differs from successor calendar"
            )
        if attempt.get("frozen_calendar_version") != calendar.version:
            raise AlphaContractError(
                f"{target}: SC003-P1 calendar version differs from successor calendar"
            )
        if _utc(
            attempt.get("target_close_timestamp_utc"),
            field="target_close_timestamp_utc",
        ) != _utc(target_close, field="calendar_target_close_timestamp_utc"):
            raise AlphaContractError(
                f"{target}: SC003-P1 target close differs from frozen calendar"
            )
    else:
        if str(attempt.get("observation_date") or "") != cutoff_session:
            raise AlphaContractError(
                f"{target}: legacy SC003 ready attempt is not next-trading-session aligned"
            )

    captured = _utc(
        attempt.get("captured_at_utc"),
        field="captured_at_utc",
    )
    close = _utc(target_close, field="calendar_target_close_timestamp_utc")
    if captured < close:
        raise AlphaContractError(
            f"{target}: SC003 ready capture predates target close"
        )
    if captured > expected_cutoff:
        raise AlphaContractError(
            f"{target}: SC003 ready capture misses pre-open cutoff"
        )


def validated_preopen_ready_attempts(
    ledger: dict[str, Any],
    *,
    calendar: CalendarSnapshot,
) -> list[dict[str, Any]]:
    validate_sc003_ledger(ledger)
    ready = [
        row
        for row in ledger["attempts"]
        if row.get("ready_before_preopen_cutoff") is True
    ]
    ready.sort(
        key=lambda row: (
            str(row["target_session_date"]),
            str(row["captured_at_utc"]),
            int(row["seq"]),
        )
    )
    for attempt in ready:
        _validate_ready_attempt(attempt, calendar=calendar)
    return ready


def preopen_successor_readiness(
    ledger: dict[str, Any],
    *,
    calendar: CalendarSnapshot,
) -> dict[str, Any]:
    ready = validated_preopen_ready_attempts(
        ledger,
        calendar=calendar,
    )
    ready_targets = [
        str(row["target_session_date"])
        for row in ready
    ]
    if len(ready_targets) != len(set(ready_targets)):
        raise AlphaContractError(
            "pre-open successor readiness contains duplicate ready targets"
        )

    count = len(ready_targets)
    permitted = count >= MIN_READY_TARGETS
    result: dict[str, Any] = {
        "schema_version": 1,
        "analysis_id": DESIGN_ID,
        "candidate_trial_id": CANDIDATE_TRIAL_ID,
        "state": (
            "READY_TO_FREEZE_SUCCESSOR_TRIAL"
            if permitted
            else "WAITING_FOR_SC003_TIMING_EVIDENCE"
        ),
        "source_ledger_sha256": ledger["ledger_sha256"],
        "calendar_version": calendar.version,
        "calendar_sha256": calendar.sha256,
        "ready_target_session_count": count,
        "ready_target_sessions": ready_targets,
        "minimum_ready_sessions_for_successor_freeze": MIN_READY_TARGETS,
        "additional_ready_sessions_needed": max(
            0,
            MIN_READY_TARGETS - count,
        ),
        "successor_trial_registration_permitted": permitted,
        "successor_trial_frozen": False,
        "source_timing_sessions_may_be_backfilled_as_predictions": False,
        "uses_return_or_alpha_outcomes": False,
        "live_capital_allowed": False,
    }
    result["summary_sha256"] = digest(result)
    return result


def require_preopen_successor_freeze_ready(
    ledger: dict[str, Any],
    *,
    calendar: CalendarSnapshot,
) -> dict[str, Any]:
    summary = preopen_successor_readiness(
        ledger,
        calendar=calendar,
    )
    if summary["successor_trial_registration_permitted"] is not True:
        raise AlphaContractError(
            "pre-open successor requires three distinct valid SC003 timing sessions"
        )
    return summary
