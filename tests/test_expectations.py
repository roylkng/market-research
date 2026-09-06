from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from marketlab.expectations import (
    ExpectationLedgerError,
    ExpectationNotFrozen,
    ExpectationStore,
)
from marketlab.h002 import PriceReference, build_seasonal_expectation

RULE_HASH = "a86218ec529ea53f7c7918d415961bcda30c5bbdda141a05ae13225c081db2c6"
UNIVERSE_HASH = "b" * 64


@dataclass(frozen=True)
class Member:
    symbol: str


class Universe:
    cohort_id = "FY27-Q2-TEST"
    sha256 = UNIVERSE_HASH
    captured_at_utc = "2026-09-06T06:00:00Z"
    members = (Member("TESTCO"), Member("OTHER"))

    def contains(self, symbol: str) -> bool:
        return symbol.upper() in {member.symbol for member in self.members}


class Clock:
    def __init__(self, value: str):
        self.value = datetime.fromisoformat(value).astimezone(UTC)

    def set(self, value: str) -> None:
        self.value = datetime.fromisoformat(value).astimezone(UTC)

    def __call__(self) -> datetime:
        return self.value


def _expectation(symbol: str = "TESTCO", *, expected_eps: float = 10.0):
    baseline = SimpleNamespace(
        symbol=symbol,
        economic_event_id="baseline-1",
        version_id="baseline-v1",
        reporting_period_end="2025-09-30",
        reporting_quarter="Second quarter",
        accounting_basis="Consolidated",
        basic_eps=expected_eps,
        provenance=SimpleNamespace(
            exchange_published_at_utc="2025-10-20T10:00:00Z"
        ),
    )
    return build_seasonal_expectation(
        baseline,
        target_period_end="2026-09-30",
        target_quarter="Second quarter",
        target_accounting_basis="Consolidated",
        baseline_available_at_utc=None,
        expectation_as_of_utc="2026-09-06T06:10:00Z",
        corporate_action_factor=1.0,
        corporate_action_version="CA-v1",
    )


def _event(symbol: str = "TESTCO", *, publication="2026-10-20T10:00:00Z"):
    return SimpleNamespace(
        mode="PROSPECTIVE",
        symbol=symbol,
        reporting_period_end="30-09-2026",
        reporting_quarter="Second quarter",
        accounting_basis="Consolidated",
        economic_event_id="event-1",
        version_id="event-v1",
        basic_eps=12.0,
        provenance=SimpleNamespace(
            cohort_id="FY27-Q2-TEST",
            universe_snapshot_sha256=UNIVERSE_HASH,
            exchange_published_at_utc=publication,
            captured_at_utc="2026-10-20T10:01:00Z",
        ),
    )


def _store(tmp_path: Path, clock: Clock) -> ExpectationStore:
    return ExpectationStore(tmp_path, clock=clock)


def test_capture_is_append_only_and_same_payload_is_idempotent(tmp_path):
    clock = Clock("2026-09-06T06:20:00Z")
    store = _store(tmp_path, clock)
    first, created = store.capture(_expectation(), universe=Universe(), signal_rule_sha256=RULE_HASH)
    assert created is True
    clock.set("2026-09-07T06:20:00Z")
    second, created = store.capture(_expectation(), universe=Universe(), signal_rule_sha256=RULE_HASH)
    assert created is False
    assert second.record_id == first.record_id
    assert second.captured_at_utc == first.captured_at_utc


def test_second_expectation_for_same_company_is_rejected(tmp_path):
    clock = Clock("2026-09-06T06:20:00Z")
    store = _store(tmp_path, clock)
    store.capture(_expectation(), universe=Universe(), signal_rule_sha256=RULE_HASH)
    with pytest.raises(ExpectationLedgerError, match="slot already frozen"):
        store.capture(
            _expectation(expected_eps=11.0),
            universe=Universe(),
            signal_rule_sha256=RULE_HASH,
        )


def test_manifest_freezes_coverage_and_explicitly_lists_uncovered_symbols(tmp_path):
    clock = Clock("2026-09-06T06:20:00Z")
    store = _store(tmp_path, clock)
    record, _ = store.capture(_expectation(), universe=Universe(), signal_rule_sha256=RULE_HASH)
    clock.set("2026-09-08T06:20:00Z")
    manifest, created = store.freeze_manifest(universe=Universe(), signal_rule_sha256=RULE_HASH)
    assert created is True
    assert [entry.symbol for entry in manifest.records] == ["TESTCO"]
    assert manifest.records[0].record_id == record.record_id
    assert manifest.uncovered_symbols == ("OTHER",)
    assert len(manifest.manifest_id) == 64


def test_manifest_is_idempotent_and_blocks_later_capture(tmp_path):
    clock = Clock("2026-09-06T06:20:00Z")
    store = _store(tmp_path, clock)
    store.capture(_expectation(), universe=Universe(), signal_rule_sha256=RULE_HASH)
    first, _ = store.freeze_manifest(universe=Universe(), signal_rule_sha256=RULE_HASH)
    clock.set("2026-09-09T06:20:00Z")
    second, created = store.freeze_manifest(universe=Universe(), signal_rule_sha256=RULE_HASH)
    assert created is False
    assert second.manifest_id == first.manifest_id
    with pytest.raises(ExpectationLedgerError, match="manifest is already frozen"):
        store.capture(_expectation("OTHER"), universe=Universe(), signal_rule_sha256=RULE_HASH)


