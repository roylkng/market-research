from __future__ import annotations

import pytest

from marketlab.h023_prospective import (
    H023ProspectiveError,
    append_sources,
    canonical_hash,
    new_event_ledger,
    new_source_ledger,
)
from marketlab.h023_selection import (
    strict_primary_current_source,
    strict_prior_source_at_event,
)
from scripts.run_h023_prospective_scan import _eligible_event_keys


def _source(*, record_id: str, report_date: str, broadcast: str) -> dict:
    row_digest = canonical_hash({"record_id": record_id, "broadcast": broadcast})
    xbrl_url = f"https://nsearchives.nseindia.com/corporate/xbrl/{record_id}.xml"
    identity = {
        "source_contract_id": "H023-NSE-SHAREHOLDING-XBRL-V1",
        "symbol": "AAA",
        "record_id": record_id,
        "report_date": report_date,
        "broadcast_at_utc": broadcast,
        "xbrl_url": xbrl_url,
    }
    return {
        "source_id": canonical_hash(identity),
        "symbol": "AAA",
        "record_id": record_id,
        "report_date": report_date,
        "broadcast_at_utc": broadcast,
        "xbrl_url": xbrl_url,
        "master_row_sha256": row_digest,
    }


def _ledger(sources: list[dict]) -> dict:
    return append_sources(
        new_source_ledger(),
        sources,
        first_seen_at_utc="2026-10-22T12:00:00Z",
        event_ledger=new_event_ledger(),
    )


def test_strict_current_uses_earliest_unique_broadcast() -> None:
    first = _source(
        record_id="current-first",
        report_date="2026-09-30",
        broadcast="2026-10-20T08:00:00Z",
    )
    revision = _source(
        record_id="current-revision",
        report_date="2026-09-30",
        broadcast="2026-10-21T08:00:00Z",
    )
    assert strict_primary_current_source(
        _ledger([revision, first]), symbol="AAA", report_date="2026-09-30"
    ) == first


def test_strict_current_rejects_equal_timestamp_tie() -> None:
    a = _source(
        record_id="a",
        report_date="2026-09-30",
        broadcast="2026-10-20T08:00:00Z",
    )
    b = _source(
        record_id="b",
        report_date="2026-09-30",
        broadcast="2026-10-20T08:00:00Z",
    )
    with pytest.raises(H023ProspectiveError, match="ambiguous first official broadcast"):
        strict_primary_current_source(
            _ledger([a, b]), symbol="AAA", report_date="2026-09-30"
        )


def test_eligibility_ignores_preboundary_equal_timestamp_tie() -> None:
    a = _source(
        record_id="historic-a",
        report_date="2022-09-30",
        broadcast="2022-10-20T08:00:00Z",
    )
    b = _source(
        record_id="historic-b",
        report_date="2022-09-30",
        broadcast="2022-10-20T08:00:00Z",
    )
    assert _eligible_event_keys(_ledger([a, b])) == []


def test_eligibility_still_rejects_prospective_equal_timestamp_tie() -> None:
    a = _source(
        record_id="prospective-a",
        report_date="2026-09-30",
        broadcast="2026-10-20T08:00:00Z",
    )
    b = _source(
        record_id="prospective-b",
        report_date="2026-09-30",
        broadcast="2026-10-20T08:00:00Z",
    )
    with pytest.raises(H023ProspectiveError, match="ambiguous first official broadcast"):
        _eligible_event_keys(_ledger([a, b]))


def test_strict_prior_uses_latest_unique_source_public_at_event() -> None:
    old = _source(
        record_id="old",
        report_date="2026-06-30",
        broadcast="2026-07-15T08:00:00Z",
    )
    revision = _source(
        record_id="revision",
        report_date="2026-06-30",
        broadcast="2026-09-20T08:00:00Z",
    )
    future = _source(
        record_id="future",
        report_date="2026-06-30",
        broadcast="2026-10-21T08:00:00Z",
    )
    assert strict_prior_source_at_event(
        _ledger([old, revision, future]),
        symbol="AAA",
        current_report_date="2026-09-30",
        current_broadcast_at_utc="2026-10-20T08:00:00Z",
    ) == revision


def test_strict_prior_rejects_equal_timestamp_tie() -> None:
    a = _source(
        record_id="prior-a",
        report_date="2026-06-30",
        broadcast="2026-09-20T08:00:00Z",
    )
    b = _source(
        record_id="prior-b",
        report_date="2026-06-30",
        broadcast="2026-09-20T08:00:00Z",
    )
    with pytest.raises(H023ProspectiveError, match="ambiguous latest prior broadcast"):
        strict_prior_source_at_event(
            _ledger([a, b]),
            symbol="AAA",
            current_report_date="2026-09-30",
            current_broadcast_at_utc="2026-10-20T08:00:00Z",
        )
