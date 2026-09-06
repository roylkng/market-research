from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np

from marketlab.execution import PaperPosition
from marketlab.h002 import H002SignalResult
from marketlab.preparation import _parse_exchange_timestamp

RUNNER_RULE_ID = "H002-D001"
RUNNER_RULE_SHA256 = "fdf174f2a0e848356e29cff3ba3fdc8f7f674836a77c4ef6065e5ca72360d238"

ObservationState = Literal[
    "EVENT_CAPTURED",
    "CALENDAR_PENDING",
    "PRICE_REFERENCE_PENDING",
    "PRICE_BASIS_UNRESOLVED",
    "SIGNAL_SCORED",
    "PENDING",
    "SKIPPED",
    "UNRESOLVED_EXIT",
    "COMPLETED",
    "ERROR",
]


class ProspectiveError(ValueError):
    """Raised when H002-D prospective state cannot be recorded deterministically."""


@dataclass(frozen=True)
class ResultCandidate:
    symbol: str
    accounting_basis: str
    period_end: str
    exchange_published_at_utc: str
    source_url: str
    discovery_row_sha256: str


@dataclass(frozen=True)
class ResultSelection:
    first: ResultCandidate
    revisions: tuple[ResultCandidate, ...]


@dataclass(frozen=True)
class ObservationSnapshot:
    schema_version: int
    snapshot_id: str
    state_hash: str
    observation_id: str
    sequence: int
    parent_snapshot_id: str | None
    runner_rule_id: str
    runner_rule_sha256: str
    cohort_id: str
    symbol: str
    target_period_end: str
    recorded_at_utc: str
    state: ObservationState
    reason: str | None
    event: dict[str, Any] | None
    expectation_record_id: str | None
    signal: dict[str, Any] | None
    paper_position: dict[str, Any] | None
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProspectiveReport:
    schema_version: int
    report_sha256: str
    runner_rule_id: str
    cohort_id: str
    generated_at_utc: str
    paper_only: bool
    live_capital_allowed: bool
    observation_count: int
    latest_state_counts: dict[str, int]
    signal_bucket_counts: dict[str, int]
    skipped_reason_counts: dict[str, int]
    completed_count: int
    completed_statistics: dict[str, Any]
    by_bucket: dict[str, Any]
    cost_sensitivity: dict[str, Any]
    mae_mfe: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_hash(payload: Any) -> str:
    try:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    except (TypeError, ValueError) as exc:
        raise ProspectiveError("prospective payload must contain finite JSON values") from exc
    return hashlib.sha256(encoded).hexdigest()


def validate_runner_rule_document(document: dict[str, Any]) -> str:
    if not isinstance(document, dict):
        raise ProspectiveError("H002-D runner rule root must be a mapping")
    declared = document.get("sha256")
    if not isinstance(declared, str) or len(declared) != 64:
        raise ProspectiveError("H002-D runner rule must declare SHA-256")
    unsigned = dict(document)
    unsigned.pop("sha256", None)
    actual = _canonical_hash(unsigned)
    if actual != declared:
        raise ProspectiveError(
            f"H002-D runner rule hash mismatch: declared={declared}, recomputed={actual}"
        )
    if document.get("id") != RUNNER_RULE_ID or declared != RUNNER_RULE_SHA256:
        raise ProspectiveError("unexpected H002-D runner rule identity")
    if document.get("status") != "FROZEN":
        raise ProspectiveError("H002-D runner rule must remain FROZEN")
    if document.get("live_capital") is not False:
        raise ProspectiveError("H002-D runner rule must keep live_capital: false")
    return actual


def load_and_validate_runner_rule(path: str | Path) -> dict[str, Any]:
    try:
        import yaml

        with Path(path).open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
    except OSError as exc:
        raise ProspectiveError(f"could not read H002-D runner rule {path}: {exc}") from exc
    validate_runner_rule_document(document)
    return document


