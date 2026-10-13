"""AE001-T012 decision artifacts and append-only prospective prediction ledger.

No return/outcome data may enter a prediction artifact. Reuses frozen T006
feature construction and exactly the historical CORE27/FULL37 model weights.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_sc003_preopen import preopen_cutoff_utc
from marketlab.alpha_t004_prospective import _score_model
from marketlab.alpha_t006 import validate_frozen_t006_models
from marketlab.alpha_t006_prospective import build_t006_current_feature_rows
from marketlab.alpha_t012_preopen import (
    AUGMENTED_SHA256,
    BASE_SHA256,
    FIRST_FEATURE_SESSION,
    MODEL_ARTIFACT_SHA256,
)
from marketlab.events import sha256_bytes

T012_DECISION_LEDGER_ID = "AE001-T012-DECISION-LEDGER-v1"
T012_DECISION_ARTIFACT_ID = "AE001-T012-DECISION-v1"
MIN_COMMON_STOCKS = 100


def _ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def _time(value: object, *, label: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(str(value))
    except (ValueError, TypeError) as exc:
        raise AlphaContractError(f"T012 {label} timestamp invalid") from exc
    if timestamp.tzinfo is None:
        raise AlphaContractError(f"T012 {label} timestamp must be timezone-aware")
    return timestamp.astimezone(UTC)


def new_t012_decision_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": T012_DECISION_LEDGER_ID,
        "decision_count": 0,
        "decisions": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def validate_t012_decision_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != T012_DECISION_LEDGER_ID:
        raise AlphaContractError("T012 decision ledger identity mismatch")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("T012 ledger cannot authorize live capital")
    decisions = ledger.get("decisions")
    if not isinstance(decisions, list):
        raise AlphaContractError("T012 decisions must be a list")
    if ledger.get("decision_count") != len(decisions):
        raise AlphaContractError("T012 decision count mismatch")
    previous = ""
    for index, entry in enumerate(decisions, start=1):
        feature = str(entry.get("session_date") or "")
        next_session = str(entry.get("entry_session") or "")
        if entry.get("seq") != index:
            raise AlphaContractError("T012 decision sequence mismatch")
        if feature < FIRST_FEATURE_SESSION or feature <= previous:
            raise AlphaContractError("T012 decision sessions invalid or not increasing")
        if next_session <= feature:
            raise AlphaContractError("T012 entry session must follow D")
        if entry.get("live_capital_allowed") is not False:
            raise AlphaContractError("T012 entry cannot allow live capital")
        if int(entry.get("common_row_count") or 0) < MIN_COMMON_STOCKS:
            raise AlphaContractError("T012 decision below common-stock minimum")
        if entry.get("frozen_model_artifact_sha256") != MODEL_ARTIFACT_SHA256:
            raise AlphaContractError("T012 decision model artifact drift")
        if _time(entry.get("sealed_at_utc"), label="sealed") > preopen_cutoff_utc(
            next_session
        ):
            raise AlphaContractError("T012 decision sealed after pre-open cutoff")
        if not all(
            isinstance(entry.get(key), str) and len(entry[key]) == 64
            for key in (
                "sc001_attempt_sha256",
                "sc003_attempt_sha256",
                "artifact_sha256",
            )
        ):
            raise AlphaContractError("T012 missing source/artifact identity")
        stored = str(entry.get("decision_entry_sha256") or "")
        unsigned = dict(entry)
        unsigned.pop("decision_entry_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("T012 decision entry hash mismatch")
        previous = feature
    if ledger.get("ledger_sha256") != _ledger_hash(ledger):
        raise AlphaContractError("T012 decision ledger hash mismatch")


def build_t012_decision_artifact(
    *,
    admission: dict[str, Any],
    prior_market_sessions: list[dict[str, Any]],
    current_market_raw: bytes,
    prior_delivery_sessions: list[dict[str, Any]],
    current_delivery_raw: bytes,
    current_futures_raw: bytes,
    corporate_action_payload: object,
    corporate_action_raw: bytes,
    frozen_models: dict[str, Any],
) -> dict[str, Any]:
    """Score approved D-only information; require caller's final-clock admission."""
    preflight = dict(admission)
    preflight.pop("admission_sha256", None)
    if admission.get("admission_sha256") != digest(preflight):
        raise AlphaContractError("T012 admission hash mismatch")
    if admission.get("trial_id") != "AE001-T012":
        raise AlphaContractError("T012 admission trial identity mismatch")
    feature = str(admission.get("feature_session") or "")
    if feature < FIRST_FEATURE_SESSION:
        raise AlphaContractError("T012 decision precedes first feature session")
    if _time(admission.get("sealed_at_utc"), label="sealed") > preopen_cutoff_utc(
        str(admission.get("entry_session"))
    ):
        raise AlphaContractError("T012 prediction sealing missed pre-open cutoff")
    if admission.get("live_capital_allowed") is not False:
        raise AlphaContractError("T012 admission cannot allow live capital")
    if admission.get("outcomes_attached") is not False:
        raise AlphaContractError("T012 admission contains outcomes")
    for label, raw in (
        ("cash_market", current_market_raw),
        ("delivery", current_delivery_raw),
        ("futures", current_futures_raw),
    ):
        expected = admission.get(f"{label}_raw_sha256")
        if sha256_bytes(raw) != expected:
            raise AlphaContractError(f"T012 {label} raw source hash mismatch")
    validate_frozen_t006_models(frozen_models)
    if frozen_models["artifact_sha256"] != MODEL_ARTIFACT_SHA256:
        raise AlphaContractError("T012 frozen model artifact drift")

    rows, diagnostics = build_t006_current_feature_rows(
        prior_market_sessions=prior_market_sessions,
        current_market_raw=current_market_raw,
        prior_delivery_sessions=prior_delivery_sessions,
        current_delivery_raw=current_delivery_raw,
        current_futures_raw=current_futures_raw,
        session_date=feature,
        corporate_action_payload=corporate_action_payload,
    )
    if len(rows) < MIN_COMMON_STOCKS:
        raise AlphaContractError(
            f"T012 common row count below frozen minimum: {len(rows)}"
        )
    base = _score_model(frozen_models["base_model"], rows)
    augmented = _score_model(frozen_models["augmented_model"], rows)
    if [(r["symbol"], r["isin"]) for r in base] != [
        (r["symbol"], r["isin"]) for r in augmented
    ]:
        raise AlphaContractError("T012 base and augmented prediction identities differ")
    if frozen_models["base_model"]["model_sha256"] != BASE_SHA256:
        raise AlphaContractError("T012 CORE27 model mismatch")
    if frozen_models["augmented_model"]["model_sha256"] != AUGMENTED_SHA256:
        raise AlphaContractError("T012 FULL37 model mismatch")
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "artifact_id": T012_DECISION_ARTIFACT_ID,
        "trial_id": "AE001-T012",
        "session_date": feature,
        "entry_session": admission["entry_session"],
        "sealed_at_utc": admission["sealed_at_utc"],
        "decision_cutoff_utc": admission["decision_deadline_utc"],
        "admission_sha256": admission["admission_sha256"],
        "sc001_attempt_sha256": admission["sc001_attempt_sha256"],
        "sc003_attempt_sha256": admission["sc003_attempt_sha256"],
        "current_market_sha256": sha256_bytes(current_market_raw),
        "current_delivery_sha256": sha256_bytes(current_delivery_raw),
        "current_futures_sha256": sha256_bytes(current_futures_raw),
        "prior_market_support_sha256": digest(prior_market_sessions),
        "prior_delivery_support_sha256": digest(prior_delivery_sessions),
        "corporate_action_raw_sha256": sha256_bytes(corporate_action_raw),
        "frozen_model_artifact_sha256": MODEL_ARTIFACT_SHA256,
        "base_model_sha256": BASE_SHA256,
        "augmented_model_sha256": AUGMENTED_SHA256,
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
    artifact: dict[str, Any],
    artifact_path: str,
) -> dict[str, Any]:
    validate_t012_decision_ledger(ledger)
    if artifact.get("artifact_id") != T012_DECISION_ARTIFACT_ID:
        raise AlphaContractError("T012 append artifact identity mismatch")
    if artifact.get("outcomes_attached") is not False:
        raise AlphaContractError("T012 cannot append outcome-contaminated prediction")
    if artifact.get("live_capital_allowed") is not False:
        raise AlphaContractError("T012 cannot append live-capital prediction")
    unsigned = dict(artifact)
    unsigned.pop("artifact_sha256", None)
    if artifact.get("artifact_sha256") != digest(unsigned):
        raise AlphaContractError("T012 prediction artifact hash mismatch")
    feature = str(artifact.get("session_date") or "")
    if any(row["session_date"] == feature for row in ledger["decisions"]):
        raise AlphaContractError("T012 decision already sealed for feature session")
    entry = {
        "seq": len(ledger["decisions"]) + 1,
        "session_date": feature,
        "entry_session": artifact["entry_session"],
        "sealed_at_utc": artifact["sealed_at_utc"],
        "artifact_path": artifact_path,
        "artifact_sha256": artifact["artifact_sha256"],
        "admission_sha256": artifact["admission_sha256"],
        "common_row_count": artifact["common_row_count"],
        "sc001_attempt_sha256": artifact["sc001_attempt_sha256"],
        "sc003_attempt_sha256": artifact["sc003_attempt_sha256"],
        "frozen_model_artifact_sha256": artifact[
            "frozen_model_artifact_sha256"
        ],
        "live_capital_allowed": False,
    }
    entry["decision_entry_sha256"] = digest(entry)
    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    updated["decisions"].append(entry)
    updated["decision_count"] = len(updated["decisions"])
    updated["ledger_sha256"] = _ledger_hash(updated)
    validate_t012_decision_ledger(updated)
    return updated


