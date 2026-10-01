from __future__ import annotations

import copy
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_futures import parse_fo_udiff_stock_futures
from marketlab.alpha_prospective_sources import validate_source_ledger
from marketlab.events import sha256_bytes

SC003_LEDGER_ID = "AE001-SC003-PREOPEN-FUTURES-SOURCE-LEDGER-v1"
SC003_START_OBSERVATION_DATE = date(2026, 10, 2)
IST = ZoneInfo("Asia/Kolkata")
PREOPEN_CUTOFF = time(8, 30)
RAW_ROOT_REPO = "research/prospective/ae001-sc003/raw"


def _ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def new_sc003_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": SC003_LEDGER_ID,
        "attempt_count": 0,
        "attempts": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def validate_sc003_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != SC003_LEDGER_ID:
        raise AlphaContractError("unexpected SC003 ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("SC003 cannot allow live capital")
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list):
        raise AlphaContractError("SC003 attempts must be a list")
    if ledger.get("attempt_count") != len(attempts):
        raise AlphaContractError("SC003 attempt count mismatch")
    seen_ready_targets: set[str] = set()
    for index, attempt in enumerate(attempts, start=1):
        if attempt.get("seq") != index:
            raise AlphaContractError("SC003 attempt sequence mismatch")
        target = str(attempt.get("target_session_date") or "")
        observation = str(attempt.get("observation_date") or "")
        if not target or not observation:
            raise AlphaContractError("SC003 target/observation date is required")
        if target >= observation:
            raise AlphaContractError(
                "SC003 target session must precede observation date"
            )
        stored = str(attempt.get("attempt_sha256") or "")
        unsigned = dict(attempt)
        unsigned.pop("attempt_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("SC003 attempt hash mismatch")
        if attempt.get("source_status") == "READY":
            if target in seen_ready_targets:
                raise AlphaContractError(
                    "SC003 contains multiple READY observations for one target"
                )
            seen_ready_targets.add(target)
    if str(ledger.get("ledger_sha256") or "") != _ledger_hash(ledger):
        raise AlphaContractError("SC003 ledger hash mismatch")


def preopen_cutoff_utc(observation_date: str) -> datetime:
    day = date.fromisoformat(observation_date)
    return datetime.combine(day, PREOPEN_CUTOFF, IST).astimezone(UTC)


def latest_completed_sc001_target(
    sc001_ledger: dict[str, Any],
    *,
    observation_date: str,
) -> dict[str, Any]:
    validate_source_ledger(sc001_ledger)
    candidates = [
        attempt
        for attempt in sc001_ledger["attempts"]
        if attempt.get("eligible_before_cutoff") is True
        and str(attempt.get("session_date") or "") < observation_date
    ]
    if not candidates:
        raise AlphaContractError(
            f"{observation_date}: no prior SC001 eligible completed session"
        )
    candidates.sort(
        key=lambda row: (
            str(row["session_date"]),
            str(row["captured_at_utc"]),
            int(row["seq"]),
        )
    )
    target = candidates[-1]
    target_session = str(target["session_date"])
    same_session = [
        row for row in candidates
        if str(row["session_date"]) == target_session
    ]
    same_session.sort(
        key=lambda row: (
            str(row["captured_at_utc"]),
            int(row["seq"]),
        )
    )
    return same_session[0]


def target_ready_observed(
    ledger: dict[str, Any],
    target_session_date: str,
) -> bool:
    validate_sc003_ledger(ledger)
    return any(
        attempt.get("target_session_date") == target_session_date
        and attempt.get("source_status") == "READY"
        for attempt in ledger["attempts"]
    )


def _source_observation(
    raw: bytes | None,
    *,
    target_session_date: date,
    source_url: str,
) -> dict[str, Any]:
    if raw is None:
        return {
            "source_url": source_url,
            "source_status": "UNAVAILABLE",
            "raw_sha256": None,
            "raw_repo_path": None,
            "diagnostics": None,
        }
    raw_sha = sha256_bytes(raw)
    raw_repo_path = (
        f"{RAW_ROOT_REPO}/{target_session_date.isoformat()}/"
        f"futures-{raw_sha}.zip"
    )
    try:
        rows, diagnostics = parse_fo_udiff_stock_futures(
            raw,
            session_date=target_session_date,
        )
    except AlphaContractError as exc:
        return {
            "source_url": source_url,
            "source_status": "PARSER_REJECTED",
            "raw_sha256": raw_sha,
            "raw_repo_path": raw_repo_path,
            "diagnostics": {"error": str(exc)},
        }
    if not rows:
        return {
            "source_url": source_url,
            "source_status": "PARSER_REJECTED",
            "raw_sha256": raw_sha,
            "raw_repo_path": raw_repo_path,
            "diagnostics": {
                **diagnostics,
                "error": "SC003 parsed zero accepted STF contract rows",
            },
        }
    return {
        "source_url": source_url,
        "source_status": "READY",
        "raw_sha256": raw_sha,
        "raw_repo_path": raw_repo_path,
        "diagnostics": diagnostics,
    }


def append_sc003_probe(
    ledger: dict[str, Any],
    *,
    sc001_attempt: dict[str, Any],
    observation_date: str,
    captured_at_utc: str,
    source_url: str,
    raw: bytes | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    validate_sc003_ledger(ledger)
    observation_day = date.fromisoformat(observation_date)
    if observation_day < SC003_START_OBSERVATION_DATE:
        raise AlphaContractError("SC003 observation precedes frozen start")
    target_session = str(sc001_attempt.get("session_date") or "")
    if not target_session:
        raise AlphaContractError("SC003 SC001 target session is missing")
    if sc001_attempt.get("eligible_before_cutoff") is not True:
        raise AlphaContractError("SC003 target requires eligible SC001 source")
    if target_session >= observation_date:
        raise AlphaContractError(
            "SC003 target session must precede observation date"
        )
    if target_ready_observed(ledger, target_session):
        return copy.deepcopy(ledger), None

    try:
        captured = datetime.fromisoformat(captured_at_utc)
    except ValueError as exc:
        raise AlphaContractError("SC003 capture timestamp is invalid") from exc
    if captured.tzinfo is None:
        raise AlphaContractError("SC003 capture timestamp must be timezone-aware")
    captured = captured.astimezone(UTC)
    cutoff = preopen_cutoff_utc(observation_date)

    source = _source_observation(
        raw,
        target_session_date=date.fromisoformat(target_session),
        source_url=source_url,
    )
    ready_before_cutoff = (
        source["source_status"] == "READY"
        and captured <= cutoff
    )

    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    attempt: dict[str, Any] = {
        "seq": len(updated["attempts"]) + 1,
        "target_session_date": target_session,
        "observation_date": observation_date,
        "captured_at_utc": captured.isoformat(),
        "preopen_cutoff_utc": cutoff.isoformat(),
        "captured_before_or_at_preopen_cutoff": captured <= cutoff,
        "sc001_attempt_sha256": sc001_attempt["attempt_sha256"],
        **source,
        "ready_before_preopen_cutoff": ready_before_cutoff,
        "live_capital_allowed": False,
    }
    attempt["attempt_sha256"] = digest(attempt)
    updated["attempts"].append(attempt)
    updated["attempt_count"] = len(updated["attempts"])
    updated["ledger_sha256"] = _ledger_hash(updated)
    validate_sc003_ledger(updated)
    return updated, attempt


def preopen_readiness_summary(
    ledger: dict[str, Any],
) -> dict[str, Any]:
    validate_sc003_ledger(ledger)
    ready = [
        attempt
        for attempt in ledger["attempts"]
        if attempt.get("source_status") == "READY"
    ]
    distinct_ready = {
        str(attempt["target_session_date"])
        for attempt in ready
        if attempt.get("ready_before_preopen_cutoff") is True
    }
    all_targets = {
        str(attempt["target_session_date"])
        for attempt in ledger["attempts"]
    }
    result: dict[str, Any] = {
        "schema_version": 1,
        "analysis_id": "AE001-SC003-PREOPEN-READINESS-v1",
        "source_ledger_sha256": ledger["ledger_sha256"],
        "distinct_target_session_count": len(all_targets),
        "distinct_ready_before_cutoff_session_count": len(distinct_ready),
        "minimum_ready_sessions_for_successor_design": 3,
        "additional_ready_sessions_needed": max(0, 3 - len(distinct_ready)),
        "successor_preopen_design_ready": len(distinct_ready) >= 3,
        "successor_trial_frozen": False,
        "uses_return_or_alpha_outcomes": False,
        "live_capital_allowed": False,
    }
    result["summary_sha256"] = digest(result)
    return result
