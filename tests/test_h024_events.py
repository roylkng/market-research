from __future__ import annotations

from datetime import date, timedelta

import pytest

from marketlab.h024_acquisition import SOURCE_CONTRACT_ID, canonical_hash
from marketlab.h024_events import (
    EXCLUDED_EVENT_STATUS,
    PRIMARY_EVENT_STATUS,
    append_event,
    build_event_record,
    build_investability_evidence,
    due_event_keys,
    new_event_ledger,
    validate_event_ledger,
)
from marketlab.h024_prospective import (
    H024ProspectiveError,
    append_evidence,
    append_signal,
    append_sources,
    build_signal_record,
    new_evidence_ledger,
    new_signal_ledger,
    new_source_ledger,
)


def _source(
    *,
    symbol: str = "ABC",
    app_id: str,
    submission_type: str,
    disseminated: str,
    prev_app_id: str = "",
) -> dict:
    xml_url = f"https://nsearchives.nseindia.com/corporate/xbrl/{app_id}.xml"
    payload = {
        "source_contract_id": SOURCE_CONTRACT_ID,
        "symbol": symbol,
        "app_id": app_id,
        "submission_type": submission_type,
        "exchange_disseminated_at_utc": disseminated,
        "xml_url": xml_url,
    }
    return {
        "source_id": canonical_hash(payload),
        "symbol": symbol,
        "company_name": "ABC LIMITED",
        "app_id": app_id,
        "prev_app_id": prev_app_id,
        "submission_type": submission_type,
        "revision_remark": "",
        "broadcast_at_utc": disseminated,
        "exchange_disseminated_at_utc": disseminated,
        "xml_url": xml_url,
        "ixbrl_url": f"https://nsearchives.nseindia.com/corporate/ixbrl/{app_id}.html",
        "discovery_row_sha256": "a" * 64,
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
        ]
    }


def _ready_evidence(
    source_id: str,
    *,
    name: str,
    category: str = "Promoter",
    value: float = 30_000_000.0,
) -> dict:
    return {
        "status": "READY",
        "source_id": source_id,
        "xbrl_sha256": canonical_hash({"xbrl": source_id}),
        "date_of_filing": "2026-09-16",
        "transaction_count": 1,
        "direct_market_purchase_count": 1,
        "direct_market_purchase_value_inr": value,
        "direct_market_purchase_quantity": 100_000,
        "direct_market_purchase_ownership_delta_pp": 0.10,
        "direct_market_purchase_actor_count": 1,
        "direct_market_purchase_categories": [category],
        "direct_market_purchase_names": [name],
    }


def _state_with_signals(*sources: tuple[dict, str, str]) -> tuple[dict, dict, dict]:
    source_ledger = new_source_ledger()
    evidence_ledger = new_evidence_ledger()
    signal_ledger = new_signal_ledger()
    for source, first_seen, actor in sources:
        source_ledger = append_sources(
            source_ledger, [source], first_seen_at_utc=first_seen
        )
        if source["submission_type"] != "Original":
            continue
        evidence_ledger = append_evidence(
            evidence_ledger,
            source_ledger,
            _ready_evidence(source["source_id"], name=actor),
            frozen_at_utc=first_seen,
        )
        signal = build_signal_record(
            source_ledger=source_ledger,
            evidence_ledger=evidence_ledger,
            calendar=_calendar(),
            source_id=source["source_id"],
            frozen_at_utc=first_seen,
        )
        assert signal is not None
        signal_ledger = append_signal(signal_ledger, signal)
    return source_ledger, evidence_ledger, signal_ledger


