from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from run_h002_historical_phase_b import OutcomeSources, _benchmark_bars, _record_schedule
from run_h002_historical_replay_v2r2 import (
    BOUND_HR001_PHASE_A_PATH,
    BOUND_HR001_PHASE_A_SHA256,
)

from marketlab.execution import TradingCalendar, build_paper_position
from marketlab.h002 import PriceReference
from marketlab.h002_historical_calendar import (
    HOLIDAY_2025_SOURCE_URL,
    IST,
    MUHURAT_2025_SOURCE_URL,
    build_hr002_calendar,
)
from marketlab.h002_historical_identity import (
    historical_isins_equivalent,
    historical_symbol_variants,
)
from marketlab.h002_historical_outcomes import adapt_signal_for_execution, load_phase_a_manifest
from marketlab.h002_historical_v2_outcomes import load_phase_a_manifest_v2
from marketlab.marketdata import (
    MarketDataError,
    audit_price_basis_actions,
    equity_price_bar,
    parse_udiff_equity,
)
from marketlab.nse import NSEClient
from marketlab.universe import UniverseMember, load_universe_snapshot


class PhaseBV2Error(RuntimeError):
    pass


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _calendar_from_frozen_phase_a(
    phase_a: dict[str, Any],
    *,
    client: NSEClient,
) -> tuple[TradingCalendar, dict[str, Any]]:
    evidence = phase_a.get("calendar_evidence")
    if not isinstance(evidence, dict):
        raise PhaseBV2Error("HR002 Phase A is missing frozen calendar evidence")
    bound = load_phase_a_manifest(
        BOUND_HR001_PHASE_A_PATH,
        expected_sha256=BOUND_HR001_PHASE_A_SHA256,
    )
    holiday_raw = client.archive_bytes(HOLIDAY_2025_SOURCE_URL)
    muhurat_raw = client.archive_bytes(MUHURAT_2025_SOURCE_URL)
    holiday_sha = _sha256(holiday_raw)
    muhurat_sha = _sha256(muhurat_raw)
    if holiday_sha != evidence.get("holiday_2025_raw_sha256"):
        raise PhaseBV2Error("2025 NSE holiday circular bytes changed after Phase-A freeze")
    if muhurat_sha != evidence.get("muhurat_2025_raw_sha256"):
        raise PhaseBV2Error("2025 NSE Muhurat circular bytes changed after Phase-A freeze")
    calendar, rebuilt = build_hr002_calendar(
        phase_a_2026_manifest=bound,
        phase_a_2026_manifest_sha256=BOUND_HR001_PHASE_A_SHA256,
        holiday_2025_raw_sha256=holiday_sha,
        muhurat_2025_raw_sha256=muhurat_sha,
    )
    if calendar.sha256 != evidence.get("trading_calendar_sha256"):
        raise PhaseBV2Error("rebuilt HR002 calendar SHA differs from frozen Phase A")
    if calendar.version != evidence.get("trading_calendar_version"):
        raise PhaseBV2Error("rebuilt HR002 calendar version differs from frozen Phase A")
    return calendar, {
        "holiday_2025_source_url": HOLIDAY_2025_SOURCE_URL,
        "holiday_2025_raw_sha256": holiday_sha,
        "muhurat_2025_source_url": MUHURAT_2025_SOURCE_URL,
        "muhurat_2025_raw_sha256": muhurat_sha,
        "trading_calendar_sha256": calendar.sha256,
        "trading_calendar_version": calendar.version,
        "rebuilt_calendar_evidence": rebuilt,
    }


def _trading_symbol(record: dict[str, Any], member: UniverseMember) -> str:
    candidate = record.get("target_candidate")
    if not isinstance(candidate, dict):
        raise PhaseBV2Error("SIGNAL record is missing frozen target candidate")
    symbol = str(candidate.get("symbol") or "").strip().upper()
    if not symbol:
        raise PhaseBV2Error("target candidate is missing its historical trading symbol")
    registered = set(historical_symbol_variants(member.symbol))
    if symbol not in registered:
        raise PhaseBV2Error(
            f"historical trading symbol is not a registered identity for {member.symbol}: {symbol}"
        )
    return symbol


def _target_isin(record: dict[str, Any]) -> str | None:
    event = record.get("target_event")
    if not isinstance(event, dict):
        return None
    value = str(event.get("isin") or "").strip().upper()
    return value or None


def _parse_historical_equity(
    raw: bytes,
    *,
    canonical_symbol: str,
    trading_symbol: str,
    session_date: date,
    series: str,
    expected_isin: str | None,
):
    try:
        return parse_udiff_equity(
            raw,
            symbol=trading_symbol,
            session_date=session_date,
            series=series,
            expected_isin=expected_isin,
        )
    except MarketDataError as exc:
        if expected_isin is None or "ISIN mismatch" not in str(exc):
            raise
        observed = parse_udiff_equity(
            raw,
            symbol=trading_symbol,
            session_date=session_date,
            series=series,
            expected_isin=None,
        )
        if not historical_isins_equivalent(canonical_symbol, expected_isin, observed.isin):
            raise
        return observed


