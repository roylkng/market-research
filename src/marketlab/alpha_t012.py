from __future__ import annotations

import copy
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_prospective_futures_sources import (
    validate_futures_source_ledger,
)
from marketlab.alpha_t004_prospective import _score_model
from marketlab.alpha_t006 import validate_frozen_t006_models
from marketlab.alpha_t006_prospective import (
    T006_MIN_COMMON_STOCKS,
    build_t006_current_feature_rows,
)
from marketlab.events import sha256_bytes

T012_TRIAL_ID = "AE001-T012"
T012_CUTOFF_ARTIFACT_ID = "AE001-T012-CUTOFF-FREEZE-v1"
T012_DECISION_LEDGER_ID = "AE001-T012-DECISION-LEDGER-v1"
T012_DECISION_ARTIFACT_ID = "AE001-T012-DECISION-v1"
T012_MIN_COMMON_STOCKS = T006_MIN_COMMON_STOCKS
IST = ZoneInfo("Asia/Kolkata")


def _hash_without(payload: dict[str, Any], field: str) -> str:
    unsigned = copy.deepcopy(payload)
    unsigned.pop(field, None)
    return digest(unsigned)


def new_t012_cutoff_freeze() -> dict[str, Any]:
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "artifact_id": T012_CUTOFF_ARTIFACT_ID,
        "trial_id": T012_TRIAL_ID,
        "state": "WAITING_FOR_SC002_TIMING_EVIDENCE",
        "frozen_at_utc": None,
        "source_timing_summary_sha256": None,
        "source_ledger_sha256": None,
        "timing_basis_sessions": [],
        "latest_timing_basis_session": None,
        "cutoff_ist": None,
        "cutoff_session_offset_days": None,
        "first_eligible_session_rule": (
            "STRICTLY_AFTER_LATEST_TIMING_BASIS_SESSION"
        ),
        "manual_override_allowed": False,
        "live_capital_allowed": False,
    }
    artifact["freeze_sha256"] = _hash_without(artifact, "freeze_sha256")
    return artifact


def validate_t012_cutoff_freeze(artifact: dict[str, Any]) -> None:
    if artifact.get("artifact_id") != T012_CUTOFF_ARTIFACT_ID:
        raise AlphaContractError("unexpected T012 cutoff artifact id")
    if artifact.get("trial_id") != T012_TRIAL_ID:
        raise AlphaContractError("unexpected T012 cutoff trial id")
    if artifact.get("live_capital_allowed") is not False:
        raise AlphaContractError("T012 cutoff artifact cannot allow live capital")
    if artifact.get("manual_override_allowed") is not False:
        raise AlphaContractError("T012 cutoff artifact permits manual override")
    state = artifact.get("state")
    if state not in {
        "WAITING_FOR_SC002_TIMING_EVIDENCE",
        "FROZEN",
    }:
        raise AlphaContractError("unexpected T012 cutoff state")
    stored = str(artifact.get("freeze_sha256") or "")
    if stored != _hash_without(artifact, "freeze_sha256"):
        raise AlphaContractError("T012 cutoff artifact hash mismatch")

    if state == "WAITING_FOR_SC002_TIMING_EVIDENCE":
        if any(
            artifact.get(field) is not None
            for field in (
                "frozen_at_utc",
                "source_timing_summary_sha256",
                "source_ledger_sha256",
                "latest_timing_basis_session",
                "cutoff_ist",
                "cutoff_session_offset_days",
            )
        ):
            raise AlphaContractError(
                "waiting T012 cutoff artifact contains frozen values"
            )
        if artifact.get("timing_basis_sessions") != []:
            raise AlphaContractError(
                "waiting T012 cutoff artifact contains timing sessions"
            )
        return

    sessions = artifact.get("timing_basis_sessions")
    if not isinstance(sessions, list) or len(sessions) < 3:
        raise AlphaContractError("frozen T012 cutoff lacks timing basis sessions")
    if sessions != sorted(set(str(value) for value in sessions)):
        raise AlphaContractError(
            "T012 timing basis sessions must be sorted and unique"
        )
    latest = str(artifact.get("latest_timing_basis_session") or "")
    if latest != sessions[-1]:
        raise AlphaContractError("T012 latest timing basis session mismatch")
    cutoff = str(artifact.get("cutoff_ist") or "")
    try:
        time.fromisoformat(cutoff)
    except ValueError as exc:
        raise AlphaContractError("T012 cutoff_ist is invalid") from exc
    offset = artifact.get("cutoff_session_offset_days")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise AlphaContractError(
            "T012 cutoff session offset must be a non-negative integer"
        )
    frozen_at = str(artifact.get("frozen_at_utc") or "")
    try:
        parsed = datetime.fromisoformat(frozen_at)
    except ValueError as exc:
        raise AlphaContractError("T012 frozen_at_utc is invalid") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError("T012 frozen_at_utc must be timezone-aware")


