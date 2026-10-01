from __future__ import annotations

import copy
from dataclasses import asdict
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_market import parse_udiff_eq_panel
from marketlab.events import sha256_bytes
from marketlab.rm001_size_source import (
    audit_security_master_session,
    parse_security_master_eq,
)

LEDGER_ID = "RM001-SC001-SIZE-PREOPEN-SOURCE-LEDGER-v1"
START_OBSERVATION_DATE = date(2026, 10, 2)
IST = ZoneInfo("Asia/Kolkata")
PREOPEN_CUTOFF = time(8, 30)
RAW_ROOT_REPO = "research/prospective/rm001-sc001/raw"


def _ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def new_size_source_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": LEDGER_ID,
        "attempt_count": 0,
        "attempts": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def validate_size_source_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != LEDGER_ID:
        raise AlphaContractError("unexpected RM001-SC001 ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("RM001-SC001 cannot allow live capital")
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list):
        raise AlphaContractError("RM001-SC001 attempts must be a list")
    if int(ledger.get("attempt_count") or 0) != len(attempts):
        raise AlphaContractError("RM001-SC001 attempt count mismatch")

    ready_targets: set[str] = set()
    for index, attempt in enumerate(attempts, start=1):
        if int(attempt.get("seq") or 0) != index:
            raise AlphaContractError("RM001-SC001 attempt sequence mismatch")
        target = str(attempt.get("target_session_date") or "")
        observation = str(attempt.get("observation_date") or "")
        if not target or not observation or target >= observation:
            raise AlphaContractError(
                "RM001-SC001 target must precede observation date"
            )
        stored = str(attempt.get("attempt_sha256") or "")
        unsigned = copy.deepcopy(attempt)
        unsigned.pop("attempt_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("RM001-SC001 attempt hash mismatch")
        if attempt.get("source_status") == "READY":
            if target in ready_targets:
                raise AlphaContractError(
                    "RM001-SC001 contains duplicate READY target"
                )
            ready_targets.add(target)

    if str(ledger.get("ledger_sha256") or "") != _ledger_hash(ledger):
        raise AlphaContractError("RM001-SC001 ledger hash mismatch")


def preopen_cutoff_utc(observation_date: str) -> datetime:
    day = date.fromisoformat(observation_date)
    return datetime.combine(day, PREOPEN_CUTOFF, IST).astimezone(UTC)


def target_ready_observed(
    ledger: dict[str, Any],
    target_session_date: str,
) -> bool:
    validate_size_source_ledger(ledger)
    return any(
        attempt.get("target_session_date") == target_session_date
        and attempt.get("source_status") == "READY"
        for attempt in ledger["attempts"]
    )


def _source_observation(
    *,
    target_session_date: date,
    market_raw: bytes,
    market_raw_sha256: str,
    security_raw: bytes | None,
    source_url: str,
) -> dict[str, Any]:
    try:
        market_rows = parse_udiff_eq_panel(
            market_raw,
            session_date=target_session_date,
        )
    except AlphaContractError as exc:
        return {
            "source_url": source_url,
            "source_status": "SC001_MARKET_REJECTED",
            "raw_sha256": None,
            "raw_repo_path": None,
            "market_raw_sha256": market_raw_sha256,
            "diagnostics": {"error": str(exc)},
        }

    if security_raw is None:
        return {
            "source_url": source_url,
            "source_status": "UNAVAILABLE",
            "raw_sha256": None,
            "raw_repo_path": None,
            "market_raw_sha256": market_raw_sha256,
            "diagnostics": None,
        }

    raw_sha = sha256_bytes(security_raw)
    raw_repo_path = (
        f"{RAW_ROOT_REPO}/{target_session_date.isoformat()}/"
        f"security-{raw_sha}.csv.gz"
    )
    try:
        security_rows, parser_diagnostics = parse_security_master_eq(
            security_raw,
            session_date=target_session_date,
        )
    except AlphaContractError as exc:
        return {
            "source_url": source_url,
            "source_status": "PARSER_REJECTED",
            "raw_sha256": raw_sha,
            "raw_repo_path": raw_repo_path,
            "market_raw_sha256": market_raw_sha256,
            "diagnostics": {"error": str(exc)},
        }

    audit = audit_security_master_session(
        market_session={
            "session_date": target_session_date.isoformat(),
            "equities": [asdict(row) for row in market_rows],
        },
        security_rows=security_rows,
        parser_diagnostics=parser_diagnostics,
        source_url=source_url,
        raw_sha256=raw_sha,
    )
    status = (
        "READY"
        if audit["total_size_session_pass"]
        else "SIZE_QUALITY_REJECTED"
    )
    return {
        "source_url": source_url,
        "source_status": status,
        "raw_sha256": raw_sha,
        "raw_repo_path": raw_repo_path,
        "market_raw_sha256": market_raw_sha256,
        "diagnostics": audit,
    }


def append_size_source_probe(
    ledger: dict[str, Any],
    *,
    sc001_attempt: dict[str, Any],
    observation_date: str,
    captured_at_utc: str,
    market_raw: bytes,
    security_raw: bytes | None,
    source_url: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    validate_size_source_ledger(ledger)
    observation_day = date.fromisoformat(observation_date)
    if observation_day < START_OBSERVATION_DATE:
        raise AlphaContractError(
            "RM001-SC001 observation precedes frozen start"
        )
    target_session = str(sc001_attempt.get("session_date") or "")
    if sc001_attempt.get("eligible_before_cutoff") is not True:
        raise AlphaContractError(
            "RM001-SC001 target requires eligible SC001 source"
        )
    if not target_session or target_session >= observation_date:
        raise AlphaContractError(
            "RM001-SC001 target must precede observation date"
        )
    if target_ready_observed(ledger, target_session):
        return copy.deepcopy(ledger), None

    market = sc001_attempt.get("market")
    if not isinstance(market, dict):
        raise AlphaContractError("RM001-SC001 SC001 market metadata missing")
    expected_market_sha = str(market.get("raw_sha256") or "")
    if sha256_bytes(market_raw) != expected_market_sha:
        raise AlphaContractError("RM001-SC001 SC001 market bytes hash mismatch")

    try:
        captured = datetime.fromisoformat(captured_at_utc)
    except ValueError as exc:
        raise AlphaContractError(
            "RM001-SC001 capture timestamp is invalid"
        ) from exc
    if captured.tzinfo is None:
        raise AlphaContractError(
            "RM001-SC001 capture timestamp must be timezone-aware"
        )
    captured = captured.astimezone(UTC)
    cutoff = preopen_cutoff_utc(observation_date)

    source = _source_observation(
        target_session_date=date.fromisoformat(target_session),
        market_raw=market_raw,
        market_raw_sha256=expected_market_sha,
        security_raw=security_raw,
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
    validate_size_source_ledger(updated)
    return updated, attempt


def size_timing_summary(ledger: dict[str, Any]) -> dict[str, Any]:
    validate_size_source_ledger(ledger)
    ready = {
        str(attempt["target_session_date"])
        for attempt in ledger["attempts"]
        if attempt.get("source_status") == "READY"
        and attempt.get("ready_before_preopen_cutoff") is True
    }
    targets = {
        str(attempt["target_session_date"])
        for attempt in ledger["attempts"]
    }
    result: dict[str, Any] = {
        "schema_version": 1,
        "analysis_id": "RM001-SC001-PREOPEN-SIZE-READINESS-v1",
        "source_ledger_sha256": ledger["ledger_sha256"],
        "distinct_target_session_count": len(targets),
        "distinct_ready_before_cutoff_session_count": len(ready),
        "minimum_ready_sessions_for_prospective_size": 3,
        "additional_ready_sessions_needed": max(0, 3 - len(ready)),
        "prospective_size_source_timing_ready": len(ready) >= 3,
        "prospective_size_use_enabled": False,
        "uses_return_or_alpha_outcomes": False,
        "live_capital_allowed": False,
    }
    result["summary_sha256"] = digest(result)
    return result
