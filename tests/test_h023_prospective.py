from __future__ import annotations

import copy

import pytest

from marketlab.h023_prospective import (
    PROSPECTIVE_START_UTC,
    RetroactiveSourceGap,
    append_event,
    append_scan,
    append_sources,
    build_event_record,
    build_scan_record,
    canonical_hash,
    event_exists,
    new_event_ledger,
    new_scan_ledger,
    new_source_ledger,
    primary_current_source,
    prior_source_at_event,
    validate_event_ledger,
    validate_scan_ledger,
    validate_source_ledger,
)


def _universe() -> dict:
    return {
        "cohort_id": "FY27-Q2-2026-09-06",
        "members": [
            {
                "symbol": f"S{index:03d}",
                "isin": f"INE{index:09d}",
            }
            for index in range(100)
        ],
    }


def _source(
    *,
    symbol: str = "S000",
    record_id: str,
    report_date: str,
    broadcast_at_utc: str,
    row_marker: str | None = None,
) -> dict:
    master_row_sha256 = canonical_hash(
        {
            "symbol": symbol,
            "record_id": record_id,
            "report_date": report_date,
            "broadcast_at_utc": broadcast_at_utc,
            "row_marker": row_marker or record_id,
        }
    )
    payload = {
        "source_contract_id": "H023-NSE-SHAREHOLDING-XBRL-V1",
        "symbol": symbol,
        "record_id": record_id,
        "report_date": report_date,
        "broadcast_at_utc": broadcast_at_utc,
        "xbrl_url": f"https://nsearchives.nseindia.com/corporate/xbrl/{record_id}.xml",
        "master_row_sha256": master_row_sha256,
    }
    return {"source_id": canonical_hash(payload), **{k: v for k, v in payload.items() if k != "source_contract_id"}}


def _ready(source: dict, percentage: float) -> dict:
    return {
        "status": "READY",
        "source_id": source["source_id"],
        "xbrl_sha256": canonical_hash({"xbrl": source["source_id"]}),
        "mutual_fund_percentage": percentage,
    }


def _append(
    ledger: dict,
    event_ledger: dict,
    sources: list[dict],
    *,
    seen: str = "2026-10-20T10:00:00Z",
) -> dict:
    return append_sources(
        ledger,
        sources,
        first_seen_at_utc=seen,
        event_ledger=event_ledger,
    )


def test_zero_ledgers_validate() -> None:
    validate_source_ledger(new_source_ledger())
    validate_event_ledger(new_event_ledger())
    validate_scan_ledger(new_scan_ledger())


def test_preboundary_quarter_never_becomes_event() -> None:
    source = _source(
        record_id="q2",
        report_date="2026-06-30",
        broadcast_at_utc="2026-07-16T13:54:44Z",
    )
    source_ledger = _append(new_source_ledger(), new_event_ledger(), [source])
    assert (
        build_event_record(
            source_ledger=source_ledger,
            symbol="S000",
            report_date="2026-06-30",
            frozen_at_utc="2026-10-20T10:05:00Z",
            current_evidence=_ready(source, 10.0),
            prior_evidence=None,
        )
        is None
    )


def test_first_current_broadcast_wins_and_prior_is_latest_available_at_event() -> None:
    q2_original = _source(
        record_id="q2-original",
        report_date="2026-06-30",
        broadcast_at_utc="2026-07-16T13:54:44Z",
    )
    q2_revision_before = _source(
        record_id="q2-revision-before",
        report_date="2026-06-30",
        broadcast_at_utc="2026-09-20T08:00:00Z",
    )
    q2_revision_after = _source(
        record_id="q2-revision-after",
        report_date="2026-06-30",
        broadcast_at_utc="2026-10-25T08:00:00Z",
    )
    q3_first = _source(
        record_id="q3-first",
        report_date="2026-09-30",
        broadcast_at_utc="2026-10-20T08:00:00Z",
    )
    q3_revision = _source(
        record_id="q3-revision",
        report_date="2026-09-30",
        broadcast_at_utc="2026-10-21T08:00:00Z",
    )
    event_ledger = new_event_ledger()
    source_ledger = _append(
        new_source_ledger(),
        event_ledger,
        [q2_original, q2_revision_before, q2_revision_after, q3_first, q3_revision],
        seen="2026-10-26T10:00:00Z",
    )
    assert primary_current_source(
        source_ledger, symbol="S000", report_date="2026-09-30"
    )["source_id"] == q3_first["source_id"]
    assert prior_source_at_event(
        source_ledger,
        symbol="S000",
        current_report_date="2026-09-30",
        current_broadcast_at_utc=q3_first["broadcast_at_utc"],
    )["source_id"] == q2_revision_before["source_id"]