def test_event_can_only_resolve_record_and_manifest_frozen_before_publication(tmp_path):
    clock = Clock("2026-09-06T06:20:00Z")
    store = _store(tmp_path, clock)
    record, _ = store.capture(_expectation(), universe=Universe(), signal_rule_sha256=RULE_HASH)
    clock.set("2026-09-10T06:20:00Z")
    manifest, _ = store.freeze_manifest(universe=Universe(), signal_rule_sha256=RULE_HASH)
    loaded_manifest, loaded_record = store.load_for_event(
        _event(), universe=Universe(), signal_rule_sha256=RULE_HASH
    )
    assert loaded_manifest.manifest_id == manifest.manifest_id
    assert loaded_record.record_id == record.record_id


def test_manifest_frozen_after_publication_is_rejected(tmp_path):
    clock = Clock("2026-09-06T06:20:00Z")
    store = _store(tmp_path, clock)
    store.capture(_expectation(), universe=Universe(), signal_rule_sha256=RULE_HASH)
    clock.set("2026-10-21T06:20:00Z")
    store.freeze_manifest(universe=Universe(), signal_rule_sha256=RULE_HASH)
    with pytest.raises(ExpectationLedgerError, match="manifest was not frozen before"):
        store.load_for_event(_event(), universe=Universe(), signal_rule_sha256=RULE_HASH)


def test_uncovered_symbol_is_explicit_not_silently_missing(tmp_path):
    clock = Clock("2026-09-06T06:20:00Z")
    store = _store(tmp_path, clock)
    store.capture(_expectation(), universe=Universe(), signal_rule_sha256=RULE_HASH)
    store.freeze_manifest(universe=Universe(), signal_rule_sha256=RULE_HASH)
    with pytest.raises(ExpectationNotFrozen, match="explicitly uncovered"):
        store.load_for_event(
            _event("OTHER"), universe=Universe(), signal_rule_sha256=RULE_HASH
        )


def test_tampered_record_is_detected_even_if_json_remains_valid(tmp_path):
    clock = Clock("2026-09-06T06:20:00Z")
    store = _store(tmp_path, clock)
    record, _ = store.capture(_expectation(), universe=Universe(), signal_rule_sha256=RULE_HASH)
    path = store._record_path(Universe.cohort_id, record.slot_id)
    payload = json.loads(path.read_text())
    payload["captured_at_utc"] = "2026-09-01T00:00:00Z"
    path.write_text(json.dumps(payload))
    with pytest.raises(ExpectationLedgerError, match="record hash mismatch"):
        store.load_record(Universe.cohort_id, record.slot_id)


def test_tampered_manifest_is_detected(tmp_path):
    clock = Clock("2026-09-06T06:20:00Z")
    store = _store(tmp_path, clock)
    store.capture(_expectation(), universe=Universe(), signal_rule_sha256=RULE_HASH)
    store.freeze_manifest(universe=Universe(), signal_rule_sha256=RULE_HASH)
    path = store._manifest_path(Universe.cohort_id)
    payload = json.loads(path.read_text())
    payload["uncovered_symbols"] = []
    path.write_text(json.dumps(payload))
    with pytest.raises(ExpectationLedgerError, match="manifest hash mismatch"):
        store.load_manifest(universe=Universe(), signal_rule_sha256=RULE_HASH)


def test_expectation_as_of_after_capture_is_rejected(tmp_path):
    clock = Clock("2026-09-06T06:05:00Z")
    store = _store(tmp_path, clock)
    with pytest.raises(ExpectationLedgerError, match="expectation_as_of"):
        store.capture(_expectation(), universe=Universe(), signal_rule_sha256=RULE_HASH)


def test_bad_rule_hash_is_rejected(tmp_path):
    store = _store(tmp_path, Clock("2026-09-06T06:20:00Z"))
    with pytest.raises(ExpectationLedgerError, match="64-character"):
        store.capture(_expectation(), universe=Universe(), signal_rule_sha256="bad")
    with pytest.raises(ExpectationLedgerError, match="does not match frozen H002-R001"):
        store.capture(_expectation(), universe=Universe(), signal_rule_sha256="c" * 64)


def test_nonprospective_event_cannot_resolve_expectation(tmp_path):
    clock = Clock("2026-09-06T06:20:00Z")
    store = _store(tmp_path, clock)
    store.capture(_expectation(), universe=Universe(), signal_rule_sha256=RULE_HASH)
    store.freeze_manifest(universe=Universe(), signal_rule_sha256=RULE_HASH)
    event = _event()
    event.mode = "HISTORICAL_RECONSTRUCTION"
    with pytest.raises(ExpectationLedgerError, match="must be PROSPECTIVE"):
        store.load_for_event(event, universe=Universe(), signal_rule_sha256=RULE_HASH)


def test_score_event_uses_only_manifest_anchored_expectation(tmp_path):
    clock = Clock("2026-09-06T06:20:00Z")
    store = _store(tmp_path, clock)
    record, _ = store.capture(_expectation(), universe=Universe(), signal_rule_sha256=RULE_HASH)
    store.freeze_manifest(universe=Universe(), signal_rule_sha256=RULE_HASH)
    reference = PriceReference(
        symbol="TESTCO",
        role="price_day_minus_2",
        trading_date="2026-10-16",
        close_timestamp_utc="2026-10-16T10:00:00Z",
        close_price=100.0,
        source="TEST",
        corporate_action_version="CA-v1",
    )
    used, result = store.score_event(
        _event(),
        universe=Universe(),
        signal_rule_sha256=RULE_HASH,
        price_reference=reference,
        scored_at_utc="2026-10-20T10:02:00Z",
    )
    assert used.record_id == record.record_id
    assert result.expectation_id == record.expectation.expectation_id