def reseal_t012_decision_artifact(
    artifact: dict[str, Any],
    *,
    final_admission: dict[str, Any],
) -> dict[str, Any]:
    """Bind the *completed* computation to a fresh final pre-open clock proof.

    A preflight admission before data download/computation is not a final
    sealing event. The runner MUST call this after scoring and before writing.
    """
    initial = dict(artifact)
    stored_artifact_sha256 = initial.pop("artifact_sha256", None)
    if digest(initial) != stored_artifact_sha256:
        raise AlphaContractError("T012 preflight artifact hash mismatch")
    final = dict(final_admission)
    stored_admission_sha256 = final.pop("admission_sha256", None)
    if digest(final) != stored_admission_sha256:
        raise AlphaContractError("T012 final admission hash mismatch")
    if final_admission.get("trial_id") != "AE001-T012":
        raise AlphaContractError("T012 final admission is for wrong trial")
    pairs = {
        "session_date": "feature_session",
        "entry_session": "entry_session",
        "sc001_attempt_sha256": "sc001_attempt_sha256",
        "sc003_attempt_sha256": "sc003_attempt_sha256",
        "current_market_sha256": "cash_market_raw_sha256",
        "current_delivery_sha256": "delivery_raw_sha256",
        "current_futures_sha256": "futures_raw_sha256",
        "frozen_model_artifact_sha256": "frozen_model_artifact_sha256",
    }
    for artifact_key, admission_key in pairs.items():
        if artifact.get(artifact_key) != final_admission.get(admission_key):
            raise AlphaContractError(
                f"T012 final admission source/model drift: {artifact_key}"
            )
    final_sealed = _time(final_admission.get("sealed_at_utc"), label="final seal")
    if final_sealed < _time(artifact.get("sealed_at_utc"), label="preflight"):
        raise AlphaContractError("T012 final seal predates preflight")
    if final_sealed > preopen_cutoff_utc(str(artifact["entry_session"])):
        raise AlphaContractError("T012 final seal missed pre-open cutoff")
    if final_admission.get("live_capital_allowed") is not False:
        raise AlphaContractError("T012 final admission cannot permit live capital")
    updated = copy.deepcopy(artifact)
    updated.pop("artifact_sha256", None)
    updated["sealed_at_utc"] = final_admission["sealed_at_utc"]
    updated["admission_sha256"] = final_admission["admission_sha256"]
    updated["decision_cutoff_utc"] = final_admission["decision_deadline_utc"]
    updated["artifact_sha256"] = digest(updated)
    return updated
