from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from marketlab.h024_events import (
    build_event_record,
    validate_event_ledger,
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


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def verify(
    *,
    calendar: dict[str, Any],
    source_ledger: dict[str, Any],
    evidence_ledger: dict[str, Any],
    signal_ledger: dict[str, Any],
    scan_ledger: dict[str, Any],
    event_ledger: dict[str, Any],
) -> dict[str, Any]:
    validate_calendar(calendar)
    validate_source_ledger(source_ledger)
    validate_evidence_ledger(evidence_ledger)
    validate_signal_ledger(signal_ledger)
    validate_scan_ledger(scan_ledger)
    validate_event_ledger(event_ledger)

    source_ids = {
        str(row["source"]["source_id"]) for row in source_ledger["records"]
    }
    evidence_ids = {
        str(row["evidence"]["source_id"]) for row in evidence_ledger["records"]
    }
    if not evidence_ids.issubset(source_ids):
        raise H024ProspectiveError(
            "H024 evidence ledger references unknown source"
        )

    source_by_app: dict[tuple[str, str], str] = {}
    for row in source_ledger["records"]:
        source = row["source"]
        key = (str(source["symbol"]), str(source["app_id"]))
        source_id = str(source["source_id"])
        prior = source_by_app.get(key)
        if prior is not None and prior != source_id:
            raise H024ProspectiveError(
                f"{key[0]}/{key[1]}: appId identity drift"
            )
        source_by_app[key] = source_id

    signal_status_counts: Counter[str] = Counter()
    source_signal_counts: Counter[str] = Counter()
    grouped_entry_signals: dict[
        tuple[str, str], list[dict[str, Any]]
    ] = defaultdict(list)
    qualifying_entry_signals: dict[
        tuple[str, str], list[dict[str, Any]]
    ] = defaultdict(list)
    for signal in signal_ledger["records"]:
        source_id = str(signal["source_id"])
        source = source_by_id(source_ledger, source_id)
        evidence = evidence_by_source(evidence_ledger, source_id)
        if source["submission_type"] != "Original":
            raise H024ProspectiveError(
                f"{signal['signal_id']}: revision created H024 signal"
            )
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
                f"{signal['signal_id']}: signal does not reproduce "
                "from sealed source state"
            )
        if (
            source_first_seen(source_ledger, source_id)
            != signal["source_first_seen_at_utc"]
        ):
            raise H024ProspectiveError(
                f"{signal['signal_id']}: source first-seen mismatch"
            )
        signal_status_counts[str(signal["status"])] += 1
        source_signal_counts[str(source["symbol"])] += 1
        key = (
            str(signal["symbol"]),
            str(signal["planned_entry_session"]),
        )
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
                and original_time
                < str(row["source"]["exchange_disseminated_at_utc"])
                < entry_open
                and str(row["first_seen_at_utc"]) < entry_open
            ]
            if blockers:
                pre_entry_revision_blocked_signal_count += 1

    event_status_counts: Counter[str] = Counter()
    event_keys: set[tuple[str, str]] = set()
    retroactive_preentry_revision_gap_events = 0
    for event in event_ledger["records"]:
        key = (
            str(event["symbol"]),
            str(event["planned_entry_session"]),
        )
        if key in event_keys:
            raise H024ProspectiveError(
                f"{key[0]}/{key[1]}: duplicate H024 symbol-entry event"
            )
        event_keys.add(key)
        current_candidates = sorted(
            str(signal["source_id"])
            for signal in qualifying_entry_signals.get(key, [])
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
                f"{event['event_id']}: event does not reproduce "
                "from sealed pre-entry state"
            )
        event_status_counts[
            (
                str(event["status"])
                if event["status"] == "PRIMARY_ELIGIBLE"
                else f"EXCLUDED:{event['exclusion_reason']}"
            )
        ] += 1

        event_frozen = str(event["event_frozen_at_utc"])
        entry_open = str(event["planned_entry_open_utc"])
        candidate_times = {
            str(signal["source_id"]): str(
                signal["exchange_disseminated_at_utc"]
            )
            for signal in qualifying_entry_signals.get(key, [])
        }
        retroactive_gap = False
        for row in source_ledger["records"]:
            source = row["source"]
            if (
                source["symbol"] != key[0]
                or source["submission_type"] != "Revision"
            ):
                continue
            revision_time = str(source["exchange_disseminated_at_utc"])
            revision_seen = str(row["first_seen_at_utc"])
            if not (
                event_frozen < revision_seen
                and revision_time < entry_open
            ):
                continue
            if any(
                original_time < revision_time
                for original_time in candidate_times.values()
            ):
                retroactive_gap = True
                break
        if retroactive_gap:
            retroactive_preentry_revision_gap_events += 1

    for scan in scan_ledger["records"]:
        for source_id in scan["source_ids"]:
            if source_id not in source_ids:
                raise H024ProspectiveError(
                    f"{scan['scan_id']}: scan references unknown "
                    f"H024 source {source_id}"
                )

    preboundary_source_count = sum(
        str(row["source"]["exchange_disseminated_at_utc"])
        < PROSPECTIVE_START_UTC.isoformat().replace("+00:00", "Z")
        for row in source_ledger["records"]
    )
    return {
        "hypothesis_id": "H024",
        "prospective_start_utc": (
            PROSPECTIVE_START_UTC.isoformat().replace("+00:00", "Z")
        ),
        "source_record_count": source_ledger["record_count"],
        "evidence_record_count": evidence_ledger["record_count"],
        "signal_record_count": signal_ledger["record_count"],
        "scan_record_count": scan_ledger["record_count"],
        "event_record_count": event_ledger["record_count"],
        "signal_status_counts": dict(sorted(signal_status_counts.items())),
        "event_status_counts": dict(sorted(event_status_counts.items())),
        "signal_symbol_count": len(source_signal_counts),
        "symbol_entry_group_count": len(grouped_entry_signals),
        "qualifying_symbol_entry_group_count": len(qualifying_entry_signals),
        "sealed_symbol_entry_group_count": len(event_keys),
        "pending_symbol_entry_group_count": len(
            set(qualifying_entry_signals) - event_keys
        ),
        "pre_entry_revision_blocked_signal_count": (
            pre_entry_revision_blocked_signal_count
        ),
        "retroactive_preentry_revision_gap_event_count": (
            retroactive_preentry_revision_gap_events
        ),
        "preboundary_source_count": preboundary_source_count,
        "source_ledger_sha256": source_ledger["ledger_sha256"],
        "evidence_ledger_sha256": evidence_ledger["ledger_sha256"],
        "signal_ledger_sha256": signal_ledger["ledger_sha256"],
        "scan_ledger_sha256": scan_ledger["ledger_sha256"],
        "event_ledger_sha256": event_ledger["ledger_sha256"],
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify H024 prospective state offline"
    )
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
    )
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
