"""Event-independent, fail-closed AE001 SC001 NSE same-day source timing gate.

Only an actual repository runner executing within 16:30-18:30 IST may
perform automatic same-session capture. An event created inside the
window but run after the 18:30 cutoff is not retroactively eligible.

Workflow completion triggers are independent fallback *wake-ups*, not
permission to inherit source timestamps or data from another workflow.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
FROZEN_START = date(2026, 9, 30)
WINDOW_START = time(16, 30)
WINDOW_END_EXCLUSIVE = time(18, 30)
SUPPORTED_EVENTS = frozenset({"push", "workflow_dispatch", "schedule", "workflow_run"})
AUTO_EVENTS = frozenset({"push", "schedule", "workflow_run"})


def resolve_sc001_source_window(
    *,
    observed_at_utc: datetime,
    event_name: str,
    upstream_head_branch: str | None = None,
) -> dict[str, Any]:
    """Return an observational gate, never source availability or eligibility."""
    if not isinstance(observed_at_utc, datetime) or observed_at_utc.tzinfo is None:
        raise ValueError("SC001 requires actual timezone-aware runner observation time")
    if event_name not in SUPPORTED_EVENTS:
        raise ValueError("unrecognized SC001 workflow event")
    actual = observed_at_utc.astimezone(UTC)
    local = actual.astimezone(IST)
    local_clock = local.timetz().replace(tzinfo=None)
    date_ist = local.date()
    state = "READY"
    reason = "ACTUAL_RUNNER_WITHIN_SOURCE_CAPTURE_POLICY"
    if date_ist < FROZEN_START:
        state, reason = "BEFORE_START", "FROZEN_SC001_START_NOT_REACHED"
    elif event_name == "workflow_run" and upstream_head_branch != "main":
        state, reason = "UNTRUSTED_UPSTREAM", "ONLY_DEFAULT_BRANCH_WORKFLOW_CAN_WAKE_SC001"
    elif event_name in AUTO_EVENTS and not (
        WINDOW_START <= local_clock < WINDOW_END_EXCLUSIVE
    ):
        state, reason = (
            "OUTSIDE_PROSPECTIVE_WINDOW",
            "AUTO_SOURCE_WAKEUP_OUTSIDE_1630_TO_1829_IST",
        )
    return {
        "schema_version": 1,
        "policy_id": "AE001-SC001-P002-2026-10-13-RUNNER-WINDOW-BACKSTOP-v1",
        "date_ist": date_ist.isoformat(),
        "observed_runner_utc": actual.isoformat().replace("+00:00", "Z"),
        "observed_clock_ist": local_clock.strftime("%H%M"),
        "event_name": event_name,
        "upstream_head_branch": upstream_head_branch if event_name == "workflow_run" else None,
        "state": state,
        "reason": reason,
        "nse_source_retrieved": False,
        "data_available_before_1830_ist": False,
        "prospective_market_decision_authorized": False,
        "missed_past_market_cutoff_backfill_authorized": False,
        "live_capital_allowed": False,
    }
