from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from marketlab.execution import TradingCalendar, TradingSession, build_paper_position
from marketlab.h002 import PriceReference
from marketlab.h002_historical_outcomes import (
    adapt_signal_for_execution,
    load_phase_a_manifest,
    phase_b_manifest,
)
from marketlab.marketdata import (
    MarketDataMissingRow,
    audit_price_basis_actions,
    equity_price_bar,
    index_price_bar,
    index_snapshot_url,
    parse_index_snapshot,
    parse_udiff_equity,
    udiff_url,
)
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.universe import UniverseMember, load_universe_snapshot

IST = ZoneInfo("Asia/Kolkata")
BENCHMARK_IDS = ("nifty_50", "nifty_200_momentum_30")


class PhaseBError(RuntimeError):
    pass


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _retain(root: Path, raw: bytes, *, kind: str, suffix: str, source_url: str) -> dict[str, Any]:
    import hashlib

    digest = hashlib.sha256(raw).hexdigest()
    path = root / "raw" / kind / "sha256" / f"{digest}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise PhaseBError("content-addressed phase-B evidence collision")
    else:
        path.write_bytes(raw)
    return {
        "source_url": source_url,
        "raw_sha256": digest,
        "raw_path": str(path),
        "byte_count": len(raw),
    }


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise PhaseBError(f"timestamp must include timezone: {value}")
    return parsed.astimezone(UTC)


def _archive_with_retry(client: NSEClient, url: str, *, attempts: int, sleep_seconds: float) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return client.archive_bytes(url)
        except NSEAcquisitionError as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(sleep_seconds * attempt)
    raise PhaseBError(f"archive acquisition failed after {attempts} attempts: {url}: {last_error}")


class OutcomeSources:
    def __init__(
        self,
        *,
        client: NSEClient,
        root: Path,
        captured_at: datetime,
        attempts: int,
        sleep_seconds: float,
    ) -> None:
        self.client = client
        self.root = root
        self.captured_at = captured_at
        self.attempts = attempts
        self.sleep_seconds = sleep_seconds
        self.udiff: dict[str, tuple[bytes, dict[str, Any]]] = {}
        self.indices: dict[str, tuple[bytes, dict[str, Any]]] = {}
        self.actions: dict[str, tuple[Any, bytes, dict[str, Any]]] = {}

    def udiff_for(self, day: date) -> tuple[bytes, dict[str, Any]]:
        key = day.isoformat()
        if key not in self.udiff:
            url = udiff_url(day)
            raw = _archive_with_retry(
                self.client,
                url,
                attempts=self.attempts,
                sleep_seconds=self.sleep_seconds,
            )
            self.udiff[key] = (
                raw,
                _retain(self.root, raw, kind="udiff", suffix=".zip", source_url=url),
            )
            time.sleep(self.sleep_seconds)
        return self.udiff[key]

    def indices_for(self, day: date) -> tuple[bytes, dict[str, Any]]:
        key = day.isoformat()
        if key not in self.indices:
            url = index_snapshot_url(day)
            raw = _archive_with_retry(
                self.client,
                url,
                attempts=self.attempts,
                sleep_seconds=self.sleep_seconds,
            )
            self.indices[key] = (
                raw,
                _retain(self.root, raw, kind="index-snapshot", suffix=".csv", source_url=url),
            )
            time.sleep(self.sleep_seconds)
        return self.indices[key]

    def actions_for(
        self,
        member: UniverseMember,
        *,
        from_date: date,
        to_date: date,
    ) -> tuple[Any, bytes, dict[str, Any]]:
        key = member.symbol.upper()
        cached = self.actions.get(key)
        if cached is not None:
            return cached
        last_error: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                payload, raw = self.client.corporate_actions_with_raw(
                    member.symbol,
                    from_date=from_date.strftime("%d-%m-%Y"),
                    to_date=to_date.strftime("%d-%m-%Y"),
                )
                query = urlencode(
                    {
                        "index": "equities",
                        "symbol": member.symbol,
                        "from_date": from_date.strftime("%d-%m-%Y"),
                        "to_date": to_date.strftime("%d-%m-%Y"),
                    }
                )
                url = f"{self.client.CORPORATE_ACTION_ENDPOINT.url}?{query}"
                evidence = _retain(
                    self.root,
                    raw,
                    kind="corporate-actions",
                    suffix=".json",
                    source_url=url,
                )
                cached = (payload, raw, evidence)
                self.actions[key] = cached
                time.sleep(self.sleep_seconds)
                return cached
            except NSEAcquisitionError as exc:
                last_error = exc
                if attempt < self.attempts:
                    time.sleep(self.sleep_seconds * attempt)
        raise PhaseBError(
            f"corporate-action acquisition failed for {member.symbol}: {last_error}"
        )


