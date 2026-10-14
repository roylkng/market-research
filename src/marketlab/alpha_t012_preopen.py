"""AE001-T012 prospective pre-open registration and timing gate.

This module authorizes a source-bound decision clock. It does not make scores,
look at outcomes, backfill evidence, or authorize live capital.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_preopen_successor import (
    require_preopen_successor_freeze_ready,
    validated_preopen_ready_attempts,
)
from marketlab.alpha_prospective_sources import (
    decision_cutoff_utc,
    validate_source_ledger,
)
from marketlab.alpha_sc003_preopen import (
    next_frozen_trading_session,
    preopen_cutoff_utc,
)
from marketlab.alpha_t006 import validate_frozen_t006_models
from marketlab.alpha_trials import trial_state
from marketlab.calendar_snapshot import CalendarSnapshot

TRIAL_ID = "AE001-T012"
FIRST_FEATURE_SESSION = "2026-10-15"
CALENDAR_SHA256 = "2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce"
MODEL_ARTIFACT_SHA256 = "da1ce462b5d9c59fb5bea2f4b69c574c8ecbf1f728c44b23af8f3e73bd5de091"
BASE_SHA256 = "774ce4b6ac0955b213521f017116ea32e579e73bfcbdb9ed3441c8e57248378c"
AUGMENTED_SHA256 = "7030afd449058e54a03d3febb6db0910b75acbe2be403e01ded8ee14eb68fa02"
EXPECTED_SOURCE_TARGETS = ("2026-10-01", "2026-10-05", "2026-10-12")
IST = ZoneInfo("Asia/Kolkata")


def _utc(value: object, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise AlphaContractError(f"T012 invalid timestamp: {label}") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError(f"T012 timestamp must be aware: {label}")
    return parsed.astimezone(UTC)


def require_t012_registration(
    *,
    trial_ledger: dict[str, Any],
    rta_manifest: dict[str, Any],
    sc003_ledger: dict[str, Any],
    calendar: CalendarSnapshot,
    frozen_models: dict[str, Any],
) -> dict[str, Any]:
    """Verify immutability and the three-session source-only registration gate."""
    if calendar.sha256 != CALENDAR_SHA256:
        raise AlphaContractError("T012 frozen calendar hash mismatch")
    readiness = require_preopen_successor_freeze_ready(sc003_ledger, calendar=calendar)
    targets = readiness["ready_target_sessions"]
    # A real new READY SC003 session (e.g., Oct 14) can arrive between the
    # Oct 13 trial registration and the first Oct 15 D feature session.
    # Filtering all dates before D would falsely invalidate the preregistered
    # model, despite these later observations having their own source clock.
    # The immutable *first five source attempts* and the exact three frozen
    # READY target hashes are separately checked below.
    original_targets = tuple(
        session for session in targets if session in EXPECTED_SOURCE_TARGETS
    )
    if original_targets != EXPECTED_SOURCE_TARGETS:
        raise AlphaContractError("T012 registration readiness targets drifted")
    # New source observations do not amend or backdate the three freeze probes.

    state = trial_state(trial_ledger, TRIAL_ID)
    if state["result_count"] or state["amendment_count"]:
        raise AlphaContractError("T012 registration already has amendments/results")
    registration = state["registration"]
    payload = registration["payload"]
    if payload.get("status") != "FROZEN_BEFORE_FIRST_ELIGIBLE_PREOPEN_DECISION":
        raise AlphaContractError("T012 registration not frozen")
    if payload.get("earliest_feature_session") != FIRST_FEATURE_SESSION:
        raise AlphaContractError("T012 earliest feature-session drift")
    if payload.get("calendar_sha256") != CALENDAR_SHA256:
        raise AlphaContractError("T012 trial calendar mismatch")
    if payload.get("model_artifact_sha256") != MODEL_ARTIFACT_SHA256:
        raise AlphaContractError("T012 model artifact lineage mismatch")
    # SC003 may accumulate new observations, but the *entire* original
    # five-attempt source ledger, including two failed probes, is immutable.
    # Proving only the original READY attempt hashes would leave room to
    # rewrite source-timing failures without invalidating the registration.
    frozen_attempt_count = 5
    if len(sc003_ledger["attempts"]) < frozen_attempt_count:
        raise AlphaContractError("T012 source evidence prefix truncated")
    frozen_prefix = {
        "schema_version": sc003_ledger["schema_version"],
        "ledger_id": sc003_ledger["ledger_id"],
        "attempt_count": frozen_attempt_count,
        "attempts": sc003_ledger["attempts"][:frozen_attempt_count],
        "live_capital_allowed": False,
    }
    if digest(frozen_prefix) != payload.get("sc003_source_ledger_sha256_at_freeze"):
        raise AlphaContractError("T012 sealed SC003 evidence prefix changed")
    frozen_target_hashes = payload.get("source_gate_attempt_hashes")
    observed_gate_hashes = [
        row["attempt_sha256"]
        for row in validated_preopen_ready_attempts(sc003_ledger, calendar=calendar)
        if row["target_session_date"] in EXPECTED_SOURCE_TARGETS
    ]
    if frozen_target_hashes != observed_gate_hashes:
        raise AlphaContractError("T012 source gate attempts changed after freeze")
    frozen_date = _utc(
        registration["recorded_at_utc"], label="registration recorded_at_utc"
    ).astimezone(IST).date()
    if frozen_date >= date.fromisoformat(FIRST_FEATURE_SESSION):
        raise AlphaContractError("T012 registration is not before first D session")
    validate_frozen_t006_models(frozen_models)
    if frozen_models["artifact_sha256"] != MODEL_ARTIFACT_SHA256:
        raise AlphaContractError("T012 model artifact SHA mismatch")
    if frozen_models["base_model"]["model_sha256"] != BASE_SHA256:
        raise AlphaContractError("T012 CORE27 SHA mismatch")
    if frozen_models["augmented_model"]["model_sha256"] != AUGMENTED_SHA256:
        raise AlphaContractError("T012 FULL37 SHA mismatch")
    if rta_manifest.get("live_capital_allowed") is not False:
        raise AlphaContractError("T012 RTA manifest must forbid live capital")
    accounting = [
        row for row in rta_manifest.get("trials", [])
        if row.get("trial_id") == TRIAL_ID
    ]
    if len(accounting) != 1:
        raise AlphaContractError("T012 missing unique global research accounting")
    trial = accounting[0]
    if (
        trial.get("fdr_family") != "ALPHA_FEATURE_DISCOVERY_V1"
        or trial.get("result_state") != "PENDING_PROSPECTIVE"
        or trial.get("scientifically_preregistered_before_outcomes") is not True
        or trial.get("source_anchor_sha256") != registration["event_sha256"]
        or trial.get("fdr_accounting_p_value") is not None
    ):
        raise AlphaContractError("T012 preregistered RTA record mismatch")
    return registration


def admit_t012_preopen(
    *,
    feature_session: str,
    sealed_at_utc: str,
    sc001_ledger: dict[str, Any],
    sc003_ledger: dict[str, Any],
    calendar: CalendarSnapshot,
    trial_ledger: dict[str, Any],
    rta_manifest: dict[str, Any],
    frozen_models: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed unless the exact D-source chain was sealed before N 08:30."""
    registration = require_t012_registration(
        trial_ledger=trial_ledger,
        rta_manifest=rta_manifest,
        sc003_ledger=sc003_ledger,
        calendar=calendar,
        frozen_models=frozen_models,
    )
    if feature_session < FIRST_FEATURE_SESSION:
        raise AlphaContractError("T012 feature session precedes prospective start")
    target_close, next_session = next_frozen_trading_session(
        calendar, target_session_date=feature_session
    )
    sealed = _utc(sealed_at_utc, label="sealed_at_utc")
    cutoff = preopen_cutoff_utc(next_session)
    if sealed > cutoff:
        raise AlphaContractError("T012 pre-open decision missed N cutoff")
    if sealed < _utc(target_close, label="target_close"):
        raise AlphaContractError("T012 decision precedes D close")
    validate_source_ledger(sc001_ledger)
    cash_attempts = {
        row["attempt_sha256"]: row
        for row in sc001_ledger["attempts"]
        if row.get("session_date") == feature_session
        and row.get("eligible_before_cutoff") is True
        and row.get("market", {}).get("status") == "READY"
        and row.get("delivery", {}).get("status") == "READY"
    }
    futures_attempts = [
        row for row in validated_preopen_ready_attempts(
            sc003_ledger, calendar=calendar
        )
        if row["target_session_date"] == feature_session
        and row["sc001_attempt_sha256"] in cash_attempts
        and _utc(row["captured_at_utc"], label="futures capture") <= sealed
    ]
    if len(futures_attempts) != 1:
        raise AlphaContractError("T012 requires one linked timely D futures source")
    futures = futures_attempts[0]
    cash = cash_attempts[futures["sc001_attempt_sha256"]]
    cash_captured = _utc(cash["captured_at_utc"], label="cash capture")
    if cash_captured < _utc(target_close, label="target_close"):
        raise AlphaContractError("T012 cash evidence predates D close")
    if cash_captured > sealed:
        raise AlphaContractError("T012 cash evidence observed after decision")
    if _utc(cash["captured_at_utc"], label="cash capture") > decision_cutoff_utc(
        feature_session
    ):
        raise AlphaContractError("T012 SC001 capture misses D cutoff")
    if any(
        not source.get("raw_sha256") or not source.get("raw_repo_path")
        for source in (cash["market"], cash["delivery"])
    ):
        raise AlphaContractError("T012 official cash/delivery bytes absent")
    if not futures.get("raw_sha256") or not futures.get("raw_repo_path"):
        raise AlphaContractError("T012 official futures bytes absent")
    if _utc(registration["recorded_at_utc"], label="registration") >= sealed:
        raise AlphaContractError("T012 registration is not before decision")
    admission = {
        "schema_version": 1,
        "trial_id": TRIAL_ID,
        "feature_session": feature_session,
        "entry_session": next_session,
        "decision_deadline_utc": cutoff.isoformat(),
        "sealed_at_utc": sealed.isoformat(),
        "sc001_attempt_sha256": cash["attempt_sha256"],
        "sc003_attempt_sha256": futures["attempt_sha256"],
        "cash_market_raw_sha256": cash["market"]["raw_sha256"],
        "delivery_raw_sha256": cash["delivery"]["raw_sha256"],
        "futures_raw_sha256": futures["raw_sha256"],
        "frozen_model_artifact_sha256": MODEL_ARTIFACT_SHA256,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    admission["admission_sha256"] = digest(admission)
    return admission
