from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

from marketlab.events import PROSPECTIVE, FinancialEvent
from marketlab.h002 import (
    RULE_ID,
    H002SignalResult,
    PriceReference,
    SeasonalEPSExpectation,
    _validate_expectation,
    score_h002,
)
from marketlab.universe import UniverseSnapshot

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows import compatibility
    fcntl = None  # type: ignore[assignment]


FROZEN_SIGNAL_RULE_SHA256 = "a86218ec529ea53f7c7918d415961bcda30c5bbdda141a05ae13225c081db2c6"


class ExpectationLedgerError(ValueError):
    """Raised when prospective expectation evidence violates the frozen ledger."""


class ExpectationNotFrozen(ExpectationLedgerError):
    """Raised when a frozen cohort manifest explicitly has no expectation for a symbol."""


@dataclass(frozen=True)
class ExpectationCaptureRecord:
    schema_version: int
    record_id: str
    slot_id: str
    cohort_id: str
    universe_snapshot_sha256: str
    signal_rule_id: str
    signal_rule_sha256: str
    captured_at_utc: str
    expectation_sha256: str
    expectation: SeasonalEPSExpectation

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["expectation"] = self.expectation.to_dict()
        return payload


@dataclass(frozen=True)
class ManifestEntry:
    symbol: str
    slot_id: str
    record_id: str
    expectation_id: str
    target_period_end: str
    captured_at_utc: str


@dataclass(frozen=True)
class FrozenExpectationManifest:
    schema_version: int
    manifest_id: str
    cohort_id: str
    universe_snapshot_sha256: str
    signal_rule_id: str
    signal_rule_sha256: str
    frozen_at_utc: str
    records: tuple[ManifestEntry, ...]
    uncovered_symbols: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["records"] = [asdict(entry) for entry in self.records]
        payload["uncovered_symbols"] = list(self.uncovered_symbols)
        return payload


def _canonical_hash(payload: dict[str, Any]) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ExpectationLedgerError("ledger payload must contain finite JSON values") from exc
    return hashlib.sha256(raw).hexdigest()


