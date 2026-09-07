from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import run_h002_historical_v2_phase_b_shard as base
import run_h002_historical_v2_phase_b_shard_r2 as resolver
import yaml

from marketlab.h002_historical_identity import historical_symbol_variants
from marketlab.h002_historical_pit_outcomes import load_phase_a_manifest_pit
from marketlab.h002_historical_v2_outcomes import load_phase_a_manifest_v2
from marketlab.nse import NSEClient
from marketlab.universe import UniverseMember

EXPERIMENT_ID = "H002-HR003"
RESOLVER_VERSION = "H002-HR003-PHASE-B-PIT-NIFTY200-R1"
HR002_FREEZE_PATH = Path("registry/h002_hr002_phase_a_freeze.yaml")


class PitPhaseBError(RuntimeError):
    pass


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _calendar(client: NSEClient) -> tuple[Any, dict[str, Any]]:
    """Rebuild the exact calendar used by historical Phase A from frozen dependencies."""

    freeze = yaml.safe_load(HR002_FREEZE_PATH.read_text(encoding="utf-8"))
    if freeze.get("freeze_id") != "H002-HR002-PHASE-A-FREEZE-V1":
        raise PitPhaseBError("unexpected HR002 calendar dependency freeze")
    phase_a_path = str(freeze.get("phase_a_manifest_path") or "")
    phase_a_sha = str(freeze.get("phase_a_manifest_sha256") or "")
    hr002_phase_a = load_phase_a_manifest_v2(
        phase_a_path,
        expected_sha256=phase_a_sha,
    )
    calendar, evidence = base._calendar_from_frozen_phase_a(hr002_phase_a, client=client)
    evidence = dict(evidence)
    evidence["calendar_dependency_phase_a_sha256"] = phase_a_sha
    evidence["calendar_dependency_freeze"] = str(HR002_FREEZE_PATH)
    return calendar, evidence


def _member_from_record(record: dict[str, Any]) -> UniverseMember:
    symbol = str(record.get("symbol") or "").strip().upper()
    if not symbol:
        raise PitPhaseBError("SIGNAL record has no calculation symbol")
    target_event = record.get("target_event")
    if not isinstance(target_event, dict):
        raise PitPhaseBError(f"{symbol} SIGNAL record has no target event")
    eligibility = record.get("point_in_time_eligibility")
    if not isinstance(eligibility, dict):
        raise PitPhaseBError(f"{symbol} SIGNAL record has no point-in-time eligibility")
    rank = int(eligibility.get("deterministic_membership_order", 0))
    if rank <= 0:
        raise PitPhaseBError(f"{symbol} has invalid point-in-time membership rank")
    isin = str(target_event.get("isin") or record.get("isin") or "").strip().upper()
    company_name = str(
        target_event.get("company_name") or record.get("company_name") or symbol
    ).strip()
    return UniverseMember(
        rank=rank,
        source_rank=rank,
        symbol=symbol,
        isin=isin,
        ffmc=0.0,
        company_name=company_name,
        constituent_industry="POINT_IN_TIME_NON_FINANCIAL_NIFTY_200",
        series="EQ",
    )


def _cluster_symbol(symbol: str) -> str:
    """Cluster only explicitly registered identity-preserving ticker aliases."""

    return min(historical_symbol_variants(symbol))


