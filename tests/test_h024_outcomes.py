from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from marketlab.h024_acquisition import source_from_discovery_row
from marketlab.h024_events import PRIMARY_EVENT_STATUS
from marketlab.h024_outcomes import (
    PRIMARY_POPULATION_ELIGIBLE,
    PRIMARY_POPULATION_RETROACTIVE_GAP,
    append_entry,
    append_outcome,
    build_entry_record,
    build_outcome_record,
    current_primary_population_audit,
    horizon_exit_session,
    new_entry_ledger,
    new_outcome_ledger,
    validate_entry_ledger,
    validate_outcome_ledger,
)
from marketlab.h024_prospective import H024ProspectiveError, append_sources, new_source_ledger


def _event(*, event_id: str = "a" * 64, symbol: str = "ABC") -> dict:
    return {
        "event_id": event_id,
        "symbol": symbol,
        "status": PRIMARY_EVENT_STATUS,
        "planned_entry_session": "2026-09-17",
        "planned_entry_open_utc": "2026-09-17T03:45:00Z",
        "event_frozen_at_utc": "2026-09-17T03:44:00Z",
        "candidate_source_ids": [],
        "eligible_source_ids": [],
        "investability": {"entry_isin": "INE000A01001"},
    }


def _stock_bar(
    *,
    session: str,
    symbol: str = "ABC",
    isin: str = "INE000A01001",
    open_price: float = 100.0,
    close_price: float = 105.0,
) -> dict:
    return {
        "symbol": symbol,
        "isin": isin,
        "series": "EQ",
        "session_date": session,
        "open_price": open_price,
        "high_price": max(open_price, close_price),
        "low_price": min(open_price, close_price),
        "close_price": close_price,
        "source_url": "https://nsearchives.nseindia.com/content/cm/example.zip",
        "raw_sha256": "b" * 64,
    }


def _benchmark_bar(
    *, session: str, open_price: float = 1000.0, close_price: float = 1010.0
) -> dict:
    return {
        "benchmark_id": "nifty_500",
        "index_name": "Nifty 500",
        "session_date": session,
        "open_price": open_price,
        "close_price": close_price,
        "source_url": "https://archives.nseindia.com/content/indices/example.csv",
        "raw_sha256": "c" * 64,
    }


def _entry_ready(event: dict | None = None) -> dict:
    event = _event() if event is None else event
    return build_entry_record(
        event=event,
        stock_bar=_stock_bar(session="2026-09-17"),
        benchmark_bar=_benchmark_bar(session="2026-09-17"),
        observed_at_utc="2026-09-17T11:00:00Z",
    )


def _calendar(count: int = 130) -> dict:
    rows = []
    cursor = date(2026, 9, 17)
    for _ in range(count):
        opened = datetime(cursor.year, cursor.month, cursor.day, 3, 45, tzinfo=UTC)
        closed = datetime(cursor.year, cursor.month, cursor.day, 10, 0, tzinfo=UTC)
        rows.append(
            {
                "session_date": cursor.isoformat(),
                "open_timestamp_utc": opened.isoformat().replace("+00:00", "Z"),
                "close_timestamp_utc": closed.isoformat().replace("+00:00", "Z"),
            }
        )
        cursor += timedelta(days=1)
    return {"sessions": rows}


def _source(
    *,
    app_id: str,
    submission_type: str,
    disseminated: str,
    symbol: str = "ABC",
) -> dict:
    source = source_from_discovery_row(
        {
            "symbol": symbol,
            "companyName": "ABC Limited",
            "regulation": "Regulation 7 (2)",
            "appId": app_id,
            "prevAppId": "",
            "typeOfSubmission": submission_type,
            "revisionRemark": "",
            "broadcastDateTime": disseminated,
            "exchdisstime": disseminated,
            "xmlFileName": f"https://nsearchives.nseindia.com/corporate/xbrl/{app_id}.xml",
            "ixbrl": f"https://nsearchives.nseindia.com/corporate/xbrl/{app_id}.html",
        }
    )
    assert source is not None
    return source


