"""Resolve oldest missing *completed* H021 daily source session, not future dates.

Three independent automatic attempts maximum per session. Persistent source
failure becomes an explicit missing observation, not a fake zero or a loop
that blocks every later trading day.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021_daily_prices import CALENDAR_SHA256, validate_daily_source_observation

FIRST_FUTURE_SESSION = "2026-10-13"
MAX_AUTOMATED_ATTEMPTS = 3


def resolve_session(calendar, observations_root: Path, *, as_of_utc: datetime) -> dict:
    if as_of_utc.tzinfo is None:
        raise ValueError("as-of time must be timezone-aware")
    current = as_of_utc.astimezone(UTC)
    if calendar.sha256 != CALENDAR_SHA256:
        raise ValueError("original H021 NSE source calendar changed")
    skipped = []
    complete = 0
    for session in calendar.sessions:
        day = session.session_date
        if day < FIRST_FUTURE_SESSION:
            continue
        if datetime.fromisoformat(session.close_timestamp_utc).astimezone(UTC) > current:
            break
        record = observations_root / f"{day}-v1.json"
        if record.exists():
            payload=json.loads(record.read_text(encoding="utf-8"))
            validate_daily_source_observation(payload)
            if payload["session_date_ist"] != day or payload["capture_state"] != "SOURCE_COMPLETE":
                raise ValueError("unexpected sealed H021 daily price record")
            complete += 1
            continue
        attempts=len(list((observations_root/"attempts").glob(f"{day}-*.json")))
        if attempts >= MAX_AUTOMATED_ATTEMPTS:
            skipped.append({"session_date":day,"state":"SOURCE_UNRESOLVED_AFTER_BOUNDED_RETRIES",
                            "attempts":attempts})
            continue
        return {
            "schema_version":1,
            "state":"CAPTURE",
            "session_date":day,
            "attempts_so_far":attempts,
            "maximum_automatic_attempts":MAX_AUTOMATED_ATTEMPTS,
            "previous_complete_sessions":complete,
            "unresolved_past_sessions":skipped,
            "outcomes_opened":False,
            "live_capital_allowed":False,
        }
    return {
        "schema_version":1,
        "state":"NO_COMPLETED_PENDING_SESSION",
        "session_date":None,
        "previous_complete_sessions":complete,
        "unresolved_past_sessions":skipped,
        "outcomes_opened":False,
        "live_capital_allowed":False,
    }


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calendar",type=Path,required=True)
    parser.add_argument("--observations-dir",type=Path,required=True)
    args=parser.parse_args()
    snapshot=load_calendar_snapshot(args.calendar)
    result=resolve_session(
        snapshot,args.observations_dir,as_of_utc=datetime.now(UTC),
    )
    print(json.dumps(result,sort_keys=True,allow_nan=False))


if __name__=="__main__":
    main()
