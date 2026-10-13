"""Calendar-strict, source-retained, prospective T012 return evaluation.

The original AE001-T006 return evaluator is reused without mutating T006.
Only *future* NSE trading sessions fixed by the registered calendar can be
attached, and all source attempts retain their true acquisition timestamp.
"""

from __future__ import annotations

import copy
from datetime import UTC, date, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_diagnostics import paired_report_difference_inference
from marketlab.alpha_t006_outcomes import build_t006_horizon_outcome
from marketlab.alpha_t012_decisions import validate_t012_decision_ledger
from marketlab.alpha_t012_preopen import CALENDAR_SHA256, FIRST_FEATURE_SESSION
from marketlab.alpha_trials import append_trial_event, trial_state
from marketlab.calendar_snapshot import CalendarSnapshot
from marketlab.marketdata import index_snapshot_url, udiff_url

TRIAL = "AE001-T012"
OUTCOME_LEDGER_ID = "AE001-T012-OUTCOME-LEDGER-v1"
HORIZONS = (1, 5)
MIN_DECISIONS = 60
MIN_VALID_IC = 50


def _time(value: object, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise AlphaContractError(f"T012 {label} is not an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError(f"T012 {label} must have a timezone")
    return parsed.astimezone(UTC)


def _hash_without(payload: dict[str, Any], key: str) -> str:
    obj = copy.deepcopy(payload)
    obj.pop(key, None)
    return digest(obj)


def _calendar_sessions(
    calendar: CalendarSnapshot,
    *,
    decision_session: str,
    horizon: int,
) -> list[Any]:
    if calendar.sha256 != CALENDAR_SHA256:
        raise AlphaContractError("T012 outcome frozen calendar SHA mismatch")
    if horizon not in HORIZONS:
        raise AlphaContractError("T012 unsupported holding horizon")
    if decision_session < FIRST_FEATURE_SESSION:
        raise AlphaContractError("T012 outcome predates frozen first decision")
    dates = [s.session_date for s in calendar.sessions]
    if decision_session not in dates:
        raise AlphaContractError("T012 decision absent from frozen trading calendar")
    first = dates.index(decision_session) + 1
    holding = list(calendar.sessions[first : first + horizon])
    if len(holding) != horizon:
        raise AlphaContractError("T012 frozen calendar lacks full holding horizon")
    if any(
        decision_session < unresolved <= holding[-1].session_date
        for unresolved in calendar.unresolved_special_dates
    ):
        raise AlphaContractError(
            "T012 holding horizon crosses unresolved special trading session"
        )
    return holding


def expected_t012_holding_dates(
    calendar: CalendarSnapshot,
    *,
    decision_session: str,
    horizon: int,
) -> list[str]:
    return [
        row.session_date for row in _calendar_sessions(
            calendar, decision_session=decision_session, horizon=horizon
        )
    ]


def new_t012_outcome_ledger() -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": OUTCOME_LEDGER_ID,
        "outcome_count": 0,
        "outcomes": [],
        "live_capital_allowed": False,
    }
    result["ledger_sha256"] = _hash_without(result, "ledger_sha256")
    return result


def validate_t012_outcome_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != OUTCOME_LEDGER_ID:
        raise AlphaContractError("T012 outcome ledger identity mismatch")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("T012 outcome ledger authorizes live capital")
    rows = ledger.get("outcomes")
    if not isinstance(rows, list) or ledger.get("outcome_count") != len(rows):
        raise AlphaContractError("T012 outcome count mismatch")
    seen: set[tuple[str, int]] = set()
    for seq, row in enumerate(rows, start=1):
        key = (str(row.get("decision_session") or ""), int(
            row.get("horizon_sessions") or 0
        ))
        if row.get("seq") != seq or key in seen or key[1] not in HORIZONS:
            raise AlphaContractError("T012 outcome sequence/identity conflict")
        if key[0] < FIRST_FEATURE_SESSION:
            raise AlphaContractError("T012 retroactive outcome not permitted")
        if row.get("live_capital_allowed") is not False:
            raise AlphaContractError("T012 outcome entry permits live capital")
        if row.get("entry_session") <= key[0]:
            raise AlphaContractError("T012 outcome entry session invalid")
        if row.get("exit_session") < row["entry_session"]:
            raise AlphaContractError("T012 outcome exit session invalid")
        if not isinstance(row.get("valid_paired_ic"), bool):
            raise AlphaContractError("T012 invalid paired IC status")
        expected = _hash_without(row, "outcome_entry_sha256")
        if row.get("outcome_entry_sha256") != expected:
            raise AlphaContractError("T012 outcome entry hash mismatch")
        seen.add(key)
    if ledger.get("ledger_sha256") != _hash_without(ledger, "ledger_sha256"):
        raise AlphaContractError("T012 outcome ledger hash mismatch")


def build_t012_horizon_outcome(
    *,
    decision_artifact: dict[str, Any],
    market_sessions: list[dict[str, Any]],
    corporate_action_payload: object,
    corporate_action_raw: bytes,
    horizon_sessions: int,
    calendar: CalendarSnapshot,
    captured_at_utc: str,
) -> dict[str, Any]:
    """Reject missing intermediate dates instead of silently extending a horizon."""
    if decision_artifact.get("trial_id") != TRIAL:
        raise AlphaContractError("T012 outcome requires exact trial decision")
    if decision_artifact.get("outcomes_attached") is not False:
        raise AlphaContractError("T012 decision already contaminated with outcomes")
    if decision_artifact.get("live_capital_allowed") is not False:
        raise AlphaContractError("T012 decision permits live capital")
    if decision_artifact.get("artifact_sha256") != _hash_without(
        decision_artifact, "artifact_sha256"
    ):
        raise AlphaContractError("T012 decision artifact hash mismatch")

    d = str(decision_artifact.get("session_date") or "")
    holding = _calendar_sessions(
        calendar, decision_session=d, horizon=horizon_sessions
    )
    expected_dates = [session.session_date for session in holding]
    if decision_artifact.get("entry_session") != expected_dates[0]:
        raise AlphaContractError("T012 decision entry does not match frozen N")
    actual_dates = [str(row.get("session_date") or "") for row in market_sessions]
    if actual_dates != expected_dates:
        raise AlphaContractError(
            f"T012 missing/duplicate/shifted frozen holding session: "
            f"expected {expected_dates}, received {actual_dates}"
        )
    captured = _time(captured_at_utc, label="outcome capture")
    if captured < _time(holding[-1].close_timestamp_utc, label="exit close"):
        raise AlphaContractError("T012 return observed before frozen exit close")
    if captured <= _time(
        decision_artifact["sealed_at_utc"], label="prediction seal"
    ):
        raise AlphaContractError("T012 outcome source predates forecast seal")

    for row in market_sessions:
        iso = row["session_date"]
        benchmark = row.get("benchmark") or {}
        if (
            benchmark.get("benchmark_id") != "nifty_500"
            or benchmark.get("session_date") != iso
            or not row.get("equities")
        ):
            raise AlphaContractError("T012 missing exact NSE EQ/Nifty500 session")
        if (
            row.get("udiff_url") != udiff_url(date.fromisoformat(iso))
            or row.get("benchmark_url") != index_snapshot_url(
                date.fromisoformat(iso)
            )
            or not row.get("udiff_sha256")
            or not row.get("benchmark_sha256")
            or not row.get("original_market_raw_path")
            or not row.get("original_index_raw_path")
        ):
            raise AlphaContractError("T012 original official market source absent")
        if _time(row.get("captured_at_utc"), label="source capture") < _time(
            next(
                session.close_timestamp_utc
                for session in holding
                if session.session_date == iso
            ),
            label="source session close",
        ):
            raise AlphaContractError("T012 source was captured before its close")

    # T006 implementation defines the frozen exact daily rank-IC / price-index
    # outcome semantics. Its trial is not modified or appended here.
    evaluated = build_t006_horizon_outcome(
        decision_artifact=decision_artifact,
        market_sessions=market_sessions,
        corporate_action_payload=corporate_action_payload,
        corporate_action_raw=corporate_action_raw,
        horizon_sessions=horizon_sessions,
    )
    if (
        evaluated.get("entry_session") != expected_dates[0]
        or evaluated.get("exit_session") != expected_dates[-1]
        or evaluated.get("decision_artifact_sha256")
        != decision_artifact["artifact_sha256"]
        or evaluated.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("T012 legacy evaluator produced wrong chronology")
    result = copy.deepcopy(evaluated)
    result.pop("artifact_sha256", None)
    result["artifact_id"] = f"AE001-T012-H{horizon_sessions}-OUTCOME-v1"
    result["trial_id"] = TRIAL
    result["frozen_calendar_sha256"] = CALENDAR_SHA256
    result["expected_holding_sessions"] = expected_dates
    result["captured_at_utc"] = captured.isoformat()
    result["source_basis"] = "POST_DECISION_ORIGINAL_NSE_EQ_AND_NIFTY500"
    result["historical_archive_first_publication_time_inferred"] = False
    result["fill_executed"] = False
    result["live_capital_allowed"] = False
    result["holding_session_evidence"] = [
        {
            **entry,
            "original_market_raw_path": market["original_market_raw_path"],
            "original_index_raw_path": market["original_index_raw_path"],
            "actual_source_captured_at_utc": market["captured_at_utc"],
        }
        for entry, market in zip(
            evaluated["holding_session_evidence"], market_sessions, strict=True
        )
    ]
    result["artifact_sha256"] = digest(result)
    return result


def append_t012_outcome(
    ledger: dict[str, Any],
    *,
    outcome_artifact: dict[str, Any],
    artifact_path: str,
) -> dict[str, Any]:
    validate_t012_outcome_ledger(ledger)
    if outcome_artifact.get("trial_id") != TRIAL:
        raise AlphaContractError("T012 outcome artifact wrong trial")
    if outcome_artifact.get("artifact_sha256") != _hash_without(
        outcome_artifact, "artifact_sha256"
    ):
        raise AlphaContractError("T012 outcome artifact hash mismatch")
    if outcome_artifact.get("live_capital_allowed") is not False:
        raise AlphaContractError("T012 outcome permits live capital")
    key = (
        str(outcome_artifact["decision_session"]),
        int(outcome_artifact["horizon_sessions"]),
    )
    if key[1] not in HORIZONS or any(
        (row["decision_session"], row["horizon_sessions"]) == key
        for row in ledger["outcomes"]
    ):
        raise AlphaContractError("T012 duplicate/invalid horizon outcome")
    entry = {
        "seq": len(ledger["outcomes"]) + 1,
        "decision_session": key[0],
        "horizon_sessions": key[1],
        "entry_session": outcome_artifact["entry_session"],
        "exit_session": outcome_artifact["exit_session"],
        "captured_at_utc": outcome_artifact["captured_at_utc"],
        "artifact_path": artifact_path,
        "artifact_sha256": outcome_artifact["artifact_sha256"],
        "decision_artifact_sha256": outcome_artifact[
            "decision_artifact_sha256"
        ],
        "valid_outcome_row_count": outcome_artifact["valid_outcome_row_count"],
        "valid_paired_ic": bool(outcome_artifact["valid_paired_ic"]),
        "live_capital_allowed": False,
    }
    entry["outcome_entry_sha256"] = digest(entry)
    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    updated["outcomes"].append(entry)
    updated["outcome_count"] = len(updated["outcomes"])
    updated["ledger_sha256"] = _hash_without(updated, "ledger_sha256")
    validate_t012_outcome_ledger(updated)
    return updated


def find_t012_primary_cohort(
    *,
    decision_ledger: dict[str, Any],
    outcome_ledger: dict[str, Any],
) -> list[str] | None:
    validate_t012_decision_ledger(decision_ledger)
    validate_t012_outcome_ledger(outcome_ledger)
    decisions = decision_ledger["decisions"]
    if len(decisions) < MIN_DECISIONS:
        return None
    h5 = {
        row["decision_session"]: row
        for row in outcome_ledger["outcomes"]
        if row["horizon_sessions"] == 5
    }
    for size in range(MIN_DECISIONS, len(decisions) + 1):
        prefix = decisions[:size]
        dates = [row["session_date"] for row in prefix]
        if not all(d in h5 for d in dates):
            return None
        valid = sum(bool(h5[d]["valid_paired_ic"]) for d in dates)
        if valid >= MIN_VALID_IC:
            return dates
    return None


def _summary_report(
    artifacts: list[dict[str, Any]],
    *,
    model: str,
) -> dict[str, Any]:
    return {
        "session_metrics": [
            a[f"{model}_metrics"]["session_metrics"][0]
            for a in artifacts
            if a[f"{model}_metrics"].get("session_metrics")
        ]
    }


def _supported(inference: dict[str, Any]) -> bool:
    for kind in ("rank_ic", "top_minus_bottom_spread"):
        row = inference["metrics"][kind]
        if (
            row.get("mean") is None
            or float(row["mean"]) <= 0
            or row.get("p_value_two_sided") is None
            or float(row["p_value_two_sided"]) >= 0.05
        ):
            return False
    return True


def finalize_t012_results(
    *,
    trial_ledger: dict[str, Any],
    decision_ledger: dict[str, Any],
    outcome_ledger: dict[str, Any],
    outcome_artifacts: list[dict[str, Any]],
    recorded_at_utc: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Append frozen 60/50 primary only after *every* prefix H5 is mature."""
    validate_t012_decision_ledger(decision_ledger)
    validate_t012_outcome_ledger(outcome_ledger)
    state = trial_state(trial_ledger, TRIAL)
    if state["registration"]["payload"].get("status") != (
        "FROZEN_BEFORE_FIRST_ELIGIBLE_PREOPEN_DECISION"
    ):
        raise AlphaContractError("T012 historical registration state altered")
    if _time(recorded_at_utc, label="result recording") <= _time(
        state["registration"]["recorded_at_utc"], label="registration"
    ):
        raise AlphaContractError("T012 result before trial registration")
    by_key = {}
    for artifact in outcome_artifacts:
        key = (artifact.get("decision_session"), artifact.get("horizon_sessions"))
        if key in by_key:
            raise AlphaContractError("T012 duplicate outcome artifact for one horizon")
        if artifact.get("artifact_sha256") != _hash_without(
            artifact, "artifact_sha256"
        ):
            raise AlphaContractError("T012 invalid cohort outcome artifact SHA")
        by_key[key] = artifact
    for row in outcome_ledger["outcomes"]:
        key = (row["decision_session"], row["horizon_sessions"])
        if key not in by_key or row["artifact_sha256"] != by_key[key][
            "artifact_sha256"
        ]:
            raise AlphaContractError("T012 missing/mismatched cohort outcome source")
    updated = copy.deepcopy(trial_ledger)
    emitted = []
    results = {
        row["payload"].get("result_kind"): row
        for row in state["results"]
    }
    primary = results.get("PRIMARY_5D")
    if primary is None:
        cohort = find_t012_primary_cohort(
            decision_ledger=decision_ledger,
            outcome_ledger=outcome_ledger,
        )
        if cohort is not None:
            artifacts = [by_key[(d, 5)] for d in cohort]
            if any(a["horizon_sessions"] != 5 for a in artifacts):
                raise AlphaContractError("T012 primary mixes holding horizons")
            inference = paired_report_difference_inference(
                _summary_report(artifacts, model="augmented"),
                _summary_report(artifacts, model="base"),
                max_lag=4,
            )
            supported = _supported(inference)
            payload = {
                "result_kind": "PRIMARY_5D",
                "status": (
                    "NOMINAL_SUPPORT_PENDING_MULTIPLICITY_AND_COST"
                    if supported else "PRIMARY_NOT_SUPPORTED"
                ),
                "cohort_rule": "SMALLEST_COMPLETE_CHRONOLOGICAL_PREFIX_60_50",
                "cohort_decision_sessions": cohort,
                "cohort_size": len(cohort),
                "valid_paired_rank_ic_sessions": sum(
                    bool(a["valid_paired_ic"]) for a in artifacts
                ),
                "outcome_artifact_sha256s": [
                    a["artifact_sha256"] for a in artifacts
                ],
                "paired_augmented_minus_base": inference,
                "historical_t005_outcomes_included": False,
                "live_capital_allowed": False,
                "retrospective_retraining": False,
                "multiple_testing_promotion_automatic": False,
            }
            updated = append_trial_event(
                updated,
                event_type="TRIAL_RESULT_RECORDED",
                trial_id=TRIAL,
                recorded_at_utc=recorded_at_utc,
                payload=payload,
            )
            emitted.append(updated["events"][-1])
            primary = updated["events"][-1]
    if primary is not None and results.get("SECONDARY_1D") is None:
        cohort = list(primary["payload"]["cohort_decision_sessions"])
        if all((d, 1) in by_key for d in cohort):
            artifacts = [by_key[(d, 1)] for d in cohort]
            inference = paired_report_difference_inference(
                _summary_report(artifacts, model="augmented"),
                _summary_report(artifacts, model="base"),
                max_lag=5,
            )
            payload = {
                "result_kind": "SECONDARY_1D",
                "status": "REPORTED_NON_RESCUING_SECONDARY",
                "rescues_failed_primary": False,
                "cohort_decision_sessions": cohort,
                "paired_augmented_minus_base": inference,
                "outcome_artifact_sha256s": [
                    a["artifact_sha256"] for a in artifacts
                ],
                "live_capital_allowed": False,
            }
            updated = append_trial_event(
                updated,
                event_type="TRIAL_RESULT_RECORDED",
                trial_id=TRIAL,
                recorded_at_utc=recorded_at_utc,
                payload=payload,
            )
            emitted.append(updated["events"][-1])
    return updated, emitted
