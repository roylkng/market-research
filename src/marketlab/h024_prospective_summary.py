from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.h024_events import PRIMARY_EVENT_STATUS, validate_event_ledger
from marketlab.h024_historical import (
    EXECUTION_RULE_ID,
    HORIZONS,
    HYPOTHESIS_ID,
    canonical_hash,
    summarize_outcomes,
)
from marketlab.h024_outcomes import (
    OUTCOME_COMPLETE,
    PRIMARY_POPULATION_ELIGIBLE,
    current_primary_population_audit,
    validate_outcome_ledger,
)
from marketlab.h024_prospective import (
    H024ProspectiveError,
    evidence_by_source,
    source_by_id,
    validate_evidence_ledger,
    validate_source_ledger,
)
from marketlab.h024_sessions import (
    observed_horizon_exit_session,
    validate_session_ledger,
)

IST = ZoneInfo("Asia/Kolkata")
EVIDENCE_CLASS = "PROSPECTIVE_VALIDATION"


def _timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise H024ProspectiveError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise H024ProspectiveError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H024ProspectiveError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _outcome_index(outcome_ledger: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    validate_outcome_ledger(outcome_ledger)
    result: dict[tuple[str, int], dict[str, Any]] = {}
    for row in outcome_ledger["records"]:
        key = (str(row["event_id"]), int(row["horizon_sessions"]))
        if key in result:
            raise H024ProspectiveError(f"duplicate H024 prospective outcome: {key}")
        result[key] = dict(row)
    return result


def _session_index(session_ledger: dict[str, Any]) -> dict[str, int]:
    validate_session_ledger(session_ledger)
    return {
        str(row["session_date"]): index
        for index, row in enumerate(session_ledger["records"])
    }


def _current_event_descriptives(
    *,
    event: dict[str, Any],
    population_audit: dict[str, Any],
    source_ledger: dict[str, Any],
    evidence_ledger: dict[str, Any],
) -> tuple[str, float]:
    surviving = [str(value) for value in population_audit["surviving_candidate_source_ids"]]
    if not surviving:
        raise H024ProspectiveError(
            f"{event['event_id']}: current primary event has no surviving source"
        )
    dissemination_times: list[datetime] = []
    purchase_value = 0.0
    for source_id in surviving:
        source = source_by_id(source_ledger, source_id)
        evidence = evidence_by_source(evidence_ledger, source_id)
        if evidence is None or evidence.get("status") != "READY":
            raise H024ProspectiveError(
                f"{event['event_id']}: surviving source lacks READY evidence: {source_id}"
            )
        if int(evidence.get("direct_market_purchase_count") or 0) < 1:
            raise H024ProspectiveError(
                f"{event['event_id']}: surviving source has no qualifying purchase: {source_id}"
            )
        dissemination_times.append(
            _timestamp(
                source["exchange_disseminated_at_utc"],
                field="source.exchange_disseminated_at_utc",
            )
        )
        purchase_value += float(evidence["direct_market_purchase_value_inr"])
    if purchase_value <= 0.0:
        raise H024ProspectiveError(
            f"{event['event_id']}: current prospective purchase value is not positive"
        )
    first_local = min(dissemination_times).astimezone(IST)
    publication_month = f"{first_local.year:04d}-{first_local.month:02d}"
    return publication_month, purchase_value


def _horizon_payload(
    *,
    event_id: str,
    entry_session: str,
    horizon: int,
    session_ledger: dict[str, Any],
    outcomes: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    exit_observation = observed_horizon_exit_session(
        session_ledger,
        entry_session=entry_session,
        horizon=horizon,
    )
    outcome = outcomes.get((event_id, horizon))
    if exit_observation is None:
        if outcome is not None:
            raise H024ProspectiveError(
                f"{event_id}/H{horizon}: outcome exists before observed maturity"
            )
        return {"status": "NOT_MATURE"}

    exit_session = str(exit_observation["session_date"])
    if outcome is None:
        return {
            "status": "MATURE_OUTCOME_PENDING",
            "exit_session": {"session_date": exit_session},
        }
    if str(outcome["exit_session"]) != exit_session:
        raise H024ProspectiveError(
            f"{event_id}/H{horizon}: outcome exit disagrees with observed maturity"
        )
    if outcome["status"] == OUTCOME_COMPLETE:
        return {
            "status": "COMPLETE",
            "exit_session": {"session_date": exit_session},
            "gross_excess_pp": float(outcome["gross_excess_pp"]),
            "cost_adjusted_excess_pp": float(outcome["cost_adjusted_excess_pp"]),
            "beat_benchmark": bool(outcome["beat_benchmark"]),
        }
    return {
        "status": f"BLOCKED:{outcome['block_reason']}",
        "exit_session": {"session_date": exit_session},
    }


def build_prospective_evaluation_report(
    *,
    source_ledger: dict[str, Any],
    evidence_ledger: dict[str, Any],
    event_ledger: dict[str, Any],
    session_ledger: dict[str, Any],
    outcome_ledger: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_source_ledger(source_ledger)
    validate_evidence_ledger(evidence_ledger)
    validate_event_ledger(event_ledger)
    validate_session_ledger(session_ledger)
    validate_outcome_ledger(outcome_ledger)

    outcomes = _outcome_index(outcome_ledger)
    session_indices = _session_index(session_ledger)
    records: list[dict[str, Any]] = []
    diagnostic_counts = {
        "sealed_primary_event_count": 0,
        "current_primary_event_count": 0,
        "retroactive_preentry_revision_excluded_event_count": 0,
        "provenance_drift_event_count": 0,
    }

    for event in event_ledger["records"]:
        if event["status"] != PRIMARY_EVENT_STATUS:
            continue
        diagnostic_counts["sealed_primary_event_count"] += 1
        audit = current_primary_population_audit(event=event, source_ledger=source_ledger)
        if audit["provenance_drift"]:
            diagnostic_counts["provenance_drift_event_count"] += 1
        if audit["status"] != PRIMARY_POPULATION_ELIGIBLE:
            diagnostic_counts["retroactive_preentry_revision_excluded_event_count"] += 1
            continue
        diagnostic_counts["current_primary_event_count"] += 1

        event_id = str(event["event_id"])
        entry_session = str(event["planned_entry_session"])
        publication_month, purchase_value = _current_event_descriptives(
            event=event,
            population_audit=audit,
            source_ledger=source_ledger,
            evidence_ledger=evidence_ledger,
        )
        row = {
            "event_id": event_id,
            "symbol": str(event["symbol"]),
            "entry_session_date": entry_session,
            "entry_index": session_indices.get(entry_session, -1),
            "publication_month": publication_month,
            "purchase_value_inr": purchase_value,
            "horizons": {
                str(horizon): _horizon_payload(
                    event_id=event_id,
                    entry_session=entry_session,
                    horizon=horizon,
                    session_ledger=session_ledger,
                    outcomes=outcomes,
                )
                for horizon in HORIZONS
            },
        }
        records.append(row)

    records.sort(
        key=lambda row: (
            str(row["entry_session_date"]),
            str(row["symbol"]),
            str(row["event_id"]),
        )
    )
    latest_session = (
        str(session_ledger["records"][-1]["session_date"])
        if session_ledger["records"]
        else None
    )
    report = {
        "schema_version": 1,
        "hypothesis_id": HYPOTHESIS_ID,
        "execution_rule_id": EXECUTION_RULE_ID,
        "evidence_class": EVIDENCE_CLASS,
        "market_data_cutoff_session": latest_session,
        "event_panel_sha256": event_ledger["ledger_sha256"],
        "event_count": len(records),
        "records": records,
    }
    report["report_sha256"] = canonical_hash(report)
    diagnostics = {
        **diagnostic_counts,
        "source_ledger_sha256": source_ledger["ledger_sha256"],
        "evidence_ledger_sha256": evidence_ledger["ledger_sha256"],
        "event_ledger_sha256": event_ledger["ledger_sha256"],
        "session_ledger_sha256": session_ledger["ledger_sha256"],
        "outcome_ledger_sha256": outcome_ledger["ledger_sha256"],
    }
    return report, diagnostics


def build_prospective_summary(
    *,
    source_ledger: dict[str, Any],
    evidence_ledger: dict[str, Any],
    event_ledger: dict[str, Any],
    session_ledger: dict[str, Any],
    outcome_ledger: dict[str, Any],
) -> dict[str, Any]:
    report, diagnostics = build_prospective_evaluation_report(
        source_ledger=source_ledger,
        evidence_ledger=evidence_ledger,
        event_ledger=event_ledger,
        session_ledger=session_ledger,
        outcome_ledger=outcome_ledger,
    )
    frozen_summary = summarize_outcomes(report)
    summary = {
        "schema_version": 1,
        "hypothesis_id": HYPOTHESIS_ID,
        "execution_rule_id": EXECUTION_RULE_ID,
        "evidence_class": EVIDENCE_CLASS,
        "primary_horizon_sessions": frozen_summary["primary_horizon_sessions"],
        "primary_classification": frozen_summary["primary_classification"],
        "market_data_cutoff_session": frozen_summary["market_data_cutoff_session"],
        "current_primary_event_count": report["event_count"],
        "diagnostics": diagnostics,
        "horizons": frozen_summary["horizons"],
        "evaluation_report_sha256": report["report_sha256"],
        "frozen_evaluator_summary_sha256": frozen_summary["summary_sha256"],
        "live_capital_allowed": False,
    }
    summary["summary_sha256"] = canonical_hash(summary)
    return summary
