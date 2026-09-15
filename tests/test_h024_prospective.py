from __future__ import annotations

import copy

import pytest

from marketlab.h024_acquisition import canonical_hash, source_from_discovery_row
from marketlab.h024_prospective import (
    PROSPECTIVE_START_UTC,
    H024ProspectiveError,
    append_evidence,
    append_scan,
    append_signal,
    append_sources,
    build_scan_record,
    build_signal_record,
    new_evidence_ledger,
    new_scan_ledger,
    new_signal_ledger,
    new_source_ledger,
    planned_entry_session,
    signal_exists,
    validate_evidence_ledger,
    validate_scan_ledger,
    validate_signal_ledger,
    validate_source_ledger,
)


def _row(
    *,
    app_id: str = "APP-1",
    submission_type: str = "Original",
    disseminated: str = "2026-09-16T00:30:02",
) -> dict:
    return {
        "symbol": "AAA",
        "companyName": "AAA Limited",
        "regulation": "Regulation 7 (2)",
        "appId": app_id,
        "prevAppId": "",
        "typeOfSubmission": submission_type,
        "revisionRemark": "",
        "broadcastDateTime": disseminated,
        "exchdisstime": disseminated,
        "xmlFileName": f"https://nsearchives.nseindia.com/corporate/xbrl/{app_id}.xml",
        "ixbrl": f"https://nsearchives.nseindia.com/corporate/xbrl/{app_id}_WEB.html",
    }


def _source(**kwargs) -> dict:
    source = source_from_discovery_row(_row(**kwargs))
    assert source is not None
    return source


def _ready(source: dict, *, direct_count: int = 1) -> dict:
    return {
        "status": "READY",
        "source_id": source["source_id"],
        "xbrl_sha256": canonical_hash({"raw": source["source_id"]}),
        "date_of_filing": "2026-09-16",
        "transaction_count": 1,
        "direct_market_purchase_count": direct_count,
        "direct_market_purchase_value_inr": 15_000_000.0 if direct_count else 0.0,
        "direct_market_purchase_quantity": 10_000 if direct_count else 0,
        "direct_market_purchase_ownership_delta_pp": 0.05 if direct_count else 0.0,
        "direct_market_purchase_actor_count": 1 if direct_count else 0,
        "direct_market_purchase_categories": ["Promoter"] if direct_count else [],
        "direct_market_purchase_names": ["Example Insider"] if direct_count else [],
    }


def _calendar() -> dict:
    return {
        "sessions": [
            {
                "session_date": "2026-09-16",
                "open_timestamp_utc": "2026-09-16T03:45:00Z",
                "close_timestamp_utc": "2026-09-16T10:00:00Z",
            },
            {
                "session_date": "2026-09-17",
                "open_timestamp_utc": "2026-09-17T03:45:00Z",
                "close_timestamp_utc": "2026-09-17T10:00:00Z",
            },
            {
                "session_date": "2026-09-18",
                "open_timestamp_utc": "2026-09-18T03:45:00Z",
                "close_timestamp_utc": "2026-09-18T10:00:00Z",
            },
        ]
    }


def test_zero_ledgers_validate() -> None:
    validate_source_ledger(new_source_ledger())
    validate_evidence_ledger(new_evidence_ledger())
    validate_signal_ledger(new_signal_ledger())
    validate_scan_ledger(new_scan_ledger())


def test_same_calendar_session_execution_is_prohibited() -> None:
    entry = planned_entry_session(_calendar(), "2026-09-16T02:00:00Z")
    assert entry["session_date"] == "2026-09-17"


def test_qualifying_original_source_seals_source_signal_before_next_day_entry() -> None:
    source = _source()
    sources = append_sources(
        new_source_ledger(),
        [source],
        first_seen_at_utc="2026-09-15T19:00:10Z",
    )
    evidence = append_evidence(
        new_evidence_ledger(),
        sources,
        _ready(source),
        frozen_at_utc="2026-09-15T19:01:00Z",
    )
    record = build_signal_record(
        source_ledger=sources,
        evidence_ledger=evidence,
        calendar=_calendar(),
        source_id=source["source_id"],
        frozen_at_utc="2026-09-15T19:02:00Z",
    )
    assert record is not None
    assert record["status"] == "QUALIFYING"
    assert record["planned_entry_session"] == "2026-09-17"
    assert record["direct_market_purchase_value_inr"] == pytest.approx(15_000_000.0)
    signals = append_signal(new_signal_ledger(), record)
    assert signal_exists(signals, source["source_id"])
    assert append_signal(signals, copy.deepcopy(record)) == signals


