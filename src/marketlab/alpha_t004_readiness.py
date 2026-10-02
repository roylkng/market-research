from __future__ import annotations

import copy
from typing import Any

from marketlab.alpha import AlphaContractError, digest

T004_READINESS_ID = "AE001-T004-READINESS-v1"
ALLOWED_STATES = {
    "DELIVERY_SOURCE_WARMUP_BLOCKED",
    "SESSION_EXCLUDED",
    "SEALED",
    "ALREADY_SEALED",
}


def _hash(payload: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(payload)
    unsigned.pop("readiness_sha256", None)
    return digest(unsigned)


def validate_t004_readiness(readiness: dict[str, Any]) -> None:
    if readiness.get("readiness_id") != T004_READINESS_ID:
        raise AlphaContractError("unexpected T004 readiness id")
    if readiness.get("live_capital_allowed") is not False:
        raise AlphaContractError("T004 readiness cannot allow live capital")
    state = str(readiness.get("state") or "")
    if state not in ALLOWED_STATES:
        raise AlphaContractError(f"unsupported T004 readiness state: {state}")
    session = str(readiness.get("session_date") or "")
    if not session:
        raise AlphaContractError("T004 readiness session_date is required")
    attempt = str(readiness.get("sc001_attempt_sha256") or "")
    if len(attempt) != 64:
        raise AlphaContractError("T004 readiness SC001 attempt SHA is required")
    stored = str(readiness.get("readiness_sha256") or "")
    if len(stored) != 64 or stored != _hash(readiness):
        raise AlphaContractError("T004 readiness hash mismatch")
    if state == "DELIVERY_SOURCE_WARMUP_BLOCKED":
        warmup = readiness.get("delivery_warmup")
        if not isinstance(warmup, dict):
            raise AlphaContractError("T004 warmup readiness details are required")
        if warmup.get("state") != "WARMUP_BLOCKED":
            raise AlphaContractError("T004 warmup state disagrees with readiness")
        needed = int(warmup.get("additional_clean_prior_sessions_needed") or 0)
        if needed <= 0:
            raise AlphaContractError(
                "T004 warmup blocker requires positive additional sessions"
            )
    if state in {"SEALED", "ALREADY_SEALED"}:
        artifact_sha = str(readiness.get("decision_artifact_sha256") or "")
        if len(artifact_sha) != 64:
            raise AlphaContractError(
                "T004 sealed readiness requires decision artifact SHA"
            )


def build_t004_readiness(
    *,
    session_date: str,
    state: str,
    sc001_attempt_sha256: str,
    support_market_panel_sha256: str | None = None,
    support_delivery_panel_sha256: str | None = None,
    delivery_warmup: dict[str, Any] | None = None,
    reason: str | None = None,
    decision_artifact_sha256: str | None = None,
    common_row_count: int | None = None,
    source_workflow_run_id: int | None = None,
) -> dict[str, Any]:
    readiness: dict[str, Any] = {
        "schema_version": 1,
        "readiness_id": T004_READINESS_ID,
        "session_date": session_date,
        "state": state,
        "sc001_attempt_sha256": sc001_attempt_sha256,
        "support_market_panel_sha256": support_market_panel_sha256,
        "support_delivery_panel_sha256": support_delivery_panel_sha256,
        "delivery_warmup": delivery_warmup,
        "reason": reason,
        "decision_artifact_sha256": decision_artifact_sha256,
        "common_row_count": common_row_count,
        "source_workflow_run_id": source_workflow_run_id,
        "derived_operational_state_only": True,
        "live_capital_allowed": False,
    }
    readiness["readiness_sha256"] = _hash(readiness)
    validate_t004_readiness(readiness)
    return readiness
