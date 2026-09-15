from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

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
) -> dict[str, Any]:
    validate_calendar(calendar)
    validate_source_ledger(source_ledger)
    validate_evidence_ledger(evidence_ledger)
    validate_signal_ledger(signal_ledger)
    validate_scan_ledger(scan_ledger)

    source_ids = {str(row["source"]["source_id"]) for row in source_ledger["records"]}
    evidence_ids = {str(row["evidence"]["source_id"]) for row in evidence_ledger["records"]}
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
    for signal in signal_ledger["records"]:
        source_id = str(signal["source_id"])
        source = source_by_id(source_ledger, source_id)
        evidence = evidence_by_source(evidence_ledger, source_id)
        if source["submission_type"] != "Original":
            raise H024ProspectiveError(f"{signal['signal_id']}: revision created H024 signal")
        if evidence is None or evidence["status"] != "READY":
            raise H024ProspectiveError(f"{signal['signal_id']}: signal lacks READY source evidence")
        if int(evidence["direct_market_purchase_count"]) < 1:
            raise H024ProspectiveError(f"{signal['signal_id']}: signal has no direct market purchase")
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
            raise H024ProspectiveError(
                f"{signal['signal_id']}: source first-seen mismatch"
            )
        signal_status_counts[str(signal["status"])] += 1
        source_signal_counts[str(source["symbol"])] += 1
        grouped_entry_signals[(str(signal["symbol"]), str(signal["planned_entry_session"]))].append(
            signal
        )

    pre_entry_revision_blocked_groups = 0
    retroactive_revision_gap_groups = 0
    for (symbol, entry_session), signals in grouped_entry_signals.items():
        entry_open = min(str(signal["planned_entry_open_utc"]) for signal in signals)
        earliest_exchange = min(
            str(signal["exchange_disseminated_at_utc"]) for signal in signals
        )
        blockers = []
        retroactive = []
        for row in source_ledger["records"]:
            source = row["source"]
            if source["symbol"] != symbol or source["submission_type"] != "Revision":
                continue
            disseminated = str(source["exchange_disseminated_at_utc"])
            if not (earliest_exchange < disseminated < entry_open):
                continue
            first_seen = str(row["first_seen_at_utc"])
            if first_seen < entry_open:
                blockers.append(str(source["source_id"]))
            else:
                retroactive.append(str(source["source_id"]))
        if blockers:
            pre_entry_revision_blocked_groups += 1
        if retroactive:
            retroactive_revision_gap_groups += 1
        if blockers and retroactive:
            raise H024ProspectiveError(
                f"{symbol}/{entry_session}: revision appears both timely and retroactive"
            )

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
        "signal_status_counts": dict(sorted(signal_status_counts.items())),
        "signal_symbol_count": len(source_signal_counts),
        "symbol_entry_group_count": len(grouped_entry_signals),
        "pre_entry_revision_blocked_group_count": pre_entry_revision_blocked_groups,
        "retroactive_revision_gap_group_count": retroactive_revision_gap_groups,
        "preboundary_source_count": preboundary_source_count,
        "source_ledger_sha256": source_ledger["ledger_sha256"],
        "evidence_ledger_sha256": evidence_ledger["ledger_sha256"],
        "signal_ledger_sha256": signal_ledger["ledger_sha256"],
        "scan_ledger_sha256": scan_ledger["ledger_sha256"],
        "outcome_data_attached": False,
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
    )
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