def freeze_t012_cutoff(
    current: dict[str, Any],
    *,
    timing_summary: dict[str, Any],
    frozen_at_utc: str | None = None,
) -> dict[str, Any]:
    validate_t012_cutoff_freeze(current)
    if current["state"] == "FROZEN":
        return copy.deepcopy(current)

    if timing_summary.get("state") != (
        "SOURCE_TIMING_READY_FOR_SUCCESSOR_DESIGN"
    ):
        raise AlphaContractError(
            "SC002 timing evidence is not ready for T012 cutoff freeze"
        )
    if int(timing_summary.get("distinct_ready_session_count") or 0) < 3:
        raise AlphaContractError(
            "T012 cutoff freeze requires at least three READY sessions"
        )
    if timing_summary.get("uses_stock_return_or_alpha_outcomes") is not False:
        raise AlphaContractError(
            "T012 cutoff source unexpectedly uses alpha/return outcomes"
        )
    candidate = str(timing_summary.get("candidate_cutoff_ist") or "")
    if not candidate:
        raise AlphaContractError("SC002 timing summary lacks candidate cutoff")
    offset_raw = timing_summary.get("candidate_cutoff_session_offset_days")
    if isinstance(offset_raw, bool) or not isinstance(offset_raw, int):
        raise AlphaContractError("SC002 timing summary cutoff offset is invalid")
    observations = timing_summary.get("observations")
    if not isinstance(observations, list) or len(observations) < 3:
        raise AlphaContractError("SC002 timing observations are incomplete")
    sessions = sorted(
        {
            str(row.get("session_date") or "")
            for row in observations
            if str(row.get("session_date") or "")
        }
    )
    if len(sessions) < 3:
        raise AlphaContractError(
            "SC002 timing summary has fewer than three distinct sessions"
        )

    frozen = (
        datetime.now(UTC)
        if frozen_at_utc is None
        else datetime.fromisoformat(frozen_at_utc)
    )
    if frozen.tzinfo is None:
        raise AlphaContractError("T012 freeze timestamp must be timezone-aware")

    result = copy.deepcopy(current)
    result.pop("freeze_sha256", None)
    result.update(
        {
            "state": "FROZEN",
            "frozen_at_utc": frozen.astimezone(UTC).isoformat(),
            "source_timing_summary_sha256": timing_summary["summary_sha256"],
            "source_ledger_sha256": timing_summary["source_ledger_sha256"],
            "timing_basis_sessions": sessions,
            "latest_timing_basis_session": sessions[-1],
            "cutoff_ist": candidate,
            "cutoff_session_offset_days": offset_raw,
        }
    )
    result["freeze_sha256"] = _hash_without(result, "freeze_sha256")
    validate_t012_cutoff_freeze(result)
    return result


def t012_cutoff_utc(
    session_date: str,
    cutoff_freeze: dict[str, Any],
) -> datetime:
    validate_t012_cutoff_freeze(cutoff_freeze)
    if cutoff_freeze["state"] != "FROZEN":
        raise AlphaContractError("T012 cutoff is not frozen")
    day = date.fromisoformat(session_date) + timedelta(
        days=int(cutoff_freeze["cutoff_session_offset_days"])
    )
    cutoff_time = time.fromisoformat(str(cutoff_freeze["cutoff_ist"]))
    local = datetime.combine(day, cutoff_time, tzinfo=IST)
    return local.astimezone(UTC)


def session_is_post_timing_basis(
    session_date: str,
    cutoff_freeze: dict[str, Any],
) -> bool:
    validate_t012_cutoff_freeze(cutoff_freeze)
    if cutoff_freeze["state"] != "FROZEN":
        return False
    return session_date > str(cutoff_freeze["latest_timing_basis_session"])


