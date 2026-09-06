from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any, Literal

import numpy as np
import pandas as pd
import yaml

from marketlab.evaluation import evaluate_binary_groups, winner_concentration
from marketlab.events import PROSPECTIVE, FinancialEvent
from marketlab.execution import PaperPosition, load_and_validate_execution_rule
from marketlab.h002 import H002SignalResult, load_and_validate_rule
from marketlab.universe import load_universe_snapshot

RecordType = Literal["EVENT_CAPTURED", "SIGNAL_FIXED", "REVISION_SEEN", "POSITION_STATE"]

TERMINAL_POSITION_STATES = {"COMPLETED", "SKIPPED"}
ALLOWED_POSITION_TRANSITIONS = {
    "PENDING": {"PENDING", "COMPLETED", "SKIPPED", "UNRESOLVED_EXIT"},
    "UNRESOLVED_EXIT": {"UNRESOLVED_EXIT", "COMPLETED"},
    "COMPLETED": {"COMPLETED"},
    "SKIPPED": {"SKIPPED"},
}


class ProspectiveLedgerError(ValueError):
    """Raised when prospective cohort or ledger invariants are violated."""


@dataclass(frozen=True)
class ProspectiveCohort:
    cohort_id: str
    activated_at_utc: str
    universe_id: str
    universe_snapshot_path: str
    universe_snapshot_sha256: str
    signal_rule_id: str
    signal_rule_sha256: str
    execution_rule_id: str
    execution_rule_sha256: str
    ledger_format: str
    local_ledger_path: str
    historical_backfill_allowed: bool
    live_capital: bool


@dataclass(frozen=True)
class LedgerEntry:
    schema_version: int
    cohort_id: str
    sequence: int
    record_type: RecordType
    created_at_utc: str
    event_id: str
    event_version_id: str | None
    symbol: str
    payload: dict[str, Any]
    previous_hash: str | None
    entry_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AppendResult:
    entry: LedgerEntry
    created: bool


def _utc_iso(value: str | datetime, *, field: str) -> str:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise ProspectiveLedgerError(f"invalid {field}: {value}") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise ProspectiveLedgerError(f"{field} must be an ISO timestamp")
    if parsed.tzinfo is None:
        raise ProspectiveLedgerError(f"{field} must include timezone")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


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
        raise ProspectiveLedgerError("ledger payload must be finite canonical JSON") from exc