def test_entry_observation_freezes_exact_entry_open_evidence() -> None:
    event = _event()
    record = _entry_ready(event)

    assert record["status"] == "READY"
    assert record["stock_bar"]["open_price"] == 100.0
    assert record["benchmark_bar"]["open_price"] == 1000.0
    ledger = append_entry(new_entry_ledger(), record)
    validate_entry_ledger(ledger)


def test_entry_observation_blocks_missing_or_wrong_identity() -> None:
    event = _event()
    missing = build_entry_record(
        event=event,
        stock_bar=None,
        benchmark_bar=_benchmark_bar(session="2026-09-17"),
        observed_at_utc="2026-09-17T11:00:00Z",
    )
    assert missing["status"] == "BLOCKED"
    assert missing["block_reason"] == "MISSING_ENTRY_STOCK_BAR"

    drift = build_entry_record(
        event=event,
        stock_bar=_stock_bar(session="2026-09-17", isin="INE999A01001"),
        benchmark_bar=_benchmark_bar(session="2026-09-17"),
        observed_at_utc="2026-09-17T11:00:00Z",
    )
    assert drift["status"] == "BLOCKED"
    assert drift["block_reason"] == "ENTRY_IDENTITY_DRIFT"


def test_horizon_session_counts_entry_as_session_one() -> None:
    calendar = _calendar()

    assert horizon_exit_session(calendar, entry_session="2026-09-17", horizon=20)[
        "session_date"
    ] == "2026-10-06"
    assert horizon_exit_session(calendar, entry_session="2026-09-17", horizon=60)[
        "session_date"
    ] == "2026-11-15"
    assert horizon_exit_session(calendar, entry_session="2026-09-17", horizon=120)[
        "session_date"
    ] == "2027-01-14"


def test_complete_outcome_matches_frozen_return_formula() -> None:
    event = _event()
    entry = _entry_ready(event)
    record = build_outcome_record(
        event=event,
        entry_record=entry,
        horizon=20,
        exit_session="2026-10-06",
        exit_stock_bar=_stock_bar(
            session="2026-10-06", open_price=118.0, close_price=120.0
        ),
        exit_benchmark_bar=_benchmark_bar(
            session="2026-10-06", open_price=1080.0, close_price=1100.0
        ),
        corporate_action_audit={
            "status": "READY",
            "actions": [],
            "unresolved_subjects": [],
        },
        corporate_action_source_url="https://www.nseindia.com/api/corporates-corporateActions",
        corporate_action_raw_sha256="d" * 64,
        observed_at_utc="2026-10-06T11:00:00Z",
    )

    assert record["status"] == "COMPLETE"
    assert record["stock_return_pct"] == pytest.approx(20.0)
    assert record["benchmark_return_pct"] == pytest.approx(10.0)
    assert record["gross_excess_pp"] == pytest.approx(10.0)
    assert record["cost_adjusted_excess_pp"] == pytest.approx(9.5)
    assert record["beat_benchmark"] is True
    ledger = append_outcome(new_outcome_ledger(), record)
    validate_outcome_ledger(ledger)


def test_share_changing_action_blocks_horizon_without_guessing() -> None:
    event = _event()
    entry = _entry_ready(event)
    record = build_outcome_record(
        event=event,
        entry_record=entry,
        horizon=20,
        exit_session="2026-10-06",
        exit_stock_bar=_stock_bar(session="2026-10-06", close_price=120.0),
        exit_benchmark_bar=_benchmark_bar(session="2026-10-06", close_price=1100.0),
        corporate_action_audit={
            "status": "READY",
            "actions": [{"ex_date": "2026-09-25", "subject": "Stock Split"}],
            "unresolved_subjects": [],
        },
        corporate_action_source_url="https://www.nseindia.com/api/corporates-corporateActions",
        corporate_action_raw_sha256="d" * 64,
        observed_at_utc="2026-10-06T11:00:00Z",
    )

    assert record["status"] == "BLOCKED"
    assert record["block_reason"] == "SHARE_CHANGING_CORPORATE_ACTION"
    assert record["gross_excess_pp"] is None
    assert record["corporate_action_audit"]["relevant_blocked_actions"] == [
        {"ex_date": "2026-09-25", "subject": "Stock Split"}
    ]