def test_preboundary_original_never_becomes_prospective_signal() -> None:
    source = _source(disseminated="2026-09-15T23:00:00")
    sources = append_sources(
        new_source_ledger(),
        [source],
        first_seen_at_utc="2026-09-15T17:30:10Z",
    )
    evidence = append_evidence(
        new_evidence_ledger(), sources, _ready(source), frozen_at_utc="2026-09-15T17:31:00Z"
    )
    assert (
        build_signal_record(
            source_ledger=sources,
            evidence_ledger=evidence,
            calendar=_calendar(),
            source_id=source["source_id"],
            frozen_at_utc="2026-09-15T17:32:00Z",
        )
        is None
    )


def test_revision_and_nonqualifying_original_do_not_create_positive_signal() -> None:
    revision = _source(app_id="REV-1", submission_type="Revision")
    original = _source(app_id="NO-DIRECT")
    sources = append_sources(
        new_source_ledger(),
        [revision, original],
        first_seen_at_utc="2026-09-15T19:00:10Z",
    )
    evidence = new_evidence_ledger()
    evidence = append_evidence(
        evidence, sources, _ready(revision), frozen_at_utc="2026-09-15T19:01:00Z"
    )
    evidence = append_evidence(
        evidence,
        sources,
        _ready(original, direct_count=0),
        frozen_at_utc="2026-09-15T19:01:01Z",
    )
    assert (
        build_signal_record(
            source_ledger=sources,
            evidence_ledger=evidence,
            calendar=_calendar(),
            source_id=revision["source_id"],
            frozen_at_utc="2026-09-15T19:02:00Z",
        )
        is None
    )
    assert (
        build_signal_record(
            source_ledger=sources,
            evidence_ledger=evidence,
            calendar=_calendar(),
            source_id=original["source_id"],
            frozen_at_utc="2026-09-15T19:02:00Z",
        )
        is None
    )


def test_late_signal_freeze_is_retained_but_not_primary_qualifying() -> None:
    source = _source()
    sources = append_sources(
        new_source_ledger(), [source], first_seen_at_utc="2026-09-15T19:00:10Z"
    )
    evidence = append_evidence(
        new_evidence_ledger(), sources, _ready(source), frozen_at_utc="2026-09-17T03:40:00Z"
    )
    record = build_signal_record(
        source_ledger=sources,
        evidence_ledger=evidence,
        calendar=_calendar(),
        source_id=source["source_id"],
        frozen_at_utc="2026-09-17T04:00:00Z",
    )
    assert record is not None
    assert record["status"] == "LATE_SIGNAL_FREEZE"


def test_evidence_and_signal_are_immutable() -> None:
    source = _source()
    sources = append_sources(
        new_source_ledger(), [source], first_seen_at_utc="2026-09-15T19:00:10Z"
    )
    evidence = append_evidence(
        new_evidence_ledger(), sources, _ready(source), frozen_at_utc="2026-09-15T19:01:00Z"
    )
    changed = _ready(source)
    changed["direct_market_purchase_value_inr"] = 99_000_000.0
    with pytest.raises(H024ProspectiveError, match="immutable"):
        append_evidence(
            evidence, sources, changed, frozen_at_utc="2026-09-15T19:02:00Z"
        )

    record = build_signal_record(
        source_ledger=sources,
        evidence_ledger=evidence,
        calendar=_calendar(),
        source_id=source["source_id"],
        frozen_at_utc="2026-09-15T19:02:00Z",
    )
    assert record is not None
    signals = append_signal(new_signal_ledger(), record)
    changed_signal = copy.deepcopy(record)
    changed_signal["direct_market_purchase_value_inr"] = 100_000_000.0
    changed_signal["signal_record_sha256"] = canonical_hash(
        {key: value for key, value in changed_signal.items() if key != "signal_record_sha256"}
    )
    with pytest.raises(H024ProspectiveError, match="immutable"):
        append_signal(signals, changed_signal)


def test_scan_ledger_seals_raw_discovery_hash_and_source_ids() -> None:
    source = _source()
    record = build_scan_record(
        scanned_at_utc="2026-09-15T19:05:00Z",
        window_start="2026-09-09",
        window_end="2026-09-15",
        discovery_raw_sha256=canonical_hash({"raw": "discovery"}),
        source_ids=[source["source_id"]],
    )
    ledger = append_scan(new_scan_ledger(), record)
    validate_scan_ledger(ledger)
    assert ledger["record_count"] == 1


def test_prospective_boundary_is_midnight_ist_on_september_16() -> None:
    assert PROSPECTIVE_START_UTC.isoformat() == "2026-09-15T18:30:00+00:00"