def eligible_sc002_t012_attempt(
    source_ledger: dict[str, Any],
    *,
    session_date: str,
    cutoff_freeze: dict[str, Any],
) -> dict[str, Any]:
    validate_futures_source_ledger(source_ledger)
    validate_t012_cutoff_freeze(cutoff_freeze)
    if not session_is_post_timing_basis(session_date, cutoff_freeze):
        raise AlphaContractError(
            f"{session_date}: T012 timing-basis session is ineligible"
        )
    cutoff = t012_cutoff_utc(session_date, cutoff_freeze)
    candidates = []
    for row in source_ledger.get("attempts", []):
        if row.get("session_date") != session_date:
            continue
        futures = row.get("futures")
        if not isinstance(futures, dict) or futures.get("status") != "READY":
            continue
        captured_raw = str(row.get("captured_at_utc") or "")
        try:
            captured = datetime.fromisoformat(captured_raw)
        except ValueError as exc:
            raise AlphaContractError(
                "T012 SC002 capture timestamp is invalid"
            ) from exc
        if captured.tzinfo is None:
            raise AlphaContractError(
                "T012 SC002 capture timestamp must be timezone-aware"
            )
        if captured.astimezone(UTC) <= cutoff:
            candidates.append(row)
    if not candidates:
        raise AlphaContractError(
            f"{session_date}: no SC002 READY source by frozen T012 cutoff"
        )
    candidates.sort(
        key=lambda row: (
            str(row.get("captured_at_utc") or ""),
            int(row.get("seq") or 0),
        )
    )
    return candidates[0]


def new_t012_decision_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": T012_DECISION_LEDGER_ID,
        "decision_count": 0,
        "decisions": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _hash_without(ledger, "ledger_sha256")
    return ledger