def select_first_result_candidate(
    payload: Any,
    *,
    symbol: str,
    target_period_end: str,
    accounting_basis: str,
) -> ResultSelection | None:
    target = date.fromisoformat(target_period_end)
    wanted_symbol = symbol.strip().upper()
    wanted_basis = accounting_basis.strip().casefold()
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ProspectiveError("NSE result discovery payload does not contain a data list")

    matches: list[ResultCandidate] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("type") or "").strip().casefold() != "integrated filing- financials":
            continue
        if str(row.get("symbol") or "").strip().upper() != wanted_symbol:
            continue
        if str(row.get("consolidated") or "").strip().casefold() != wanted_basis:
            continue
        try:
            period = _parse_date(row.get("qe_Date"))
        except ProspectiveError:
            continue
        if period != target:
            continue
        source_url = str(row.get("xbrl") or "").strip()
        if not source_url:
            continue
        timestamp = _official_timestamp(row)
        matches.append(
            ResultCandidate(
                symbol=wanted_symbol,
                accounting_basis=accounting_basis,
                period_end=target.isoformat(),
                exchange_published_at_utc=timestamp.astimezone(UTC).isoformat().replace(
                    "+00:00", "Z"
                ),
                source_url=source_url,
                discovery_row_sha256=_canonical_hash(row),
            )
        )

    if not matches:
        return None
    matches.sort(key=lambda item: (item.exchange_published_at_utc, item.source_url))
    earliest = matches[0].exchange_published_at_utc
    earliest_urls = {
        item.source_url for item in matches if item.exchange_published_at_utc == earliest
    }
    if len(earliest_urls) != 1:
        raise ProspectiveError(
            f"ambiguous first official result filing for {wanted_symbol}: {sorted(earliest_urls)}"
        )
    first = next(item for item in matches if item.exchange_published_at_utc == earliest)
    revisions = tuple(item for item in matches if item.source_url != first.source_url)
    return ResultSelection(first=first, revisions=revisions)


def _official_timestamp(row: dict[str, Any]) -> datetime:
    last_error: Exception | None = None
    for key in ("broadcast_Date", "revisedDate", "creationDate"):
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return _parse_exchange_timestamp(value)
        except Exception as exc:
            last_error = exc
    raise ProspectiveError(
        f"result discovery row has no parseable official timestamp: {last_error}"
    )


def _parse_date(value: Any) -> date:
    if not isinstance(value, str):
        raise ProspectiveError("result period date must be a string")
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise ProspectiveError(f"unsupported result period date: {value}")


def _observation_id(cohort_id: str, symbol: str, target_period_end: str) -> str:
    return _canonical_hash(
        {
            "runner_rule_id": RUNNER_RULE_ID,
            "cohort_id": cohort_id,
            "symbol": symbol.upper(),
            "target_period_end": target_period_end,
        }
    )[:24]


def _snapshot_payload_for_state(snapshot: ObservationSnapshot) -> dict[str, Any]:
    payload = snapshot.to_dict()
    for key in (
        "snapshot_id",
        "state_hash",
        "sequence",
        "parent_snapshot_id",
        "recorded_at_utc",
    ):
        payload.pop(key, None)
    return payload


def _snapshot_digest(snapshot: ObservationSnapshot) -> str:
    payload = snapshot.to_dict()
    payload.pop("snapshot_id", None)
    return _canonical_hash(payload)