def test_signal_record_uses_raw_percentage_point_delta_and_is_immutable() -> None:
    q2 = _source(
        record_id="q2",
        report_date="2026-06-30",
        broadcast_at_utc="2026-07-16T13:54:44Z",
    )
    q3 = _source(
        record_id="q3",
        report_date="2026-09-30",
        broadcast_at_utc="2026-10-20T08:00:00Z",
    )
    source_ledger = _append(
        new_source_ledger(),
        new_event_ledger(),
        [q2, q3],
        seen="2026-10-20T08:01:00Z",
    )
    record = build_event_record(
        source_ledger=source_ledger,
        symbol="S000",
        report_date="2026-09-30",
        frozen_at_utc="2026-10-20T08:02:00Z",
        current_evidence=_ready(q3, 11.25),
        prior_evidence=_ready(q2, 9.75),
    )
    assert record is not None
    assert record["status"] == "SIGNAL"
    assert record["mf_ownership_delta_pp"] == pytest.approx(1.5)
    event_ledger = append_event(new_event_ledger(), record)
    assert event_exists(event_ledger, symbol="S000", report_date="2026-09-30")
    assert append_event(event_ledger, copy.deepcopy(record)) == event_ledger
    changed = copy.deepcopy(record)
    changed["mf_ownership_delta_pp"] = 2.0
    changed["record_sha256"] = canonical_hash(
        {k: v for k, v in changed.items() if k != "record_sha256"}
    )
    with pytest.raises(Exception, match="immutable"):
        append_event(event_ledger, changed)


def test_no_prior_is_sealed_and_later_prior_backfill_raises_gap() -> None:
    q3 = _source(
        record_id="q3",
        report_date="2026-09-30",
        broadcast_at_utc="2026-10-20T08:00:00Z",
    )
    source_ledger = _append(
        new_source_ledger(), new_event_ledger(), [q3], seen="2026-10-20T08:01:00Z"
    )
    record = build_event_record(
        source_ledger=source_ledger,
        symbol="S000",
        report_date="2026-09-30",
        frozen_at_utc="2026-10-20T08:02:00Z",
        current_evidence=_ready(q3, 10.0),
        prior_evidence=None,
    )
    assert record is not None
    assert record["status"] == "NO_SIGNAL_PRIOR_UNAVAILABLE"
    event_ledger = append_event(new_event_ledger(), record)
    late_discovered_q2 = _source(
        record_id="q2-backfill",
        report_date="2026-06-30",
        broadcast_at_utc="2026-07-16T13:54:44Z",
    )
    with pytest.raises(RetroactiveSourceGap, match="invalidates sealed no-prior"):
        _append(
            source_ledger,
            event_ledger,
            [late_discovered_q2],
            seen="2026-10-21T08:00:00Z",
        )


def test_later_discovered_prior_revision_before_event_raises_gap() -> None:
    q2_old = _source(
        record_id="q2-old",
        report_date="2026-06-30",
        broadcast_at_utc="2026-07-16T08:00:00Z",
    )
    q3 = _source(
        record_id="q3",
        report_date="2026-09-30",
        broadcast_at_utc="2026-10-20T08:00:00Z",
    )
    source_ledger = _append(
        new_source_ledger(), new_event_ledger(), [q2_old, q3], seen="2026-10-20T08:01:00Z"
    )
    record = build_event_record(
        source_ledger=source_ledger,
        symbol="S000",
        report_date="2026-09-30",
        frozen_at_utc="2026-10-20T08:02:00Z",
        current_evidence=_ready(q3, 10.0),
        prior_evidence=_ready(q2_old, 9.0),
    )
    event_ledger = append_event(new_event_ledger(), record)
    q2_newer = _source(
        record_id="q2-newer",
        report_date="2026-06-30",
        broadcast_at_utc="2026-09-20T08:00:00Z",
    )
    with pytest.raises(RetroactiveSourceGap, match="supersedes sealed prior context"):
        _append(
            source_ledger,
            event_ledger,
            [q2_newer],
            seen="2026-10-21T08:00:00Z",
        )


def test_source_identity_drift_is_rejected() -> None:
    original = _source(
        record_id="q2",
        report_date="2026-06-30",
        broadcast_at_utc="2026-07-16T08:00:00Z",
    )
    source_ledger = _append(new_source_ledger(), new_event_ledger(), [original])
    drifted = _source(
        record_id="q2",
        report_date="2026-06-30",
        broadcast_at_utc="2026-07-16T08:00:00Z",
        row_marker="mutated-row",
    )
    with pytest.raises(Exception, match="identity drift"):
        _append(source_ledger, new_event_ledger(), [drifted])


def test_scan_requires_exact_100_member_accounting() -> None:
    universe = _universe()
    master_hashes = {
        row["symbol"]: canonical_hash({"master": row["symbol"]}) for row in universe["members"]
    }
    source_ids = {row["symbol"]: [] for row in universe["members"]}
    record = build_scan_record(
        universe_snapshot=universe,
        scanned_at_utc="2026-09-15T03:00:00Z",
        master_response_sha256_by_symbol=master_hashes,
        source_ids_by_symbol=source_ids,
    )
    ledger = append_scan(new_scan_ledger(), record)
    validate_scan_ledger(ledger)
    assert ledger["record_count"] == 1

    broken = dict(master_hashes)
    broken.pop("S099")
    with pytest.raises(Exception, match="exactly account"):
        build_scan_record(
            universe_snapshot=universe,
            scanned_at_utc="2026-09-15T03:01:00Z",
            master_response_sha256_by_symbol=broken,
            source_ids_by_symbol=source_ids,
        )


def test_boundary_constant_is_midnight_ist() -> None:
    assert PROSPECTIVE_START_UTC.isoformat() == "2026-09-14T18:30:00+00:00"