def _equity_bars_v2(
    sources: OutcomeSources,
    member: UniverseMember,
    *,
    trading_symbol: str,
    expected_isin: str | None,
    entry_day: date,
    exit_day: date,
    entry_basis_version: str,
    exit_basis_version: str,
) -> tuple[list[Any], dict[str, Any]]:
    bars: list[Any] = []
    evidence: dict[str, Any] = {
        "historical_trading_symbol": trading_symbol,
        "target_event_isin": expected_isin,
    }
    for role, day, basis_version in (
        ("entry", entry_day, entry_basis_version),
        ("exit", exit_day, exit_basis_version),
    ):
        raw, artifact = sources.udiff_for(day)
        evidence[f"{role}_udiff"] = artifact
        price = _parse_historical_equity(
            raw,
            canonical_symbol=member.symbol,
            trading_symbol=trading_symbol,
            session_date=day,
            series=member.series,
            expected_isin=expected_isin,
        )
        evidence[f"{role}_observed_isin"] = price.isin
        bars.append(
            replace(
                equity_price_bar(
                    price,
                    source_url=artifact["source_url"],
                    source_timestamp_utc=_iso(sources.captured_at),
                ),
                instrument_id=member.symbol,
                corporate_action_version=basis_version,
            )
        )
    return bars, evidence


def _pending_outcome(
    record: dict[str, Any],
    *,
    member: UniverseMember,
    trading_symbol: str,
    publication: datetime,
    entry_day: date,
    exit_day: date,
    started_at: datetime,
) -> dict[str, Any]:
    signal = record.get("signal") or {}
    return {
        "schema_version": 1,
        "symbol": member.symbol,
        "isin": member.isin,
        "historical_trading_symbol": trading_symbol,
        "quarter_id": record.get("quarter_id"),
        "target_period_end": record.get("target_period_end"),
        "phase_a_signal_event_id": signal.get("event_id"),
        "signal_bucket": signal.get("bucket"),
        "signal_ue": signal.get("ue"),
        "exchange_published_at_utc": _iso(publication),
        "entry_session_date": entry_day.isoformat(),
        "exit_session_date": exit_day.isoformat(),
        "status": "PENDING",
        "reason": "exit_not_matured_before_reconstruction_date",
        "evaluation_as_of_utc": _iso(started_at),
        "live_order_created": False,
    }