def test_unresolved_action_audit_blocks_horizon() -> None:
    event = _event()
    entry = _entry_ready(event)
    record = build_outcome_record(
        event=event,
        entry_record=entry,
        horizon=20,
        exit_session="2026-10-06",
        exit_stock_bar=_stock_bar(session="2026-10-06", close_price=120.0),
        exit_benchmark_bar=_benchmark_bar(session="2026-10-06", close_price=1100.0),
        corporate_action_audit={
            "status": "UNRESOLVED",
            "actions": [],
            "unresolved_subjects": ["Scheme of Arrangement"],
        },
        corporate_action_source_url="https://www.nseindia.com/api/corporates-corporateActions",
        corporate_action_raw_sha256="d" * 64,
        observed_at_utc="2026-10-06T11:00:00Z",
    )

    assert record["status"] == "BLOCKED"
    assert record["block_reason"] == "CORPORATE_ACTION_AUDIT_UNRESOLVED"


def test_late_preentry_revision_excludes_only_if_all_candidates_are_blocked() -> None:
    first = _source(
        app_id="A1",
        submission_type="Original",
        disseminated="16-Sep-2026 12:00:00",
    )
    second = _source(
        app_id="A2",
        submission_type="Original",
        disseminated="16-Sep-2026 14:00:00",
    )
    early_revision = _source(
        app_id="R1",
        submission_type="Revision",
        disseminated="16-Sep-2026 13:00:00",
    )
    ledger = new_source_ledger()
    ledger = append_sources(
        ledger, [first, second], first_seen_at_utc="2026-09-16T08:31:00Z"
    )
    ledger = append_sources(
        ledger, [early_revision], first_seen_at_utc="2026-09-17T04:00:00Z"
    )
    event = _event()
    event["candidate_source_ids"] = [first["source_id"], second["source_id"]]
    event["eligible_source_ids"] = [first["source_id"], second["source_id"]]

    partial = current_primary_population_audit(event=event, source_ledger=ledger)
    assert partial["status"] == PRIMARY_POPULATION_ELIGIBLE
    assert partial["surviving_candidate_source_ids"] == [second["source_id"]]
    assert partial["provenance_drift"] is True

    late_revision = _source(
        app_id="R2",
        submission_type="Revision",
        disseminated="16-Sep-2026 15:00:00",
    )
    ledger = append_sources(
        ledger, [late_revision], first_seen_at_utc="2026-09-17T04:01:00Z"
    )
    excluded = current_primary_population_audit(event=event, source_ledger=ledger)
    assert excluded["status"] == PRIMARY_POPULATION_RETROACTIVE_GAP
    assert excluded["surviving_candidate_source_ids"] == []
    assert set(excluded["late_discovered_preentry_revision_source_ids"]) == {
        early_revision["source_id"],
        late_revision["source_id"],
    }


def test_entry_and_outcome_ledgers_are_immutable() -> None:
    event = _event()
    entry = _entry_ready(event)
    entries = append_entry(new_entry_ledger(), entry)
    changed_entry = dict(entry)
    changed_entry["entry_isin"] = "INE999A01001"
    changed_entry["entry_record_sha256"] = "e" * 64
    with pytest.raises(H024ProspectiveError):
        append_entry(entries, changed_entry)

    outcome = build_outcome_record(
        event=event,
        entry_record=entry,
        horizon=20,
        exit_session="2026-10-06",
        exit_stock_bar=_stock_bar(session="2026-10-06", close_price=120.0),
        exit_benchmark_bar=_benchmark_bar(session="2026-10-06", close_price=1100.0),
        corporate_action_audit={
            "status": "READY",
            "actions": [],
            "unresolved_subjects": [],
        },
        corporate_action_source_url="https://www.nseindia.com/api/corporates-corporateActions",
        corporate_action_raw_sha256="d" * 64,
        observed_at_utc="2026-10-06T11:00:00Z",
    )
    outcomes = append_outcome(new_outcome_ledger(), outcome)
    changed_outcome = dict(outcome)
    changed_outcome["gross_excess_pp"] = 99.0
    changed_outcome["outcome_record_sha256"] = "f" * 64
    with pytest.raises(H024ProspectiveError):
        append_outcome(outcomes, changed_outcome)
