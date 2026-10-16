"""Cheap T012 preflight for delayed GitHub schedule/workflow-run dispatch.

The trial's frozen source/decision gate remains alpha_t012_preopen.py.
This helper MAY SKIP an obviously impossible/late attempt, but MUST NEVER
declare a scientifically valid prediction. No historical repair is allowed.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

class PreflightContractError(ValueError):
    """Operational scheduling contract, deliberately no MarketLab dependencies."""


IST = timezone(timedelta(hours=5, minutes=30))
FIRST_FEATURE_SESSION = "2026-10-15"
EARLIEST_PREOPEN_MARGIN_SECONDS = 120


def _time(value: object, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise PreflightContractError(f"T012 preflight invalid {label}") from exc
    if parsed.tzinfo is None:
        raise PreflightContractError(f"T012 preflight {label} missing timezone")
    return parsed.astimezone(UTC)


def next_target_gate(
    *,
    now_utc: datetime,
    calendar: dict[str, Any],
    sc001_ledger: dict[str, Any],
    sc003_ledger: dict[str, Any],
    decision_ledger: dict[str, Any],
) -> dict[str, Any]:
    """Return a *non-authoritative* run/no-run decision, never a prediction."""
    if now_utc.tzinfo is None:
        raise PreflightContractError("T012 preflight now must have offset")
    now = now_utc.astimezone(UTC)
    sessions = calendar.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise PreflightContractError("T012 preflight original calendar missing")
    dates = [s.get("session_date") for s in sessions]
    if len(set(dates)) != len(dates) or dates != sorted(dates):
        raise PreflightContractError("T012 preflight calendar not strict and unique")
    if not isinstance(sc001_ledger.get("attempts"), list):
        raise PreflightContractError("T012 preflight cash source ledger malformed")
    if not isinstance(sc003_ledger.get("attempts"), list):
        raise PreflightContractError("T012 preflight F&O source ledger malformed")
    decisions = decision_ledger.get("decisions")
    if not isinstance(decisions, list):
        raise PreflightContractError("T012 preflight decision ledger malformed")

    # Probe most recent READY target only. We cannot retry historical targets
    # after the original *next-trading-morning* 08:30 IST deadline.
    observed = [
        r for r in sc003_ledger["attempts"]
        if r.get("ready_before_preopen_cutoff") is True
        and r.get("source_status") == "READY"
        and r.get("target_session_date", "") >= FIRST_FEATURE_SESSION
    ]
    if not observed:
        return {
            "should_score": False,
            "state": "NO_PROSPECTIVE_READY_FUTURES_SOURCE",
            "feature_session": None,
            "entry_session": None,
        }
    target = max(r["target_session_date"] for r in observed)
    if target not in dates or dates.index(target) + 1 >= len(dates):
        raise PreflightContractError("T012 preflight lacks next frozen trading session")
    entry_date = dates[dates.index(target) + 1]
    cutoff = datetime.fromisoformat(
        f"{entry_date}T08:30:00"
    ).replace(tzinfo=IST).astimezone(UTC)
    close = _time(
        sessions[dates.index(target)]["close_timestamp_utc"],
        "target NSE session close",
    )
    if any(d.get("session_date") == target for d in decisions):
        state = "ALREADY_SEALED"
    elif now < close:
        state = "TARGET_EXCHANGE_SESSION_NOT_CLOSED"
    elif now >= cutoff - timedelta(seconds=EARLIEST_PREOPEN_MARGIN_SECONDS):
        state = "MISSED_REMOTE_ANCHOR_MARGIN_NO_BACKFILL"
    else:
        cash_ok = {
            r.get("attempt_sha256")
            for r in sc001_ledger["attempts"]
            if r.get("session_date") == target
            and r.get("eligible_before_cutoff") is True
            and r.get("market", {}).get("status") == "READY"
            and r.get("delivery", {}).get("status") == "READY"
        }
        ready = [
            r for r in observed
            if r["target_session_date"] == target
            and r.get("sc001_attempt_sha256") in cash_ok
            and _time(r.get("captured_at_utc"), "futures source") <= now
        ]
        state = (
            "READY_FOR_AUTHORITATIVE_TRIAL_GATES"
            if ready else "SOURCE_NOT_YET_LINKED_AND_TIMELY"
        )
    return {
        "should_score": state == "READY_FOR_AUTHORITATIVE_TRIAL_GATES",
        "state": state,
        "feature_session": target,
        "entry_session": entry_date,
        "cutoff_utc": cutoff.isoformat(),
        "observed_at_utc": now.isoformat(),
        "operational_preflight_not_scientific_evidence": True,
        "live_capital_allowed": False,
    }


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise PreflightContractError("T012 preflight original source must be object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--calendar", type=Path,
        default=Path(
            "research/prospective/calendars/FY27-Q2-2026-09-06/"
            "NSE-CM-FY27Q2-v1.json"
        ),
    )
    parser.add_argument(
        "--sc001", type=Path,
        default=Path("research/prospective/ae001-sc001/source-ledger.json")
    )
    parser.add_argument(
        "--sc003", type=Path,
        default=Path("research/prospective/ae001-sc003/source-ledger.json")
    )
    parser.add_argument(
        "--decisions", type=Path,
        default=Path("research/prospective/ae001-t012/decision-ledger.json")
    )
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    result = next_target_gate(
        now_utc=datetime.now(UTC),
        calendar=_read(args.calendar),
        sc001_ledger=_read(args.sc001),
        sc003_ledger=_read(args.sc003),
        decision_ledger=_read(args.decisions),
    )
    if args.github_output is not None:
        # Output is a fixed token, not user-controlled shell content.
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(
                "should_score=" + (
                    "true" if result["should_score"] else "false"
                ) + "\n"
            )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
