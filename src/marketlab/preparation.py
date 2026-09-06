from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from marketlab.events import EventParseError, EventStore, sha256_bytes
from marketlab.expectations import (
    FROZEN_SIGNAL_RULE_SHA256,
    ExpectationCaptureRecord,
    ExpectationLedgerError,
    ExpectationStore,
    FrozenExpectationManifest,
)
from marketlab.h002 import build_seasonal_expectation
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.universe import UniverseSnapshot

IST = ZoneInfo("Asia/Kolkata")

Outcome = Literal["CAPTURED", "UNCOVERED"]
ReasonCode = Literal[
    "CAPTURED",
    "DISCOVERY_FETCH_FAILED",
    "NO_BASELINE_FILING",
    "AMBIGUOUS_BASELINE_FILING",
    "CORPORATE_ACTION_FETCH_FAILED",
    "UNRESOLVED_CORPORATE_ACTION",
    "SOURCE_FETCH_FAILED",
    "SOURCE_PARSE_FAILED",
    "BASELINE_IDENTITY_MISMATCH",
    "EXPECTATION_CAPTURE_FAILED",
]


class PreparationError(ValueError):
    """Raised when a cohort preparation artifact cannot be produced deterministically."""


@dataclass(frozen=True)
class FilingCandidate:
    symbol: str
    company_name: str
    accounting_basis: str
    period_end: str
    exchange_available_at_utc: str
    source_url: str
    discovery_row_sha256: str
    revision_count: int


@dataclass(frozen=True)
class CorporateActionAnalysis:
    status: Literal["READY", "UNRESOLVED"]
    factor: float | None
    version: str | None
    relevant_actions: tuple[dict[str, str], ...]
    unresolved_subjects: tuple[str, ...]
    payload_sha256: str


