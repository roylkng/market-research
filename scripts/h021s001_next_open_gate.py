"""Operational H021S001 next-open gate, preserving the frozen EPS model.

A valid historic comparison is not a *new prospective decision* after its
next official trading open. Skip late automation retries without backdating
the signed intent or modifying the H021S001 model/registration.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from marketlab.h021_first_entry_intent import git_blob_sha
from marketlab.h021_signed_challenger import (
    FIRST_PROSPECTIVE_CAPTURE,
    _next_open,
)

CALENDAR = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/"
    "NSE-CM-FY27Q2-v1.json"
)
FROZEN_CALENDAR_GIT_BLOB = "9ac614820a67b0f7b20d8170d15b84df3c996b62"
ANCHOR_SAFETY_MARGIN = timedelta(minutes=2)


def _aware(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None:
        raise ValueError("H021S001 operational clock requires aware UTC timestamp")
    return timestamp.astimezone(UTC)


def assess_next_open(
    *,
    calendar: dict[str, Any],
    comparison_date: str,
    as_of_utc: datetime,
) -> dict[str, Any]:
    if as_of_utc.tzinfo is None:
        raise ValueError("H021S001 operational current timestamp must be aware")
    as_of = as_of_utc.astimezone(UTC)
    day = datetime.fromisoformat(comparison_date).date()
    if day < FIRST_PROSPECTIVE_CAPTURE:
        return {
            "state": "SKIP_BEFORE_SEPARATE_TRIAL_FROZEN_START",
            "comparison_date": comparison_date,
            "entry_session": None,
            "planned_open_utc": None,
            "can_seal": False,
        }
    try:
        closing, entry, opening = _next_open(calendar, comparison_date)
    except ValueError as exc:
        # This is a genuine blocked session if a missing/unresolved official
        # calendar could alter what the correct next entry is.
        return {
            "state": "SKIP_FROZEN_CALENDAR_UNRESOLVED",
            "comparison_date": comparison_date,
            "entry_session": None,
            "planned_open_utc": None,
            "can_seal": False,
            "reason": str(exc),
        }
    closing_at, opening_at = _aware(closing), _aware(opening)
    if as_of < closing_at:
        state = "SKIP_COMPARISON_SESSION_NOT_CLOSED"
    elif as_of >= opening_at - ANCHOR_SAFETY_MARGIN:
        state = "SKIP_MISSED_NEXT_OPEN_NO_BACKFILL"
    else:
        state = "CAPTURE"
    return {
        "state": state,
        "comparison_date": comparison_date,
        "entry_session": entry,
        "planned_open_utc": opening_at.isoformat(),
        "can_seal": state == "CAPTURE",
        "preopen_anchoring_margin_seconds": int(
            ANCHOR_SAFETY_MARGIN.total_seconds()
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--comparison-date", required=True)
    p.add_argument("--calendar", type=Path, default=CALENDAR)
    args = p.parse_args()
    raw = args.calendar.read_bytes()
    if git_blob_sha(raw) != FROZEN_CALENDAR_GIT_BLOB:
        raise ValueError("H021S001 operational gate original calendar Git blob drift")
    document = json.loads(raw)
    status = assess_next_open(
        calendar=document,
        comparison_date=args.comparison_date,
        as_of_utc=datetime.now(UTC),
    )
    print(json.dumps(status, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
