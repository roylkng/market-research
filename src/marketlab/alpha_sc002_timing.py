from __future__ import annotations

import copy
import statistics
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_prospective_futures_sources import (
    validate_futures_source_ledger,
)

IST = ZoneInfo("Asia/Kolkata")
MIN_DISTINCT_READY_SESSIONS = 3
SAFETY_BUFFER_MINUTES = 30
ROUNDING_MINUTES = 15


def _parse_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise AlphaContractError(f"{field} timestamp is required")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise AlphaContractError(f"{field} timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError(f"{field} timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _ceil_local_minutes(value: datetime, *, minutes: int) -> datetime:
    if minutes < 1 or 60 % minutes != 0:
        raise AlphaContractError(
            "SC002 timing rounding minutes must divide one hour"
        )
    local = value.astimezone(IST)
    total = local.hour * 60 + local.minute
    if local.second or local.microsecond:
        total += 1
    rounded = ((total + minutes - 1) // minutes) * minutes
    day_shift, minute_of_day = divmod(rounded, 24 * 60)
    hour, minute = divmod(minute_of_day, 60)
    target_date = local.date() + timedelta(days=day_shift)
    return datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        hour,
        minute,
        tzinfo=IST,
    )


def first_ready_observations(
    ledger: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return the earliest READY observation for each distinct session."""

    validate_futures_source_ledger(ledger)
    by_session: dict[str, list[dict[str, Any]]] = {}
    for attempt in ledger["attempts"]:
        futures = attempt.get("futures")
        if (
            isinstance(futures, dict)
            and futures.get("status") == "READY"
        ):
            session = str(attempt.get("session_date") or "")
            if not session:
                raise AlphaContractError(
                    "SC002 READY attempt is missing session_date"
                )
            by_session.setdefault(session, []).append(attempt)

    observations = []
    for session in sorted(by_session):
        candidates = sorted(
            by_session[session],
            key=lambda row: (
                _parse_timestamp(
                    row.get("captured_at_utc"),
                    field="SC002 captured_at_utc",
                ),
                int(row.get("seq") or 0),
            ),
        )
        first = candidates[0]
        captured_utc = _parse_timestamp(
            first["captured_at_utc"],
            field="SC002 captured_at_utc",
        )
        captured_ist = captured_utc.astimezone(IST)
        session_local_date = datetime.fromisoformat(
            f"{session}T00:00:00+05:30"
        ).astimezone(IST)
        local_seconds_after_session_midnight = (
            (captured_ist - session_local_date).total_seconds()
        )
        if local_seconds_after_session_midnight < 0:
            raise AlphaContractError(
                "SC002 READY capture precedes its local session date"
            )
        observations.append(
            {
                "session_date": session,
                "attempt_seq": int(first["seq"]),
                "attempt_sha256": first["attempt_sha256"],
                "captured_at_utc": captured_utc.isoformat(),
                "captured_at_ist": captured_ist.isoformat(),
                "local_seconds_after_session_midnight": (
                    local_seconds_after_session_midnight
                ),
                "eligible_before_1830": bool(
                    first.get("eligible_before_cutoff")
                ),
                "futures_raw_sha256": first["futures"][
                    "raw_sha256"
                ],
            }
        )
    return observations


def publication_timing_summary(
    ledger: dict[str, Any],
) -> dict[str, Any]:
    """Summarize SC002 first-READY publication observations.

    The candidate cutoff is source-only. It is intentionally unavailable until
    at least three distinct READY sessions exist.
    """

    validate_futures_source_ledger(ledger)
    observations = first_ready_observations(ledger)
    ready_count = len(observations)

    summary: dict[str, Any] = {
        "schema_version": 1,
        "analysis_id": "AE001-SC002-PUBLICATION-TIMING-v1",
        "source_ledger_sha256": ledger["ledger_sha256"],
        "minimum_distinct_ready_sessions": MIN_DISTINCT_READY_SESSIONS,
        "distinct_ready_session_count": ready_count,
        "observations": observations,
        "candidate_rule": (
            "LATEST_FIRST_READY_PLUS_30_MINUTES_ROUNDED_UP_TO_NEXT_15_MINUTES"
        ),
        "safety_buffer_minutes": SAFETY_BUFFER_MINUTES,
        "rounding_minutes": ROUNDING_MINUTES,
        "uses_stock_return_or_alpha_outcomes": False,
        "successor_trial_cutoff_frozen": False,
        "live_capital_allowed": False,
    }

    if ready_count < MIN_DISTINCT_READY_SESSIONS:
        summary.update(
            {
                "state": "INSUFFICIENT_EVIDENCE",
                "additional_distinct_ready_sessions_needed": (
                    MIN_DISTINCT_READY_SESSIONS - ready_count
                ),
                "latest_first_ready_at_ist": (
                    None
                    if not observations
                    else max(
                        observation["captured_at_ist"]
                        for observation in observations
                    )
                ),
                "candidate_cutoff_ist": None,
                "candidate_cutoff_session_offset_days": None,
                "candidate_cutoff_basis_session": None,
                "median_first_ready_local_seconds": (
                    None
                    if not observations
                    else float(
                        statistics.median(
                            observation[
                                "local_seconds_after_session_midnight"
                            ]
                            for observation in observations
                        )
                    )
                ),
            }
        )
    else:
        latest = max(
            observations,
            key=lambda observation: observation[
                "local_seconds_after_session_midnight"
            ],
        )
        latest_local = datetime.fromisoformat(
            latest["captured_at_ist"]
        )
        buffered = latest_local + timedelta(
            minutes=SAFETY_BUFFER_MINUTES
        )
        candidate = _ceil_local_minutes(
            buffered,
            minutes=ROUNDING_MINUTES,
        )
        summary.update(
            {
                "state": "SOURCE_TIMING_READY_FOR_SUCCESSOR_DESIGN",
                "additional_distinct_ready_sessions_needed": 0,
                "latest_first_ready_at_ist": latest[
                    "captured_at_ist"
                ],
                "candidate_cutoff_ist": candidate.strftime("%H:%M:%S"),
                "candidate_cutoff_session_offset_days": (
                    candidate.date()
                    - datetime.fromisoformat(
                        f"{latest['session_date']}T00:00:00+05:30"
                    ).date()
                ).days,
                "candidate_cutoff_basis_session": latest[
                    "session_date"
                ],
                "median_first_ready_local_seconds": float(
                    statistics.median(
                        observation[
                            "local_seconds_after_session_midnight"
                        ]
                        for observation in observations
                    )
                ),
            }
        )

    unsigned = copy.deepcopy(summary)
    summary["summary_sha256"] = digest(unsigned)
    return summary
