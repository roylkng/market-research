"""Do not evaluate H021 20/60-session outcomes on an unresolved NSE calendar.

The frozen 2026 NSE calendar explicitly labels 2026-11-08 Muhurat trading
as an unresolved special session. This must not silently be counted as
either a normal non-session or a verified completed trading session.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from marketlab.calendar_snapshot import CalendarSnapshot

FIRST_INTENT_ID = "H021-P003-2026-10-09-FIRST-COHORT-v1"
HORIZON_READINESS_ID = "H021-P006-FIRST-COHORT-HORIZON-CALENDAR-v1"
FROZEN_CALENDAR_SHA256 = "2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce"
HORIZONS = (20, 60)


def first_cohort_horizon_readiness(
    intent: dict[str, Any], calendar: CalendarSnapshot
) -> dict[str, Any]:
    if intent.get("schema_version") != 1 or intent.get("intent_id") != FIRST_INTENT_ID:
        raise ValueError("unexpected H021 first prospective entry intent")
    if intent.get("portfolio_eligibility_allowed") is not False:
        raise ValueError("H021 portfolio eligibility must remain disabled")
    if intent.get("live_capital_allowed") is not False:
        raise ValueError("H021 live capital must remain disabled")
    outcome = intent.get("outcome_plan")
    if not isinstance(outcome, dict) or outcome.get("return_outcomes_opened") is not False:
        raise ValueError("H021 holding-period return outcomes must be unopened")
    if (
        outcome.get("primary_horizon_completed_sessions") != 60
        or outcome.get("secondary_horizon_completed_sessions") != 20
    ):
        raise ValueError("frozen H021 20/60 session horizons changed")
    planned = intent.get("entry_plan")
    if not isinstance(planned, dict):
        raise TypeError("H021 entry plan missing")
    entry_date = planned.get("session_date_ist")
    if entry_date != "2026-10-12":
        raise ValueError("frozen first H021 entry date changed")
    if calendar.version != "NSE-CM-FY27Q2-v1":
        raise ValueError("unreviewed calendar version cannot replace frozen calendar")
    if calendar.sha256 != FROZEN_CALENDAR_SHA256:
        raise ValueError("frozen NSE calendar original content SHA mismatch")
    if calendar.end_date != "2026-12-31":
        raise ValueError("original frozen calendar end date changed")
    if entry_date not in {item.session_date for item in calendar.sessions}:
        raise ValueError("first entry date absent from source-verified calendar")

    ordered = [item.session_date for item in calendar.sessions if item.session_date >= entry_date]
    unresolved = sorted(
        day for day in calendar.unresolved_special_dates
        if day >= entry_date and day <= calendar.end_date
    )
    horizon_states: dict[str, dict[str, Any]] = {}
    for horizon in HORIZONS:
        candidate = ordered[horizon - 1] if len(ordered) >= horizon else None
        if candidate is None:
            crossing_special = list(unresolved)
        else:
            crossing_special = [day for day in unresolved if day <= candidate]
        blockers = []
        if crossing_special:
            blockers.append("UNRESOLVED_OFFICIAL_SPECIAL_SESSION")
        if candidate is None:
            blockers.append("FUTURE_VERIFIED_SESSION_CALENDAR_MISSING")
        state = "BLOCKED" if blockers else "CALENDAR_READY_FOR_SEPARATE_SOURCE_EVALUATION"
        horizon_states[str(horizon)] = {
            "holding_sessions": horizon,
            "state": state,
            "weekday_only_candidate_date_not_verified": candidate if blockers else None,
            "verified_exit_session_date": candidate if not blockers else None,
            "blockers": blockers,
            "unresolved_special_dates_in_horizon": crossing_special,
            "provisional_session_count_available": len(ordered),
            "minimum_additional_sessions_before_unresolved_adjustment": max(
                0, horizon - len(ordered)
            ),
            "stock_and_benchmark_price_source_verified": False,
            "corporate_action_and_dividend_basis_verified": False,
            "return_outcomes_opened": False,
        }
    return {
        "schema_version": 1,
        "readiness_id": HORIZON_READINESS_ID,
        "classification": "OUTCOME_BLIND_SOURCE_CALENDAR_READINESS_ONLY",
        "entry_date_ist": entry_date,
        "calendar_version": calendar.version,
        "calendar_sha256": calendar.sha256,
        "source_url": calendar.source_url,
        "source_sha256": calendar.source_sha256,
        "calendar_end_date": calendar.end_date,
        "unresolved_special_dates": unresolved,
        "horizons": horizon_states,
        "all_horizon_calendars_ready": all(
            row["state"] == "CALENDAR_READY_FOR_SEPARATE_SOURCE_EVALUATION"
            for row in horizon_states.values()
        ),
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def require_horizon_calendar_ready(readiness: dict[str, Any], horizon: int) -> str:
    """Evaluator gate: no guessed exit date for a 20/60-session outcome."""
    if readiness.get("readiness_id") != HORIZON_READINESS_ID:
        raise ValueError("unrecognized H021 horizon-readiness protocol")
    if readiness.get("return_outcomes_opened") is not False:
        raise ValueError("H021 future outcomes already opened")
    state = readiness.get("horizons", {}).get(str(horizon))
    if not isinstance(state, dict):
        raise ValueError("horizon not declared by frozen H021 experiment")
    if state.get("state") != "CALENDAR_READY_FOR_SEPARATE_SOURCE_EVALUATION":
        raise ValueError(
            f"H021 {horizon}-session calendar not ready: {state.get('blockers')}"
        )
    date_value = state.get("verified_exit_session_date")
    if not isinstance(date_value, str) or date.fromisoformat(date_value).isoformat() != date_value:
        raise ValueError("calendar-ready horizon has no valid exit date")
    return date_value
