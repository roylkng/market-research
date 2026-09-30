from __future__ import annotations

import copy
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_futures import parse_fo_udiff_stock_futures
from marketlab.events import sha256_bytes

SC002_LEDGER_ID = "AE001-SC002-FUTURES-SOURCE-LEDGER-v1"
SC002_START_DATE = date(2026, 9, 30)
IST = ZoneInfo("Asia/Kolkata")
DECISION_CUTOFF = time(18, 30)
RAW_ROOT_REPO = "research/prospective/ae001-sc002/raw"


def _ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def new_futures_source_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": SC002_LEDGER_ID,
        "attempt_count": 0,
        "attempts": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def validate_futures_source_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != SC002_LEDGER_ID:
        raise AlphaContractError("unexpected SC002 source ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("SC002 cannot allow live capital")
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list):
        raise AlphaContractError("SC002 attempts must be a list")
    if ledger.get("attempt_count") != len(attempts):
        raise AlphaContractError("SC002 attempt count mismatch")
    for index, attempt in enumerate(attempts, start=1):
        if attempt.get("seq") != index:
            raise AlphaContractError("SC002 attempt sequence mismatch")
        stored = str(attempt.get("attempt_sha256") or "")
        unsigned = dict(attempt)
        unsigned.pop("attempt_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("SC002 attempt hash mismatch")
    if str(ledger.get("ledger_sha256") or "") != _ledger_hash(ledger):
        raise AlphaContractError("SC002 ledger hash mismatch")


def decision_cutoff_utc(session_date: str) -> datetime:
    day = date.fromisoformat(session_date)
    return datetime.combine(day, DECISION_CUTOFF, IST).astimezone(UTC)


def session_already_eligible(
    ledger: dict[str, Any],
    session_date: str,
) -> bool:
    validate_futures_source_ledger(ledger)
    return any(
        attempt.get("session_date") == session_date
        and attempt.get("eligible_before_cutoff") is True
        for attempt in ledger["attempts"]
    )


def _futures_observation(
    raw: bytes | None,
    *,
    session_date: date,
    source_url: str,
) -> dict[str, Any]:
    if raw is None:
        return {
            "source_url": source_url,
            "status": "UNAVAILABLE",
            "raw_sha256": None,
            "raw_repo_path": None,
            "diagnostics": None,
        }
    raw_sha = sha256_bytes(raw)
    raw_repo_path = (
        f"{RAW_ROOT_REPO}/{session_date.isoformat()}/"
        f"futures-{raw_sha}.zip"
    )
    try:
        rows, diagnostics = parse_fo_udiff_stock_futures(
            raw,
            session_date=session_date,
        )
    except AlphaContractError as exc:
        return {
            "source_url": source_url,
            "status": "PARSER_REJECTED",
            "raw_sha256": raw_sha,
            "raw_repo_path": raw_repo_path,
            "diagnostics": {"error": str(exc)},
        }
    if not rows:
        return {
            "source_url": source_url,
            "status": "PARSER_REJECTED",
            "raw_sha256": raw_sha,
            "raw_repo_path": raw_repo_path,
            "diagnostics": {
                **diagnostics,
                "error": "SC002 parsed zero accepted STF contract rows",
            },
        }
    return {
        "source_url": source_url,
        "status": "READY",
        "raw_sha256": raw_sha,
        "raw_repo_path": raw_repo_path,
        "diagnostics": diagnostics,
    }


def append_futures_source_probe(
    ledger: dict[str, Any],
    *,
    session_date: str,
    captured_at_utc: str,
    source_url: str,
    raw: bytes | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    validate_futures_source_ledger(ledger)
    day = date.fromisoformat(session_date)
    if day < SC002_START_DATE:
        raise AlphaContractError("SC002 probe precedes frozen start boundary")
    if session_already_eligible(ledger, session_date):
        return copy.deepcopy(ledger), None

    try:
        captured = datetime.fromisoformat(captured_at_utc)
    except ValueError as exc:
        raise AlphaContractError("SC002 capture timestamp is invalid") from exc
    if captured.tzinfo is None:
        raise AlphaContractError("SC002 capture timestamp must be timezone-aware")
    captured = captured.astimezone(UTC)
    cutoff = decision_cutoff_utc(session_date)

    observation = _futures_observation(
        raw,
        session_date=day,
        source_url=source_url,
    )
    eligible = captured <= cutoff and observation["status"] == "READY"

    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    attempt: dict[str, Any] = {
        "seq": len(updated["attempts"]) + 1,
        "session_date": session_date,
        "captured_at_utc": captured.isoformat(),
        "decision_cutoff_utc": cutoff.isoformat(),
        "captured_before_or_at_cutoff": captured <= cutoff,
        "futures": observation,
        "eligible_before_cutoff": eligible,
        "live_capital_allowed": False,
    }
    attempt["attempt_sha256"] = digest(attempt)
    updated["attempts"].append(attempt)
    updated["attempt_count"] = len(updated["attempts"])
    updated["ledger_sha256"] = _ledger_hash(updated)
    validate_futures_source_ledger(updated)
    return updated, attempt