def _record_key(record: dict[str, Any]) -> tuple[str, str]:
    eligibility = record.get("point_in_time_eligibility")
    if not isinstance(eligibility, dict):
        raise PitPhaseBError("SIGNAL record has no point-in-time eligibility")
    freeze_symbol = str(eligibility.get("symbol_at_freeze") or "").strip().upper()
    quarter = str(record.get("quarter_id") or "")
    if not freeze_symbol or not quarter:
        raise PitPhaseBError("SIGNAL record has incomplete historical observation key")
    return quarter, freeze_symbol


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        raise ValueError("shard_index must be within [0, shard_count)")

    started_at = datetime.now(UTC)
    as_of_day = started_at.astimezone(base.IST).date()
    phase_a = load_phase_a_manifest_pit(
        args.phase_a,
        expected_sha256=args.expected_phase_a_sha256,
    )
    eligible = [record for record in phase_a.get("records", []) if record.get("status") == "SIGNAL"]
    if len(eligible) != int(phase_a.get("status_counts", {}).get("SIGNAL", -1)):
        raise PitPhaseBError("eligible HR003 Phase-B count differs from frozen Phase-A SIGNAL count")

    clusters = sorted({_cluster_symbol(str(record.get("symbol") or "")) for record in eligible})
    shard_clusters = {
        cluster
        for index, cluster in enumerate(clusters)
        if index % args.shard_count == args.shard_index
    }
    shard_records = [
        record
        for record in eligible
        if _cluster_symbol(str(record.get("symbol") or "")) in shard_clusters
    ]

    client = NSEClient(timeout=args.timeout, attempts=args.attempts)
    calendar, calendar_evidence = _calendar(client)

    schedules: dict[tuple[str, str], tuple[datetime, date, date]] = {}
    members: dict[tuple[str, str], UniverseMember] = {}
    trading_symbols: dict[tuple[str, str], str] = {}
    cluster_symbols: dict[tuple[str, str], str] = {}
    action_windows: dict[str, tuple[date, date]] = {}
    action_members: dict[str, UniverseMember] = {}

    for record in shard_records:
        key = _record_key(record)
        member = _member_from_record(record)
        publication, entry_day, exit_day = base._record_schedule(record, calendar)
        trading = resolver._point_in_time_trading_symbol(record, member)
        cluster = _cluster_symbol(member.symbol)
        schedules[key] = (publication, entry_day, exit_day)
        members[key] = member
        trading_symbols[key] = trading
        cluster_symbols[key] = cluster
        if exit_day >= as_of_day:
            continue
        publication_day = publication.astimezone(base.IST).date()
        current = action_windows.get(trading)
        if current is None:
            action_windows[trading] = (publication_day, exit_day)
            action_members[trading] = replace(member, symbol=trading)
        else:
            action_windows[trading] = (
                min(current[0], publication_day),
                max(current[1], exit_day),
            )

    store_root = Path(args.store)
    store_root.mkdir(parents=True, exist_ok=True)
    sources = base.OutcomeSources(
        client=client,
        root=store_root,
        captured_at=started_at,
        attempts=args.attempts,
        sleep_seconds=args.sleep,
    )
    for trading, (start, end) in sorted(action_windows.items()):
        sources.actions_for(action_members[trading], from_date=start, to_date=end)

    outcomes: list[dict[str, Any]] = []
    for index, record in enumerate(shard_records, start=1):
        key = _record_key(record)
        member = members[key]
        publication, entry_day, exit_day = schedules[key]
        trading = trading_symbols[key]
        cluster = cluster_symbols[key]
        if exit_day >= as_of_day:
            outcome = base._pending_outcome(
                record,
                member=member,
                trading_symbol=trading,
                publication=publication,
                entry_day=entry_day,
                exit_day=exit_day,
                started_at=started_at,
            )
        else:
            action_payload, action_raw, action_evidence = sources.actions[trading]
            try:
                outcome = base._execute_record_v2(
                    record,
                    member=member,
                    trading_symbol=trading,
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
                signal = record.get("signal") or {}
                outcome = {
                    "schema_version": 1,
                    "symbol": member.symbol,
                    "isin": member.isin,
                    "historical_trading_symbol": trading,
                    "quarter_id": record.get("quarter_id"),
                    "target_period_end": record.get("target_period_end"),
                    "signal_bucket": signal.get("bucket"),
                    "signal_ue": signal.get("ue"),
                    "status": "ERROR",
                    "reason": f"{type(exc).__name__}: {exc}",
                }
        outcome["statistical_cluster_symbol"] = cluster
        outcome["point_in_time_eligibility"] = record.get("point_in_time_eligibility")
        outcomes.append(outcome)
        if index % 10 == 0:
            print(f"HR003 shard {args.shard_index}: {index}/{len(shard_records)}", flush=True)

    document = {
        "schema_version": 1,
        "phase": "B_OUTCOME_RECONSTRUCTION_SHARD",
        "replay_rule_id": EXPERIMENT_ID,
        "phase_a_manifest_sha256": args.expected_phase_a_sha256,
        "resolver_version": RESOLVER_VERSION,
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "statistical_clusters": sorted(shard_clusters),
        "eligible_record_count": len(shard_records),
        "generated_at_utc": _iso(started_at),
        "reconstruction_local_date": as_of_day.isoformat(),
        "records": outcomes,
        "evidence": {
            "calendar": calendar_evidence,
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
    parser = argparse.ArgumentParser(
        description="Reconstruct one survivorship-clean H002-HR003 outcome shard"
    )
    parser.add_argument(
        "--phase-a",
        default="research/historical/h002/H002-HR003/phase-a/point-in-time-nifty200-signals.json",
    )
    parser.add_argument("--expected-phase-a-sha256", required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, default=8)
    parser.add_argument("--store", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=0.05)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
