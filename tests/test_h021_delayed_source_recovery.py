"""Regress conservative next-day recovery of genuinely unpublished NSE market files.

Original H021-P008 three-attempt limit is unchanged. Only later
source-transport acquisition is retried, with no backdated observation,
future session, missing-price fill, new cohort, trade or return.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from marketlab.marketdata import index_snapshot_url, udiff_url
from scripts.collect_h021_daily_official import load_frozen_sources
from scripts.resolve_h021_daily_session import (
    MAX_AUTOMATED_ATTEMPTS,
    MAX_DELAYED_PUBLICATION_RECOVERY_ATTEMPTS,
    _eligible_delayed_publication_recovery,
    resolve_session,
)


def _capture_day(day: str, *, index_state: str = "NOT_PUBLISHED",
                 stock_state: str = "OK", utc_hour: int = 16) -> dict:
    original_day = date.fromisoformat(day)

    def source(kind: str, state: str) -> dict:
        successful = state == "OK"
        return {
            "url": (
                index_snapshot_url(original_day)
                if kind == "index"
                else udiff_url(original_day)
            ),
            "status": state,
            "captured_at_utc": f"{day}T{utc_hour:02d}:00:00Z",
            "http_status": (
                200 if successful else (404 if state == "NOT_PUBLISHED" else 403)
            ),
            "sha256": "a" * 64 if successful else None,
            "byte_count": 15700 if successful else None,
            "error": None if successful else f"HTTP_{state}",
        }

    return {
        "schema_version": 1,
        "id": "H021-P008-OFFICIAL-SOURCE-ATTEMPT-v1",
        "session_date": day,
        "recorded_at_utc": f"{day}T{utc_hour:02d}:01:00Z",
        "packet_sha256": "f" * 64,
        "source_index": source("index", index_state),
        "source_stock": source("stock", stock_state),
        "capture_state": "SOURCE_INCOMPLETE",
        "horizon_returns_opened": False,
        "live_capital_allowed": False,
    }


def _record_attempts(root: Path, day: str, number: int, *,
                     index_state: str = "NOT_PUBLISHED",
                     stock_state: str = "OK") -> None:
    (root / "attempts").mkdir(parents=True, exist_ok=True)
    for index in range(number):
        (root / "attempts" / f"{day}-synthetic-{index:02d}.json").write_text(
            json.dumps(
                _capture_day(day, index_state=index_state, stock_state=stock_state),
                indent=2,
            ),
            encoding="utf-8",
        )


def _calendar():
    _intent, _universe, snapshot = load_frozen_sources()
    return snapshot


def _asof(day: str, hour: int = 18) -> datetime:
    return datetime.fromisoformat(f"{day}T{hour:02d}:00:00Z").astimezone(UTC)


def _close(calendar, day: str) -> datetime:
    return datetime.fromisoformat(
        next(s.close_timestamp_utc for s in calendar.sessions if s.session_date == day)
    ).astimezone(UTC)


def test_real_source_publication_delay_allows_next_day_limited_recovery(
    tmp_path: Path,
) -> None:
    snapshot = _calendar()
    _record_attempts(tmp_path, "2026-10-13", 3)
    ready, count = _eligible_delayed_publication_recovery(
        root=tmp_path,
        session_date="2026-10-13",
        official_close=_close(snapshot, "2026-10-13"),
        as_of_utc=_asof("2026-10-14"),
    )
    assert ready is True
    assert count == MAX_AUTOMATED_ATTEMPTS == 3

    # Freeze the 14 Oct primary attempts as already exhausted, but only
    # the 13th is eligible for next-day late-publication recovery.
    _record_attempts(tmp_path, "2026-10-14", 3)
    blocked = resolve_session(
        snapshot, tmp_path,
        as_of_utc=_asof("2026-10-14"),
        allow_delayed_publication_recovery=False,
    )
    assert blocked["state"] == "NO_COMPLETED_PENDING_SESSION"
    approved = resolve_session(
        snapshot, tmp_path,
        as_of_utc=_asof("2026-10-14"),
        allow_delayed_publication_recovery=True,
    )
    assert approved["state"] == "CAPTURE"
    assert approved["session_date"] == "2026-10-13"
    assert approved["capture_mode"] == "DELAYED_ORIGINAL_NSE_404_RECOVERY_NOT_BACKFILL"
    assert approved["attempts_so_far"] == 3
    assert approved["maximum_automatic_attempts"] == 5
    assert approved["outcomes_opened"] is False
    assert approved["live_capital_allowed"] is False


def test_current_new_completed_session_is_prioritized_over_old_404_recovery(
    tmp_path: Path,
) -> None:
    snapshot = _calendar()
    _record_attempts(tmp_path, "2026-10-13", 3)
    answer = resolve_session(
        snapshot, tmp_path,
        as_of_utc=_asof("2026-10-14"),
        allow_delayed_publication_recovery=True,
    )
    assert answer["state"] == "CAPTURE"
    assert answer["session_date"] == "2026-10-14"
    assert answer["capture_mode"] == "NORMAL_AFTER_COMPLETED_EXCHANGE_CLOSE"
    assert answer["attempts_so_far"] == 0


def test_same_day_probes_cannot_exhaust_recovery_quota(
    tmp_path: Path,
) -> None:
    calendar = _calendar()
    _record_attempts(tmp_path, "2026-10-13", 3)
    eligible, count = _eligible_delayed_publication_recovery(
        root=tmp_path,
        session_date="2026-10-13",
        official_close=_close(calendar, "2026-10-13"),
        as_of_utc=_asof("2026-10-13", 18),
    )
    assert count == 3
    assert eligible is False


def test_access_denied_does_not_grant_additional_automatic_probes(
    tmp_path: Path,
) -> None:
    calendar = _calendar()
    _record_attempts(tmp_path, "2026-10-13", 3, index_state="ACCESS_BLOCKED")
    eligible, count = _eligible_delayed_publication_recovery(
        root=tmp_path,
        session_date="2026-10-13",
        official_close=_close(calendar, "2026-10-13"),
        as_of_utc=_asof("2026-10-14"),
    )
    assert eligible is False
    assert count == 3


def test_later_successful_transport_does_not_become_an_extra_404_attempt(
    tmp_path: Path,
) -> None:
    calendar = _calendar()
    _record_attempts(tmp_path, "2026-10-13", 3)
    extra = _capture_day("2026-10-13", index_state="OK")
    (tmp_path / "attempts" / "2026-10-13-synthetic-04.json").write_text(
        json.dumps(extra), encoding="utf-8"
    )
    eligible, count = _eligible_delayed_publication_recovery(
        root=tmp_path,
        session_date="2026-10-13",
        official_close=_close(calendar, "2026-10-13"),
        as_of_utc=_asof("2026-10-15"),
    )
    assert eligible is False
    assert count == 4


def test_two_recoveries_are_maximum_and_not_a_floating_experiment(
    tmp_path: Path,
) -> None:
    calendar = _calendar()
    _record_attempts(tmp_path, "2026-10-13", 5)
    eligible, count = _eligible_delayed_publication_recovery(
        root=tmp_path,
        session_date="2026-10-13",
        official_close=_close(calendar, "2026-10-13"),
        as_of_utc=_asof("2026-10-15"),
    )
    assert eligible is False
    assert count == (
        MAX_AUTOMATED_ATTEMPTS + MAX_DELAYED_PUBLICATION_RECOVERY_ATTEMPTS
    )


def test_recovery_never_uses_unverified_evidence_or_more_than_seven_days(
    tmp_path: Path,
) -> None:
    calendar = _calendar()
    _record_attempts(tmp_path, "2026-10-13", 3)
    ready, _ = _eligible_delayed_publication_recovery(
        root=tmp_path,
        session_date="2026-10-13",
        official_close=_close(calendar, "2026-10-13"),
        as_of_utc=_asof("2026-10-22"),
    )
    assert ready is False
    file = tmp_path / "attempts" / "2026-10-13-synthetic-00.json"
    obj = json.loads(file.read_text(encoding="utf-8"))
    obj["source_index"]["url"] = "https://other.example/index-fake.csv"
    file.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ValueError, match="original NSE report URL"):
        _eligible_delayed_publication_recovery(
            root=tmp_path,
            session_date="2026-10-13",
            official_close=_close(calendar, "2026-10-13"),
            as_of_utc=_asof("2026-10-14"),
        )


def test_recovery_timestamp_cannot_come_from_preclose_observation(
    tmp_path: Path,
) -> None:
    calendar = _calendar()
    _record_attempts(tmp_path, "2026-10-13", 3)
    first = tmp_path / "attempts" / "2026-10-13-synthetic-01.json"
    receipt = json.loads(first.read_text(encoding="utf-8"))
    receipt["source_stock"]["captured_at_utc"] = "2026-10-13T09:00:00Z"
    first.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="impossible original exchange capture chronology"):
        _eligible_delayed_publication_recovery(
            root=tmp_path,
            session_date="2026-10-13",
            official_close=_close(calendar, "2026-10-13"),
            as_of_utc=_asof("2026-10-14"),
        )
