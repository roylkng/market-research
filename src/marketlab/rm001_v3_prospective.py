from __future__ import annotations

import copy
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_prospective_sources import validate_source_ledger
from marketlab.events import sha256_bytes
from marketlab.rm001_size_timing import validate_size_source_ledger

LEDGER_ID = "RM001-v3-PROSPECTIVE-RISK-LEDGER-v1"
START_DATE = date(2026, 10, 2)
IST = ZoneInfo("Asia/Kolkata")
SEAL_CUTOFF = time(9, 5)
MIN_READY_SIZE_SESSIONS = 3


def _ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def new_prospective_v3_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": LEDGER_ID,
        "state_count": 0,
        "states": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def validate_prospective_v3_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != LEDGER_ID:
        raise AlphaContractError("unexpected prospective RM001-v3 ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("prospective RM001-v3 cannot allow live capital")
    rows = ledger.get("states")
    if not isinstance(rows, list):
        raise AlphaContractError("prospective RM001-v3 states must be a list")
    if int(ledger.get("state_count") or 0) != len(rows):
        raise AlphaContractError("prospective RM001-v3 state count mismatch")
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if int(row.get("seq") or 0) != index:
            raise AlphaContractError("prospective RM001-v3 sequence mismatch")
        target = str(row.get("target_session_date") or "")
        observation = str(row.get("observation_date") or "")
        if not target or not observation or target >= observation:
            raise AlphaContractError(
                "prospective RM001-v3 target must precede observation date"
            )
        if target in seen:
            raise AlphaContractError(
                "prospective RM001-v3 target session duplicated"
            )
        seen.add(target)
        stored = str(row.get("entry_sha256") or "")
        unsigned = copy.deepcopy(row)
        unsigned.pop("entry_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError(
                "prospective RM001-v3 state entry hash mismatch"
            )
    if str(ledger.get("ledger_sha256") or "") != _ledger_hash(ledger):
        raise AlphaContractError("prospective RM001-v3 ledger hash mismatch")


def seal_cutoff_utc(observation_date: str) -> datetime:
    day = date.fromisoformat(observation_date)
    return datetime.combine(day, SEAL_CUTOFF, IST).astimezone(UTC)


def _ready_size_attempts(size_ledger: dict[str, Any]) -> list[dict[str, Any]]:
    validate_size_source_ledger(size_ledger)
    rows = [
        row
        for row in size_ledger.get("attempts", [])
        if row.get("source_status") == "READY"
        and row.get("ready_before_preopen_cutoff") is True
    ]
    rows.sort(
        key=lambda row: (
            str(row["target_session_date"]),
            str(row["captured_at_utc"]),
            int(row["seq"]),
        )
    )
    return rows


def latest_activation_target(
    *,
    size_ledger: dict[str, Any],
    readiness_summary: dict[str, Any],
) -> dict[str, Any] | None:
    ready = _ready_size_attempts(size_ledger)
    if readiness_summary.get("source_ledger_sha256") != size_ledger.get(
        "ledger_sha256"
    ):
        raise AlphaContractError(
            "prospective RM001-v3 readiness summary/source ledger binding mismatch"
        )
    summary_count = int(
        readiness_summary.get(
            "distinct_ready_before_cutoff_session_count",
            -1,
        )
    )
    if summary_count != len(
        {str(row["target_session_date"]) for row in ready}
    ):
        raise AlphaContractError(
            "prospective RM001-v3 size readiness summary disagrees with ledger"
        )
    ready_flag = readiness_summary.get(
        "prospective_size_source_timing_ready"
    )
    expected_ready = summary_count >= MIN_READY_SIZE_SESSIONS
    if ready_flag is not expected_ready:
        raise AlphaContractError(
            "prospective RM001-v3 readiness flag disagrees with frozen threshold"
        )
    if not expected_ready:
        return None
    return ready[-1]


def find_sc001_attempt(
    *,
    sc001_ledger: dict[str, Any],
    attempt_sha256: str,
) -> dict[str, Any]:
    validate_source_ledger(sc001_ledger)
    matches = [
        row
        for row in sc001_ledger.get("attempts", [])
        if row.get("attempt_sha256") == attempt_sha256
    ]
    if len(matches) != 1:
        raise AlphaContractError(
            "prospective RM001-v3 cannot resolve exact SC001 attempt"
        )
    row = matches[0]
    if row.get("eligible_before_cutoff") is not True:
        raise AlphaContractError(
            "prospective RM001-v3 requires eligible SC001 attempt"
        )
    return row


def target_already_sealed(
    ledger: dict[str, Any],
    target_session_date: str,
) -> bool:
    validate_prospective_v3_ledger(ledger)
    return any(
        row.get("target_session_date") == target_session_date
        for row in ledger["states"]
    )


def append_prospective_v3_state(
    ledger: dict[str, Any],
    *,
    target_session_date: str,
    observation_date: str,
    size_attempt: dict[str, Any],
    sc001_attempt: dict[str, Any],
    v2_exposure_panel_sha256: str,
    v2_factor_history_sha256: str,
    v2_risk_state_sha256: str,
    v3_risk_state: dict[str, Any],
    state_artifact_path: str,
    state_artifact_bytes: bytes,
    support_hashes: dict[str, str],
    sealed_at_utc: str,
) -> dict[str, Any]:
    validate_prospective_v3_ledger(ledger)
    target_day = date.fromisoformat(target_session_date)
    if target_day < START_DATE:
        raise AlphaContractError(
            "prospective RM001-v3 target precedes frozen start"
        )
    if target_already_sealed(ledger, target_session_date):
        raise AlphaContractError(
            f"prospective RM001-v3 target already sealed: {target_session_date}"
        )
    if str(size_attempt.get("target_session_date") or "") != target_session_date:
        raise AlphaContractError("prospective RM001-v3 size target mismatch")
    if str(size_attempt.get("observation_date") or "") != observation_date:
        raise AlphaContractError(
            "prospective RM001-v3 size observation date mismatch"
        )
    if size_attempt.get("source_status") != "READY" or size_attempt.get(
        "ready_before_preopen_cutoff"
    ) is not True:
        raise AlphaContractError(
            "prospective RM001-v3 requires READY pre-open size attempt"
        )
    if size_attempt.get("sc001_attempt_sha256") != sc001_attempt.get(
        "attempt_sha256"
    ):
        raise AlphaContractError(
            "prospective RM001-v3 SC001/size attempt binding mismatch"
        )
    if str(sc001_attempt.get("session_date") or "") != target_session_date:
        raise AlphaContractError(
            "prospective RM001-v3 SC001 target session mismatch"
        )

    try:
        sealed = datetime.fromisoformat(sealed_at_utc)
    except ValueError as exc:
        raise AlphaContractError(
            "prospective RM001-v3 seal timestamp is invalid"
        ) from exc
    if sealed.tzinfo is None:
        raise AlphaContractError(
            "prospective RM001-v3 seal timestamp must be timezone-aware"
        )
    sealed = sealed.astimezone(UTC)
    cutoff = seal_cutoff_utc(observation_date)
    if sealed > cutoff:
        raise AlphaContractError(
            "prospective RM001-v3 seal missed 09:05 IST cutoff"
        )

    if str(v3_risk_state.get("as_of_session") or "") != target_session_date:
        raise AlphaContractError(
            "prospective RM001-v3 state as-of session mismatch"
        )
    stored_state_sha = str(v3_risk_state.get("state_sha256") or "")
    unsigned_state = copy.deepcopy(v3_risk_state)
    unsigned_state.pop("state_sha256", None)
    if stored_state_sha != digest(unsigned_state):
        raise AlphaContractError(
            "prospective RM001-v3 state hash mismatch"
        )
    if v3_risk_state.get("parent_v2_risk_state_sha256") != (
        v2_risk_state_sha256
    ):
        raise AlphaContractError(
            "prospective RM001-v3 parent v2 state binding mismatch"
        )
    if v3_risk_state.get("parent_v2_factor_history_sha256") != (
        v2_factor_history_sha256
    ):
        raise AlphaContractError(
            "prospective RM001-v3 parent factor history binding mismatch"
        )

    entry: dict[str, Any] = {
        "seq": len(ledger["states"]) + 1,
        "target_session_date": target_session_date,
        "observation_date": observation_date,
        "sealed_at_utc": sealed.isoformat(),
        "seal_cutoff_utc": cutoff.isoformat(),
        "rm001_sc001_attempt_sha256": size_attempt["attempt_sha256"],
        "sc001_attempt_sha256": sc001_attempt["attempt_sha256"],
        "current_market_raw_sha256": sc001_attempt["market"]["raw_sha256"],
        "current_security_raw_sha256": size_attempt["raw_sha256"],
        "v2_exposure_panel_sha256": v2_exposure_panel_sha256,
        "v2_factor_history_sha256": v2_factor_history_sha256,
        "v2_risk_state_sha256": v2_risk_state_sha256,
        "v3_risk_state_sha256": stored_state_sha,
        "state_artifact_path": state_artifact_path,
        "state_artifact_sha256": sha256_bytes(state_artifact_bytes),
        "support_hashes": dict(sorted(support_hashes.items())),
        "live_capital_allowed": False,
    }
    entry["entry_sha256"] = digest(entry)
    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    updated["states"].append(entry)
    updated["state_count"] = len(updated["states"])
    updated["ledger_sha256"] = _ledger_hash(updated)
    validate_prospective_v3_ledger(updated)
    return updated