def _prior_sessions(
    *,
    count: int = 60,
    isin: str = "INE000A01001",
    value: float = 30_000_000.0,
) -> list[dict]:
    result = []
    cursor = date(2026, 9, 15)
    for index in range(count):
        result.append(
            {
                "session_date": cursor.isoformat(),
                "source_url": (
                    "https://nsearchives.nseindia.com/content/cm/"
                    f"BhavCopy_NSE_CM_0_0_0_{cursor.strftime('%Y%m%d')}_F_0000.csv.zip"
                ),
                "raw_sha256": canonical_hash({"session": cursor.isoformat()}),
                "isin": isin,
                "traded_value_inr": value,
            }
        )
        cursor -= timedelta(days=1)
    return result


def _investability(
    *,
    status: str = "1",
    value: float = 30_000_000.0,
    count: int = 60,
) -> dict:
    isin = "INE000A01001"
    return build_investability_evidence(
        symbol="ABC",
        planned_entry_session="2026-09-17",
        security_master_source_url=(
            "https://www.nseindia.com/api/reports?mode=single"
        ),
        security_master_sha256="b" * 64,
        security_master_fields={
            "TckrSymb": "ABC",
            "SctySrs": "EQ",
            "ISIN": isin,
            "SctyTpFlg": "EQ",
            "PrtdToTrad": "1",
            "SctyStsNrmlMkt": status,
            "ElgbltyNrmlMkt": "1",
            "DelFlg": "N",
        },
        prior_sessions=_prior_sessions(count=count, isin=isin, value=value),
    )


def test_primary_event_is_aggregated_and_sealed() -> None:
    first = _source(
        app_id="A1",
        submission_type="Original",
        disseminated="2026-09-16T06:30:00Z",
    )
    second = _source(
        app_id="A2",
        submission_type="Original",
        disseminated="2026-09-16T08:30:00Z",
    )
    source_ledger, evidence_ledger, signal_ledger = _state_with_signals(
        (first, "2026-09-16T06:31:00Z", "Alice Promoter"),
        (second, "2026-09-16T08:31:00Z", "Bob Director"),
    )
    record = build_event_record(
        source_ledger=source_ledger,
        evidence_ledger=evidence_ledger,
        signal_ledger=signal_ledger,
        symbol="ABC",
        planned_entry_session="2026-09-17",
        investability=_investability(),
        frozen_at_utc="2026-09-17T03:44:00Z",
    )
    assert record["status"] == PRIMARY_EVENT_STATUS
    assert record["h024_direct_market_purchase"] == 1
    assert record["qualifying_filing_count"] == 2
    assert record["qualifying_transaction_count"] == 2
    assert record["direct_market_purchase_actor_count"] == 2
    assert record["direct_market_purchase_names"] == [
        "Alice Promoter",
        "Bob Director",
    ]
    ledger = append_event(new_event_ledger(), record)
    validate_event_ledger(ledger)
    assert due_event_keys(
        signal_ledger=signal_ledger,
        event_ledger=ledger,
        planned_entry_session="2026-09-17",
    ) == []


def test_revision_blocks_only_the_earlier_candidate() -> None:
    first = _source(
        app_id="A1",
        submission_type="Original",
        disseminated="2026-09-16T06:30:00Z",
    )
    revision = _source(
        app_id="R1",
        submission_type="Revision",
        disseminated="2026-09-16T07:30:00Z",
        prev_app_id="A1",
    )
    second = _source(
        app_id="A2",
        submission_type="Original",
        disseminated="2026-09-16T08:30:00Z",
    )
    source_ledger, evidence_ledger, signal_ledger = _state_with_signals(
        (first, "2026-09-16T06:31:00Z", "Alice Promoter"),
        (revision, "2026-09-16T07:31:00Z", ""),
        (second, "2026-09-16T08:31:00Z", "Bob Director"),
    )
    record = build_event_record(
        source_ledger=source_ledger,
        evidence_ledger=evidence_ledger,
        signal_ledger=signal_ledger,
        symbol="ABC",
        planned_entry_session="2026-09-17",
        investability=_investability(),
        frozen_at_utc="2026-09-17T03:44:00Z",
    )
    assert record["status"] == PRIMARY_EVENT_STATUS
    assert record["revision_blocked_source_ids"] == [first["source_id"]]
    assert record["eligible_source_ids"] == [second["source_id"]]
    assert record["revision_source_ids"] == [revision["source_id"]]


