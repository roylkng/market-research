from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from marketlab.calendar_snapshot import CalendarSnapshot, CalendarSnapshotError
from marketlab.events import EventParseError, EventStore, FinancialEvent, SourceProvenance
from marketlab.execution import ExecutionError, PriceBar, TradingCalendar, build_paper_position
from marketlab.frozen_bundle import FrozenBundleView, FrozenBundleError
from marketlab.h002 import (
    H002SignalError,
    H002SignalResult,
    PriceReference,
    RULE_ID,
    SIGNAL_VERSION,
    score_h002,
)
from marketlab.marketdata import (
    MarketArtifact,
    MarketArtifactStore,
    MarketDataError,
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
from marketlab.prospective import (
    ObservationStore,
    ProspectiveReport,
    build_prospective_report,
    select_first_result_candidate,
)
from marketlab.universe import UniverseMember, UniverseSnapshot

IST = ZoneInfo("Asia/Kolkata")
DISCOVERY_START = date(2026, 10, 1)
DISCOVERY_END = date(2027, 1, 31)
TARGET_PERIOD_END = "2026-09-30"

RunOutcome = Literal["NO_EVENT", "UNCHANGED", "UPDATED", "ERROR"]


class RunnerError(ValueError):
    """Raised when a cohort run violates a frozen H002-D integrity boundary."""


@dataclass(frozen=True)
class RawEvidence:
    schema_version: int
    evidence_id: str
    kind: str
    source_url: str
    captured_at_utc: str
    raw_sha256: str
    raw_path: str
    byte_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SymbolRunResult:
    symbol: str
    outcome: RunOutcome
    state: str | None
    detail: str | None


@dataclass(frozen=True)
class CohortRunSummary:
    schema_version: int
    run_sha256: str
    cohort_id: str
    as_of_utc: str
    discovery_enabled: bool
    member_count: int
    outcome_counts: dict[str, int]
    results: tuple[SymbolRunResult, ...]
    report_sha256: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["results"] = [asdict(item) for item in self.results]
        return payload


class RawEvidenceStore:
    """Content-addressed exact bytes for non-event research evidence."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def retain(
        self,
        raw: bytes,
        *,
        kind: str,
        source_url: str,
        captured_at: datetime,
        suffix: str,
    ) -> RawEvidence:
        if not raw:
            raise RunnerError("raw evidence bytes are empty")
        if not kind.strip() or not source_url.strip():
            raise RunnerError("raw evidence kind and source URL are required")
        if captured_at.tzinfo is None:
            raise RunnerError("raw evidence captured_at must include timezone")
        digest = hashlib.sha256(raw).hexdigest()
        raw_path = self.root / "raw-evidence" / kind / "sha256" / f"{digest}{suffix}"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        if raw_path.exists():
            if raw_path.read_bytes() != raw:
                raise RunnerError("content-addressed raw-evidence collision")
        else:
            raw_path.write_bytes(raw)
        captured = captured_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        identity = {
            "kind": kind,
            "source_url": source_url,
            "raw_sha256": digest,
            "byte_count": len(raw),
        }
        evidence_id = _canonical_hash(identity)
        metadata = self.root / "raw-evidence" / kind / "records" / f"{evidence_id}.json"
        metadata.parent.mkdir(parents=True, exist_ok=True)
        if metadata.exists():
            try:
                existing = RawEvidence(**json.loads(metadata.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, TypeError) as exc:
                raise RunnerError(f"invalid retained raw evidence: {exc}") from exc
            if (
                existing.kind != kind
                or existing.source_url != source_url
                or existing.raw_sha256 != digest
                or existing.byte_count != len(raw)
                or existing.raw_path != str(raw_path)
            ):
                raise RunnerError("raw-evidence metadata collision")
            return existing
        evidence = RawEvidence(
            schema_version=1,
            evidence_id=evidence_id,
            kind=kind,
            source_url=source_url,
            captured_at_utc=captured,
            raw_sha256=digest,
            raw_path=str(raw_path),
            byte_count=len(raw),
        )
        content = (json.dumps(evidence.to_dict(), indent=2, sort_keys=True) + "\n").encode()
        try:
            fd = os.open(metadata, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            return self.retain(
                raw,
                kind=kind,
                source_url=source_url,
                captured_at=captured_at,
                suffix=suffix,
            )
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return evidence


def _canonical_hash(payload: Any) -> str:
    try:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    except (TypeError, ValueError) as exc:
        raise RunnerError("runner payload must contain finite JSON values") from exc
    return hashlib.sha256(encoded).hexdigest()


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise RunnerError("timestamp must include timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise RunnerError(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise RunnerError(f"timestamp must include timezone: {value}")
    return parsed.astimezone(UTC)


def _event_from_dict(payload: dict[str, Any]) -> FinancialEvent:
    data = dict(payload)
    try:
        provenance = SourceProvenance(**data.pop("provenance"))
        unresolved = tuple(data.pop("unresolved_fields", []))
        return FinancialEvent(**data, unresolved_fields=unresolved, provenance=provenance)
    except (KeyError, TypeError) as exc:
        raise RunnerError(f"invalid persisted FinancialEvent: {exc}") from exc


def _terminal_no_signal(event: FinancialEvent, record_id: str, expectation: Any, as_of: datetime) -> H002SignalResult:
    return H002SignalResult(
        schema_version=1,
        rule_id=RULE_ID,
        signal_version=SIGNAL_VERSION,
        event_id=event.economic_event_id,
        event_version_id=event.version_id,
        expectation_id=expectation.expectation_id,
        symbol=event.symbol,
        scored_at_utc=event.provenance.captured_at_utc,
        actual_basic_eps=event.basic_eps,
        expected_eps=None,
        surprise_eps=None,
        price_day_minus_2=None,
        ue=None,
        bucket="NO_SIGNAL",
        no_signal_reason=expectation.no_signal_reason or f"terminal_record:{record_id}",
    )


class H002CohortRunner:
    def __init__(
        self,
        *,
        client: NSEClient,
        universe: UniverseSnapshot,
        bundle: FrozenBundleView,
        calendar_snapshot: CalendarSnapshot,
        store_root: str | Path,
    ) -> None:
        if universe.cohort_id != bundle.cohort_id:
            raise RunnerError("universe and frozen bundle cohorts differ")
        if universe.sha256 != bundle.universe_snapshot_sha256:
            raise RunnerError("universe and frozen bundle hashes differ")
        self.client = client
        self.universe = universe
        self.bundle = bundle
        self.calendar_snapshot = calendar_snapshot
        self.store_root = Path(store_root)
        self.event_store = EventStore(self.store_root)
        self.market_store = MarketArtifactStore(self.store_root)
        self.raw_store = RawEvidenceStore(self.store_root)
        self.observations = ObservationStore(self.store_root)

    def run(self, *, as_of: datetime) -> tuple[CohortRunSummary, ProspectiveReport]:
        if as_of.tzinfo is None:
            raise RunnerError("runner as_of must include timezone")
        as_of = as_of.astimezone(UTC)
        local_day = as_of.astimezone(IST).date()
        discovery_enabled = DISCOVERY_START <= local_day <= DISCOVERY_END
        before_window = local_day < DISCOVERY_START

        results: list[SymbolRunResult] = []
        if before_window:
            report = build_prospective_report(
                self.observations, cohort_id=self.universe.cohort_id, generated_at=as_of
            )
            summary = _run_summary(
                cohort_id=self.universe.cohort_id,
                as_of=as_of,
                discovery_enabled=False,
                member_count=len(self.universe.members),
                results=results,
                report_sha256=report.report_sha256,
            )
            return summary, report

        for member in self.universe.members:
            try:
                result = self._run_symbol(
                    member,
                    as_of=as_of,
                    discovery_enabled=discovery_enabled,
                )
            except (
                CalendarSnapshotError,
                EventParseError,
                ExecutionError,
                FrozenBundleError,
                H002SignalError,
                MarketDataError,
                NSEAcquisitionError,
                RunnerError,
            ) as exc:
                result = SymbolRunResult(
                    symbol=member.symbol,
                    outcome="ERROR",
                    state="ERROR",
                    detail=str(exc),
                )
            results.append(result)

        report = build_prospective_report(
            self.observations, cohort_id=self.universe.cohort_id, generated_at=as_of
        )
        summary = _run_summary(
            cohort_id=self.universe.cohort_id,
            as_of=as_of,
            discovery_enabled=discovery_enabled,
            member_count=len(self.universe.members),
            results=results,
            report_sha256=report.report_sha256,
        )
        return summary, report

    def _run_symbol(
        self,
        member: UniverseMember,
        *,
        as_of: datetime,
        discovery_enabled: bool,
    ) -> SymbolRunResult:
        symbol = member.symbol.upper()
        record = self.bundle.records_by_symbol[symbol]
        expectation = record.expectation
        latest = self.observations.latest(
            self.universe.cohort_id, symbol, TARGET_PERIOD_END
        )
        event = (
            _event_from_dict(latest.event)
            if latest is not None and isinstance(latest.event, dict)
            else None
        )
        previous_evidence = (
            dict(latest.evidence) if latest is not None and isinstance(latest.evidence, dict) else {}
        )
        revisions: list[dict[str, Any]] = list(previous_evidence.get("revisions", []))
        discovery_evidence: dict[str, Any] = {
            key: previous_evidence[key]
            for key in ("discovery_sha256", "first_discovery_row_sha256")
            if key in previous_evidence
        }

        if discovery_enabled:
            try:
                discovery_payload, discovery_raw = self.client.integrated_financial_filings_with_raw(
                    symbol
                )
            except NSEAcquisitionError:
                if event is None:
                    raise
            else:
                selection = select_first_result_candidate(
                    discovery_payload,
                    symbol=symbol,
                    target_period_end=TARGET_PERIOD_END,
                    accounting_basis=expectation.accounting_basis,
                )
                if selection is None:
                    if event is None:
                        return SymbolRunResult(symbol, "NO_EVENT", None, None)
                else:
                    discovery_evidence = {
                        "discovery_sha256": hashlib.sha256(discovery_raw).hexdigest(),
                        "first_discovery_row_sha256": selection.first.discovery_row_sha256,
                    }
                    revisions = []
                    if event is None:
                        source_raw = self.client.archive_bytes(selection.first.source_url)
                        event, _ = self.event_store.capture_prospective_bytes(
                            source_raw,
                            discovery_bytes=discovery_raw,
                            source_url=selection.first.source_url,
                            exchange_published_at_utc=selection.first.exchange_published_at_utc,
                            universe=self.universe,
                            suffix=".xml",
                            captured_at=as_of,
                        )
                        self.observations.append(
                            cohort_id=self.universe.cohort_id,
                            symbol=symbol,
                            target_period_end=TARGET_PERIOD_END,
                            recorded_at=as_of,
                            state="EVENT_CAPTURED",
                            event=event.to_dict(),
                            expectation_record_id=record.record_id,
                            evidence=discovery_evidence,
                        )
                        latest = self.observations.latest(
                            self.universe.cohort_id, symbol, TARGET_PERIOD_END
                        )
                    elif event.provenance.source_url != selection.first.source_url:
                        snapshot, created = self.observations.append(
                            cohort_id=self.universe.cohort_id,
                            symbol=symbol,
                            target_period_end=TARGET_PERIOD_END,
                            recorded_at=as_of,
                            state="ERROR",
                            reason="first_filing_identity_changed_after_initial_capture",
                            event=event.to_dict(),
                            expectation_record_id=record.record_id,
                            signal=None if latest is None else latest.signal,
                            paper_position=None if latest is None else latest.paper_position,
                            evidence=discovery_evidence,
                        )
                        return SymbolRunResult(
                            symbol,
                            "UPDATED" if created else "UNCHANGED",
                            snapshot.state,
                            snapshot.reason,
                        )
                    for revision in selection.revisions:
                        try:
                            raw = self.client.archive_bytes(revision.source_url)
                        except NSEAcquisitionError:
                            revisions.append(
                                {
                                    "source_url": revision.source_url,
                                    "exchange_published_at_utc": revision.exchange_published_at_utc,
                                    "raw_sha256": None,
                                    "status": "FETCH_PENDING",
                                }
                            )
                            continue
                        retained = self.raw_store.retain(
                            raw,
                            kind="result-revisions",
                            source_url=revision.source_url,
                            captured_at=as_of,
                            suffix=".xml",
                        )
                        revisions.append(
                            {
                                "source_url": revision.source_url,
                                "exchange_published_at_utc": revision.exchange_published_at_utc,
                                "raw_sha256": retained.raw_sha256,
                                "evidence_id": retained.evidence_id,
                                "status": "RETAINED_NOT_SCORED",
                            }
                        )
        elif event is None:
            return SymbolRunResult(symbol, "NO_EVENT", None, "discovery_window_closed")

        assert event is not None
        record = self.bundle.resolve_for_event(event)
        expectation = record.expectation
        base_evidence = {
            **previous_evidence,
            **discovery_evidence,
            "event_source_sha256": event.provenance.raw_sha256,
            "event_discovery_sha256": event.provenance.discovery_sha256,
            "calendar_snapshot_sha256": self.calendar_snapshot.sha256,
            "revisions": revisions,
        }

        if expectation.status == "NO_SIGNAL":
            signal = _terminal_no_signal(event, record.record_id, expectation, as_of)
            calendar = TradingCalendar(
                list(self.calendar_snapshot.sessions), version=self.calendar_snapshot.version
            )
            position = build_paper_position(
                signal,
                exchange_published_at_utc=event.provenance.exchange_published_at_utc or "",
                calendar=calendar,
                stock_bars=[],
                benchmark_bars=[],
                as_of_utc=_iso(as_of),
            )
            snapshot, created = self.observations.append(
                cohort_id=self.universe.cohort_id,
                symbol=symbol,
                target_period_end=TARGET_PERIOD_END,
                recorded_at=as_of,
                state="SKIPPED",
                reason=position.skip_or_pending_reason,
                event=event.to_dict(),
                expectation_record_id=record.record_id,
                signal=signal,
                paper_position=position,
                evidence=base_evidence,
            )
            return SymbolRunResult(
                symbol,
                "UPDATED" if created else "UNCHANGED",
                snapshot.state,
                snapshot.reason,
            )

        publication = _parse_timestamp(event.provenance.exchange_published_at_utc or "")
        publication_day = publication.astimezone(IST).date()
        expectation_day = _parse_timestamp(expectation.expectation_as_of_utc).astimezone(IST).date()
        action_payload, action_raw, action_artifact = self._corporate_actions(
            member,
            from_date=expectation_day,
            to_date=publication_day,
            as_of=as_of,
        )
        pre_event_basis = audit_price_basis_actions(
            action_payload,
            raw_payload=action_raw,
            symbol=symbol,
            start_date=expectation_day,
            end_date=publication_day,
        )
        base_evidence["pre_event_corporate_action_artifact"] = action_artifact.to_dict()
        base_evidence["pre_event_price_basis"] = asdict(pre_event_basis)
        if pre_event_basis.relevant_actions or pre_event_basis.unresolved_actions:
            detail = "; ".join(
                sorted(
                    {item["subject"] for item in pre_event_basis.relevant_actions}
                    | set(pre_event_basis.unresolved_actions)
                )
            )
            snapshot, created = self.observations.append(
                cohort_id=self.universe.cohort_id,
                symbol=symbol,
                target_period_end=TARGET_PERIOD_END,
                recorded_at=as_of,
                state="SKIPPED",
                reason=f"post_expectation_freeze_eps_basis_action:{detail}",
                event=event.to_dict(),
                expectation_record_id=record.record_id,
                evidence=base_evidence,
            )
            return SymbolRunResult(
                symbol,
                "UPDATED" if created else "UNCHANGED",
                snapshot.state,
                snapshot.reason,
            )

        unresolved = [date.fromisoformat(value) for value in self.calendar_snapshot.unresolved_special_dates]
        if any(value <= publication_day for value in unresolved):
            snapshot, created = self.observations.append(
                cohort_id=self.universe.cohort_id,
                symbol=symbol,
                target_period_end=TARGET_PERIOD_END,
                recorded_at=as_of,
                state="CALENDAR_PENDING",
                reason="unresolved_special_session_precedes_event",
                event=event.to_dict(),
                expectation_record_id=record.record_id,
                evidence=base_evidence,
            )
            return SymbolRunResult(
                symbol,
                "UPDATED" if created else "UNCHANGED",
                snapshot.state,
                snapshot.reason,
            )

        base_calendar = TradingCalendar(
            list(self.calendar_snapshot.sessions), version=self.calendar_snapshot.version
        )
        reference_session = base_calendar.reference_session(
            event.provenance.exchange_published_at_utc or ""
        )
        reference_day = date.fromisoformat(reference_session.session_date)
        reference_status, reference_price, reference_artifact = self._equity_day(
            member, reference_day, as_of=as_of
        )
        if reference_status == "ARCHIVE_UNAVAILABLE":
            snapshot, created = self.observations.append(
                cohort_id=self.universe.cohort_id,
                symbol=symbol,
                target_period_end=TARGET_PERIOD_END,
                recorded_at=as_of,
                state="PRICE_REFERENCE_PENDING",
                reason="reference_udiff_archive_unavailable",
                event=event.to_dict(),
                expectation_record_id=record.record_id,
                evidence=base_evidence,
            )
            return SymbolRunResult(
                symbol,
                "UPDATED" if created else "UNCHANGED",
                snapshot.state,
                snapshot.reason,
            )
        assert reference_artifact is not None
        reference = PriceReference(
            symbol=symbol,
            role="price_day_minus_2",
            trading_date=reference_session.session_date,
            close_timestamp_utc=reference_session.close_timestamp_utc,
            close_price=None if reference_price is None else reference_price.close_price,
            source=reference_artifact.source_url,
            corporate_action_version=pre_event_basis.version or "PB-PRE-EVENT-UNRESOLVED",
        )
        base_evidence["price_reference_artifact"] = reference_artifact.to_dict()
        base_evidence["price_reference"] = reference.to_dict()
        signal = score_h002(
            event,
            expectation,
            reference,
            scored_at_utc=event.provenance.captured_at_utc,
        )
        if latest is None or latest.signal != signal.to_dict():
            self.observations.append(
                cohort_id=self.universe.cohort_id,
                symbol=symbol,
                target_period_end=TARGET_PERIOD_END,
                recorded_at=as_of,
                state="SIGNAL_SCORED",
                event=event.to_dict(),
                expectation_record_id=record.record_id,
                signal=signal,
                evidence=base_evidence,
            )

        if signal.bucket == "NO_SIGNAL":
            position = build_paper_position(
                signal,
                exchange_published_at_utc=event.provenance.exchange_published_at_utc or "",
                calendar=base_calendar,
                stock_bars=[],
                benchmark_bars=[],
                as_of_utc=_iso(as_of),
                price_reference=reference,
            )
            snapshot, created = self.observations.append(
                cohort_id=self.universe.cohort_id,
                symbol=symbol,
                target_period_end=TARGET_PERIOD_END,
                recorded_at=as_of,
                state="SKIPPED",
                reason=position.skip_or_pending_reason,
                event=event.to_dict(),
                expectation_record_id=record.record_id,
                signal=signal,
                paper_position=position,
                evidence=base_evidence,
            )
            return SymbolRunResult(
                symbol,
                "UPDATED" if created else "UNCHANGED",
                snapshot.state,
                snapshot.reason,
            )

        try:
            calendar = self.calendar_snapshot.trading_calendar_for_event(
                event.provenance.exchange_published_at_utc or ""
            )
        except CalendarSnapshotError as exc:
            snapshot, created = self.observations.append(
                cohort_id=self.universe.cohort_id,
                symbol=symbol,
                target_period_end=TARGET_PERIOD_END,
                recorded_at=as_of,
                state="CALENDAR_PENDING",
                reason=str(exc),
                event=event.to_dict(),
                expectation_record_id=record.record_id,
                signal=signal,
                evidence=base_evidence,
            )
            return SymbolRunResult(
                symbol,
                "UPDATED" if created else "UNCHANGED",
                snapshot.state,
                snapshot.reason,
            )

        entry_session, exit_session = calendar.schedule(
            event.provenance.exchange_published_at_utc or ""
        )
        entry_close = _parse_timestamp(entry_session.close_timestamp_utc)
        exit_close = _parse_timestamp(exit_session.close_timestamp_utc)
        stock_bars: list[PriceBar] = []
        benchmark_bars: list[PriceBar] = []

        if as_of >= entry_close:
            entry_day = date.fromisoformat(entry_session.session_date)
            status, entry_price, entry_artifact = self._equity_day(member, entry_day, as_of=as_of)
            if status == "ARCHIVE_UNAVAILABLE":
                return self._append_runner_pending(
                    member,
                    as_of=as_of,
                    event=event,
                    record_id=record.record_id,
                    signal=signal,
                    evidence=base_evidence,
                    reason="entry_udiff_archive_unavailable",
                )
            if entry_artifact is not None:
                base_evidence["entry_price_artifact"] = entry_artifact.to_dict()
            if entry_price is not None:
                entry_action_payload, entry_action_raw, entry_action_artifact = self._corporate_actions(
                    member,
                    from_date=publication_day,
                    to_date=entry_day,
                    as_of=as_of,
                )
                entry_basis = audit_price_basis_actions(
                    entry_action_payload,
                    raw_payload=entry_action_raw,
                    symbol=symbol,
                    start_date=publication_day,
                    end_date=entry_day,
                )
                base_evidence["entry_corporate_action_artifact"] = entry_action_artifact.to_dict()
                base_evidence["entry_price_basis"] = asdict(entry_basis)
                if entry_basis.status != "READY" or entry_basis.version is None:
                    return self._append_price_basis_unresolved(
                        member,
                        as_of=as_of,
                        event=event,
                        record_id=record.record_id,
                        signal=signal,
                        evidence=base_evidence,
                        reason="entry_price_basis_unresolved",
                    )
                stock_bars.append(
                    replace(
                        equity_price_bar(
                            entry_price,
                            source_url=entry_artifact.source_url,
                            source_timestamp_utc=entry_artifact.captured_at_utc,
                        ),
                        corporate_action_version=entry_basis.version,
                    )
                )

        if as_of >= exit_close:
            exit_day = date.fromisoformat(exit_session.session_date)
            status, exit_price, exit_artifact = self._equity_day(member, exit_day, as_of=as_of)
            if status == "ARCHIVE_UNAVAILABLE":
                return self._append_runner_pending(
                    member,
                    as_of=as_of,
                    event=event,
                    record_id=record.record_id,
                    signal=signal,
                    evidence=base_evidence,
                    reason="exit_udiff_archive_unavailable",
                )
            if exit_artifact is not None:
                base_evidence["exit_price_artifact"] = exit_artifact.to_dict()
            if exit_price is not None:
                exit_action_payload, exit_action_raw, exit_action_artifact = self._corporate_actions(
                    member,
                    from_date=publication_day,
                    to_date=exit_day,
                    as_of=as_of,
                )
                exit_basis = audit_price_basis_actions(
                    exit_action_payload,
                    raw_payload=exit_action_raw,
                    symbol=symbol,
                    start_date=publication_day,
                    end_date=exit_day,
                )
                base_evidence["exit_corporate_action_artifact"] = exit_action_artifact.to_dict()
                base_evidence["exit_price_basis"] = asdict(exit_basis)
                if exit_basis.status != "READY" or exit_basis.version is None:
                    return self._append_price_basis_unresolved(
                        member,
                        as_of=as_of,
                        event=event,
                        record_id=record.record_id,
                        signal=signal,
                        evidence=base_evidence,
                        reason="exit_price_basis_unresolved",
                    )
                stock_bars.append(
                    replace(
                        equity_price_bar(
                            exit_price,
                            source_url=exit_artifact.source_url,
                            source_timestamp_utc=exit_artifact.captured_at_utc,
                        ),
                        corporate_action_version=exit_basis.version,
                    )
                )
            benchmark_bars.extend(
                self._benchmark_window(
                    entry_day=date.fromisoformat(entry_session.session_date),
                    exit_day=exit_day,
                    as_of=as_of,
                    evidence=base_evidence,
                )
            )

        position = build_paper_position(
            signal,
            exchange_published_at_utc=event.provenance.exchange_published_at_utc or "",
            calendar=calendar,
            stock_bars=stock_bars,
            benchmark_bars=benchmark_bars,
            as_of_utc=_iso(as_of),
            price_reference=reference,
        )
        state = position.status
        snapshot, created = self.observations.append(
            cohort_id=self.universe.cohort_id,
            symbol=symbol,
            target_period_end=TARGET_PERIOD_END,
            recorded_at=as_of,
            state=state,
            reason=position.skip_or_pending_reason,
            event=event.to_dict(),
            expectation_record_id=record.record_id,
            signal=signal,
            paper_position=position,
            evidence=base_evidence,
        )
        return SymbolRunResult(
            symbol,
            "UPDATED" if created else "UNCHANGED",
            snapshot.state,
            snapshot.reason,
        )

    def _corporate_actions(
        self,
        member: UniverseMember,
        *,
        from_date: date,
        to_date: date,
        as_of: datetime,
    ) -> tuple[Any, bytes, MarketArtifact]:
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
        artifact = self.market_store.retain(
            raw,
            source_url=f"{self.client.CORPORATE_ACTION_ENDPOINT.url}?{query}",
            captured_at=as_of,
            suffix=".json",
        )
        return payload, raw, artifact

    def _equity_day(
        self,
        member: UniverseMember,
        session_date: date,
        *,
        as_of: datetime,
    ) -> tuple[str, Any | None, MarketArtifact | None]:
        url = udiff_url(session_date)
        try:
            raw = self.client.archive_bytes(url)
        except NSEAcquisitionError:
            return "ARCHIVE_UNAVAILABLE", None, None
        artifact = self.market_store.retain(
            raw, source_url=url, captured_at=as_of, suffix=".zip"
        )
        try:
            price = parse_udiff_equity(
                raw,
                symbol=member.symbol,
                session_date=session_date,
                series=member.series,
                expected_isin=member.isin,
            )
        except MarketDataMissingRow:
            return "MISSING_ROW", None, artifact
        return "READY", price, artifact

    def _benchmark_window(
        self,
        *,
        entry_day: date,
        exit_day: date,
        as_of: datetime,
        evidence: dict[str, Any],
    ) -> list[PriceBar]:
        bars: list[PriceBar] = []
        for role, day in (("entry", entry_day), ("exit", exit_day)):
            url = index_snapshot_url(day)
            try:
                raw = self.client.archive_bytes(url)
            except NSEAcquisitionError:
                evidence[f"benchmark_{role}_archive"] = {
                    "source_url": url,
                    "status": "ARCHIVE_UNAVAILABLE",
                }
                continue
            artifact = self.market_store.retain(
                raw, source_url=url, captured_at=as_of, suffix=".csv"
            )
            evidence[f"benchmark_{role}_archive"] = artifact.to_dict()
            for benchmark_id in ("nifty_50", "nifty_200_momentum_30"):
                try:
                    price = parse_index_snapshot(
                        raw, benchmark_id=benchmark_id, session_date=day
                    )
                except MarketDataMissingRow:
                    continue
                bars.append(
                    index_price_bar(
                        price,
                        source_url=artifact.source_url,
                        source_timestamp_utc=artifact.captured_at_utc,
                    )
                )
        return bars

    def _append_runner_pending(
        self,
        member: UniverseMember,
        *,
        as_of: datetime,
        event: FinancialEvent,
        record_id: str,
        signal: H002SignalResult,
        evidence: dict[str, Any],
        reason: str,
    ) -> SymbolRunResult:
        snapshot, created = self.observations.append(
            cohort_id=self.universe.cohort_id,
            symbol=member.symbol,
            target_period_end=TARGET_PERIOD_END,
            recorded_at=as_of,
            state="PENDING",
            reason=reason,
            event=event.to_dict(),
            expectation_record_id=record_id,
            signal=signal,
            evidence=evidence,
        )
        return SymbolRunResult(
            member.symbol,
            "UPDATED" if created else "UNCHANGED",
            snapshot.state,
            snapshot.reason,
        )

    def _append_price_basis_unresolved(
        self,
        member: UniverseMember,
        *,
        as_of: datetime,
        event: FinancialEvent,
        record_id: str,
        signal: H002SignalResult,
        evidence: dict[str, Any],
        reason: str,
    ) -> SymbolRunResult:
        snapshot, created = self.observations.append(
            cohort_id=self.universe.cohort_id,
            symbol=member.symbol,
            target_period_end=TARGET_PERIOD_END,
            recorded_at=as_of,
            state="PRICE_BASIS_UNRESOLVED",
            reason=reason,
            event=event.to_dict(),
            expectation_record_id=record_id,
            signal=signal,
            evidence=evidence,
        )
        return SymbolRunResult(
            member.symbol,
            "UPDATED" if created else "UNCHANGED",
            snapshot.state,
            snapshot.reason,
        )


def _run_summary(
    *,
    cohort_id: str,
    as_of: datetime,
    discovery_enabled: bool,
    member_count: int,
    results: list[SymbolRunResult],
    report_sha256: str,
) -> CohortRunSummary:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.outcome] = counts.get(result.outcome, 0) + 1
    provisional = CohortRunSummary(
        schema_version=1,
        run_sha256="",
        cohort_id=cohort_id,
        as_of_utc=_iso(as_of),
        discovery_enabled=discovery_enabled,
        member_count=member_count,
        outcome_counts=dict(sorted(counts.items())),
        results=tuple(results),
        report_sha256=report_sha256,
    )
    payload = provisional.to_dict()
    payload.pop("run_sha256", None)
    return CohortRunSummary(
        **{**provisional.__dict__, "run_sha256": _canonical_hash(payload)}
    )


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
