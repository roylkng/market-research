from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.h024_events import (
    PRIMARY_EVENT_STATUS,
    build_event_record,
    validate_event_ledger,
)
from marketlab.h024_outcomes import (
    PRIMARY_POPULATION_RETROACTIVE_GAP,
    current_primary_population_audit,
    entry_by_event,
    validate_entry_ledger,
    validate_outcome_ledger,
)
from marketlab.h024_prospective import (
    PROSPECTIVE_START_UTC,
    H024ProspectiveError,
    build_signal_record,
    evidence_by_source,
    source_by_id,
    source_first_seen,
    validate_calendar,
    validate_evidence_ledger,
    validate_scan_ledger,
    validate_signal_ledger,
    validate_source_ledger,
)
from marketlab.h024_sessions import (
    observed_horizon_exit_session,
    validate_session_ledger,
)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise H024ProspectiveError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise H024ProspectiveError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H024ProspectiveError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def verify(
    *,
    calendar: dict[str, Any],
    source_ledger: dict[str, Any],
    evidence_ledger: dict[str, Any],
    signal_ledger: dict[str, Any],
    scan_ledger: dict[str, Any],
    event_ledger: dict[str, Any],
    session_ledger: dict[str, Any],
    entry_ledger: dict[str, Any],
    outcome_ledger: dict[str, Any],
) -> dict[str, Any]:
    sessions = validate_calendar(calendar)
    session_by_date = {str(row["session_date"]): row for row in sessions}
    validate_source_ledger(source_ledger)
    validate_evidence_ledger(evidence_ledger)
    validate_signal_ledger(signal_ledger)
    validate_scan_ledger(scan_ledger)
    validate_event_ledger(event_ledger)
    validate_session_ledger(session_ledger)
    validate_entry_ledger(entry_ledger)
    validate_outcome_ledger(outcome_ledger)

    observed_by_date = {
        str(row["session_date"]): row for row in session_ledger["records"]
    }
    source_ids = {
        str(row["source"]["source_id"]) for row in source_ledger["records"]
    }
    evidence_ids = {
        str(row["evidence"]["source_id"]) for row in evidence_ledger["records"]
    }
    if not evidence_ids.issubset(source_ids):
        raise H024ProspectiveError("H024 evidence ledger references unknown source")

    source_by_app: dict[tuple[str, str], str] = {}
    for row in source_ledger["records"]:
        source = row["source"]
        key = (str(source["symbol"]), str(source["app_id"]))
        source_id = str(source["source_id"])
        prior = source_by_app.get(key)
        if prior is not None and prior != source_id:
            raise H024ProspectiveError(f"{key[0]}/{key[1]}: appId identity drift")
        source_by_app[key] = source_id

    signal_status_counts: Counter[str] = Counter()
    source_signal_counts: Counter[str] = Counter()
    grouped_entry_signals: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    qualifying_entry_signals: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for signal in signal_ledger["records"]:
        source_id = str(signal["source_id"])
        source = source_by_id(source_ledger, source_id)
        evidence = evidence_by_source(evidence_ledger, source_id)
        if source["submission_type"] != "Original":
            raise H024ProspectiveError(f"{signal['signal_id']}: revision created H024 signal")
        if evidence is None or evidence["status"] != "READY":
            raise H024ProspectiveError(
                f"{signal['signal_id']}: signal lacks READY source evidence"
            )
        if int(evidence["direct_market_purchase_count"]) < 1:
            raise H024ProspectiveError(
                f"{signal['signal_id']}: signal has no direct market purchase"
            )
        expected = build_signal_record(
            source_ledger=source_ledger,
            evidence_ledger=evidence_ledger,
            calendar=calendar,
            source_id=source_id,
            frozen_at_utc=str(signal["signal_frozen_at_utc"]),
        )
        if expected != signal:
            raise H024ProspectiveError(
                f"{signal['signal_id']}: signal does not reproduce from sealed source state"
            )
        if source_first_seen(source_ledger, source_id) != signal["source_first_seen_at_utc"]:
            raise H024ProspectiveError(f"{signal['signal_id']}: source first-seen mismatch")
        signal_status_counts[str(signal["status"])] += 1
        source_signal_counts[str(source["symbol"])] += 1
        key = (str(signal["symbol"]), str(signal["planned_entry_session"]))
        grouped_entry_signals[key].append(signal)
        if signal["status"] == "QUALIFYING":
            qualifying_entry_signals[key].append(signal)

    pre_entry_revision_blocked_signal_count = 0
    for signals in qualifying_entry_signals.values():
        for signal in signals:
            symbol = str(signal["symbol"])
            original_time = str(signal["exchange_disseminated_at_utc"])
            entry_open = str(signal["planned_entry_open_utc"])
            blockers = [
                row
                for row in source_ledger["records"]
                if row["source"]["symbol"] == symbol
                and row["source"]["submission_type"] == "Revision"
                and original_time < str(row["source"]["exchange_disseminated_at_utc"]) < entry_open
                and str(row["first_seen_at_utc"]) < entry_open
            ]
            if blockers:
                pre_entry_revision_blocked_signal_count += 1

    event_status_counts: Counter[str] = Counter()
    event_keys: set[tuple[str, str]] = set()
    event_by_id_map: dict[str, dict[str, Any]] = {}
    primary_population_audits: dict[str, dict[str, Any]] = {}
    population_excluded_count = 0
    population_provenance_drift_count = 0
    for event in event_ledger["records"]:
        key = (str(event["symbol"]), str(event["planned_entry_session"]))
        if key in event_keys:
            raise H024ProspectiveError(
                f"{key[0]}/{key[1]}: duplicate H024 symbol-entry event"
            )
        event_keys.add(key)
        event_id = str(event["event_id"])
        event_by_id_map[event_id] = event
        current_candidates = sorted(
            str(signal["source_id"]) for signal in qualifying_entry_signals.get(key, [])
        )
        if current_candidates != event["candidate_source_ids"]:
            raise H024ProspectiveError(
                f"{key[0]}/{key[1]}: sealed event candidate-source set drifted"
            )
        expected_event = build_event_record(
            source_ledger=source_ledger,
            evidence_ledger=evidence_ledger,
            signal_ledger=signal_ledger,
            symbol=key[0],
            planned_entry_session=key[1],
            investability=event["investability"],
            frozen_at_utc=str(event["event_frozen_at_utc"]),
        )
        if expected_event != event:
            raise H024ProspectiveError(
                f"{event_id}: event does not reproduce from sealed pre-entry state"
            )
        event_status_counts[
            str(event["status"])
            if event["status"] == PRIMARY_EVENT_STATUS
            else f"EXCLUDED:{event['exclusion_reason']}"
        ] += 1
        if event["status"] == PRIMARY_EVENT_STATUS:
            audit = current_primary_population_audit(event=event, source_ledger=source_ledger)
            primary_population_audits[event_id] = audit
            if audit["status"] == PRIMARY_POPULATION_RETROACTIVE_GAP:
                population_excluded_count += 1
            if audit["provenance_drift"]:
                population_provenance_drift_count += 1

    entry_status_counts: Counter[str] = Counter()
    for entry in entry_ledger["records"]:
        event_id = str(entry["event_id"])
        event = event_by_id_map.get(event_id)
        if event is None or event["status"] != PRIMARY_EVENT_STATUS:
            raise H024ProspectiveError(
                f"{entry['entry_observation_id']}: entry references non-primary/unknown event"
            )
        if (
            str(entry["symbol"]) != str(event["symbol"])
            or str(entry["entry_session"]) != str(event["planned_entry_session"])
            or str(entry["entry_isin"]) != str(event["investability"]["entry_isin"])
        ):
            raise H024ProspectiveError(
                f"{entry['entry_observation_id']}: entry identity disagrees with event"
            )
        calendar_session = session_by_date.get(str(entry["entry_session"]))
        if calendar_session is None:
            raise H024ProspectiveError(
                f"{entry['entry_observation_id']}: entry session not in reviewed calendar"
            )
        observed_session = observed_by_date.get(str(entry["entry_session"]))
        if observed_session is None:
            raise H024ProspectiveError(
                f"{entry['entry_observation_id']}: entry session lacks official observed-session evidence"
            )
        entry_observed = _timestamp(entry["observed_at_utc"], "entry.observed_at_utc")
        if entry_observed < _timestamp(
            calendar_session["close_timestamp_utc"], "calendar.close_timestamp_utc"
        ):
            raise H024ProspectiveError(
                f"{entry['entry_observation_id']}: entry evidence frozen before session close"
            )
        if entry_observed < _timestamp(
            observed_session["observed_at_utc"], "session.observed_at_utc"
        ):
            raise H024ProspectiveError(
                f"{entry['entry_observation_id']}: entry evidence predates observed-session evidence"
            )
        if entry["benchmark_bar"] != observed_session["benchmark_bar"]:
            raise H024ProspectiveError(
                f"{entry['entry_observation_id']}: entry benchmark differs from session ledger"
            )
        entry_status_counts[
            str(entry["status"])
            if entry["status"] == "READY"
            else f"BLOCKED:{entry['block_reason']}"
        ] += 1

    outcome_status_counts: Counter[str] = Counter()
    outcome_horizon_counts: Counter[int] = Counter()
    primary_complete_horizon_counts: Counter[int] = Counter()
    diagnostic_only_complete_horizon_counts: Counter[int] = Counter()
    for outcome in outcome_ledger["records"]:
        event_id = str(outcome["event_id"])
        event = event_by_id_map.get(event_id)
        if event is None or event["status"] != PRIMARY_EVENT_STATUS:
            raise H024ProspectiveError(
                f"{outcome['outcome_id']}: outcome references non-primary/unknown event"
            )
        entry = entry_by_event(entry_ledger, event_id)
        if entry is None:
            raise H024ProspectiveError(f"{outcome['outcome_id']}: outcome lacks entry observation")
        if (
            outcome["entry_observation_id"] != entry["entry_observation_id"]
            or outcome["entry_record_sha256"] != entry["entry_record_sha256"]
        ):
            raise H024ProspectiveError(
                f"{outcome['outcome_id']}: outcome entry reference drifted"
            )
        horizon = int(outcome["horizon_sessions"])
        expected_exit = observed_horizon_exit_session(
            session_ledger,
            entry_session=str(event["planned_entry_session"]),
            horizon=horizon,
        )
        if expected_exit is None or str(expected_exit["session_date"]) != str(
            outcome["exit_session"]
        ):
            raise H024ProspectiveError(
                f"{outcome['outcome_id']}: outcome exit disagrees with observed-session sequence"
            )
        if outcome["exit_benchmark_bar"] != expected_exit["benchmark_bar"]:
            raise H024ProspectiveError(
                f"{outcome['outcome_id']}: outcome benchmark differs from session ledger"
            )
        if _timestamp(outcome["observed_at_utc"], "outcome.observed_at_utc") < _timestamp(
            expected_exit["observed_at_utc"], "session.observed_at_utc"
        ):
            raise H024ProspectiveError(
                f"{outcome['outcome_id']}: outcome predates exit-session observation"
            )
        outcome_status_counts[
            str(outcome["status"])
            if outcome["status"] == "COMPLETE"
            else f"BLOCKED:{outcome['block_reason']}"
        ] += 1
        outcome_horizon_counts[horizon] += 1
        if outcome["status"] == "COMPLETE":
            population = primary_population_audits[event_id]
            if population["status"] == PRIMARY_POPULATION_RETROACTIVE_GAP:
                diagnostic_only_complete_horizon_counts[horizon] += 1
            else:
                primary_complete_horizon_counts[horizon] += 1

    for scan in scan_ledger["records"]:
        for source_id in scan["source_ids"]:
            if source_id not in source_ids:
                raise H024ProspectiveError(
                    f"{scan['scan_id']}: scan references unknown H024 source {source_id}"
                )

    preboundary_source_count = sum(
        str(row["source"]["exchange_disseminated_at_utc"])
        < PROSPECTIVE_START_UTC.isoformat().replace("+00:00", "Z")
        for row in source_ledger["records"]
    )
    return {
        "hypothesis_id": "H024",
        "prospective_start_utc": PROSPECTIVE_START_UTC.isoformat().replace("+00:00", "Z"),
        "source_record_count": source_ledger["record_count"],
        "evidence_record_count": evidence_ledger["record_count"],
        "signal_record_count": signal_ledger["record_count"],
        "scan_record_count": scan_ledger["record_count"],
        "event_record_count": event_ledger["record_count"],
        "observed_session_record_count": session_ledger["record_count"],
        "entry_record_count": entry_ledger["record_count"],
        "outcome_record_count": outcome_ledger["record_count"],
        "signal_status_counts": dict(sorted(signal_status_counts.items())),
        "event_status_counts": dict(sorted(event_status_counts.items())),
        "entry_status_counts": dict(sorted(entry_status_counts.items())),
        "outcome_status_counts": dict(sorted(outcome_status_counts.items())),
        "outcome_horizon_counts": {
            str(key): value for key, value in sorted(outcome_horizon_counts.items())
        },
        "primary_complete_horizon_counts": {
            str(key): value for key, value in sorted(primary_complete_horizon_counts.items())
        },
        "diagnostic_only_complete_horizon_counts": {
            str(key): value
            for key, value in sorted(diagnostic_only_complete_horizon_counts.items())
        },
        "signal_symbol_count": len(source_signal_counts),
        "symbol_entry_group_count": len(grouped_entry_signals),
        "qualifying_symbol_entry_group_count": len(qualifying_entry_signals),
        "sealed_symbol_entry_group_count": len(event_keys),
        "pending_symbol_entry_group_count": len(set(qualifying_entry_signals) - event_keys),
        "pre_entry_revision_blocked_signal_count": pre_entry_revision_blocked_signal_count,
        "current_primary_population_excluded_event_count": population_excluded_count,
        "current_primary_population_provenance_drift_event_count": (
            population_provenance_drift_count
        ),
        "preboundary_source_count": preboundary_source_count,
        "source_ledger_sha256": source_ledger["ledger_sha256"],
        "evidence_ledger_sha256": evidence_ledger["ledger_sha256"],
        "signal_ledger_sha256": signal_ledger["ledger_sha256"],
        "scan_ledger_sha256": scan_ledger["ledger_sha256"],
        "event_ledger_sha256": event_ledger["ledger_sha256"],
        "session_ledger_sha256": session_ledger["ledger_sha256"],
        "entry_ledger_sha256": entry_ledger["ledger_sha256"],
        "outcome_ledger_sha256": outcome_ledger["ledger_sha256"],
        "outcome_data_attached_to_event_ledger": False,
        "live_capital_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify H024 prospective state offline")
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args()
    result = verify(
        calendar=_load(args.calendar),
        source_ledger=_load(args.state_dir / "source-ledger.json"),
        evidence_ledger=_load(args.state_dir / "evidence-ledger.json"),
        signal_ledger=_load(args.state_dir / "signal-ledger.json"),
        scan_ledger=_load(args.state_dir / "scan-ledger.json"),
        event_ledger=_load(args.state_dir / "event-ledger.json"),
        session_ledger=_load(args.state_dir / "session-ledger.json"),
        entry_ledger=_load(args.state_dir / "entry-ledger.json"),
        outcome_ledger=_load(args.state_dir / "outcome-ledger.json"),
    )
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