def test_revision_blocks_event_when_no_candidate_survives() -> None:
    original = _source(
        app_id="A1",
        submission_type="Original",
        disseminated="2026-09-16T06:30:00Z",
    )
    revision = _source(
        app_id="R1",
        submission_type="Revision",
        disseminated="2026-09-16T07:30:00Z",
    )
    source_ledger, evidence_ledger, signal_ledger = _state_with_signals(
        (original, "2026-09-16T06:31:00Z", "Alice Promoter"),
        (revision, "2026-09-16T07:31:00Z", ""),
    )
    record = build_event_record(
        source_ledger=source_ledger,
        evidence_ledger=evidence_ledger,
        signal_ledger=signal_ledger,
        symbol="ABC",
        planned_entry_session="2026-09-17",
        investability=_investability(),
        frozen_at_utc="2026-09-17T03:44:00Z",
    )
    assert record["status"] == EXCLUDED_EVENT_STATUS
    assert record["exclusion_reason"] == "REVISION_BLOCKED"
    assert record["h024_direct_market_purchase"] == 0


@pytest.mark.parametrize(
    ("master_status", "expected_reason"),
    [("3", "SECURITY_MASTER_BLOCKED"), ("1", None)],
)
def test_security_master_status_is_fail_closed(
    master_status: str, expected_reason: str | None
) -> None:
    evidence = _investability(status=master_status)
    assert evidence["reason"] == expected_reason


def test_liquidity_and_history_gates_match_h004_primary() -> None:
    low_liquidity = _investability(value=19_999_999.0)
    assert low_liquidity["reason"] == "LIQUIDITY_BELOW_H004_PRIMARY"
    short_history = _investability(count=59)
    assert short_history["reason"] == "INSUFFICIENT_60_SESSION_PRICE_HISTORY"


def test_late_event_freeze_is_never_executable() -> None:
    original = _source(
        app_id="A1",
        submission_type="Original",
        disseminated="2026-09-16T06:30:00Z",
    )
    source_ledger, evidence_ledger, signal_ledger = _state_with_signals(
        (original, "2026-09-16T06:31:00Z", "Alice Promoter"),
    )
    record = build_event_record(
        source_ledger=source_ledger,
        evidence_ledger=evidence_ledger,
        signal_ledger=signal_ledger,
        symbol="ABC",
        planned_entry_session="2026-09-17",
        investability=_investability(),
        frozen_at_utc="2026-09-17T03:45:00Z",
    )
    assert record["status"] == EXCLUDED_EVENT_STATUS
    assert record["exclusion_reason"] == "LATE_EVENT_FREEZE"


def test_event_is_immutable() -> None:
    original = _source(
        app_id="A1",
        submission_type="Original",
        disseminated="2026-09-16T06:30:00Z",
    )
    source_ledger, evidence_ledger, signal_ledger = _state_with_signals(
        (original, "2026-09-16T06:31:00Z", "Alice Promoter"),
    )
    record = build_event_record(
        source_ledger=source_ledger,
        evidence_ledger=evidence_ledger,
        signal_ledger=signal_ledger,
        symbol="ABC",
        planned_entry_session="2026-09-17",
        investability=_investability(),
        frozen_at_utc="2026-09-17T03:44:00Z",
    )
    ledger = append_event(new_event_ledger(), record)
    changed = dict(record)
    changed["direct_market_purchase_value_inr"] = 1.0
    changed["event_record_sha256"] = canonical_hash(
        {key: value for key, value in changed.items() if key != "event_record_sha256"}
    )
    with pytest.raises(H024ProspectiveError, match="immutable"):
        append_event(ledger, changed)
