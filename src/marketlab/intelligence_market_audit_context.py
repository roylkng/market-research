"""Prospective capture context for the daily mover/miss audit."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from marketlab.intelligence_prospective_news import (
    captures_for_audit,
    observations_for_audit,
    validate_news_ledger,
)
from marketlab.intelligence_store import ResearchStore, digest, timestamp

IST = ZoneInfo("Asia/Kolkata")


def inject_news_ledger(store: ResearchStore, ledger: dict, *, as_of: str) -> int:
    """Materialise compact ledger observations into an ephemeral audit store."""
    validate_news_ledger(ledger)
    count = 0
    for observation in observations_for_audit(ledger, as_of=as_of):
        record_id = "prospective:" + observation["observation_id"]
        body = {
            "item_id": observation["observation_id"],
            "origin_item_id": observation["item_id"],
            "source_id": observation["source_id"],
            "source_class": observation["source_class"],
            "first_seen_at": observation["first_seen_at"],
            "processed_at": observation["first_seen_at"],
            "publication": observation["publication"],
            "mentions": observation["mentions"],
            "topics": [{"topic": topic} for topic in observation["topics"]],
            "prospective_ledger_observation_id": observation["observation_id"],
        }
        store.append("news_item", record_id, body)
        count += 1
    return count


def _boundary(day: date, clock: time) -> datetime:
    return datetime.combine(day, clock, IST).astimezone(ZoneInfo("UTC"))


def apply_prospective_capture_context(report: dict, ledger: dict) -> dict:
    """Make missing scheduled capture distinct from missing source/company evidence."""
    validate_news_ledger(ledger)
    captured_at = report["captured_at"]
    session = date.fromisoformat(report["session_date"])
    prior = date.fromisoformat(report["prior_session_date"])
    prior_close = _boundary(prior, time(15, 30))
    session_open = _boundary(session, time(9, 15))
    session_close = _boundary(session, time(15, 30))
    captures = captures_for_audit(ledger, as_of=captured_at)
    window = [
        row
        for row in captures
        if prior_close < timestamp(row["captured_at"]) <= session_close
    ]
    preopen = [row for row in window if timestamp(row["captured_at"]) <= session_open]
    healthy_preopen = [
        row for row in preopen if row.get("discovery_status") == "DISCOVERY_CAPTURE_COMPLETE"
    ]
    intraday = [
        row
        for row in window
        if session_open < timestamp(row["captured_at"]) <= session_close
    ]
    for mover in report["movers"]:
        audit = mover["news_audit"]
        if audit["matched_item_ids"]:
            continue
        if not window:
            audit["coverage_class"] = "NO_SESSION_WINDOW_CAPTURE"
        elif not preopen:
            audit["coverage_class"] = "NO_PREOPEN_CAPTURE_NOT_DISCOVERED"
        elif not healthy_preopen:
            audit["coverage_class"] = "PREOPEN_CAPTURE_DEGRADED_NOT_DISCOVERED"
    report["coverage_class_counts"] = dict(
        sorted(Counter(row["news_audit"]["coverage_class"] for row in report["movers"]).items())
    )
    report["prospective_capture_context"] = {
        "prior_close_utc": prior_close.isoformat(),
        "session_open_utc": session_open.isoformat(),
        "session_close_utc": session_close.isoformat(),
        "session_window_capture_count": len(window),
        "preopen_capture_count": len(preopen),
        "healthy_preopen_capture_count": len(healthy_preopen),
        "degraded_preopen_capture_count": len(preopen) - len(healthy_preopen),
        "preopen_discovery_status_counts": dict(
            sorted(Counter(row["discovery_status"] for row in preopen).items())
        ),
        "intraday_capture_count": len(intraday),
        "capture_ids": [row["capture_id"] for row in window],
        "ledger_sha256": ledger["ledger_sha256"],
    }
    report["interpretation_contract"].update({
        "NO_SESSION_WINDOW_CAPTURE": (
            "No prospective discovery capture was sealed after the prior close and by this close. "
            "The mover cannot be scored as a source/entity discovery miss."
        ),
        "NO_PREOPEN_CAPTURE_NOT_DISCOVERED": (
            "At least one session-window capture exists but none before the open. "
            "The mover was not linked, but pre-open discovery coverage is not established."
        ),
        "PREOPEN_CAPTURE_DEGRADED_NOT_DISCOVERED": (
            "Pre-open capture exists, but every pre-open discovery pass had at least one "
            "discovery-stage source failure. The mover is not scored as a clean discovery miss."
        ),
    })
    report.pop("report_sha256", None)
    report["report_sha256"] = digest(report)
    return report