class ObservationStore:
    """Append-only, hash-chained H002-D observation snapshots."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _observation_root(self, cohort_id: str, symbol: str, target_period_end: str) -> Path:
        observation_id = _observation_id(cohort_id, symbol, target_period_end)
        return self.root / "observations" / observation_id

    def snapshots(
        self, cohort_id: str, symbol: str, target_period_end: str
    ) -> tuple[ObservationSnapshot, ...]:
        root = self._observation_root(cohort_id, symbol, target_period_end)
        if not root.exists():
            return ()
        snapshots: list[ObservationSnapshot] = []
        for path in sorted(root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                snapshot = ObservationSnapshot(**payload)
            except (OSError, json.JSONDecodeError, TypeError) as exc:
                raise ProspectiveError(f"invalid observation snapshot {path}: {exc}") from exc
            if snapshot.schema_version != 1:
                raise ProspectiveError(f"unsupported observation schema: {snapshot.schema_version}")
            if (
                snapshot.runner_rule_id != RUNNER_RULE_ID
                or snapshot.runner_rule_sha256 != RUNNER_RULE_SHA256
            ):
                raise ProspectiveError("observation snapshot runner-rule identity mismatch")
            if _snapshot_digest(snapshot) != snapshot.snapshot_id:
                raise ProspectiveError(f"observation snapshot hash mismatch: {path}")
            if _canonical_hash(_snapshot_payload_for_state(snapshot)) != snapshot.state_hash:
                raise ProspectiveError(f"observation state hash mismatch: {path}")
            snapshots.append(snapshot)
        snapshots.sort(key=lambda item: item.sequence)
        expected_parent: str | None = None
        for index, snapshot in enumerate(snapshots, start=1):
            if snapshot.sequence != index or snapshot.parent_snapshot_id != expected_parent:
                raise ProspectiveError("observation snapshot chain is not contiguous")
            expected_parent = snapshot.snapshot_id
        return tuple(snapshots)

    def latest(
        self, cohort_id: str, symbol: str, target_period_end: str
    ) -> ObservationSnapshot | None:
        values = self.snapshots(cohort_id, symbol, target_period_end)
        return values[-1] if values else None

    def append(
        self,
        *,
        cohort_id: str,
        symbol: str,
        target_period_end: str,
        recorded_at: datetime,
        state: ObservationState,
        reason: str | None = None,
        event: dict[str, Any] | None = None,
        expectation_record_id: str | None = None,
        signal: H002SignalResult | dict[str, Any] | None = None,
        paper_position: PaperPosition | dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> tuple[ObservationSnapshot, bool]:
        if recorded_at.tzinfo is None:
            raise ProspectiveError("observation recorded_at must include timezone")
        symbol = symbol.upper()
        try:
            date.fromisoformat(target_period_end)
        except ValueError as exc:
            raise ProspectiveError("target_period_end must be ISO date") from exc
        latest = self.latest(cohort_id, symbol, target_period_end)
        signal_payload = signal.to_dict() if hasattr(signal, "to_dict") else signal
        position_payload = (
            paper_position.to_dict() if hasattr(paper_position, "to_dict") else paper_position
        )
        provisional = ObservationSnapshot(
            schema_version=1,
            snapshot_id="",
            state_hash="",
            observation_id=_observation_id(cohort_id, symbol, target_period_end),
            sequence=1 if latest is None else latest.sequence + 1,
            parent_snapshot_id=None if latest is None else latest.snapshot_id,
            runner_rule_id=RUNNER_RULE_ID,
            runner_rule_sha256=RUNNER_RULE_SHA256,
            cohort_id=cohort_id,
            symbol=symbol,
            target_period_end=target_period_end,
            recorded_at_utc=recorded_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            state=state,
            reason=reason,
            event=event,
            expectation_record_id=expectation_record_id,
            signal=signal_payload,
            paper_position=position_payload,
            evidence=dict(evidence or {}),
        )
        state_hash = _canonical_hash(_snapshot_payload_for_state(provisional))
        if latest is not None and latest.state_hash == state_hash:
            return latest, False
        with_state = ObservationSnapshot(**{**provisional.__dict__, "state_hash": state_hash})
        snapshot = ObservationSnapshot(
            **{**with_state.__dict__, "snapshot_id": _snapshot_digest(with_state)}
        )
        root = self._observation_root(cohort_id, symbol, target_period_end)
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{snapshot.sequence:04d}-{snapshot.snapshot_id}.json"
        content = (json.dumps(snapshot.to_dict(), indent=2, sort_keys=True) + "\n").encode()
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            if path.read_bytes() != content:
                raise ProspectiveError("observation snapshot identity collision")
            return snapshot, False
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return snapshot, True

    def latest_all(self) -> tuple[ObservationSnapshot, ...]:
        observations_root = self.root / "observations"
        if not observations_root.exists():
            return ()
        latest: list[ObservationSnapshot] = []
        for root in sorted(observations_root.iterdir()):
            if not root.is_dir():
                continue
            paths = sorted(root.glob("*.json"))
            if not paths:
                continue
            payload = json.loads(paths[-1].read_text(encoding="utf-8"))
            snapshot = ObservationSnapshot(**payload)
            if _snapshot_digest(snapshot) != snapshot.snapshot_id:
                raise ProspectiveError(f"observation snapshot hash mismatch: {paths[-1]}")
            latest.append(snapshot)
        return tuple(sorted(latest, key=lambda item: item.symbol))


def build_prospective_report(
    store: ObservationStore,
    *,
    cohort_id: str,
    generated_at: datetime,
) -> ProspectiveReport:
    if generated_at.tzinfo is None:
        raise ProspectiveError("report generated_at must include timezone")
    latest = [item for item in store.latest_all() if item.cohort_id == cohort_id]
    state_counts = dict(sorted(Counter(item.state for item in latest).items()))
    signals = [item.signal for item in latest if isinstance(item.signal, dict)]
    bucket_counts = dict(
        sorted(
            Counter(
                str(signal.get("bucket"))
                for signal in signals
                if signal.get("bucket")
            ).items()
        )
    )
    skipped_reasons = dict(
        sorted(
            Counter(
                item.reason or "unspecified"
                for item in latest
                if item.state
                in {"SKIPPED", "UNRESOLVED_EXIT", "ERROR", "PRICE_BASIS_UNRESOLVED"}
            ).items()
        )
    )
    completed = [
        item
        for item in latest
        if isinstance(item.paper_position, dict)
        and item.paper_position.get("status") == "COMPLETED"
    ]

    gross = np.array(
        [float(item.paper_position["gross_return_pct"]) for item in completed],
        dtype=float,
    )
    nifty_excess: list[float] = []
    momentum_excess: list[float] = []
    costs: defaultdict[str, list[float]] = defaultdict(list)
    by_bucket_values: defaultdict[str, list[tuple[float, float | None]]] = defaultdict(list)
    for item in completed:
        position = item.paper_position or {}
        benchmark_map = {
            row.get("benchmark_id"): row
            for row in position.get("benchmarks", [])
            if isinstance(row, dict)
        }
        n50 = benchmark_map.get("nifty_50")
        mom = benchmark_map.get("nifty_200_momentum_30")
        n50_excess = (
            float(n50["excess_return_pct"])
            if isinstance(n50, dict) and n50.get("excess_return_pct") is not None
            else None
        )
        mom_excess = (
            float(mom["excess_return_pct"])
            if isinstance(mom, dict) and mom.get("excess_return_pct") is not None
            else None
        )
        if n50_excess is not None:
            nifty_excess.append(n50_excess)
        if mom_excess is not None:
            momentum_excess.append(mom_excess)
        for bps, value in (position.get("cost_stressed_return_pct") or {}).items():
            costs[str(bps)].append(float(value))
        bucket = str((item.signal or {}).get("bucket") or "UNKNOWN")
        by_bucket_values[bucket].append((float(position["gross_return_pct"]), n50_excess))

    completed_stats = _completed_stats(gross, nifty_excess, momentum_excess)
    by_bucket: dict[str, Any] = {}
    for bucket, values in sorted(by_bucket_values.items()):
        raw_values = np.array([value[0] for value in values], dtype=float)
        excess_values = [value[1] for value in values if value[1] is not None]
        by_bucket[bucket] = {
            "n": len(values),
            "mean_raw_return_pct": float(raw_values.mean()) if len(raw_values) else None,
            "median_raw_return_pct": float(np.median(raw_values)) if len(raw_values) else None,
            "mean_nifty50_excess_pct": float(np.mean(excess_values)) if excess_values else None,
            "nifty50_beat_rate": (
                float(np.mean(np.array(excess_values) > 0)) if excess_values else None
            ),
        }

    cost_summary = {
        bps: {
            "n": len(values),
            "mean_return_pct": float(np.mean(values)) if values else None,
            "median_return_pct": float(np.median(values)) if values else None,
        }
        for bps, values in sorted(costs.items(), key=lambda item: int(item[0]))
    }
    provisional = ProspectiveReport(
        schema_version=1,
        report_sha256="",
        runner_rule_id=RUNNER_RULE_ID,
        cohort_id=cohort_id,
        generated_at_utc=generated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        paper_only=True,
        live_capital_allowed=False,
        observation_count=len(latest),
        latest_state_counts=state_counts,
        signal_bucket_counts=bucket_counts,
        skipped_reason_counts=skipped_reasons,
        completed_count=len(completed),
        completed_statistics=completed_stats,
        by_bucket=by_bucket,
        cost_sensitivity=cost_summary,
        mae_mfe={
            "status": "NOT_CAPTURED_V1",
            "reason": (
                "H002-D v1 retains exact entry/exit sources; intraday path data is not inferred"
            ),
        },
    )
    payload = provisional.to_dict()
    payload.pop("report_sha256", None)
    return ProspectiveReport(
        **{**provisional.__dict__, "report_sha256": _canonical_hash(payload)}
    )


def _completed_stats(
    gross: np.ndarray,
    nifty_excess: list[float],
    momentum_excess: list[float],
) -> dict[str, Any]:
    if len(gross) == 0:
        return {
            "n": 0,
            "mean_raw_return_pct": None,
            "median_raw_return_pct": None,
            "mean_nifty50_excess_pct": None,
            "median_nifty50_excess_pct": None,
            "nifty50_beat_rate": None,
            "bootstrap_95_ci_mean_nifty50_excess_pct": None,
            "winner_concentration": None,
            "mean_momentum_excess_pct": None,
        }
    excess = np.array(nifty_excess, dtype=float)
    bootstrap = None
    if len(excess) >= 2:
        rng = np.random.default_rng(7)
        samples = np.empty(10_000, dtype=float)
        for index in range(len(samples)):
            samples[index] = rng.choice(excess, size=len(excess), replace=True).mean()
        bootstrap = [float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))]
    winner = None
    if len(excess) > 2:
        ordered = np.sort(excess)[::-1]
        top_n = min(2, len(ordered) - 1)
        winner = {
            "top_n": top_n,
            "full_mean": float(ordered.mean()),
            "mean_without_top_n": float(ordered[top_n:].mean()),
        }
    return {
        "n": len(gross),
        "mean_raw_return_pct": float(gross.mean()),
        "median_raw_return_pct": float(np.median(gross)),
        "mean_nifty50_excess_pct": float(excess.mean()) if len(excess) else None,
        "median_nifty50_excess_pct": float(np.median(excess)) if len(excess) else None,
        "nifty50_beat_rate": float(np.mean(excess > 0)) if len(excess) else None,
        "bootstrap_95_ci_mean_nifty50_excess_pct": bootstrap,
        "winner_concentration": winner,
        "mean_momentum_excess_pct": (
            float(np.mean(momentum_excess)) if momentum_excess else None
        ),
    }
