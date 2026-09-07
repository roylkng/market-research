from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from run_h002_historical_phase_b import (
    IST,
    OutcomeSources,
    _execute_record,
    _market_member,
    _record_schedule,
)

from marketlab.execution import TradingCalendar, TradingSession
from marketlab.h002_historical_outcomes import load_phase_a_manifest
from marketlab.nse import NSEClient
from marketlab.universe import UniverseMember, load_universe_snapshot


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _pending_outcome(
    record: dict,
    *,
    member: UniverseMember,
    publication: datetime,
    entry_day: date,
    exit_day: date,
    started_at: datetime,
) -> dict:
    return {
        "schema_version": 1,
        "symbol": member.symbol,
        "isin": member.isin,
        "quarter_id": record.get("quarter_id"),
        "target_period_end": record.get("target_period_end"),
        "phase_a_signal_event_id": record.get("signal", {}).get("event_id"),
        "signal_bucket": record.get("signal", {}).get("bucket"),
        "signal_ue": record.get("signal", {}).get("ue"),
        "exchange_published_at_utc": _iso(publication),
        "entry_session_date": entry_day.isoformat(),
        "exit_session_date": exit_day.isoformat(),
        "status": "PENDING",
        "reason": "exit_not_matured_before_reconstruction_date",
        "evaluation_as_of_utc": _iso(started_at),
        "live_order_created": False,
    }


def run(args: argparse.Namespace) -> dict:
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        raise ValueError("shard_index must be within [0, shard_count)")
    started_at = datetime.now(UTC)
    as_of_day = started_at.astimezone(IST).date()
    phase_a = load_phase_a_manifest(
        args.phase_a,
        expected_sha256=args.expected_phase_a_sha256,
    )
    universe = load_universe_snapshot(args.universe)
    if (
        universe.cohort_id != phase_a.get("cohort_id")
        or universe.sha256 != phase_a.get("cohort_sha256")
    ):
        raise ValueError("phase-A manifest and universe are not the same frozen cohort")

    calendar_document = phase_a.get("calendar_snapshot")
    if not isinstance(calendar_document, dict):
        raise TypeError("phase-A manifest is missing its frozen calendar")
    sessions = [TradingSession(**item) for item in calendar_document.get("sessions", [])]
    calendar = TradingCalendar(sessions, version=str(calendar_document.get("version") or ""))
    members = {member.symbol.upper(): member for member in universe.members}

    eligible = [record for record in phase_a.get("records", []) if record.get("status") == "SIGNAL"]
    symbols = sorted({str(record.get("symbol") or "").upper() for record in eligible})
    shard_symbols = {
        symbol
        for index, symbol in enumerate(symbols)
        if index % args.shard_count == args.shard_index
    }
    shard_records = [
        record
        for record in eligible
        if str(record.get("symbol") or "").upper() in shard_symbols
    ]

    schedules: dict[tuple[str, str], tuple[datetime, date, date]] = {}
    action_windows: dict[str, tuple[date, date]] = {}
    for record in shard_records:
        member = _market_member(record, members)
        publication, entry_day, exit_day = _record_schedule(record, calendar)
        key = (member.symbol.upper(), str(record.get("quarter_id")))
        schedules[key] = (publication, entry_day, exit_day)

        # Outcomes whose exit is today or later are deliberately censored.  We do
        # not query future/same-day archives and, more importantly, do not audit
        # corporate actions through a horizon that has not fully elapsed yet.
        if exit_day >= as_of_day:
            continue

        publication_day = publication.astimezone(IST).date()
        current = action_windows.get(member.symbol.upper())
        if current is None:
            action_windows[member.symbol.upper()] = (publication_day, exit_day)
        else:
            action_windows[member.symbol.upper()] = (
                min(current[0], publication_day),
                max(current[1], exit_day),
            )

    store_root = Path(args.store)
    store_root.mkdir(parents=True, exist_ok=True)
    client = NSEClient(timeout=args.timeout, attempts=args.attempts)
    sources = OutcomeSources(
        client=client,
        root=store_root,
        captured_at=started_at,
        attempts=args.attempts,
        sleep_seconds=args.sleep,
    )
    for symbol, (start, end) in sorted(action_windows.items()):
        sources.actions_for(members[symbol], from_date=start, to_date=end)

    outcomes: list[dict] = []
    for index, record in enumerate(shard_records, start=1):
        member = _market_member(record, members)
        key = (member.symbol.upper(), str(record.get("quarter_id")))
        publication, entry_day, exit_day = schedules[key]

        if exit_day >= as_of_day:
            outcomes.append(
                _pending_outcome(
                    record,
                    member=member,
                    publication=publication,
                    entry_day=entry_day,
                    exit_day=exit_day,
                    started_at=started_at,
                )
            )
            continue

        action_payload, action_raw, action_evidence = sources.actions[member.symbol.upper()]
        try:
            outcome = _execute_record(
                record,
                member=member,
                calendar=calendar,
                sources=sources,
                publication=publication,
                entry_day=entry_day,
                exit_day=exit_day,
                action_payload=action_payload,
                action_raw=action_raw,
                action_evidence=action_evidence,
            )
        except (RuntimeError, ValueError) as exc:
            outcome = {
                "schema_version": 1,
                "symbol": member.symbol,
                "isin": member.isin,
                "quarter_id": record.get("quarter_id"),
                "target_period_end": record.get("target_period_end"),
                "signal_bucket": record.get("signal", {}).get("bucket"),
                "signal_ue": record.get("signal", {}).get("ue"),
                "status": "ERROR",
                "reason": f"{type(exc).__name__}: {exc}",
            }
        outcomes.append(outcome)
        if index % 10 == 0:
            print(f"shard {args.shard_index}: {index}/{len(shard_records)}", flush=True)

    document = {
        "schema_version": 1,
        "phase": "B_OUTCOME_RECONSTRUCTION_SHARD",
        "phase_a_manifest_sha256": args.expected_phase_a_sha256,
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "symbols": sorted(shard_symbols),
        "eligible_record_count": len(shard_records),
        "generated_at_utc": _iso(started_at),
        "reconstruction_local_date": as_of_day.isoformat(),
        "records": outcomes,
        "evidence": {
            "calendar_version": calendar.version,
            "calendar_sha256": calendar.sha256,
            "udiff_archive_count": len(sources.udiff),
            "index_snapshot_count": len(sources.indices),
            "corporate_action_payload_count": len(sources.actions),
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"shard": args.shard_index, "records": len(outcomes)}, sort_keys=True))
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstruct one shard of frozen H002-HR001 outcomes")
    parser.add_argument(
        "--phase-a",
        default="research/historical/h002/H002-HR001/phase-a/fixed-u001-transport-signals.json",
    )
    parser.add_argument("--expected-phase-a-sha256", required=True)
    parser.add_argument(
        "--universe",
        default="research/prospective/universes/FY27-Q2-2026-09-06.json",
    )
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, default=4)
    parser.add_argument("--store", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=0.05)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