def _hash_payload(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _entry_hash_payload(entry: dict[str, Any]) -> dict[str, Any]:
    payload = dict(entry)
    payload.pop("entry_hash", None)
    return payload


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ProspectiveLedgerError(f"could not read {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise ProspectiveLedgerError(f"{path} must contain a mapping")
    return document


def load_active_cohort(
    *,
    root: str | Path,
    cohort_id: str,
    capture_policy_path: str | Path = "registry/capture_policy.yaml",
    observations_registry_path: str | Path = "registry/prospective_observations.yaml",
) -> ProspectiveCohort:
    """Load and cross-check the active paper-only cohort against frozen artifacts."""

    root = Path(root)
    policy = _read_yaml(root / capture_policy_path)
    capture = policy.get("prospective_capture")
    activation = policy.get("activation")
    if not isinstance(capture, dict) or not isinstance(activation, dict):
        raise ProspectiveLedgerError("capture policy is missing prospective_capture/activation")
    if capture.get("enabled") is not True or activation.get("state") != "ACTIVE_PAPER_ONLY":
        raise ProspectiveLedgerError("prospective paper capture is not active")
    if capture.get("allow_live_capital") is not False:
        raise ProspectiveLedgerError("capture policy must keep live capital disabled")
    if capture.get("allow_historical_backfill_as_prospective") is not False:
        raise ProspectiveLedgerError("historical backfill must remain prohibited")
    if capture.get("cohort_id") != cohort_id:
        raise ProspectiveLedgerError("capture policy cohort does not match requested cohort")

    registry = _read_yaml(root / observations_registry_path)
    cohorts = registry.get("cohorts")
    if not isinstance(cohorts, list):
        raise ProspectiveLedgerError("prospective observations registry must contain cohorts")
    matching = [item for item in cohorts if isinstance(item, dict) and item.get("cohort_id") == cohort_id]
    if len(matching) != 1:
        raise ProspectiveLedgerError(f"expected exactly one cohort registry entry for {cohort_id}")
    item = matching[0]
    if item.get("status") != "ACTIVE_PAPER_ONLY" or item.get("live_capital") is not False:
        raise ProspectiveLedgerError("cohort must be ACTIVE_PAPER_ONLY with live_capital false")
    if item.get("historical_backfill_allowed") is not False:
        raise ProspectiveLedgerError("cohort cannot allow historical backfill")
    if item.get("ledger_format") != "hash_chained_jsonl_v1":
        raise ProspectiveLedgerError("unsupported prospective ledger format")

    activation_time = _utc_iso(activation.get("activated_at_utc"), field="activated_at_utc")
    if _utc_iso(item.get("activated_at_utc"), field="cohort activated_at_utc") != activation_time:
        raise ProspectiveLedgerError("capture policy and cohort activation timestamps differ")

    universe_path = str(item.get("universe_snapshot_path") or "")
    universe = load_universe_snapshot(root / universe_path)
    if universe.cohort_id != cohort_id:
        raise ProspectiveLedgerError("frozen universe cohort id mismatch")
    if universe.sha256 != item.get("universe_snapshot_sha256"):
        raise ProspectiveLedgerError("cohort registry universe hash mismatch")
    if universe.sha256 != capture.get("universe_snapshot_sha256"):
        raise ProspectiveLedgerError("capture policy universe hash mismatch")

    signal_document = load_and_validate_rule(root / "registry/h002_signal_rule.yaml")
    signal_hash = str(signal_document["sha256"])
    if signal_document.get("id") != item.get("signal_rule_id"):
        raise ProspectiveLedgerError("signal rule id mismatch")
    if signal_hash != item.get("signal_rule_sha256") or signal_hash != capture.get("signal_rule_sha256"):
        raise ProspectiveLedgerError("signal rule hash mismatch in prospective configuration")

    execution_document = load_and_validate_execution_rule(root / "registry/h002_execution_rule.yaml")
    execution_hash = str(execution_document["sha256"])
    if execution_document.get("id") != item.get("execution_rule_id"):
        raise ProspectiveLedgerError("execution rule id mismatch")
    if execution_hash != item.get("execution_rule_sha256") or execution_hash != capture.get(
        "execution_rule_sha256"
    ):
        raise ProspectiveLedgerError("execution rule hash mismatch in prospective configuration")

    if capture.get("universe_snapshot_path") != universe_path:
        raise ProspectiveLedgerError("capture policy and cohort universe paths differ")
    for field in ("universe_id", "signal_rule_id", "execution_rule_id"):
        policy_key = "prerequisite_universe_id" if field == "universe_id" else field
        if capture.get(policy_key) != item.get(field):
            raise ProspectiveLedgerError(f"capture policy {field} mismatch")

    return ProspectiveCohort(
        cohort_id=cohort_id,
        activated_at_utc=activation_time,
        universe_id=str(item["universe_id"]),
        universe_snapshot_path=universe_path,
        universe_snapshot_sha256=str(item["universe_snapshot_sha256"]),
        signal_rule_id=str(item["signal_rule_id"]),
        signal_rule_sha256=signal_hash,
        execution_rule_id=str(item["execution_rule_id"]),
        execution_rule_sha256=execution_hash,
        ledger_format=str(item["ledger_format"]),
        local_ledger_path=str(item["local_ledger_path"]),
        historical_backfill_allowed=bool(item["historical_backfill_allowed"]),
        live_capital=bool(item["live_capital"]),
    )


class ProspectiveLedger:
    """Append-only, hash-chained JSONL ledger for one frozen H002 cohort."""

    def __init__(self, path: str | Path, *, cohort_id: str) -> None:
        self.path = Path(path)
        self.cohort_id = cohort_id

    def read(self) -> list[LedgerEntry]:
        if not self.path.exists():
            return []
        entries: list[LedgerEntry] = []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise ProspectiveLedgerError(f"could not read prospective ledger: {exc}") from exc
        previous_hash: str | None = None
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                raise ProspectiveLedgerError(f"blank line in ledger at line {line_number}")
            try:
                payload = json.loads(line)
                entry = LedgerEntry(**payload)
            except (json.JSONDecodeError, TypeError) as exc:
                raise ProspectiveLedgerError(
                    f"invalid ledger entry at line {line_number}: {exc}"
                ) from exc
            if entry.cohort_id != self.cohort_id:
                raise ProspectiveLedgerError(f"cohort mismatch at ledger line {line_number}")
            if entry.sequence != line_number:
                raise ProspectiveLedgerError(
                    f"non-contiguous ledger sequence at line {line_number}: {entry.sequence}"
                )
            if entry.previous_hash != previous_hash:
                raise ProspectiveLedgerError(f"previous_hash mismatch at line {line_number}")
            expected = _hash_payload(_entry_hash_payload(entry.to_dict()))
            if entry.entry_hash != expected:
                raise ProspectiveLedgerError(f"entry_hash mismatch at line {line_number}")
            _utc_iso(entry.created_at_utc, field=f"ledger line {line_number} created_at_utc")
            if entry.record_type not in {
                "EVENT_CAPTURED",
                "SIGNAL_FIXED",
                "REVISION_SEEN",
                "POSITION_STATE",
            }:
                raise ProspectiveLedgerError(f"unsupported record type at line {line_number}")
            entries.append(entry)
            previous_hash = entry.entry_hash
        return entries

    def validate(self) -> list[LedgerEntry]:
        return self.read()

    def _append(
        self,
        *,
        record_type: RecordType,
        event_id: str,
        event_version_id: str | None,
        symbol: str,
        payload: dict[str, Any],
        created_at: str | datetime,
    ) -> LedgerEntry:
        entries = self.read()
        created_at_utc = _utc_iso(created_at, field="ledger created_at")
        unsigned = {
            "schema_version": 1,
            "cohort_id": self.cohort_id,
            "sequence": len(entries) + 1,
            "record_type": record_type,
            "created_at_utc": created_at_utc,
            "event_id": event_id,
            "event_version_id": event_version_id,
            "symbol": symbol.upper(),
            "payload": payload,
            "previous_hash": None if not entries else entries[-1].entry_hash,
        }
        entry = LedgerEntry(**unsigned, entry_hash=_hash_payload(unsigned))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(entry.to_dict()) + "\n")
        return entry

    def record_event(self, event: FinancialEvent, *, created_at: str | datetime) -> AppendResult:
        if event.mode != PROSPECTIVE:
            raise ProspectiveLedgerError("historical reconstruction cannot enter prospective ledger")
        entries = self.read()
        payload = event.to_dict()
        matches = [
            entry
            for entry in entries
            if entry.record_type == "EVENT_CAPTURED"
            and entry.event_id == event.economic_event_id
            and entry.event_version_id == event.version_id
        ]
        if matches:
            if len(matches) != 1 or matches[0].payload != payload:
                raise ProspectiveLedgerError("same event version exists with conflicting payload")
            return AppendResult(matches[0], False)
        return AppendResult(
            self._append(
                record_type="EVENT_CAPTURED",
                event_id=event.economic_event_id,
                event_version_id=event.version_id,
                symbol=event.symbol,
                payload=payload,
                created_at=created_at,
            ),
            True,
        )

    def record_signal(
        self,
        signal: H002SignalResult,
        *,
        event_mode: str,
        created_at: str | datetime,
    ) -> AppendResult:
        if event_mode != PROSPECTIVE:
            raise ProspectiveLedgerError("historical signal cannot enter prospective ledger")
        entries = self.read()
        captured_versions = {
            entry.event_version_id
            for entry in entries
            if entry.record_type == "EVENT_CAPTURED" and entry.event_id == signal.event_id
        }
        if signal.event_version_id not in captured_versions:
            raise ProspectiveLedgerError("signal requires captured prospective event version")

        fixed = [
            entry
            for entry in entries
            if entry.record_type == "SIGNAL_FIXED" and entry.event_id == signal.event_id
        ]
        payload = signal.to_dict()
        if fixed:
            canonical = fixed[0]
            if canonical.event_version_id == signal.event_version_id:
                if canonical.payload != payload:
                    raise ProspectiveLedgerError("fixed signal payload changed for same event version")
                return AppendResult(canonical, False)

            revision_payload = {
                "canonical_signal_entry_hash": canonical.entry_hash,
                "canonical_event_version_id": canonical.event_version_id,
                "revised_event_version_id": signal.event_version_id,
                "revised_signal_payload_sha256": _hash_payload(payload),
                "signal_rewrite_allowed": False,
            }
            existing_revision = [
                entry
                for entry in entries
                if entry.record_type == "REVISION_SEEN"
                and entry.event_id == signal.event_id
                and entry.event_version_id == signal.event_version_id
            ]
            if existing_revision:
                if len(existing_revision) != 1 or existing_revision[0].payload != revision_payload:
                    raise ProspectiveLedgerError("revision record exists with conflicting payload")
                return AppendResult(existing_revision[0], False)
            return AppendResult(
                self._append(
                    record_type="REVISION_SEEN",
                    event_id=signal.event_id,
                    event_version_id=signal.event_version_id,
                    symbol=signal.symbol,
                    payload=revision_payload,
                    created_at=created_at,
                ),
                True,
            )

        return AppendResult(
            self._append(
                record_type="SIGNAL_FIXED",
                event_id=signal.event_id,
                event_version_id=signal.event_version_id,
                symbol=signal.symbol,
                payload=payload,
                created_at=created_at,
            ),
            True,
        )

    def record_position(
        self,
        position: PaperPosition,
        *,
        created_at: str | datetime,
    ) -> AppendResult:
        if position.hypothesis_id != "H002" or position.execution_rule_id != "H002-X001":
            raise ProspectiveLedgerError("position is not a frozen H002-X001 paper observation")
        if position.live_order_created:
            raise ProspectiveLedgerError("live-order state cannot enter prospective paper ledger")

        entries = self.read()
        signal_entries = [
            entry
            for entry in entries
            if entry.record_type == "SIGNAL_FIXED" and entry.event_id == position.event_id
        ]
        if len(signal_entries) != 1:
            raise ProspectiveLedgerError("position requires exactly one fixed signal")
        fixed = signal_entries[0]
        if position.event_version_id != fixed.event_version_id:
            raise ProspectiveLedgerError("revised filing cannot create a new paper position")
        if position.signal_bucket != fixed.payload.get("bucket"):
            raise ProspectiveLedgerError("position signal bucket differs from fixed signal")

        prior_states = [
            entry
            for entry in entries
            if entry.record_type == "POSITION_STATE"
            and entry.payload.get("position_id") == position.position_id
        ]
        payload = position.to_dict()
        if prior_states:
            previous = prior_states[-1]
            previous_status = str(previous.payload.get("status"))
            new_status = position.status
            allowed = ALLOWED_POSITION_TRANSITIONS.get(previous_status)
            if allowed is None or new_status not in allowed:
                raise ProspectiveLedgerError(
                    f"invalid position transition {previous_status} -> {new_status}"
                )
            if previous.payload == payload:
                return AppendResult(previous, False)
            if previous_status in TERMINAL_POSITION_STATES:
                raise ProspectiveLedgerError(f"terminal position {previous_status} cannot be rewritten")

        return AppendResult(
            self._append(
                record_type="POSITION_STATE",
                event_id=position.event_id,
                event_version_id=position.event_version_id,
                symbol=position.symbol,
                payload=payload,
                created_at=created_at,
            ),
            True,
        )


def _bootstrap_mean_ci(values: list[float], *, seed: int = 7, iterations: int = 10_000) -> dict[str, float] | None:
    if len(values) < 2:
        return None
    array = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ProspectiveLedgerError("report contains non-finite returns")
    rng = np.random.default_rng(seed)
    samples = rng.choice(array, size=(iterations, len(array)), replace=True).mean(axis=1)
    return {
        "low": float(np.quantile(samples, 0.025)),
        "high": float(np.quantile(samples, 0.975)),
    }


def _basic_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "bootstrap_95_ci_mean": None}
    if any(not math.isfinite(value) for value in values):
        raise ProspectiveLedgerError("report contains non-finite returns")
    return {
        "n": len(values),
        "mean": float(mean(values)),
        "median": float(median(values)),
        "bootstrap_95_ci_mean": _bootstrap_mean_ci(values),
    }


