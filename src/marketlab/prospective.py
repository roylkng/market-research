from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

import numpy as np

from marketlab.events import PROSPECTIVE, FinancialEvent
from marketlab.execution import PaperPosition
from marketlab.h002 import H002SignalResult

LEDGER_FORMAT = "hash_chained_jsonl_v1"


class ProspectiveLedgerError(ValueError):
    """Raised when prospective evidence violates the immutable-ledger contract."""


@dataclass(frozen=True)
class ObservationRevision:
    schema_version: int
    ledger_format: str
    cohort_id: str
    observation_id: str
    revision_number: int
    recorded_at_utc: str
    previous_record_sha256: str | None
    event_id: str
    first_event_version_id: str
    symbol: str
    signal_payload_sha256: str
    signal: dict[str, Any]
    position: dict[str, Any]
    record_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_timestamp(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ProspectiveLedgerError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise ProspectiveLedgerError(f"{field} must include timezone: {value}")
    return parsed.astimezone(UTC)


def _canonical_json(payload: Any) -> str:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ProspectiveLedgerError("prospective payload must contain finite JSON values") from exc


def _hash_payload(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _without_record_hash(payload: dict[str, Any]) -> dict[str, Any]:
    unsigned = dict(payload)
    unsigned.pop("record_sha256", None)
    return unsigned


def _signal_digest(signal: H002SignalResult | dict[str, Any]) -> str:
    payload = signal.to_dict() if isinstance(signal, H002SignalResult) else signal
    return _hash_payload(payload)


def _observation_id(cohort_id: str, event_id: str, first_event_version_id: str) -> str:
    return _hash_payload(
        {
            "cohort_id": cohort_id,
            "event_id": event_id,
            "first_event_version_id": first_event_version_id,
            "hypothesis_id": "H002",
        }
    )[:24]


def load_ledger(path: str | Path) -> list[ObservationRevision]:
    ledger_path = Path(path)
    if not ledger_path.exists():
        return []
    revisions: list[ObservationRevision] = []
    with ledger_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ProspectiveLedgerError(
                    f"invalid JSON at ledger line {line_number}: {exc}"
                ) from exc
            try:
                revision = ObservationRevision(**payload)
            except TypeError as exc:
                raise ProspectiveLedgerError(
                    f"invalid ledger schema at line {line_number}: {exc}"
                ) from exc
            revisions.append(revision)
    validate_ledger(revisions)
    return revisions


def validate_ledger(revisions: list[ObservationRevision]) -> None:
    previous_global_hash: str | None = None
    per_observation_revision: dict[str, int] = {}
    first_event_version: dict[str, str] = {}
    signal_hash: dict[str, str] = {}

    for index, revision in enumerate(revisions, start=1):
        if revision.schema_version != 1:
            raise ProspectiveLedgerError(
                f"unsupported ledger schema at revision {index}: {revision.schema_version}"
            )
        if revision.ledger_format != LEDGER_FORMAT:
            raise ProspectiveLedgerError(
                f"unexpected ledger format at revision {index}: {revision.ledger_format}"
            )
        _parse_timestamp(revision.recorded_at_utc, field="recorded_at_utc")
        if revision.previous_record_sha256 != previous_global_hash:
            raise ProspectiveLedgerError(
                f"broken global hash chain at revision {index}: expected {previous_global_hash}"
            )
        recomputed = _hash_payload(_without_record_hash(revision.to_dict()))
        if recomputed != revision.record_sha256:
            raise ProspectiveLedgerError(
                f"record hash mismatch at revision {index}: {revision.observation_id}"
            )
        if _hash_payload(revision.signal) != revision.signal_payload_sha256:
            raise ProspectiveLedgerError(
                f"signal payload hash mismatch at revision {index}: {revision.observation_id}"
            )

        expected_number = per_observation_revision.get(revision.observation_id, 0) + 1
        if revision.revision_number != expected_number:
            raise ProspectiveLedgerError(
                f"non-sequential observation revision for {revision.observation_id}: "
                f"expected {expected_number}, got {revision.revision_number}"
            )
        per_observation_revision[revision.observation_id] = revision.revision_number

        existing_event_version = first_event_version.get(revision.observation_id)
        if existing_event_version is None:
            first_event_version[revision.observation_id] = revision.first_event_version_id
        elif existing_event_version != revision.first_event_version_id:
            raise ProspectiveLedgerError(
                f"first event version changed for observation {revision.observation_id}"
            )

        existing_signal_hash = signal_hash.get(revision.observation_id)
        if existing_signal_hash is None:
            signal_hash[revision.observation_id] = revision.signal_payload_sha256
        elif existing_signal_hash != revision.signal_payload_sha256:
            raise ProspectiveLedgerError(
                f"signal changed after first observation revision: {revision.observation_id}"
            )

        position = revision.position
        if position.get("event_id") != revision.event_id:
            raise ProspectiveLedgerError(
                f"position event mismatch: {revision.observation_id}"
            )
        if position.get("event_version_id") != revision.first_event_version_id:
            raise ProspectiveLedgerError(
                f"position event version does not use first prospective version: "
                f"{revision.observation_id}"
            )
        if position.get("live_order_created") is not False:
            raise ProspectiveLedgerError(
                f"live order flag must remain false: {revision.observation_id}"
            )
        previous_global_hash = revision.record_sha256


def latest_revisions(revisions: list[ObservationRevision]) -> dict[str, ObservationRevision]:
    latest: dict[str, ObservationRevision] = {}
    for revision in revisions:
        latest[revision.observation_id] = revision
    return latest


def append_observation_revision(
    path: str | Path,
    *,
    cohort_id: str,
    event: FinancialEvent,
    signal: H002SignalResult,
    position: PaperPosition,
    recorded_at_utc: str,
) -> ObservationRevision:
    """Append one immutable prospective revision.

    The first prospectively captured event version fixes the H002 signal. Later
    position-state evaluations append revisions using the same signal and event
    version. A corrected/revised filing must be preserved in the event store but
    cannot rewrite this observation's signal.
    """

    if event.mode != PROSPECTIVE:
        raise ProspectiveLedgerError("only PROSPECTIVE events may enter prospective ledger")
    if event.provenance.cohort_id != cohort_id:
        raise ProspectiveLedgerError(
            f"event cohort mismatch: event={event.provenance.cohort_id}, ledger={cohort_id}"
        )
    if not event.provenance.universe_snapshot_sha256:
        raise ProspectiveLedgerError("event is missing frozen universe snapshot hash")
    if signal.event_id != event.economic_event_id:
        raise ProspectiveLedgerError("signal event id does not match captured event")
    if signal.event_version_id != event.version_id:
        raise ProspectiveLedgerError("signal must use the captured event version")
    if position.event_id != signal.event_id:
        raise ProspectiveLedgerError("position event id does not match signal")
    if position.event_version_id != signal.event_version_id:
        raise ProspectiveLedgerError("position event version does not match signal")
    if position.signal_rule_id != signal.rule_id:
        raise ProspectiveLedgerError("position signal rule does not match signal")
    if position.hypothesis_id != "H002":
        raise ProspectiveLedgerError("prospective ledger accepts H002 positions only")
    if position.live_order_created is not False:
        raise ProspectiveLedgerError("live order creation is prohibited")

    recorded = _parse_timestamp(recorded_at_utc, field="recorded_at_utc")
    scored = _parse_timestamp(signal.scored_at_utc, field="signal scored_at_utc")
    evaluated = _parse_timestamp(position.evaluation_as_of_utc, field="position evaluation_as_of_utc")
    if recorded < scored or recorded < evaluated:
        raise ProspectiveLedgerError(
            "ledger record time cannot precede signal score or position evaluation"
        )

    ledger_path = Path(path)
    existing = load_ledger(ledger_path)
    signal_payload = signal.to_dict()
    signal_payload_hash = _signal_digest(signal_payload)
    observation_id = _observation_id(cohort_id, event.economic_event_id, event.version_id)
    same = [item for item in existing if item.observation_id == observation_id]

    # An economic event already locked to a different first prospective version
    # cannot create a second H002 observation after a corrected filing.
    for item in existing:
        if item.cohort_id == cohort_id and item.event_id == event.economic_event_id:
            if item.first_event_version_id != event.version_id:
                raise ProspectiveLedgerError(
                    "later filing revision cannot create or rewrite H002 signal for existing event"
                )

    if same:
        if same[-1].signal_payload_sha256 != signal_payload_hash:
            raise ProspectiveLedgerError("signal payload cannot change after first revision")
        revision_number = same[-1].revision_number + 1
        latest_position = same[-1].position
        current_position = position.to_dict()
        if latest_position == current_position:
            return same[-1]
    else:
        revision_number = 1

    previous_hash = existing[-1].record_sha256 if existing else None
    unsigned = {
        "schema_version": 1,
        "ledger_format": LEDGER_FORMAT,
        "cohort_id": cohort_id,
        "observation_id": observation_id,
        "revision_number": revision_number,
        "recorded_at_utc": recorded.isoformat().replace("+00:00", "Z"),
        "previous_record_sha256": previous_hash,
        "event_id": event.economic_event_id,
        "first_event_version_id": event.version_id,
        "symbol": event.symbol,
        "signal_payload_sha256": signal_payload_hash,
        "signal": signal_payload,
        "position": position.to_dict(),
    }
    revision = ObservationRevision(**unsigned, record_sha256=_hash_payload(unsigned))

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(_canonical_json(revision.to_dict()) + "\n")
    # Verify the complete file after append. A failed verification leaves evidence
    # of corruption rather than silently continuing with an invalid chain.
    load_ledger(ledger_path)
    return revision


def _finite_values(values: list[float | None]) -> list[float]:
    return [float(value) for value in values if value is not None and math.isfinite(float(value))]


def _bootstrap_mean_ci(values: list[float], *, iterations: int = 10_000, seed: int = 7) -> tuple[float, float] | None:
    if len(values) < 2:
        return None
    rng = np.random.default_rng(seed)
    array = np.asarray(values, dtype=float)
    means = np.empty(iterations, dtype=float)
    for index in range(iterations):
        means[index] = rng.choice(array, size=len(array), replace=True).mean()
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def prospective_report(revisions: list[ObservationRevision]) -> dict[str, Any]:
    """Generate a descriptive H002 paper report from latest observation revisions."""

    validate_ledger(revisions)
    latest = list(latest_revisions(revisions).values())
    status_counts = Counter(item.position.get("status") for item in latest)
    skip_reasons = Counter(
        item.position.get("skip_or_pending_reason")
        for item in latest
        if item.position.get("status") in {"SKIPPED", "UNRESOLVED_EXIT"}
    )
    bucket_counts = Counter(item.signal.get("bucket") for item in latest)
    completed = [item for item in latest if item.position.get("status") == "COMPLETED"]
    raw_returns = _finite_values(
        [item.position.get("gross_return_pct") for item in completed]
    )

    benchmark_ids = ["nifty_50", "nifty_200_momentum_30"]
    benchmark_stats: dict[str, Any] = {}
    for benchmark_id in benchmark_ids:
        excess: list[float] = []
        hits = 0
        comparable = 0
        for item in completed:
            benchmark = next(
                (
                    row
                    for row in item.position.get("benchmarks", [])
                    if row.get("benchmark_id") == benchmark_id
                ),
                None,
            )
            if not benchmark or benchmark.get("status") != "COMPLETE":
                continue
            value = benchmark.get("excess_return_pct")
            if value is None or not math.isfinite(float(value)):
                continue
            comparable += 1
            value = float(value)
            excess.append(value)
            if value > 0:
                hits += 1
        benchmark_stats[benchmark_id] = {
            "comparable_completed": comparable,
            "mean_excess_return_pct": mean(excess) if excess else None,
            "median_excess_return_pct": median(excess) if excess else None,
            "hit_rate": hits / comparable if comparable else None,
            "bootstrap_mean_excess_95_ci_pct": _bootstrap_mean_ci(excess),
        }

    by_bucket: dict[str, Any] = {}
    for bucket in ("POSITIVE", "ZERO", "NEGATIVE", "NO_SIGNAL"):
        rows = [item for item in latest if item.signal.get("bucket") == bucket]
        done = [item for item in rows if item.position.get("status") == "COMPLETED"]
        returns = _finite_values([item.position.get("gross_return_pct") for item in done])
        nifty_excess: list[float] = []
        for item in done:
            benchmark = next(
                (
                    row
                    for row in item.position.get("benchmarks", [])
                    if row.get("benchmark_id") == "nifty_50" and row.get("status") == "COMPLETE"
                ),
                None,
            )
            if benchmark and benchmark.get("excess_return_pct") is not None:
                value = float(benchmark["excess_return_pct"])
                if math.isfinite(value):
                    nifty_excess.append(value)
        by_bucket[bucket] = {
            "observations": len(rows),
            "completed": len(done),
            "mean_raw_return_pct": mean(returns) if returns else None,
            "median_raw_return_pct": median(returns) if returns else None,
            "mean_excess_vs_nifty_pct": mean(nifty_excess) if nifty_excess else None,
            "median_excess_vs_nifty_pct": median(nifty_excess) if nifty_excess else None,
        }

    winner_concentration: dict[str, Any] | None = None
    if len(raw_returns) >= 3:
        ordered = sorted(raw_returns, reverse=True)
        top_n = min(2, len(ordered) - 1)
        winner_concentration = {
            "top_n": top_n,
            "full_mean_pct": mean(ordered),
            "mean_without_top_n_pct": mean(ordered[top_n:]),
        }

    cost_sensitivity: dict[str, Any] = {}
    for bps in ("0", "25", "50"):
        values = _finite_values(
            [
                (item.position.get("cost_stressed_return_pct") or {}).get(bps)
                for item in completed
            ]
        )
        cost_sensitivity[bps] = {
            "n": len(values),
            "mean_return_pct": mean(values) if values else None,
            "median_return_pct": median(values) if values else None,
        }

    cohorts = sorted({item.cohort_id for item in latest})
    return {
        "schema_version": 1,
        "hypothesis_id": "H002",
        "paper_only": True,
        "cohorts": cohorts,
        "ledger_revisions": len(revisions),
        "unique_observations": len(latest),
        "status_counts": dict(status_counts),
        "skip_or_unresolved_reasons": {
            str(key): value for key, value in skip_reasons.items() if key is not None
        },
        "signal_bucket_counts": dict(bucket_counts),
        "completed_outcome_windows": len(completed),
        "raw_return": {
            "mean_pct": mean(raw_returns) if raw_returns else None,
            "median_pct": median(raw_returns) if raw_returns else None,
            "bootstrap_mean_95_ci_pct": _bootstrap_mean_ci(raw_returns),
        },
        "benchmarks": benchmark_stats,
        "by_signal_bucket": by_bucket,
        "winner_concentration": winner_concentration,
        "cost_sensitivity": cost_sensitivity,
        "promotion_decision": "DESCRIPTIVE_ONLY",
        "warning": (
            "Prospective evidence remains paper-only. No threshold optimization or live-capital "
            "authorization is implied by this report."
        ),
    }