def validate_t012_decision_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != T012_DECISION_LEDGER_ID:
        raise AlphaContractError("unexpected T012 decision ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("T012 decision ledger cannot allow live capital")
    rows = ledger.get("decisions")
    if not isinstance(rows, list):
        raise AlphaContractError("T012 decisions must be a list")
    if ledger.get("decision_count") != len(rows):
        raise AlphaContractError("T012 decision count mismatch")
    previous: str | None = None
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if row.get("seq") != index:
            raise AlphaContractError("T012 decision sequence mismatch")
        session = str(row.get("session_date") or "")
        if not session or session in seen:
            raise AlphaContractError("T012 decision session is duplicated")
        if previous is not None and session <= previous:
            raise AlphaContractError(
                "T012 decision sessions must be strictly increasing"
            )
        seen.add(session)
        previous = session
        stored = str(row.get("decision_entry_sha256") or "")
        unsigned = dict(row)
        unsigned.pop("decision_entry_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("T012 decision entry hash mismatch")
    if str(ledger.get("ledger_sha256") or "") != _hash_without(
        ledger,
        "ledger_sha256",
    ):
        raise AlphaContractError("T012 decision ledger hash mismatch")


def build_t012_decision_artifact(
    *,
    session_date: str,
    cutoff_freeze: dict[str, Any],
    sc001_attempt: dict[str, Any],
    sc002_attempt: dict[str, Any],
    prior_market_sessions: list[dict[str, Any]],
    current_market_raw: bytes,
    prior_delivery_sessions: list[dict[str, Any]],
    current_delivery_raw: bytes,
    current_futures_raw: bytes,
    corporate_action_payload: object,
    corporate_action_raw: bytes,
    frozen_models: dict[str, Any],
    sealed_at_utc: str | None = None,
) -> dict[str, Any]:
    validate_t012_cutoff_freeze(cutoff_freeze)
    validate_frozen_t006_models(frozen_models)
    if cutoff_freeze["state"] != "FROZEN":
        raise AlphaContractError("T012 cutoff is not frozen")
    if not session_is_post_timing_basis(session_date, cutoff_freeze):
        raise AlphaContractError("T012 timing-basis session cannot be scored")
    if sc001_attempt.get("eligible_before_cutoff") is not True:
        raise AlphaContractError("T012 requires SC001 cash/delivery eligibility")
    if sc001_attempt.get("session_date") != session_date:
        raise AlphaContractError("T012 SC001 session mismatch")
    if sc002_attempt.get("session_date") != session_date:
        raise AlphaContractError("T012 SC002 session mismatch")

    sc002_captured = datetime.fromisoformat(
        str(sc002_attempt.get("captured_at_utc") or "")
    )
    if sc002_captured.tzinfo is None:
        raise AlphaContractError(
            "T012 SC002 capture timestamp must be timezone-aware"
        )
    cutoff = t012_cutoff_utc(session_date, cutoff_freeze)
    if sc002_captured.astimezone(UTC) > cutoff:
        raise AlphaContractError(
            "T012 SC002 source arrived after frozen decision cutoff"
        )

    rows, diagnostics = build_t006_current_feature_rows(
        prior_market_sessions=prior_market_sessions,
        current_market_raw=current_market_raw,
        prior_delivery_sessions=prior_delivery_sessions,
        current_delivery_raw=current_delivery_raw,
        current_futures_raw=current_futures_raw,
        session_date=session_date,
        corporate_action_payload=corporate_action_payload,
    )
    if len(rows) < T012_MIN_COMMON_STOCKS:
        raise AlphaContractError(
            f"T012 common row count below frozen minimum: {len(rows)}"
        )

    base = _score_model(frozen_models["base_model"], rows)
    augmented = _score_model(frozen_models["augmented_model"], rows)
    base_ids = [(row["symbol"], row["isin"]) for row in base]
    augmented_ids = [(row["symbol"], row["isin"]) for row in augmented]
    if base_ids != augmented_ids:
        raise AlphaContractError("T012 base/augmented prediction rows differ")

    sealed = (
        datetime.now(UTC)
        if sealed_at_utc is None
        else datetime.fromisoformat(sealed_at_utc)
    )
    if sealed.tzinfo is None:
        raise AlphaContractError("T012 seal timestamp must be timezone-aware")
    sealed = sealed.astimezone(UTC)
    if sealed > cutoff:
        raise AlphaContractError(
            "T012 prediction sealing missed frozen late-evening cutoff"
        )

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "artifact_id": T012_DECISION_ARTIFACT_ID,
        "trial_id": T012_TRIAL_ID,
        "session_date": session_date,
        "sealed_at_utc": sealed.isoformat(),
        "decision_cutoff_utc": cutoff.isoformat(),
        "cutoff_freeze_sha256": cutoff_freeze["freeze_sha256"],
        "source_timing_summary_sha256": cutoff_freeze[
            "source_timing_summary_sha256"
        ],
        "latest_timing_basis_session": cutoff_freeze[
            "latest_timing_basis_session"
        ],
        "sc001_attempt_sha256": sc001_attempt["attempt_sha256"],
        "sc002_attempt_sha256": sc002_attempt["attempt_sha256"],
        "sc001_captured_at_utc": sc001_attempt["captured_at_utc"],
        "sc002_captured_at_utc": sc002_attempt["captured_at_utc"],
        "current_market_sha256": sha256_bytes(current_market_raw),
        "current_delivery_sha256": sha256_bytes(current_delivery_raw),
        "current_futures_sha256": sha256_bytes(current_futures_raw),
        "corporate_action_raw_sha256": sha256_bytes(corporate_action_raw),
        "prior_market_support_sha256": digest(prior_market_sessions),
        "prior_delivery_support_sha256": digest(prior_delivery_sessions),
        "frozen_model_artifact_sha256": frozen_models["artifact_sha256"],
        "base_model_sha256": frozen_models["base_model"]["model_sha256"],
        "augmented_model_sha256": frozen_models["augmented_model"][
            "model_sha256"
        ],
        "common_row_count": len(rows),
        "feature_rows_sha256": diagnostics["feature_rows_sha256"],
        "feature_exclusions": diagnostics["exclusions"],
        "futures_parser_diagnostics": diagnostics["futures_parser"],
        "base_predictions": base,
        "augmented_predictions": augmented,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def append_t012_decision(
    ledger: dict[str, Any],
    *,
    decision_artifact: dict[str, Any],
    artifact_path: str,
) -> dict[str, Any]:
    validate_t012_decision_ledger(ledger)
    session = str(decision_artifact.get("session_date") or "")
    if any(row["session_date"] == session for row in ledger["decisions"]):
        raise AlphaContractError(f"T012 decision already exists for {session}")
    if decision_artifact.get("outcomes_attached") is not False:
        raise AlphaContractError("T012 decision cannot contain outcomes")

    entry = {
        "seq": len(ledger["decisions"]) + 1,
        "session_date": session,
        "artifact_path": artifact_path,
        "artifact_sha256": decision_artifact["artifact_sha256"],
        "sealed_at_utc": decision_artifact["sealed_at_utc"],
        "decision_cutoff_utc": decision_artifact["decision_cutoff_utc"],
        "common_row_count": decision_artifact["common_row_count"],
        "cutoff_freeze_sha256": decision_artifact["cutoff_freeze_sha256"],
        "sc001_attempt_sha256": decision_artifact["sc001_attempt_sha256"],
        "sc002_attempt_sha256": decision_artifact["sc002_attempt_sha256"],
        "base_model_sha256": decision_artifact["base_model_sha256"],
        "augmented_model_sha256": decision_artifact[
            "augmented_model_sha256"
        ],
        "live_capital_allowed": False,
    }
    entry["decision_entry_sha256"] = digest(entry)
    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    updated["decisions"].append(entry)
    updated["decision_count"] = len(updated["decisions"])
    updated["ledger_sha256"] = _hash_without(updated, "ledger_sha256")
    validate_t012_decision_ledger(updated)
    return updated
