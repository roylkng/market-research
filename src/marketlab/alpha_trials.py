from __future__ import annotations

import copy
from typing import Any

from marketlab.alpha import AlphaContractError, digest

AE001_TRIAL_LEDGER_ID = "AE001-TRIAL-LEDGER-v1"
EVENT_TYPES = {"TRIAL_REGISTERED", "TRIAL_RESULT_RECORDED"}


def new_trial_ledger() -> dict[str, Any]:
    ledger = {
        "schema_version": 1,
        "ledger_id": AE001_TRIAL_LEDGER_ID,
        "events": [],
        "event_count": 0,
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def _ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def validate_trial_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != AE001_TRIAL_LEDGER_ID:
        raise AlphaContractError("unexpected AE001 trial ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("AE001 trial ledger cannot allow live capital")
    events = ledger.get("events")
    if not isinstance(events, list):
        raise AlphaContractError("AE001 trial ledger events must be a list")
    if ledger.get("event_count") != len(events):
        raise AlphaContractError("AE001 trial ledger event count mismatch")
    seen_ids: set[str] = set()
    registered: set[str] = set()
    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            raise AlphaContractError("AE001 trial event must be an object")
        if event.get("seq") != index:
            raise AlphaContractError("AE001 trial event sequence mismatch")
        if event.get("event_type") not in EVENT_TYPES:
            raise AlphaContractError("unsupported AE001 trial event type")
        trial_id = str(event.get("trial_id") or "").strip()
        if not trial_id:
            raise AlphaContractError("AE001 trial event requires trial_id")
        stored = str(event.get("event_sha256") or "")
        unsigned = dict(event)
        unsigned.pop("event_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("AE001 trial event hash mismatch")
        if stored in seen_ids:
            raise AlphaContractError("duplicate AE001 trial event hash")
        seen_ids.add(stored)
        if event["event_type"] == "TRIAL_REGISTERED":
            if trial_id in registered:
                raise AlphaContractError(f"trial registered twice: {trial_id}")
            registered.add(trial_id)
        elif trial_id not in registered:
            raise AlphaContractError(
                f"trial result precedes registration: {trial_id}"
            )
    if str(ledger.get("ledger_sha256") or "") != _ledger_hash(ledger):
        raise AlphaContractError("AE001 trial ledger hash mismatch")


def append_trial_event(
    ledger: dict[str, Any],
    *,
    event_type: str,
    trial_id: str,
    recorded_at_utc: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    validate_trial_ledger(ledger)
    if event_type not in EVENT_TYPES:
        raise AlphaContractError("unsupported AE001 trial event type")
    if not trial_id.strip() or not recorded_at_utc.strip():
        raise AlphaContractError("trial_id and recorded_at_utc are required")
    if not isinstance(payload, dict):
        raise AlphaContractError("AE001 trial payload must be an object")
    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    event = {
        "seq": len(updated["events"]) + 1,
        "event_type": event_type,
        "trial_id": trial_id,
        "recorded_at_utc": recorded_at_utc,
        "payload": payload,
    }
    event["event_sha256"] = digest(event)
    updated["events"].append(event)
    updated["event_count"] = len(updated["events"])
    updated["ledger_sha256"] = _ledger_hash(updated)
    validate_trial_ledger(updated)
    return updated



def trial_state(ledger: dict[str, Any], trial_id: str) -> dict[str, Any]:
    """Return registration/result state for one immutable trial identity."""

    validate_trial_ledger(ledger)
    registration = None
    results = []
    for event in ledger["events"]:
        if event["trial_id"] != trial_id:
            continue
        if event["event_type"] == "TRIAL_REGISTERED":
            registration = event
        elif event["event_type"] == "TRIAL_RESULT_RECORDED":
            results.append(event)
    if registration is None:
        raise AlphaContractError(f"trial is not registered: {trial_id}")
    return {
        "registration": registration,
        "results": results,
        "result_count": len(results),
    }


def require_unopened_registered_trial(
    ledger: dict[str, Any],
    *,
    trial_id: str,
    required_status: str,
) -> dict[str, Any]:
    state = trial_state(ledger, trial_id)
    status = str(state["registration"]["payload"].get("status") or "")
    if status != required_status:
        raise AlphaContractError(
            f"{trial_id}: expected registration status {required_status}, got {status}"
        )
    if state["result_count"] != 0:
        raise AlphaContractError(
            f"{trial_id}: outcome result already exists in trial ledger"
        )
    return state["registration"]