def build_prospective_report(
    ledger: ProspectiveLedger,
    *,
    generated_at: str | datetime,
) -> dict[str, Any]:
    """Build a paper-only report using only each position's latest completed state."""

    entries = ledger.read()
    generated_at_utc = _utc_iso(generated_at, field="report generated_at")
    event_entries = [entry for entry in entries if entry.record_type == "EVENT_CAPTURED"]
    signal_entries = [entry for entry in entries if entry.record_type == "SIGNAL_FIXED"]
    revisions = [entry for entry in entries if entry.record_type == "REVISION_SEEN"]

    latest_positions: dict[str, LedgerEntry] = {}
    for entry in entries:
        if entry.record_type != "POSITION_STATE":
            continue
        position_id = str(entry.payload.get("position_id") or "")
        if not position_id:
            raise ProspectiveLedgerError("POSITION_STATE is missing position_id")
        latest_positions[position_id] = entry

    status_counts: dict[str, int] = {}
    for entry in latest_positions.values():
        status = str(entry.payload.get("status"))
        status_counts[status] = status_counts.get(status, 0) + 1

    bucket_counts: dict[str, int] = {}
    for entry in signal_entries:
        bucket = str(entry.payload.get("bucket"))
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    completed = [
        entry.payload
        for entry in latest_positions.values()
        if entry.payload.get("status") == "COMPLETED"
    ]
    gross_returns = [float(item["gross_return_pct"]) for item in completed]

    cost_scenarios: dict[str, list[float]] = {}
    for item in completed:
        scenarios = item.get("cost_stressed_return_pct") or {}
        for name, value in scenarios.items():
            cost_scenarios.setdefault(str(name), []).append(float(value))

    benchmark_data: dict[str, list[float]] = {}
    benchmark_hits: dict[str, list[bool]] = {}
    for item in completed:
        for outcome in item.get("benchmarks", []):
            if outcome.get("status") != "COMPLETE" or outcome.get("excess_return_pct") is None:
                continue
            benchmark_id = str(outcome["benchmark_id"])
            excess = float(outcome["excess_return_pct"])
            benchmark_data.setdefault(benchmark_id, []).append(excess)
            benchmark_hits.setdefault(benchmark_id, []).append(excess > 0)

    benchmark_report = {
        benchmark_id: {
            **_basic_stats(values),
            "hit_rate": float(sum(hits) / len(hits)) if hits else None,
        }
        for benchmark_id, values in sorted(benchmark_data.items())
        for hits in [benchmark_hits[benchmark_id]]
    }

    winner_report: dict[str, Any] | None = None
    if len(gross_returns) > 2:
        winner_report = winner_concentration(pd.Series(gross_returns), top_n=min(2, len(gross_returns) - 1))

    sign_spread: dict[str, Any] | None = None
    nifty_rows: list[dict[str, Any]] = []
    for item in completed:
        nifty = next(
            (
                outcome
                for outcome in item.get("benchmarks", [])
                if outcome.get("benchmark_id") == "nifty_50"
                and outcome.get("status") == "COMPLETE"
                and outcome.get("excess_return_pct") is not None
            ),
            None,
        )
        if nifty and item.get("signal_bucket") in {"POSITIVE", "NEGATIVE"}:
            nifty_rows.append(
                {
                    "bucket": item["signal_bucket"],
                    "excess": float(nifty["excess_return_pct"]),
                }
            )
    if sum(row["bucket"] == "POSITIVE" for row in nifty_rows) >= 2 and sum(
        row["bucket"] == "NEGATIVE" for row in nifty_rows
    ) >= 2:
        evaluation = evaluate_binary_groups(
            pd.DataFrame(nifty_rows),
            group_col="bucket",
            excess_return_col="excess",
            positive_value="POSITIVE",
            negative_value="NEGATIVE",
        )
        sign_spread = evaluation.to_dict()

    return {
        "schema_version": 1,
        "cohort_id": ledger.cohort_id,
        "generated_at_utc": generated_at_utc,
        "paper_only": True,
        "live_capital": False,
        "ledger_entries": len(entries),
        "ledger_head_hash": None if not entries else entries[-1].entry_hash,
        "economic_events": len({entry.event_id for entry in event_entries}),
        "event_versions": len(event_entries),
        "revisions_seen": len(revisions),
        "signals_fixed": len(signal_entries),
        "signal_bucket_counts": dict(sorted(bucket_counts.items())),
        "latest_position_status_counts": dict(sorted(status_counts.items())),
        "completed_positions": len(completed),
        "gross_return_pct": _basic_stats(gross_returns),
        "cost_stressed_return_pct": {
            scenario: _basic_stats(values) for scenario, values in sorted(cost_scenarios.items())
        },
        "benchmark_excess_return_pct": benchmark_report,
        "winner_concentration_gross": winner_report,
        "positive_vs_negative_nifty_excess": sign_spread,
        "mfe_mae": {
            "status": "NOT_AVAILABLE",
            "reason": "H002-X001 stores entry/exit execution points, not intrahorizon path data",
        },
        "interpretation": "DESCRIPTIVE_UNTIL_OUTCOME_WINDOWS_AND_REGIME_COVERAGE_ARE_ADEQUATE",
    }
