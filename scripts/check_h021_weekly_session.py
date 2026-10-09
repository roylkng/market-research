from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from marketlab.h021_stockanalysis_acquisition import (
    CAPTURE,
    WeeklySessionDecision,
    weekly_session_decision,
)


def enforce_completed_session(
    decision: WeeklySessionDecision,
    calendar: dict,
    *,
    as_of_utc: datetime,
) -> WeeklySessionDecision:
    """A final trading date is capturable only after its actual frozen close."""
    if decision.state != CAPTURE:
        return decision
    if as_of_utc.tzinfo is None or as_of_utc.utcoffset() is None:
        raise ValueError("as_of_utc must be timezone-aware")
    now = as_of_utc.astimezone(UTC)
    if now.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat() != decision.capture_date_ist:
        raise ValueError("capture date differs from current India date")
    rows = [
        row for row in calendar["sessions"]
        if row["session_date"] == decision.capture_date_ist
    ]
    if len(rows) != 1:
        raise ValueError("frozen calendar must have exactly one matching session")
    close_raw = rows[0].get("close_timestamp_utc")
    if not isinstance(close_raw, str):
        raise TypeError("frozen close timestamp must be an ISO timestamp")
    try:
        close = datetime.fromisoformat(close_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid frozen close timestamp") from exc
    if close.tzinfo is None or close.utcoffset() is None:
        raise ValueError("frozen close timestamp must be timezone-aware")
    if now < close.astimezone(UTC):
        return WeeklySessionDecision(
            state="SESSION_NOT_CLOSED",
            capture_date_ist=decision.capture_date_ist,
            final_session_date=decision.final_session_date,
            reason="final frozen NSE cash-market session has not yet closed",
        )
    return decision


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-date", required=True)
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    calendar = json.loads(args.calendar.read_text(encoding="utf-8"))
    if not isinstance(calendar, dict):
        raise TypeError("calendar must contain a JSON object")

    decision = weekly_session_decision(args.capture_date, calendar)
    decision = enforce_completed_session(decision, calendar, as_of_utc=datetime.now(UTC))
    payload = asdict(decision)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