def _market_member(record: dict[str, Any], members: dict[str, UniverseMember]) -> UniverseMember:
    symbol = str(record.get("symbol") or "").upper()
    try:
        return members[symbol]
    except KeyError as exc:
        raise PhaseBError(f"phase-A symbol no longer exists in bound cohort: {symbol}") from exc


def _record_schedule(
    record: dict[str, Any],
    calendar: TradingCalendar,
) -> tuple[datetime, date, date]:
    target_event = record.get("target_event")
    if not isinstance(target_event, dict):
        raise PhaseBError("phase-A SIGNAL record is missing target_event")
    provenance = target_event.get("provenance")
    if not isinstance(provenance, dict):
        raise PhaseBError("phase-A SIGNAL record is missing target-event provenance")
    publication_value = provenance.get("exchange_published_at_utc")
    if not isinstance(publication_value, str) or not publication_value:
        raise PhaseBError("phase-A SIGNAL record is missing publication timestamp")
    publication = _parse_timestamp(publication_value)
    entry_session, exit_session = calendar.schedule(publication_value)
    return (
        publication,
        date.fromisoformat(entry_session.session_date),
        date.fromisoformat(exit_session.session_date),
    )


def _equity_bars(
    sources: OutcomeSources,
    member: UniverseMember,
    *,
    entry_day: date,
    exit_day: date,
    entry_basis_version: str,
    exit_basis_version: str,
) -> tuple[list[Any], dict[str, Any]]:
    bars = []
    evidence: dict[str, Any] = {}
    for role, day, basis_version in (
        ("entry", entry_day, entry_basis_version),
        ("exit", exit_day, exit_basis_version),
    ):
        raw, artifact = sources.udiff_for(day)
        evidence[f"{role}_udiff"] = artifact
        try:
            price = parse_udiff_equity(
                raw,
                symbol=member.symbol,
                session_date=day,
                series=member.series,
                expected_isin=member.isin,
            )
        except MarketDataMissingRow as exc:
            raise PhaseBError(f"missing {role} UDiFF row for {member.symbol}: {exc}") from exc
        bars.append(
            replace(
                equity_price_bar(
                    price,
                    source_url=artifact["source_url"],
                    source_timestamp_utc=_iso(sources.captured_at),
                ),
                corporate_action_version=basis_version,
            )
        )
    return bars, evidence


def _benchmark_bars(
    sources: OutcomeSources,
    *,
    entry_day: date,
    exit_day: date,
) -> tuple[list[Any], dict[str, Any]]:
    bars = []
    evidence: dict[str, Any] = {}
    for role, day in (("entry", entry_day), ("exit", exit_day)):
        raw, artifact = sources.indices_for(day)
        evidence[f"{role}_index_snapshot"] = artifact
        for benchmark_id in BENCHMARK_IDS:
            try:
                price = parse_index_snapshot(raw, benchmark_id=benchmark_id, session_date=day)
            except MarketDataMissingRow:
                continue
            bars.append(
                index_price_bar(
                    price,
                    source_url=artifact["source_url"],
                    source_timestamp_utc=_iso(sources.captured_at),
                )
            )
    return bars, evidence


