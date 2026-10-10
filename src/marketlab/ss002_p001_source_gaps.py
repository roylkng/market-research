"""Append-only, non-promotable NSE source-failure evidence for SS002-P001.

A timeout, HTTP access restriction or other official-source failure is
NOT an empty announcement day and must NEVER create a canonical capture.
After three *scheduled run* failures, leave a visible source gap and
allow subsequent dates to progress. Manual date-scoped recovery remains
possible without changing the original requested NSE date.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError
from marketlab.ss002_daily_capture import FIRST_SOURCE_DATE, classify_capture_lag

MAX_AUTOMATED_ATTEMPTS_PER_DAY = 3
ATTEMPT_CONTRACT = "SS002-P013-OFFICIAL-SOURCE-UNAVAILABLE-v1"
ALLOWED_PHASES = frozenset({"EQUITY_MASTER_FETCH", "CORPORATE_ANNOUNCEMENTS_FETCH"})
ALLOWED_REASONS = frozenset({
    "OFFICIAL_NSE_TIMEOUT_OR_NETWORK_UNAVAILABLE",
    "OFFICIAL_NSE_HTTP_REJECTED",
    "OFFICIAL_NSE_SOURCE_UNAVAILABLE",
})


def _hash(record: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            record, ensure_ascii=False, allow_nan=False,
            sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _valid_attempt_name(name: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,110}", name):
        raise ValueError("SS002 source attempt identity contains unsupported characters")


def build_source_failure(
    *,
    source_day: date,
    recorded_at_utc: str,
    source_phase: str,
    exception: Exception,
    attempt_identity: str,
) -> dict[str, Any]:
    _valid_attempt_name(attempt_identity)
    if source_phase not in ALLOWED_PHASES:
        raise ValueError("unsupported NSE source failure phase")
    if source_day < FIRST_SOURCE_DATE:
        raise ValueError("source day precedes frozen SS002 start")
    classify_capture_lag(source_day, observed_at_utc=recorded_at_utc)
    raw = str(exception).casefold()
    if "timed out" in raw or "timeout" in raw:
        reason = "OFFICIAL_NSE_TIMEOUT_OR_NETWORK_UNAVAILABLE"
    elif "http 403" in raw or "http 401" in raw or "http 429" in raw:
        reason = "OFFICIAL_NSE_HTTP_REJECTED"
    else:
        reason = "OFFICIAL_NSE_SOURCE_UNAVAILABLE"
    payload: dict[str, Any] = {
        "schema_version": 1,
        "attempt_contract_id": ATTEMPT_CONTRACT,
        "attempt_identity": attempt_identity,
        "requested_source_day_ist": source_day.isoformat(),
        "observed_at_utc": datetime.fromisoformat(recorded_at_utc).isoformat(),
        "source_phase": source_phase,
        "source_state": "OFFICIAL_SOURCE_UNAVAILABLE_NO_CANONICAL_CAPTURE",
        "source_failure_reason": reason,
        "exception_type": type(exception).__name__,
        "exception_summary": str(exception)[:300],
        "official_source_date_requested_unchanged": True,
        "raw_announcement_bytes_retained": False,
        "announcement_count": None,
        "economic_relevance_verified": False,
        "source_day_zero_announcements_proven": False,
        "model_inference_executed": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    payload["attempt_sha256"] = _hash(payload)
    return payload


def validate_source_failure(attempt: dict[str, Any], *, expected_day: date) -> None:
    if attempt.get("attempt_contract_id") != ATTEMPT_CONTRACT:
        raise AlphaContractError("unrecognized SS002 official source failure receipt")
    if attempt.get("requested_source_day_ist") != expected_day.isoformat():
        raise AlphaContractError("SS002 failure receipt source date disagreement")
    _valid_attempt_name(attempt.get("attempt_identity") or "")
    if attempt.get("source_phase") not in ALLOWED_PHASES:
        raise AlphaContractError("invalid official source failure phase")
    if attempt.get("source_failure_reason") not in ALLOWED_REASONS:
        raise AlphaContractError("invalid official source failure reason")
    if attempt.get("source_state") != "OFFICIAL_SOURCE_UNAVAILABLE_NO_CANONICAL_CAPTURE":
        raise AlphaContractError("source failure receipt was promoted to a capture")
    if (
        attempt.get("announcement_count") is not None
        or attempt.get("source_day_zero_announcements_proven") is not False
        or attempt.get("raw_announcement_bytes_retained") is not False
        or attempt.get("official_source_date_requested_unchanged") is not True
    ):
        raise AlphaContractError("SS002 source failure inferred a fabricated announcement")
    for field in (
        "economic_relevance_verified", "model_inference_executed",
        "return_outcomes_opened", "portfolio_eligibility_allowed", "live_capital_allowed",
    ):
        if attempt.get(field) is not False:
            raise AlphaContractError(f"source failure cannot set {field}=true")
    digest = attempt.get("attempt_sha256")
    if not isinstance(digest, str) or _hash(
        {k: v for k, v in attempt.items() if k != "attempt_sha256"}
    ) != digest:
        raise AlphaContractError("SS002 source failure receipt hash mismatch")


def source_attempts_for_day(root: Path, day: date) -> list[dict[str, Any]]:
    source_dir = root / "attempts" / day.isoformat()
    results: list[dict[str, Any]] = []
    for path in sorted(source_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("SS002 attempt JSON must be an object")
        validate_source_failure(payload, expected_day=day)
        if path.name != f"{payload['attempt_identity']}.json":
            raise AlphaContractError("SS002 attempt file identity mismatch")
        results.append(payload)
    return results


def append_source_failure(root: Path, record: dict[str, Any]) -> Path:
    day = date.fromisoformat(record["requested_source_day_ist"])
    validate_source_failure(record, expected_day=day)
    file = root / "attempts" / day.isoformat() / f"{record['attempt_identity']}.json"
    file.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if file.exists():
        if file.read_text(encoding="utf-8") != data:
            raise AlphaContractError("immutable SS002 source failure receipt cannot be overwritten")
        return file
    with file.open("x", encoding="utf-8") as handle:
        handle.write(data)
    return file