def _execute_record_v2(
    record: dict[str, Any],
    *,
    member: UniverseMember,
    trading_symbol: str,
    calendar: TradingCalendar,
    sources: OutcomeSources,
    publication: datetime,
    entry_day: date,
    exit_day: date,
    action_payload: Any,
    action_raw: bytes,
    action_evidence: dict[str, Any],
) -> dict[str, Any]:
    publication_day = publication.astimezone(IST).date()
    entry_basis = audit_price_basis_actions(
        action_payload,
        raw_payload=action_raw,
        symbol=trading_symbol,
        start_date=publication_day,
        end_date=entry_day,
    )
    exit_basis = audit_price_basis_actions(
        action_payload,
        raw_payload=action_raw,
        symbol=trading_symbol,
        start_date=publication_day,
        end_date=exit_day,
    )
    signal_payload = record.get("signal") or {}
    base = {
        "schema_version": 1,
        "symbol": member.symbol,
        "isin": member.isin,
        "historical_trading_symbol": trading_symbol,
        "quarter_id": record.get("quarter_id"),
        "target_period_end": record.get("target_period_end"),
        "phase_a_signal_event_id": signal_payload.get("event_id"),
        "signal_bucket": signal_payload.get("bucket"),
        "signal_ue": signal_payload.get("ue"),
        "exchange_published_at_utc": _iso(publication),
        "entry_session_date": entry_day.isoformat(),
        "exit_session_date": exit_day.isoformat(),
        "phase_a_compiler_revision": record.get("compiler_revision"),
        "evidence": {
            "corporate_actions": action_evidence,
            "entry_price_basis": asdict(entry_basis),
            "exit_price_basis": asdict(exit_basis),
        },
    }
    if entry_basis.status != "READY" or entry_basis.version is None:
        return {**base, "status": "SKIPPED_PRICE_BASIS", "reason": "entry_price_basis_unresolved"}
    if exit_basis.status != "READY" or exit_basis.version is None:
        return {**base, "status": "SKIPPED_PRICE_BASIS", "reason": "exit_price_basis_unresolved"}
    if entry_basis.version != exit_basis.version:
        return {
            **base,
            "status": "SKIPPED_PRICE_BASIS",
            "reason": "holding_period_price_basis_changed",
        }

    stock_bars, stock_evidence = _equity_bars_v2(
        sources,
        member,
        trading_symbol=trading_symbol,
        expected_isin=_target_isin(record),
        entry_day=entry_day,
        exit_day=exit_day,
        entry_basis_version=entry_basis.version,
        exit_basis_version=exit_basis.version,
    )
    benchmark_bars, benchmark_evidence = _benchmark_bars(
        sources,
        entry_day=entry_day,
        exit_day=exit_day,
    )
    base["evidence"].update(stock_evidence)
    base["evidence"].update(benchmark_evidence)

    signal = adapt_signal_for_execution(record)
    reference_payload = record.get("price_reference")
    if not isinstance(reference_payload, dict):
        raise PhaseBV2Error("SIGNAL record is missing its frozen price reference")
    reference = PriceReference(**reference_payload)
    position = build_paper_position(
        signal,
        exchange_published_at_utc=_iso(publication),
        calendar=calendar,
        stock_bars=stock_bars,
        benchmark_bars=benchmark_bars,
        as_of_utc=_iso(sources.captured_at),
        price_reference=reference,
    )
    if position.status != "COMPLETED":
        return {
            **base,
            "status": position.status,
            "reason": position.skip_or_pending_reason,
            "position": position.to_dict(),
        }
    missing_benchmarks = [
        outcome.benchmark_id for outcome in position.benchmarks if outcome.status != "COMPLETE"
    ]
    if missing_benchmarks:
        return {
            **base,
            "status": "MISSING_BENCHMARK",
            "reason": ",".join(sorted(missing_benchmarks)),
            "position": position.to_dict(),
        }
    return {
        **base,
        "status": "COMPLETED",
        "reason": None,
        "position_id": position.position_id,
        "entry_price": position.entry_price,
        "exit_price": position.exit_price,
        "gross_return_pct": position.gross_return_pct,
        "cost_stressed_return_pct": position.cost_stressed_return_pct,
        "benchmarks": [outcome.to_dict() for outcome in position.benchmarks],
        "live_order_created": position.live_order_created,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        raise ValueError("shard_index must be within [0, shard_count)")
    started_at = datetime.now(UTC)
    as_of_day = started_at.astimezone(IST).date()
    phase_a = load_phase_a_manifest_v2(
        args.phase_a,
        expected_sha256=args.expected_phase_a_sha256,
    )
    universe = load_universe_snapshot(args.universe)
    if (
        universe.cohort_id != phase_a.get("cohort_id")
        or universe.sha256 != phase_a.get("cohort_sha256")
    ):
        raise PhaseBV2Error("HR002 Phase A and universe are not the same frozen cohort")

    client = NSEClient(timeout=args.timeout, attempts=args.attempts)
    calendar, calendar_evidence = _calendar_from_frozen_phase_a(phase_a, client=client)
    members = {member.symbol.upper(): member for member in universe.members}
    eligible = [record for record in phase_a.get("records", []) if record.get("status") == "SIGNAL"]
    if len(eligible) != int(phase_a.get("status_counts", {}).get("SIGNAL", -1)):
        raise PhaseBV2Error("eligible HR002 Phase-B count differs from frozen Phase-A SIGNAL count")

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
    trading_symbols: dict[tuple[str, str], str] = {}
    action_windows: dict[str, tuple[date, date]] = {}
    action_members: dict[str, UniverseMember] = {}
    for record in shard_records:
        canonical = str(record.get("symbol") or "").upper()
        member = members[canonical]
        publication, entry_day, exit_day = _record_schedule(record, calendar)
        key = (canonical, str(record.get("quarter_id")))
        schedules[key] = (publication, entry_day, exit_day)
        trading = _trading_symbol(record, member)
        trading_symbols[key] = trading
        if exit_day >= as_of_day:
            continue
        publication_day = publication.astimezone(IST).date()
        current = action_windows.get(trading)
        if current is None:
            action_windows[trading] = (publication_day, exit_day)
            action_members[trading] = replace(member, symbol=trading)
        else:
            action_windows[trading] = (min(current[0], publication_day), max(current[1], exit_day))

    store_root = Path(args.store)
    store_root.mkdir(parents=True, exist_ok=True)
    sources = OutcomeSources(
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
        canonical = str(record.get("symbol") or "").upper()
        member = members[canonical]
        key = (canonical, str(record.get("quarter_id")))
        publication, entry_day, exit_day = schedules[key]
        trading = trading_symbols[key]
        if exit_day >= as_of_day:
            outcome = _pending_outcome(
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
                outcome = _execute_record_v2(
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
        outcomes.append(outcome)
        if index % 10 == 0:
            print(f"HR002 shard {args.shard_index}: {index}/{len(shard_records)}", flush=True)

    document = {
        "schema_version": 1,
        "phase": "B_OUTCOME_RECONSTRUCTION_SHARD",
        "replay_rule_id": "H002-HR002",
        "phase_a_manifest_sha256": args.expected_phase_a_sha256,
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "symbols": sorted(shard_symbols),
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
    parser = argparse.ArgumentParser(description="Reconstruct one H002-HR002 Phase-B outcome shard")
    parser.add_argument(
        "--phase-a",
        default="research/historical/h002/H002-HR002/phase-a/fixed-u001-six-quarter-signals.json",
    )
    parser.add_argument("--expected-phase-a-sha256", required=True)
    parser.add_argument(
        "--universe",
        default="research/prospective/universes/FY27-Q2-2026-09-06.json",
    )
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