@dataclass(frozen=True)
class PreparationAttempt:
    schema_version: int
    attempt_id: str
    cohort_id: str
    universe_snapshot_sha256: str
    symbol: str
    attempted_at_utc: str
    baseline_period_end: str
    target_period_end: str
    outcome: Outcome
    reason_code: ReasonCode
    detail: str | None
    discovery_payload_sha256: str | None
    discovery_row_sha256: str | None
    baseline_exchange_available_at_utc: str | None
    baseline_source_url: str | None
    baseline_source_sha256: str | None
    corporate_action_payload_sha256: str | None
    corporate_action_factor: float | None
    corporate_action_version: str | None
    expectation_id: str | None
    expectation_record_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PreparationReport:
    schema_version: int
    report_sha256: str
    cohort_id: str
    universe_snapshot_sha256: str
    generated_at_utc: str
    baseline_period_end: str
    member_count: int
    captured_count: int
    uncovered_count: int
    freeze_ready: bool
    reason_counts: dict[str, int]
    latest_attempts: tuple[PreparationAttempt, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["latest_attempts"] = [attempt.to_dict() for attempt in self.latest_attempts]
        return payload


@dataclass(frozen=True)
class FrozenExpectationBundle:
    schema_version: int
    bundle_sha256: str
    cohort_id: str
    universe_snapshot_sha256: str
    signal_rule_sha256: str
    generated_at_utc: str
    preparation_report_sha256: str
    expectation_manifest: FrozenExpectationManifest
    expectations: tuple[ExpectationCaptureRecord, ...]
    preparation_attempts: tuple[PreparationAttempt, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["expectation_manifest"] = self.expectation_manifest.to_dict()
        payload["expectations"] = [record.to_dict() for record in self.expectations]
        payload["preparation_attempts"] = [attempt.to_dict() for attempt in self.preparation_attempts]
        return payload


def _canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PreparationError("preparation payload must contain finite JSON values") from exc
    return hashlib.sha256(raw).hexdigest()


def _parse_date(value: Any, *, field: str) -> date:
    if not isinstance(value, str) or not value.strip():
        raise PreparationError(f"{field} is required")
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise PreparationError(f"unsupported {field}: {value}")


def _parse_exchange_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise PreparationError("baseline broadcast timestamp is required")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC)
    except ValueError:
        pass
    for fmt in (
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y %H:%M",
        "%d-%b-%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
    ):
        try:
            parsed = datetime.strptime(text, fmt).replace(tzinfo=IST)
            return parsed.astimezone(UTC)
        except ValueError:
            continue
    raise PreparationError(f"unsupported baseline broadcast timestamp: {value}")


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise PreparationError("timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _plus_one_year(value: date) -> date:
    try:
        return value.replace(year=value.year + 1)
    except ValueError as exc:
        raise PreparationError(f"cannot advance baseline period by one year: {value}") from exc


def _payload_rows(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise PreparationError("integrated filing payload does not contain a data list")
    return [row for row in rows if isinstance(row, dict)]


def select_baseline_candidate(
    payload: Any,
    *,
    symbol: str,
    baseline_period_end: str,
    accounting_basis: str = "Consolidated",
) -> FilingCandidate:
    wanted_period = _parse_date(baseline_period_end, field="baseline_period_end")
    wanted_symbol = symbol.strip().upper()
    wanted_basis = accounting_basis.strip().casefold()
    matches: list[tuple[datetime, dict[str, Any]]] = []
    for row in _payload_rows(payload):
        if str(row.get("type") or "").strip().casefold() != "integrated filing- financials":
            continue
        if str(row.get("symbol") or "").strip().upper() != wanted_symbol:
            continue
        if str(row.get("consolidated") or "").strip().casefold() != wanted_basis:
            continue
        try:
            period = _parse_date(row.get("qe_Date"), field="qe_Date")
            available = _parse_exchange_timestamp(row.get("broadcast_Date"))
        except PreparationError:
            continue
        if period != wanted_period:
            continue
        source_url = str(row.get("xbrl") or "").strip()
        if not source_url:
            continue
        matches.append((available, row))
    if not matches:
        raise PreparationError("NO_BASELINE_FILING")
    matches.sort(key=lambda item: (item[0], str(item[1].get("xbrl") or "")))
    latest_time = matches[-1][0]
    latest = [row for timestamp, row in matches if timestamp == latest_time]
    unique_urls = {str(row.get("xbrl") or "").strip() for row in latest}
    if len(unique_urls) != 1:
        raise PreparationError("AMBIGUOUS_BASELINE_FILING")
    row = latest[-1]
    return FilingCandidate(
        symbol=wanted_symbol,
        company_name=str(row.get("cmName") or "").strip(),
        accounting_basis=accounting_basis,
        period_end=wanted_period.isoformat(),
        exchange_available_at_utc=_iso_utc(latest_time),
        source_url=next(iter(unique_urls)),
        discovery_row_sha256=_canonical_hash(row),
        revision_count=len(matches),
    )


def _action_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    rows = payload.get("data") if isinstance(payload, dict) else None
    if rows is None and isinstance(payload, dict):
        rows = payload.get("records")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _parse_ratio(subject: str) -> tuple[float, float] | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)", subject)
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


def _parse_face_change(subject: str) -> tuple[float, float] | None:
    match = re.search(
        r"from\D{0,20}(\d+(?:\.\d+)?)\D{0,80}to\D{0,20}(\d+(?:\.\d+)?)",
        subject,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


def analyze_eps_basis_actions(
    payload: Any,
    *,
    raw_payload: bytes,
    symbol: str,
    baseline_period_end: str,
    as_of_utc: str,
) -> CorporateActionAnalysis:
    start = _parse_date(baseline_period_end, field="baseline_period_end")
    try:
        as_of = datetime.fromisoformat(as_of_utc.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PreparationError(f"invalid as_of_utc: {as_of_utc}") from exc
    if as_of.tzinfo is None:
        raise PreparationError("as_of_utc must include timezone")
    end = as_of.astimezone(IST).date()
    factor = 1.0
    relevant: list[dict[str, str]] = []
    unresolved: list[str] = []
    for row in _action_rows(payload):
        if str(row.get("symbol") or "").strip().upper() != symbol.upper():
            continue
        subject = str(row.get("subject") or row.get("purpose") or "").strip()
        if not subject:
            continue
        lowered = subject.casefold()
        share_changing = any(
            token in lowered
            for token in ("bonus", "split", "sub-division", "subdivision", "consolidation", "rights")
        )
        if not share_changing:
            continue
        ex_raw = row.get("exDate") or row.get("ex_date")
        try:
            ex_date = _parse_date(ex_raw, field="corporate action exDate")
        except PreparationError:
            unresolved.append(subject)
            continue
        if not (start < ex_date <= end):
            continue
        action = {"subject": subject, "ex_date": ex_date.isoformat()}
        if "bonus" in lowered:
            ratio = _parse_ratio(subject)
            if ratio is None or ratio[1] <= 0:
                unresolved.append(subject)
                continue
            bonus, existing = ratio
            if bonus < 0 or existing <= 0:
                unresolved.append(subject)
                continue
            factor *= existing / (existing + bonus)
            action["kind"] = "BONUS"
            action["factor"] = format(existing / (existing + bonus), ".17g")
        elif any(token in lowered for token in ("split", "sub-division", "subdivision", "consolidation")):
            change = _parse_face_change(subject)
            if change is None or change[0] <= 0 or change[1] <= 0:
                unresolved.append(subject)
                continue
            old_face, new_face = change
            factor *= new_face / old_face
            action["kind"] = "FACE_VALUE_CHANGE"
            action["factor"] = format(new_face / old_face, ".17g")
        else:
            unresolved.append(subject)
            continue
        relevant.append(action)
    payload_hash = sha256_bytes(raw_payload)
    if unresolved:
        return CorporateActionAnalysis(
            status="UNRESOLVED",
            factor=None,
            version=None,
            relevant_actions=tuple(relevant),
            unresolved_subjects=tuple(sorted(set(unresolved))),
            payload_sha256=payload_hash,
        )
    if not math.isfinite(factor) or factor <= 0:
        raise PreparationError("computed corporate-action factor is invalid")
    version_payload = {
        "schema": 1,
        "symbol": symbol.upper(),
        "baseline_period_end": start.isoformat(),
        "as_of_date": end.isoformat(),
        "relevant_actions": relevant,
    }
    return CorporateActionAnalysis(
        status="READY",
        factor=factor,
        version=f"EPSCA-{_canonical_hash(version_payload)[:20]}",
        relevant_actions=tuple(relevant),
        unresolved_subjects=(),
        payload_sha256=payload_hash,
    )


def _attempt_digest(attempt: PreparationAttempt) -> str:
    payload = attempt.to_dict()
    payload.pop("attempt_id", None)
    return _canonical_hash(payload)


class PreparationStore:
    """Append-only cohort-preparation evidence, separate from the expectation ledger."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _root(self, cohort_id: str) -> Path:
        key = hashlib.sha256(cohort_id.encode("utf-8")).hexdigest()[:20]
        return self.root / "h002-preparation" / key

    def _attempt_dir(self, cohort_id: str, symbol: str) -> Path:
        return self._root(cohort_id) / "attempts" / symbol.upper()

    def append(self, attempt: PreparationAttempt) -> None:
        path = self._attempt_dir(attempt.cohort_id, attempt.symbol) / f"{attempt.attempt_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = (json.dumps(attempt.to_dict(), indent=2, sort_keys=True) + "\n").encode()
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            if path.read_bytes() != content:
                raise PreparationError("preparation attempt id collision")
            return
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

    def attempts(self, cohort_id: str, symbol: str) -> tuple[PreparationAttempt, ...]:
        root = self._attempt_dir(cohort_id, symbol)
        if not root.exists():
            return ()
        attempts: list[PreparationAttempt] = []
        for path in sorted(root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            attempt = PreparationAttempt(**payload)
            if _attempt_digest(attempt) != attempt.attempt_id:
                raise PreparationError(f"preparation attempt hash mismatch: {path}")
            attempts.append(attempt)
        return tuple(sorted(attempts, key=lambda item: (item.attempted_at_utc, item.attempt_id)))

    def latest(self, cohort_id: str, symbol: str) -> PreparationAttempt | None:
        attempts = self.attempts(cohort_id, symbol)
        return attempts[-1] if attempts else None


def _make_attempt(
    *,
    universe: UniverseSnapshot,
    symbol: str,
    attempted_at_utc: str,
    baseline_period_end: str,
    outcome: Outcome,
    reason_code: ReasonCode,
    detail: str | None = None,
    discovery_payload_sha256: str | None = None,
    candidate: FilingCandidate | None = None,
    source_sha256: str | None = None,
    actions: CorporateActionAnalysis | None = None,
    record: ExpectationCaptureRecord | None = None,
) -> PreparationAttempt:
    baseline = _parse_date(baseline_period_end, field="baseline_period_end")
    provisional = PreparationAttempt(
        schema_version=1,
        attempt_id="",
        cohort_id=universe.cohort_id,
        universe_snapshot_sha256=universe.sha256,
        symbol=symbol.upper(),
        attempted_at_utc=attempted_at_utc,
        baseline_period_end=baseline.isoformat(),
        target_period_end=_plus_one_year(baseline).isoformat(),
        outcome=outcome,
        reason_code=reason_code,
        detail=detail,
        discovery_payload_sha256=discovery_payload_sha256,
        discovery_row_sha256=None if candidate is None else candidate.discovery_row_sha256,
        baseline_exchange_available_at_utc=(
            None if candidate is None else candidate.exchange_available_at_utc
        ),
        baseline_source_url=None if candidate is None else candidate.source_url,
        baseline_source_sha256=source_sha256,
        corporate_action_payload_sha256=None if actions is None else actions.payload_sha256,
        corporate_action_factor=None if actions is None else actions.factor,
        corporate_action_version=None if actions is None else actions.version,
        expectation_id=None if record is None else record.expectation.expectation_id,
        expectation_record_id=None if record is None else record.record_id,
    )
    return PreparationAttempt(
        **{**provisional.__dict__, "attempt_id": _attempt_digest(provisional)}
    )


def prepare_symbol(
    client: NSEClient,
    *,
    universe: UniverseSnapshot,
    symbol: str,
    baseline_period_end: str,
    attempted_at: datetime,
    event_store: EventStore,
    expectation_store: ExpectationStore,
    preparation_store: PreparationStore,
) -> PreparationAttempt:
    """Acquire and freeze one company's FY27-Q2 H002 expectation without guessing."""
    attempted_at_utc = _iso_utc(attempted_at)
    discovery_hash: str | None = None
    candidate: FilingCandidate | None = None
    actions: CorporateActionAnalysis | None = None
    source_hash: str | None = None

    def finish(reason: ReasonCode, detail: str | None = None) -> PreparationAttempt:
        attempt = _make_attempt(
            universe=universe,
            symbol=symbol,
            attempted_at_utc=attempted_at_utc,
            baseline_period_end=baseline_period_end,
            outcome="UNCOVERED",
            reason_code=reason,
            detail=detail,
            discovery_payload_sha256=discovery_hash,
            candidate=candidate,
            source_sha256=source_hash,
            actions=actions,
        )
        preparation_store.append(attempt)
        return attempt

    try:
        payload, discovery_raw = client.integrated_financial_filings_with_raw(symbol)
        discovery_hash = sha256_bytes(discovery_raw)
    except NSEAcquisitionError as exc:
        return finish("DISCOVERY_FETCH_FAILED", str(exc))
    try:
        candidate = select_baseline_candidate(
            payload,
            symbol=symbol,
            baseline_period_end=baseline_period_end,
            accounting_basis="Consolidated",
        )
    except PreparationError as exc:
        reason = str(exc)
        if reason not in {"NO_BASELINE_FILING", "AMBIGUOUS_BASELINE_FILING"}:
            reason = "AMBIGUOUS_BASELINE_FILING"
        return finish(reason)  # type: ignore[arg-type]

    baseline = _parse_date(baseline_period_end, field="baseline_period_end")
    try:
        action_payload, action_raw = client.corporate_actions_with_raw(
            symbol,
            from_date=(baseline.replace(day=baseline.day) ).strftime("%d-%m-%Y"),
            to_date=attempted_at.astimezone(IST).strftime("%d-%m-%Y"),
        )
    except NSEAcquisitionError as exc:
        return finish("CORPORATE_ACTION_FETCH_FAILED", str(exc))
    actions = analyze_eps_basis_actions(
        action_payload,
        raw_payload=action_raw,
        symbol=symbol,
        baseline_period_end=baseline_period_end,
        as_of_utc=attempted_at_utc,
    )
    if actions.status != "READY" or actions.factor is None or actions.version is None:
        return finish(
            "UNRESOLVED_CORPORATE_ACTION",
            "; ".join(actions.unresolved_subjects) or "unresolved EPS-basis action",
        )
    try:
        source_raw = client.archive_bytes(candidate.source_url)
        source_hash = sha256_bytes(source_raw)
    except NSEAcquisitionError as exc:
        return finish("SOURCE_FETCH_FAILED", str(exc))
    try:
        baseline_event, _ = event_store.reconstruct_bytes(
            source_raw,
            source_url=candidate.source_url,
            captured_at=attempted_at,
        )
    except (EventParseError, UnicodeDecodeError, OSError) as exc:
        return finish("SOURCE_PARSE_FAILED", str(exc))
    try:
        parsed_period = _parse_date(
            baseline_event.reporting_period_end, field="baseline reporting_period_end"
        )
    except PreparationError as exc:
        return finish("BASELINE_IDENTITY_MISMATCH", str(exc))
    if (
        baseline_event.symbol.upper() != symbol.upper()
        or parsed_period != baseline
        or baseline_event.accounting_basis.strip().casefold() != "consolidated"
    ):
        return finish("BASELINE_IDENTITY_MISMATCH", "parsed filing identity differs from discovery")
    target_period = _plus_one_year(parsed_period)
    try:
        expectation = build_seasonal_expectation(
            baseline_event,
            target_period_end=target_period.isoformat(),
            target_quarter=baseline_event.reporting_quarter or "",
            target_accounting_basis=baseline_event.accounting_basis,
            baseline_available_at_utc=candidate.exchange_available_at_utc,
            expectation_as_of_utc=attempted_at_utc,
            corporate_action_factor=actions.factor,
            corporate_action_version=actions.version,
        )
        record, _ = expectation_store.capture(
            expectation,
            universe=universe,
            signal_rule_sha256=FROZEN_SIGNAL_RULE_SHA256,
        )
    except (ExpectationLedgerError, ValueError) as exc:
        return finish("EXPECTATION_CAPTURE_FAILED", str(exc))
    attempt = _make_attempt(
        universe=universe,
        symbol=symbol,
        attempted_at_utc=attempted_at_utc,
        baseline_period_end=baseline_period_end,
        outcome="CAPTURED",
        reason_code="CAPTURED",
        discovery_payload_sha256=discovery_hash,
        candidate=candidate,
        source_sha256=source_hash,
        actions=actions,
        record=record,
    )
    preparation_store.append(attempt)
    return attempt


def build_preparation_report(
    *,
    universe: UniverseSnapshot,
    preparation_store: PreparationStore,
    baseline_period_end: str,
    generated_at: datetime,
) -> PreparationReport:
    latest: list[PreparationAttempt] = []
    for member in universe.members:
        attempt = preparation_store.latest(universe.cohort_id, member.symbol)
        if attempt is None:
            attempt = _make_attempt(
                universe=universe,
                symbol=member.symbol,
                attempted_at_utc=_iso_utc(generated_at),
                baseline_period_end=baseline_period_end,
                outcome="UNCOVERED",
                reason_code="DISCOVERY_FETCH_FAILED",
                detail="NO_ATTEMPT_RECORDED",
            )
        latest.append(attempt)
    latest.sort(key=lambda item: item.symbol)
    captured = sum(attempt.outcome == "CAPTURED" for attempt in latest)
    reason_counts = dict(sorted(Counter(item.reason_code for item in latest).items()))
    provisional = PreparationReport(
        schema_version=1,
        report_sha256="",
        cohort_id=universe.cohort_id,
        universe_snapshot_sha256=universe.sha256,
        generated_at_utc=_iso_utc(generated_at),
        baseline_period_end=_parse_date(baseline_period_end, field="baseline_period_end").isoformat(),
        member_count=len(universe.members),
        captured_count=captured,
        uncovered_count=len(universe.members) - captured,
        freeze_ready=captured == len(universe.members),
        reason_counts=reason_counts,
        latest_attempts=tuple(latest),
    )
    payload = provisional.to_dict()
    payload.pop("report_sha256", None)
    return PreparationReport(
        **{**provisional.__dict__, "report_sha256": _canonical_hash(payload)}
    )


def freeze_complete_bundle(
    *,
    universe: UniverseSnapshot,
    expectation_store: ExpectationStore,
    preparation_store: PreparationStore,
    baseline_period_end: str,
    generated_at: datetime,
) -> FrozenExpectationBundle:
    """Freeze only complete 100-company coverage. No discretionary omissions in v1."""
    report = build_preparation_report(
        universe=universe,
        preparation_store=preparation_store,
        baseline_period_end=baseline_period_end,
        generated_at=generated_at,
    )
    if not report.freeze_ready:
        raise PreparationError(
            f"cohort is not freeze-ready: {report.captured_count}/{report.member_count} captured"
        )
    manifest, _ = expectation_store.freeze_manifest(
        universe=universe,
        signal_rule_sha256=FROZEN_SIGNAL_RULE_SHA256,
    )
    if manifest.uncovered_symbols:
        raise PreparationError("complete-coverage bundle cannot contain uncovered symbols")
    records = tuple(
        expectation_store.load_record(manifest.cohort_id, entry.slot_id)
        for entry in manifest.records
    )
    attempts = tuple(report.latest_attempts)
    by_symbol = {attempt.symbol: attempt for attempt in attempts}
    for entry in manifest.records:
        attempt = by_symbol.get(entry.symbol)
        if (
            attempt is None
            or attempt.outcome != "CAPTURED"
            or attempt.expectation_record_id != entry.record_id
            or attempt.baseline_source_sha256 is None
            or attempt.discovery_payload_sha256 is None
            or attempt.corporate_action_payload_sha256 is None
        ):
            raise PreparationError(f"incomplete provenance for {entry.symbol}")
    provisional = FrozenExpectationBundle(
        schema_version=1,
        bundle_sha256="",
        cohort_id=universe.cohort_id,
        universe_snapshot_sha256=universe.sha256,
        signal_rule_sha256=FROZEN_SIGNAL_RULE_SHA256,
        generated_at_utc=_iso_utc(generated_at),
        preparation_report_sha256=report.report_sha256,
        expectation_manifest=manifest,
        expectations=records,
        preparation_attempts=attempts,
    )
    payload = provisional.to_dict()
    payload.pop("bundle_sha256", None)
    return FrozenExpectationBundle(
        **{**provisional.__dict__, "bundle_sha256": _canonical_hash(payload)}
    )


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