def _execute_record(
    record: dict[str, Any],
    *,
    member: UniverseMember,
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
        symbol=member.symbol,
        start_date=publication_day,
        end_date=entry_day,
    )
    exit_basis = audit_price_basis_actions(
        action_payload,
        raw_payload=action_raw,
        symbol=member.symbol,
        start_date=publication_day,
        end_date=exit_day,
    )
    base = {
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
        "phase_a_compiler_revision": record.get("compiler_revision"),
        "evidence": {
            "corporate_actions": action_evidence,
            "entry_price_basis": asdict(entry_basis),
            "exit_price_basis": asdict(exit_basis),
        },
    }
    if entry_basis.status != "READY" or entry_basis.version is None:
        return {
            **base,
            "status": "SKIPPED_PRICE_BASIS",
            "reason": "entry_price_basis_unresolved",
        }
    if exit_basis.status != "READY" or exit_basis.version is None:
        return {
            **base,
            "status": "SKIPPED_PRICE_BASIS",
            "reason": "exit_price_basis_unresolved",
        }
    if entry_basis.version != exit_basis.version:
        return {
            **base,
            "status": "SKIPPED_PRICE_BASIS",
            "reason": "holding_period_price_basis_changed",
        }

    stock_bars, stock_evidence = _equity_bars(
        sources,
        member,
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
        raise PhaseBError("phase-A SIGNAL record is missing price_reference")
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
    started_at = datetime.now(UTC)
    phase_a = load_phase_a_manifest(
        args.phase_a,
        expected_sha256=args.expected_phase_a_sha256,
    )
    universe = load_universe_snapshot(args.universe)
    if universe.cohort_id != phase_a.get("cohort_id") or universe.sha256 != phase_a.get("cohort_sha256"):
        raise PhaseBError("phase-A manifest and universe snapshot are not the same frozen cohort")

    calendar_document = phase_a.get("calendar_snapshot")
    if not isinstance(calendar_document, dict):
        raise PhaseBError("phase-A manifest is missing its frozen calendar snapshot")
    if calendar_document.get("unresolved_special_dates"):
        raise PhaseBError("phase-A calendar contains unresolved special sessions")
    sessions = [TradingSession(**item) for item in calendar_document.get("sessions", [])]
    calendar = TradingCalendar(sessions, version=str(calendar_document.get("version") or ""))

    members = {member.symbol.upper(): member for member in universe.members}
    eligible = [record for record in phase_a.get("records", []) if record.get("status") == "SIGNAL"]
    if len(eligible) != int(phase_a.get("status_counts", {}).get("SIGNAL", -1)):
        raise PhaseBError("eligible phase-B count does not match frozen phase-A SIGNAL count")

    schedules: dict[tuple[str, str], tuple[datetime, date, date]] = {}
    action_windows: dict[str, tuple[date, date]] = {}
    for record in eligible:
        member = _market_member(record, members)
        publication, entry_day, exit_day = _record_schedule(record, calendar)
        key = (member.symbol.upper(), str(record.get("quarter_id")))
        schedules[key] = (publication, entry_day, exit_day)
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

    results: list[dict[str, Any]] = []
    for index, record in enumerate(eligible, start=1):
        member = _market_member(record, members)
        key = (member.symbol.upper(), str(record.get("quarter_id")))
        publication, entry_day, exit_day = schedules[key]
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
        except PhaseBError as exc:
            outcome = {
                "schema_version": 1,
                "symbol": member.symbol,
                "isin": member.isin,
                "quarter_id": record.get("quarter_id"),
                "target_period_end": record.get("target_period_end"),
                "signal_bucket": record.get("signal", {}).get("bucket"),
                "signal_ue": record.get("signal", {}).get("ue"),
                "status": "ERROR",
                "reason": str(exc),
            }
        results.append(outcome)
        if index % 20 == 0:
            print(f"phase-B outcomes {index}/{len(eligible)}", flush=True)

    evidence_summary = {
        "phase_a_manifest_sha256": args.expected_phase_a_sha256,
        "phase_a_manifest_path": str(args.phase_a),
        "calendar_version": calendar.version,
        "trading_calendar_sha256": calendar.sha256,
        "captured_at_utc": _iso(started_at),
        "udiff_archive_count": len(sources.udiff),
        "index_snapshot_count": len(sources.indices),
        "corporate_action_payload_count": len(sources.actions),
        "raw_evidence_root": str(store_root),
    }
    manifest = phase_b_manifest(
        phase_a_manifest_sha256=args.expected_phase_a_sha256,
        generated_at_utc=_iso(started_at),
        records=results,
        evidence=evidence_summary,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "manifest_sha256": manifest["manifest_sha256"],
                "status_counts": manifest["summary"]["status_counts"],
                "completed_count": manifest["summary"]["completed_count"],
                "phase_a_manifest_sha256": args.expected_phase_a_sha256,
            },
            sort_keys=True,
        )
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstruct H002-HR001 Phase-B outcomes")
    parser.add_argument(
        "--phase-a",
        default="research/historical/h002/H002-HR001/phase-a/fixed-u001-transport-signals.json",
    )
    parser.add_argument("--expected-phase-a-sha256", required=True)
    parser.add_argument(
        "--universe",
        default="research/prospective/universes/FY27-Q2-2026-09-06.json",
    )
    parser.add_argument("--store", default=".marketlab-historical-phase-b")
    parser.add_argument(
        "--output",
        default="research/historical/h002/H002-HR001/phase-b/fixed-u001-transport-outcomes.json",
    )
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--sleep", type=float, default=0.12)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