def _validate_sha256(value: str, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ExpectationLedgerError(f"{field} must be a 64-character SHA-256 hex digest")
    if any(character not in "0123456789abcdefABCDEF" for character in value):
        raise ExpectationLedgerError(f"{field} must be a 64-character SHA-256 hex digest")
    return value.lower()


def _require_frozen_signal_rule_hash(value: str) -> str:
    digest = _validate_sha256(value, field="signal_rule_sha256")
    if digest != FROZEN_SIGNAL_RULE_SHA256:
        raise ExpectationLedgerError(
            "signal_rule_sha256 does not match frozen H002-R001"
        )
    return digest


def _parse_timestamp(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ExpectationLedgerError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise ExpectationLedgerError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _parse_period(value: str | None, *, field: str) -> date:
    if not value:
        raise ExpectationLedgerError(f"{field} is required")
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        pass
    for fmt in ("%d-%m-%Y", "%d-%b-%Y"):
        try:
            parsed = time.strptime(value, fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
        except (TypeError, ValueError):
            continue
    raise ExpectationLedgerError(f"unsupported {field}: {value}")


def _normalise_clock(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ExpectationLedgerError("ledger clock must return a timezone-aware datetime")
    return value.astimezone(UTC)


def _expectation_sha256(expectation: SeasonalEPSExpectation) -> str:
    return _canonical_hash(expectation.to_dict())


def _slot_id(cohort_id: str, symbol: str) -> str:
    return _canonical_hash(
        {"cohort_id": cohort_id, "signal_rule_id": RULE_ID, "symbol": symbol.upper()}
    )[:24]


def _record_digest(record: ExpectationCaptureRecord) -> str:
    payload = record.to_dict()
    payload.pop("record_id", None)
    return _canonical_hash(payload)


def _manifest_digest(manifest: FrozenExpectationManifest) -> str:
    payload = manifest.to_dict()
    payload.pop("manifest_id", None)
    return _canonical_hash(payload)


def _record_from_dict(payload: dict[str, Any]) -> ExpectationCaptureRecord:
    document = dict(payload)
    expectation_payload = document.pop("expectation")
    if not isinstance(expectation_payload, dict):
        raise ExpectationLedgerError("expectation record payload is invalid")
    try:
        expectation = SeasonalEPSExpectation(**expectation_payload)
        record = ExpectationCaptureRecord(**document, expectation=expectation)
    except TypeError as exc:
        raise ExpectationLedgerError(f"invalid expectation capture record: {exc}") from exc
    _validate_expectation(expectation)
    if record.schema_version != 1:
        raise ExpectationLedgerError("unsupported expectation capture record schema")
    if record.signal_rule_id != RULE_ID:
        raise ExpectationLedgerError("expectation capture record has unexpected signal rule")
    _require_frozen_signal_rule_hash(record.signal_rule_sha256)
    _validate_sha256(record.universe_snapshot_sha256, field="universe_snapshot_sha256")
    if _expectation_sha256(expectation) != record.expectation_sha256:
        raise ExpectationLedgerError("expectation capture payload hash mismatch")
    if _slot_id(record.cohort_id, expectation.symbol) != record.slot_id:
        raise ExpectationLedgerError("expectation capture slot identity mismatch")
    if _record_digest(record) != record.record_id:
        raise ExpectationLedgerError("expectation capture record hash mismatch")
    return record


def _manifest_from_dict(payload: dict[str, Any]) -> FrozenExpectationManifest:
    document = dict(payload)
    records_payload = document.pop("records", None)
    uncovered_payload = document.pop("uncovered_symbols", None)
    if not isinstance(records_payload, list) or not isinstance(uncovered_payload, list):
        raise ExpectationLedgerError("expectation manifest has invalid coverage fields")
    try:
        entries = tuple(ManifestEntry(**entry) for entry in records_payload)
        manifest = FrozenExpectationManifest(
            **document,
            records=entries,
            uncovered_symbols=tuple(str(symbol).upper() for symbol in uncovered_payload),
        )
    except TypeError as exc:
        raise ExpectationLedgerError(f"invalid expectation manifest: {exc}") from exc
    if manifest.schema_version != 1:
        raise ExpectationLedgerError("unsupported expectation manifest schema")
    if manifest.signal_rule_id != RULE_ID:
        raise ExpectationLedgerError("expectation manifest has unexpected signal rule")
    _require_frozen_signal_rule_hash(manifest.signal_rule_sha256)
    _validate_sha256(manifest.universe_snapshot_sha256, field="universe_snapshot_sha256")
    if _manifest_digest(manifest) != manifest.manifest_id:
        raise ExpectationLedgerError("expectation manifest hash mismatch")
    symbols = [entry.symbol.upper() for entry in manifest.records]
    if len(symbols) != len(set(symbols)):
        raise ExpectationLedgerError("expectation manifest contains duplicate symbols")
    if set(symbols) & set(manifest.uncovered_symbols):
        raise ExpectationLedgerError("manifest symbol cannot be both covered and uncovered")
    return manifest


class ExpectationStore:
    """Append-only local ledger for pre-filing H002 expectations and cohort manifests."""

    def __init__(
        self,
        root: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.root = Path(root)
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        return _normalise_clock(self._clock())

    @staticmethod
    def _cohort_key(cohort_id: str) -> str:
        if not isinstance(cohort_id, str) or not cohort_id.strip():
            raise ExpectationLedgerError("cohort_id is required")
        return hashlib.sha256(cohort_id.encode("utf-8")).hexdigest()[:20]

    def _cohort_root(self, cohort_id: str) -> Path:
        return self.root / "prospective-expectations" / self._cohort_key(cohort_id)

    def _record_path(self, cohort_id: str, slot_id: str) -> Path:
        return self._cohort_root(cohort_id) / "records" / f"{slot_id}.json"

    def _manifest_path(self, cohort_id: str) -> Path:
        return self._cohort_root(cohort_id) / "manifest.json"

    @contextmanager
    def _cohort_lock(self, cohort_id: str):
        if fcntl is None:
            raise ExpectationLedgerError(
                "concurrent-safe expectation ledger requires POSIX file locking"
            )
        lock_path = self._cohort_root(cohort_id) / ".lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _write_exclusive_json(path: Path, payload: dict[str, Any]) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            return False
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            try:
                path.unlink()
            except OSError:
                pass
            raise
        return True

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise ExpectationLedgerError(f"could not read ledger file {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ExpectationLedgerError(f"ledger file root must be an object: {path}")
        return payload

    def capture(
        self,
        expectation: SeasonalEPSExpectation,
        *,
        universe: UniverseSnapshot,
        signal_rule_sha256: str,
    ) -> tuple[ExpectationCaptureRecord, bool]:
        """Freeze exactly one H002 expectation slot per company in a prospective cohort."""

        _validate_expectation(expectation)
        if expectation.rule_id != RULE_ID:
            raise ExpectationLedgerError("only H002-R001 expectations can enter this ledger")
        if not universe.contains(expectation.symbol):
            raise ExpectationLedgerError(
                f"symbol {expectation.symbol} is not in frozen cohort {universe.cohort_id}"
            )
        rule_hash = _require_frozen_signal_rule_hash(signal_rule_sha256)
        universe_hash = _validate_sha256(
            universe.sha256, field="universe_snapshot_sha256"
        )
        slot_id = _slot_id(universe.cohort_id, expectation.symbol)
        path = self._record_path(universe.cohort_id, slot_id)
        expectation_hash = _expectation_sha256(expectation)

        with self._cohort_lock(universe.cohort_id):
            if self._manifest_path(universe.cohort_id).exists():
                raise ExpectationLedgerError("cohort expectation manifest is already frozen")
            if path.exists():
                existing = _record_from_dict(self._load_json(path))
                if (
                    existing.expectation_sha256 == expectation_hash
                    and existing.universe_snapshot_sha256 == universe_hash
                    and existing.signal_rule_sha256 == rule_hash
                ):
                    return existing, False
                raise ExpectationLedgerError(
                    f"expectation slot already frozen for {expectation.symbol} "
                    f"in {universe.cohort_id}"
                )

            captured = self._now()
            universe_captured = _parse_timestamp(
                universe.captured_at_utc, field="universe.captured_at_utc"
            )
            if universe_captured > captured:
                raise ExpectationLedgerError("universe snapshot is newer than expectation capture")
            expectation_as_of = _parse_timestamp(
                expectation.expectation_as_of_utc, field="expectation_as_of_utc"
            )
            if expectation_as_of > captured:
                raise ExpectationLedgerError(
                    "expectation_as_of cannot be later than ledger capture"
                )

            provisional = ExpectationCaptureRecord(
                schema_version=1,
                record_id="",
                slot_id=slot_id,
                cohort_id=universe.cohort_id,
                universe_snapshot_sha256=universe_hash,
                signal_rule_id=RULE_ID,
                signal_rule_sha256=rule_hash,
                captured_at_utc=captured.isoformat().replace("+00:00", "Z"),
                expectation_sha256=expectation_hash,
                expectation=expectation,
            )
            record = ExpectationCaptureRecord(
                **{**provisional.__dict__, "record_id": _record_digest(provisional)}
            )
            if not self._write_exclusive_json(path, record.to_dict()):
                existing = _record_from_dict(self._load_json(path))
                if existing.record_id == record.record_id:
                    return existing, False
                raise ExpectationLedgerError(
                    f"expectation slot raced with another writer for {expectation.symbol}"
                )
            return record, True

    def load_record(self, cohort_id: str, slot_id: str) -> ExpectationCaptureRecord:
        return _record_from_dict(self._load_json(self._record_path(cohort_id, slot_id)))

    def freeze_manifest(
        self,
        *,
        universe: UniverseSnapshot,
        signal_rule_sha256: str,
    ) -> tuple[FrozenExpectationManifest, bool]:
        """Freeze cohort coverage so later filings cannot change which symbols had expectations."""

        rule_hash = _require_frozen_signal_rule_hash(signal_rule_sha256)
        universe_hash = _validate_sha256(
            universe.sha256, field="universe_snapshot_sha256"
        )
        manifest_path = self._manifest_path(universe.cohort_id)
        with self._cohort_lock(universe.cohort_id):
            if manifest_path.exists():
                existing = _manifest_from_dict(self._load_json(manifest_path))
                self._validate_manifest_context(
                    existing, universe=universe, rule_hash=rule_hash
                )
                return existing, False

            cohort_root = self._cohort_root(universe.cohort_id)
            records: list[ExpectationCaptureRecord] = []
            records_root = cohort_root / "records"
            if records_root.exists():
                for path in sorted(records_root.glob("*.json")):
                    record = _record_from_dict(self._load_json(path))
                    if record.cohort_id != universe.cohort_id:
                        raise ExpectationLedgerError(
                            "record cohort does not match manifest cohort"
                        )
                    if record.universe_snapshot_sha256 != universe_hash:
                        raise ExpectationLedgerError(
                            "record universe hash does not match manifest"
                        )
                    if record.signal_rule_sha256 != rule_hash:
                        raise ExpectationLedgerError(
                            "record signal-rule hash does not match manifest"
                        )
                    records.append(record)

            by_symbol: dict[str, ExpectationCaptureRecord] = {}
            for record in records:
                symbol = record.expectation.symbol.upper()
                if symbol in by_symbol:
                    raise ExpectationLedgerError(
                        f"multiple expectation records for symbol {symbol}"
                    )
                if not universe.contains(symbol):
                    raise ExpectationLedgerError(
                        f"manifest record symbol {symbol} is outside universe"
                    )
                by_symbol[symbol] = record

            universe_symbols = {member.symbol.upper() for member in universe.members}
            uncovered = tuple(sorted(universe_symbols - set(by_symbol)))
            entries = tuple(
                ManifestEntry(
                    symbol=symbol,
                    slot_id=record.slot_id,
                    record_id=record.record_id,
                    expectation_id=record.expectation.expectation_id,
                    target_period_end=record.expectation.target_period_end,
                    captured_at_utc=record.captured_at_utc,
                )
                for symbol, record in sorted(by_symbol.items())
            )
            frozen = self._now()
            universe_captured = _parse_timestamp(
                universe.captured_at_utc, field="universe.captured_at_utc"
            )
            if universe_captured > frozen:
                raise ExpectationLedgerError(
                    "universe snapshot is newer than manifest freeze"
                )

            provisional = FrozenExpectationManifest(
                schema_version=1,
                manifest_id="",
                cohort_id=universe.cohort_id,
                universe_snapshot_sha256=universe_hash,
                signal_rule_id=RULE_ID,
                signal_rule_sha256=rule_hash,
                frozen_at_utc=frozen.isoformat().replace("+00:00", "Z"),
                records=entries,
                uncovered_symbols=uncovered,
            )
            manifest = FrozenExpectationManifest(
                **{**provisional.__dict__, "manifest_id": _manifest_digest(provisional)}
            )
            if not self._write_exclusive_json(manifest_path, manifest.to_dict()):
                existing = _manifest_from_dict(self._load_json(manifest_path))
                self._validate_manifest_context(
                    existing, universe=universe, rule_hash=rule_hash
                )
                return existing, False
            return manifest, True

    @staticmethod
    def _validate_manifest_context(
        manifest: FrozenExpectationManifest,
        *,
        universe: UniverseSnapshot,
        rule_hash: str,
    ) -> None:
        if manifest.cohort_id != universe.cohort_id:
            raise ExpectationLedgerError("manifest cohort does not match universe")
        if manifest.universe_snapshot_sha256 != universe.sha256.lower():
            raise ExpectationLedgerError("manifest universe snapshot hash mismatch")
        if manifest.signal_rule_sha256 != rule_hash:
            raise ExpectationLedgerError("manifest signal-rule hash mismatch")
        expected = {member.symbol.upper() for member in universe.members}
        covered = {entry.symbol.upper() for entry in manifest.records}
        uncovered = set(manifest.uncovered_symbols)
        if covered | uncovered != expected or covered & uncovered:
            raise ExpectationLedgerError("manifest coverage does not exactly partition the universe")

    def load_manifest(
        self,
        *,
        universe: UniverseSnapshot,
        signal_rule_sha256: str,
    ) -> FrozenExpectationManifest:
        rule_hash = _require_frozen_signal_rule_hash(signal_rule_sha256)
        manifest = _manifest_from_dict(self._load_json(self._manifest_path(universe.cohort_id)))
        self._validate_manifest_context(manifest, universe=universe, rule_hash=rule_hash)
        return manifest

    def load_for_event(
        self,
        actual_event: FinancialEvent,
        *,
        universe: UniverseSnapshot,
        signal_rule_sha256: str,
    ) -> tuple[FrozenExpectationManifest, ExpectationCaptureRecord]:
        """Resolve only an expectation anchored in the cohort manifest before publication."""

        if actual_event.mode != PROSPECTIVE:
            raise ExpectationLedgerError("actual event must be PROSPECTIVE")
        provenance = actual_event.provenance
        if provenance.cohort_id != universe.cohort_id:
            raise ExpectationLedgerError("event cohort does not match expectation universe")
        if provenance.universe_snapshot_sha256 != universe.sha256:
            raise ExpectationLedgerError("event universe snapshot does not match expectation universe")
        if not provenance.exchange_published_at_utc:
            raise ExpectationLedgerError("prospective event is missing publication timestamp")
        publication = _parse_timestamp(
            provenance.exchange_published_at_utc, field="exchange_published_at_utc"
        )
        manifest = self.load_manifest(
            universe=universe, signal_rule_sha256=signal_rule_sha256
        )
        manifest_frozen = _parse_timestamp(
            manifest.frozen_at_utc, field="manifest.frozen_at_utc"
        )
        if manifest_frozen >= publication:
            raise ExpectationLedgerError("expectation manifest was not frozen before publication")

        symbol = actual_event.symbol.upper()
        entry = next((item for item in manifest.records if item.symbol.upper() == symbol), None)
        if entry is None:
            if symbol in manifest.uncovered_symbols:
                raise ExpectationNotFrozen(
                    f"{symbol} is explicitly uncovered in frozen expectation manifest"
                )
            raise ExpectationLedgerError("event symbol is absent from manifest coverage")
        record = self.load_record(manifest.cohort_id, entry.slot_id)
        if record.record_id != entry.record_id:
            raise ExpectationLedgerError("manifest expectation record id does not match ledger")
        captured = _parse_timestamp(record.captured_at_utc, field="record.captured_at_utc")
        if captured >= publication:
            raise ExpectationLedgerError("expectation record was not captured before publication")

        expectation = record.expectation
        if expectation.symbol.upper() != symbol:
            raise ExpectationLedgerError("expectation symbol does not match event")
        actual_period = _parse_period(
            actual_event.reporting_period_end, field="actual reporting_period_end"
        )
        if expectation.target_period_end != actual_period.isoformat():
            raise ExpectationLedgerError("expectation target period does not match event")
        if (actual_event.reporting_quarter or "").strip().casefold() != expectation.target_quarter.strip().casefold():
            raise ExpectationLedgerError("expectation quarter does not match event")
        if actual_event.accounting_basis.strip().casefold() != expectation.accounting_basis.strip().casefold():
            raise ExpectationLedgerError("expectation accounting basis does not match event")
        return manifest, record

    def score_event(
        self,
        actual_event: FinancialEvent,
        *,
        universe: UniverseSnapshot,
        signal_rule_sha256: str,
        price_reference: PriceReference,
        scored_at_utc: str,
    ) -> tuple[ExpectationCaptureRecord, H002SignalResult]:
        """Score a prospective event only from the pre-publication frozen expectation ledger."""

        _, record = self.load_for_event(
            actual_event,
            universe=universe,
            signal_rule_sha256=signal_rule_sha256,
        )
        result = score_h002(
            actual_event,
            record.expectation,
            price_reference,
            scored_at_utc=scored_at_utc,
        )
        return record, result
