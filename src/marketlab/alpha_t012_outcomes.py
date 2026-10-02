from __future__ import annotations

import copy
import statistics
from datetime import UTC, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_diagnostics import paired_report_difference_inference
from marketlab.alpha_t006_outcomes import build_t006_horizon_outcome
from marketlab.alpha_t012 import validate_t012_decision_ledger
from marketlab.alpha_trials import (
    append_trial_event,
    require_protocol_amendment,
    trial_state,
)

T012_OUTCOME_LEDGER_ID = "AE001-T012-OUTCOME-LEDGER-v1"
T012_HORIZONS = (1, 5)
PRIMARY_MIN_DECISIONS = 60
PRIMARY_MIN_VALID_PAIRED_IC = 50
OUTCOME_PROTOCOL_ID = "AE001-T012-P2"


def _ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def new_t012_outcome_ledger() -> dict[str, Any]:
    ledger = {
        "schema_version": 1,
        "ledger_id": T012_OUTCOME_LEDGER_ID,
        "outcome_count": 0,
        "outcomes": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def validate_t012_outcome_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != T012_OUTCOME_LEDGER_ID:
        raise AlphaContractError("unexpected T012 outcome ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("T012 outcome ledger cannot allow live capital")
    rows = ledger.get("outcomes")
    if not isinstance(rows, list):
        raise AlphaContractError("T012 outcomes must be a list")
    if ledger.get("outcome_count") != len(rows):
        raise AlphaContractError("T012 outcome count mismatch")
    seen: set[tuple[str, int]] = set()
    for index, row in enumerate(rows, start=1):
        if row.get("seq") != index:
            raise AlphaContractError("T012 outcome sequence mismatch")
        key = (
            str(row.get("decision_session") or ""),
            int(row.get("horizon_sessions") or 0),
        )
        if not key[0] or key[1] not in T012_HORIZONS or key in seen:
            raise AlphaContractError(
                "T012 outcome identity is invalid or duplicated"
            )
        seen.add(key)
        stored = str(row.get("outcome_entry_sha256") or "")
        unsigned = dict(row)
        unsigned.pop("outcome_entry_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("T012 outcome entry hash mismatch")
    if str(ledger.get("ledger_sha256") or "") != _ledger_hash(ledger):
        raise AlphaContractError("T012 outcome ledger hash mismatch")


def build_t012_horizon_outcome(
    *,
    decision_artifact: dict[str, Any],
    market_sessions: list[dict[str, Any]],
    corporate_action_payload: object,
    corporate_action_raw: bytes,
    horizon_sessions: int,
) -> dict[str, Any]:
    """Reuse the exact T006 label/evaluation mechanics under a T012 identity."""

    if decision_artifact.get("trial_id") != "AE001-T012":
        raise AlphaContractError("T012 outcome requires a T012 decision")
    if horizon_sessions not in T012_HORIZONS:
        raise AlphaContractError("unsupported T012 outcome horizon")

    artifact = build_t006_horizon_outcome(
        decision_artifact=decision_artifact,
        market_sessions=market_sessions,
        corporate_action_payload=corporate_action_payload,
        corporate_action_raw=corporate_action_raw,
        horizon_sessions=horizon_sessions,
    )
    artifact.pop("artifact_sha256", None)
    artifact["artifact_id"] = (
        f"AE001-T012-H{horizon_sessions}-OUTCOME-v1"
    )
    artifact["trial_id"] = "AE001-T012"
    artifact["cutoff_freeze_sha256"] = decision_artifact[
        "cutoff_freeze_sha256"
    ]
    artifact["source_timing_summary_sha256"] = decision_artifact[
        "source_timing_summary_sha256"
    ]
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def append_t012_outcome(
    ledger: dict[str, Any],
    *,
    outcome_artifact: dict[str, Any],
    artifact_path: str,
) -> dict[str, Any]:
    validate_t012_outcome_ledger(ledger)
    key = (
        str(outcome_artifact["decision_session"]),
        int(outcome_artifact["horizon_sessions"]),
    )
    if any(
        (row["decision_session"], int(row["horizon_sessions"])) == key
        for row in ledger["outcomes"]
    ):
        raise AlphaContractError(
            f"T012 outcome already exists for {key[0]} H{key[1]}"
        )
    entry = {
        "seq": len(ledger["outcomes"]) + 1,
        "decision_session": key[0],
        "horizon_sessions": key[1],
        "artifact_path": artifact_path,
        "artifact_sha256": outcome_artifact["artifact_sha256"],
        "entry_session": outcome_artifact["entry_session"],
        "exit_session": outcome_artifact["exit_session"],
        "valid_outcome_row_count": outcome_artifact[
            "valid_outcome_row_count"
        ],
        "valid_paired_ic": outcome_artifact["valid_paired_ic"],
        "cutoff_freeze_sha256": outcome_artifact[
            "cutoff_freeze_sha256"
        ],
        "live_capital_allowed": False,
    }
    entry["outcome_entry_sha256"] = digest(entry)
    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    updated["outcomes"].append(entry)
    updated["outcome_count"] = len(updated["outcomes"])
    updated["ledger_sha256"] = _ledger_hash(updated)
    validate_t012_outcome_ledger(updated)
    return updated


def _session_metric(
    outcome: dict[str, Any],
    model_key: str,
) -> dict[str, Any] | None:
    metrics = outcome[f"{model_key}_metrics"]["session_metrics"]
    return metrics[0] if metrics else None


def _aggregate(
    artifacts: list[dict[str, Any]],
    *,
    model_key: str,
) -> dict[str, Any]:
    return {
        "session_metrics": [
            metric
            for artifact in artifacts
            if (metric := _session_metric(artifact, model_key)) is not None
        ]
    }


def _mean(
    artifacts: list[dict[str, Any]],
    *,
    model_key: str,
    field: str,
) -> float | None:
    values = [
        float(metric[field])
        for artifact in artifacts
        if (metric := _session_metric(artifact, model_key)) is not None
        and metric.get(field) is not None
    ]
    return statistics.mean(values) if values else None


def _result_event(
    ledger: dict[str, Any],
    kind: str,
) -> dict[str, Any] | None:
    state = trial_state(ledger, "AE001-T012")
    return next(
        (
            event
            for event in state["results"]
            if event["payload"].get("result_kind") == kind
        ),
        None,
    )


def find_t012_primary_cohort(
    *,
    decisions: list[dict[str, Any]],
    outcome_ledger: dict[str, Any],
) -> list[str] | None:
    validate_t012_outcome_ledger(outcome_ledger)
    if len(decisions) < PRIMARY_MIN_DECISIONS:
        return None
    h5 = {
        row["decision_session"]: row
        for row in outcome_ledger["outcomes"]
        if int(row["horizon_sessions"]) == 5
    }
    for size in range(PRIMARY_MIN_DECISIONS, len(decisions) + 1):
        prefix = decisions[:size]
        sessions = [str(row["session_date"]) for row in prefix]
        if not all(session in h5 for session in sessions):
            return None
        valid = sum(bool(h5[session]["valid_paired_ic"]) for session in sessions)
        if valid >= PRIMARY_MIN_VALID_PAIRED_IC:
            return sessions
    return None


def finalize_t012_results(
    *,
    trial_ledger: dict[str, Any],
    decision_ledger: dict[str, Any],
    outcome_ledger: dict[str, Any],
    outcome_artifacts: list[dict[str, Any]],
    recorded_at_utc: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    validate_t012_decision_ledger(decision_ledger)
    validate_t012_outcome_ledger(outcome_ledger)
    require_protocol_amendment(
        trial_ledger,
        trial_id="AE001-T012",
        protocol_id=OUTCOME_PROTOCOL_ID,
    )
    now = recorded_at_utc or datetime.now(UTC).isoformat()
    updated = copy.deepcopy(trial_ledger)
    emitted = []
    by_key = {
        (row["decision_session"], int(row["horizon_sessions"])): row
        for row in outcome_artifacts
    }

    primary = _result_event(updated, "PRIMARY_5D")
    if primary is None:
        cohort = find_t012_primary_cohort(
            decisions=decision_ledger["decisions"],
            outcome_ledger=outcome_ledger,
        )
        if cohort is not None:
            artifacts = [by_key[(session, 5)] for session in cohort]
            base = _aggregate(artifacts, model_key="base")
            augmented = _aggregate(artifacts, model_key="augmented")
            paired = paired_report_difference_inference(
                augmented,
                base,
                max_lag=4,
            )
            rank = paired["metrics"]["rank_ic"]
            spread = paired["metrics"]["top_minus_bottom_spread"]
            supported = (
                rank["mean"] is not None
                and float(rank["mean"]) > 0
                and rank["p_value_two_sided"] is not None
                and float(rank["p_value_two_sided"]) < 0.05
                and spread["mean"] is not None
                and float(spread["mean"]) > 0
                and spread["p_value_two_sided"] is not None
                and float(spread["p_value_two_sided"]) < 0.05
            )
            cutoff_hashes = {
                str(by_key[(session, 5)]["cutoff_freeze_sha256"])
                for session in cohort
            }
            if len(cutoff_hashes) != 1:
                raise AlphaContractError(
                    "T012 primary cohort uses multiple cutoff freezes"
                )
            payload = {
                "result_kind": "PRIMARY_5D",
                "status": "SUPPORTED" if supported else "NOT_SUPPORTED",
                "cohort_rule": (
                    "T012_P2_SMALLEST_CHRONOLOGICAL_CANONICAL_PREFIX"
                ),
                "cohort_size": len(cohort),
                "cohort_decision_sessions": cohort,
                "cutoff_freeze_sha256": next(iter(cutoff_hashes)),
                "valid_paired_ic_session_count": sum(
                    by_key[(session, 5)]["valid_paired_ic"]
                    for session in cohort
                ),
                "base_mean_rank_ic": _mean(
                    artifacts,
                    model_key="base",
                    field="rank_ic",
                ),
                "augmented_mean_rank_ic": _mean(
                    artifacts,
                    model_key="augmented",
                    field="rank_ic",
                ),
                "base_mean_top_minus_bottom_spread": _mean(
                    artifacts,
                    model_key="base",
                    field="top_minus_bottom_spread",
                ),
                "augmented_mean_top_minus_bottom_spread": _mean(
                    artifacts,
                    model_key="augmented",
                    field="top_minus_bottom_spread",
                ),
                "paired_augmented_minus_base": paired,
                "live_capital_allowed": False,
            }
            updated = append_trial_event(
                updated,
                event_type="TRIAL_RESULT_RECORDED",
                trial_id="AE001-T012",
                recorded_at_utc=now,
                payload=payload,
            )
            emitted.append(updated["events"][-1])
            primary = updated["events"][-1]

    if (
        primary is not None
        and _result_event(updated, "SECONDARY_1D") is None
    ):
        cohort = list(primary["payload"]["cohort_decision_sessions"])
        if all((session, 1) in by_key for session in cohort):
            artifacts = [by_key[(session, 1)] for session in cohort]
            base = _aggregate(artifacts, model_key="base")
            augmented = _aggregate(artifacts, model_key="augmented")
            paired = paired_report_difference_inference(
                augmented,
                base,
                max_lag=5,
            )
            payload = {
                "result_kind": "SECONDARY_1D",
                "status": "REPORTED_NON_RESCUING_SECONDARY",
                "primary_result_event_sha256": primary["event_sha256"],
                "cohort_size": len(cohort),
                "cohort_decision_sessions": cohort,
                "cutoff_freeze_sha256": primary["payload"][
                    "cutoff_freeze_sha256"
                ],
                "base_mean_rank_ic": _mean(
                    artifacts,
                    model_key="base",
                    field="rank_ic",
                ),
                "augmented_mean_rank_ic": _mean(
                    artifacts,
                    model_key="augmented",
                    field="rank_ic",
                ),
                "base_mean_top_minus_bottom_spread": _mean(
                    artifacts,
                    model_key="base",
                    field="top_minus_bottom_spread",
                ),
                "augmented_mean_top_minus_bottom_spread": _mean(
                    artifacts,
                    model_key="augmented",
                    field="top_minus_bottom_spread",
                ),
                "paired_augmented_minus_base": paired,
                "rescues_failed_primary": False,
                "live_capital_allowed": False,
            }
            updated = append_trial_event(
                updated,
                event_type="TRIAL_RESULT_RECORDED",
                trial_id="AE001-T012",
                recorded_at_utc=now,
                payload=payload,
            )
            emitted.append(updated["events"][-1])

    return updated, emitted
