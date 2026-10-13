"""T012: matured future labels and preregistered paired primary inference.

This module is deliberately downstream of the append-only T012 prediction ledger.
Outcomes never alter a previously sealed decision artifact or its model scores.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_diagnostics import paired_report_difference_inference
from marketlab.alpha_t006_outcomes import (
    _aggregate,
    _mean,
    build_t006_horizon_outcome,
)
from marketlab.alpha_t012_decisions import validate_t012_decision_ledger
from marketlab.alpha_trials import append_trial_event, trial_state, validate_trial_ledger
from marketlab.calendar_snapshot import CalendarSnapshot

T012_OUTCOME_LEDGER_ID = "AE001-T012-OUTCOME-LEDGER-v1"
HORIZONS = (1, 5)
MIN_PRIMARY_DECISIONS = 60
MIN_VALID_PAIRED_IC_SESSIONS = 50


def _hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def new_t012_outcome_ledger() -> dict[str, Any]:
    obj: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": T012_OUTCOME_LEDGER_ID,
        "outcome_count": 0,
        "outcomes": [],
        "live_capital_allowed": False,
    }
    obj["ledger_sha256"] = _hash(obj)
    return obj


def validate_t012_outcome_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != T012_OUTCOME_LEDGER_ID:
        raise AlphaContractError("T012 outcome ledger id mismatch")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("T012 outcome ledger cannot authorize live capital")
    outcomes = ledger.get("outcomes")
    if not isinstance(outcomes, list):
        raise AlphaContractError("T012 outcomes must be a list")
    if ledger.get("outcome_count") != len(outcomes):
        raise AlphaContractError("T012 outcome count mismatch")
    seen: set[tuple[str, int]] = set()
    previous: tuple[str, int] | None = None
    for position, record in enumerate(outcomes, start=1):
        key = (
            str(record.get("decision_session") or ""),
            int(record.get("horizon_sessions") or 0),
        )
        if record.get("seq") != position or not key[0] or key[1] not in HORIZONS:
            raise AlphaContractError("T012 invalid outcome ledger sequence/identity")
        if key in seen:
            raise AlphaContractError("T012 outcome duplicated")
        if record.get("live_capital_allowed") is not False:
            raise AlphaContractError("T012 outcome cannot authorize capital")
        if record.get("entry_session") <= key[0]:
            raise AlphaContractError("T012 outcome entry does not follow feature D")
        if record.get("exit_session") < record["entry_session"]:
            raise AlphaContractError("T012 outcome exit precedes entry")
        if not all(
            isinstance(record.get(k), str) and len(record[k]) == 64
            for k in ("decision_artifact_sha256", "artifact_sha256")
        ):
            raise AlphaContractError("T012 outcome missing source decision hash")
        stored = str(record.get("outcome_entry_sha256") or "")
        unsigned = dict(record)
        unsigned.pop("outcome_entry_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("T012 outcome entry hash mismatch")
        seen.add(key)
        previous = key
    if ledger.get("ledger_sha256") != _hash(ledger):
        raise AlphaContractError("T012 outcome ledger hash mismatch")


def expected_t012_holding_sessions(
    calendar: CalendarSnapshot,
    *,
    decision_session: str,
    horizon_sessions: int,
) -> list[str] | None:
    """Never replace a missing official session with the next available row."""
    if horizon_sessions not in HORIZONS:
        raise AlphaContractError("T012 unsupported outcome horizon")
    dates = [row.session_date for row in calendar.sessions]
    try:
        pos = dates.index(decision_session)
    except ValueError as exc:
        raise AlphaContractError("T012 outcome D absent from frozen calendar") from exc
    held = dates[pos + 1:pos + 1 + horizon_sessions]
    if len(held) < horizon_sessions:
        # Cannot claim that a 2027 market date exists before its authoritative
        # calendar is captured. A separately registered rollover is required.
        return None
    return held


def build_t012_horizon_outcome(
    *,
    decision_artifact: dict[str, Any],
    market_sessions: list[dict[str, Any]],
    calendar: CalendarSnapshot,
    corporate_action_payload: object,
    corporate_action_raw: bytes,
    horizon_sessions: int,
    recorded_at_utc: str,
) -> dict[str, Any]:
    """Require all exact frozen holding sessions to be completed and present."""
    if decision_artifact.get("trial_id") != "AE001-T012":
        raise AlphaContractError("T012 outcome decision must belong to T012")
    if decision_artifact.get("outcomes_attached") is not False:
        raise AlphaContractError("T012 outcome decision must remain outcome-free")
    decision = str(decision_artifact.get("session_date") or "")
    expected = expected_t012_holding_sessions(
        calendar, decision_session=decision, horizon_sessions=horizon_sessions
    )
    if expected is None:
        raise AlphaContractError("T012 outcome requires frozen calendar rollover")
    lookup = {str(row["session_date"]): row for row in market_sessions}
    if len(lookup) != len(market_sessions):
        raise AlphaContractError("T012 duplicate market holding sessions")
    if any(day not in lookup for day in expected):
        raise AlphaContractError("T012 missing official holding session evidence")
    recorded = datetime.fromisoformat(recorded_at_utc)
    if recorded.tzinfo is None:
        raise AlphaContractError("T012 outcome timestamp must be timezone-aware")
    exit_session = next(
        row for row in calendar.sessions if row.session_date == expected[-1]
    )
    exit_close = datetime.fromisoformat(exit_session.close_timestamp_utc)
    if recorded.astimezone(UTC) < exit_close.astimezone(UTC):
        raise AlphaContractError("T012 outcome created before official exit close")
    if decision_artifact.get("entry_session") != expected[0]:
        raise AlphaContractError("T012 outcome entry violates frozen next-session open")
    signed = decision_artifact.get("artifact_sha256")
    unsigned = dict(decision_artifact)
    unsigned.pop("artifact_sha256", None)
    if signed != digest(unsigned):
        raise AlphaContractError("T012 decision artifact hash mismatch")
    # Existing T006 market-relative label engine is reused unchanged;
    # it uses NSE official open-to-close and strict ISIN/corporate-action gates.
    base = build_t006_horizon_outcome(
        decision_artifact=decision_artifact,
        market_sessions=[lookup[day] for day in expected],
        corporate_action_payload=corporate_action_payload,
        corporate_action_raw=corporate_action_raw,
        horizon_sessions=horizon_sessions,
    )
    if (
        base["entry_session"] != expected[0]
        or base["exit_session"] != expected[-1]
        or base["decision_artifact_sha256"] != signed
    ):
        raise AlphaContractError("T012 reused outcome engine violated horizon/lineage")
    updated = copy.deepcopy(base)
    updated.pop("artifact_sha256", None)
    updated["artifact_id"] = f"AE001-T012-H{horizon_sessions}-OUTCOME-v1"
    updated["trial_id"] = "AE001-T012"
    updated["frozen_calendar_sha256"] = calendar.sha256
    updated["recorded_at_utc"] = recorded.astimezone(UTC).isoformat()
    updated["artifact_sha256"] = digest(updated)
    return updated


def append_t012_outcome(
    ledger: dict[str, Any],
    *,
    outcome_artifact: dict[str, Any],
    artifact_path: str,
) -> dict[str, Any]:
    validate_t012_outcome_ledger(ledger)
    h = int(outcome_artifact.get("horizon_sessions") or 0)
    if (
        outcome_artifact.get("trial_id") != "AE001-T012"
        or outcome_artifact.get("artifact_id") != f"AE001-T012-H{h}-OUTCOME-v1"
        or h not in HORIZONS
    ):
        raise AlphaContractError("T012 outcome artifact trial/horizon mismatch")
    if outcome_artifact.get("live_capital_allowed") is not False:
        raise AlphaContractError("T012 outcome cannot permit live capital")
    unsigned = dict(outcome_artifact)
    unsigned.pop("artifact_sha256", None)
    if outcome_artifact.get("artifact_sha256") != digest(unsigned):
        raise AlphaContractError("T012 outcome artifact hash mismatch")
    key = (str(outcome_artifact["decision_session"]), h)
    if any(
        (row["decision_session"], row["horizon_sessions"]) == key
        for row in ledger["outcomes"]
    ):
        raise AlphaContractError("T012 already sealed this future outcome")
    row: dict[str, Any] = {
        "seq": len(ledger["outcomes"]) + 1,
        "decision_session": key[0],
        "horizon_sessions": h,
        "entry_session": outcome_artifact["entry_session"],
        "exit_session": outcome_artifact["exit_session"],
        "artifact_path": artifact_path,
        "artifact_sha256": outcome_artifact["artifact_sha256"],
        "decision_artifact_sha256": outcome_artifact["decision_artifact_sha256"],
        "valid_outcome_row_count": outcome_artifact["valid_outcome_row_count"],
        "valid_paired_ic": outcome_artifact["valid_paired_ic"],
        "live_capital_allowed": False,
    }
    row["outcome_entry_sha256"] = digest(row)
    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    updated["outcomes"].append(row)
    updated["outcome_count"] = len(updated["outcomes"])
    updated["ledger_sha256"] = _hash(updated)
    validate_t012_outcome_ledger(updated)
    return updated


def first_t012_primary_cohort(
    *, decisions: dict[str, Any], outcomes: dict[str, Any]
) -> list[str] | None:
    validate_t012_decision_ledger(decisions)
    validate_t012_outcome_ledger(outcomes)
    decision_rows = decisions["decisions"]
    if len(decision_rows) < MIN_PRIMARY_DECISIONS:
        return None
    h5 = {
        row["decision_session"]: row
        for row in outcomes["outcomes"]
        if row["horizon_sessions"] == 5
    }
    for size in range(MIN_PRIMARY_DECISIONS, len(decision_rows) + 1):
        cohort = [r["session_date"] for r in decision_rows[:size]]
        if not all(day in h5 for day in cohort):
            return None
        if sum(bool(h5[d]["valid_paired_ic"]) for d in cohort) >= (
            MIN_VALID_PAIRED_IC_SESSIONS
        ):
            return cohort
    return None


def _result_event(trials: dict[str, Any], kind: str) -> dict | None:
    state = trial_state(trials, "AE001-T012")
    return next(
        (
            row
            for row in state["results"]
            if row["payload"].get("result_kind") == kind
        ),
        None,
    )


def _primary_payload(artifacts: list[dict], cohort: list[str]) -> dict:
    base = _aggregate(artifacts, model_key="base")
    augmented = _aggregate(artifacts, model_key="augmented")
    inference = paired_report_difference_inference(
        augmented, base, max_lag=4
    )
    rank = inference["metrics"]["rank_ic"]
    spread = inference["metrics"]["top_minus_bottom_spread"]

    def _supported(metric: dict) -> bool:
        return (
            metric["mean"] is not None
            and float(metric["mean"]) > 0
            and metric["p_value_two_sided"] is not None
            and float(metric["p_value_two_sided"]) < 0.05
        )

    supported = _supported(rank) and _supported(spread)
    return {
        "result_kind": "PRIMARY_5D",
        "status": "SUPPORTED" if supported else "NOT_SUPPORTED",
        "cohort_rule": "T012_SMALLEST_CHRONOLOGICAL_MATURED_PREFIX",
        "cohort_size": len(cohort),
        "cohort_decision_sessions": cohort,
        "valid_paired_ic_session_count": sum(
            bool(row["valid_paired_ic"]) for row in artifacts
        ),
        "base_mean_rank_ic": _mean(
            artifacts, model_key="base", field="rank_ic"
        ),
        "augmented_mean_rank_ic": _mean(
            artifacts, model_key="augmented", field="rank_ic"
        ),
        "base_mean_top_minus_bottom_spread": _mean(
            artifacts, model_key="base", field="top_minus_bottom_spread"
        ),
        "augmented_mean_top_minus_bottom_spread": _mean(
            artifacts, model_key="augmented", field="top_minus_bottom_spread"
        ),
        "paired_augmented_minus_base": inference,
        "primary_adjustment": "GLOBAL_RTA001_ALPHA_FEATURE_DISCOVERY_V1_PENDING",
        "live_capital_allowed": False,
    }


def finalize_t012_results(
    *,
    trial_ledger: dict[str, Any],
    decisions: dict[str, Any],
    outcomes: dict[str, Any],
    outcome_artifacts: list[dict],
    recorded_at_utc: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    validate_trial_ledger(trial_ledger)
    validate_t012_decision_ledger(decisions)
    validate_t012_outcome_ledger(outcomes)
    state = trial_state(trial_ledger, "AE001-T012")
    if state["registration"]["payload"].get("status") != (
        "FROZEN_BEFORE_FIRST_ELIGIBLE_PREOPEN_DECISION"
    ):
        raise AlphaContractError("T012 trial registration changed")
    if state["amendment_count"] != 0:
        raise AlphaContractError("T012 result inference has unreviewed amendment")
    by_key = {
        (a["decision_session"], int(a["horizon_sessions"])): a
        for a in outcome_artifacts
    }
    expected = {
        (r["decision_session"], r["horizon_sessions"]): r["artifact_sha256"]
        for r in outcomes["outcomes"]
    }
    if len(by_key) != len(outcomes["outcomes"]) or any(
        a.get("artifact_sha256") != expected[k]
        for k, a in by_key.items()
    ):
        raise AlphaContractError("T012 outcome artifacts do not match signed ledger")
    now = datetime.fromisoformat(recorded_at_utc)
    if now.tzinfo is None:
        raise AlphaContractError("T012 inference timestamp must be aware")
    if _result_event(trial_ledger, "PRIMARY_5D") is not None:
        return copy.deepcopy(trial_ledger), []
    cohort = first_t012_primary_cohort(decisions=decisions, outcomes=outcomes)
    if cohort is None:
        return copy.deepcopy(trial_ledger), []
    ordered = [by_key[(session, 5)] for session in cohort]
    payload = _primary_payload(ordered, cohort)
    updated = append_trial_event(
        trial_ledger, event_type="TRIAL_RESULT_RECORDED",
        trial_id="AE001-T012", recorded_at_utc=recorded_at_utc,
        payload=payload,
    )
    emitted = [updated["events"][-1]]
    if all((session, 1) in by_key for session in cohort):
        secondary = [by_key[(session, 1)] for session in cohort]
        paired = paired_report_difference_inference(
            _aggregate(secondary, model_key="augmented"),
            _aggregate(secondary, model_key="base"),
            max_lag=5,
        )
        payload_secondary = {
            "result_kind": "SECONDARY_1D",
            "status": "REPORTED_NON_RESCUING_SECONDARY",
            "cohort_rule": "SAME_AS_PRIMARY_5D",
            "cohort_size": len(cohort),
            "cohort_decision_sessions": cohort,
            "primary_result_event_sha256": emitted[0]["event_sha256"],
            "paired_augmented_minus_base": paired,
            "rescues_failed_primary": False,
            "live_capital_allowed": False,
        }
        updated = append_trial_event(
            updated, event_type="TRIAL_RESULT_RECORDED",
            trial_id="AE001-T012", recorded_at_utc=recorded_at_utc,
            payload=payload_secondary,
        )
        emitted.append(updated["events"][-1])
    return updated, emitted
