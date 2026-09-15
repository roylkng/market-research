from __future__ import annotations

from datetime import date, timedelta

from marketlab.h024_acquisition import canonical_hash, source_from_discovery_row
from marketlab.h024_events import (
    append_event,
    build_event_record,
    build_investability_evidence,
    new_event_ledger,
)
from marketlab.h024_outcomes import new_outcome_ledger
from marketlab.h024_prospective import (
    append_evidence,
    append_signal,
    append_sources,
    build_signal_record,
    new_evidence_ledger,
    new_signal_ledger,
    new_source_ledger,
)
from marketlab.h024_prospective_summary import (
    build_prospective_evaluation_report,
    build_prospective_summary,
)
from marketlab.h024_sessions import (
    append_session,
    build_session_record,
    new_session_ledger,
)


def _source(
    *,
    app_id: str,
    disseminated: str,
    submission_type: str = "Original",
) -> dict:
    source = source_from_discovery_row(
        {
            "symbol": "ABC",
            "companyName": "ABC Limited",
            "regulation": "Regulation 7 (2)",
            "appId": app_id,
            "prevAppId": "",
            "typeOfSubmission": submission_type,
            "revisionRemark": "",
            "broadcastDateTime": disseminated,
            "exchdisstime": disseminated,
            "xmlFileName": (
                f"https://nsearchives.nseindia.com/corporate/xbrl/{app_id}.xml"
            ),
            "ixbrl": (
                f"https://nsearchives.nseindia.com/corporate/xbrl/{app_id}.html"
            ),
        }
    )
    assert source is not None
    return source


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


def _ready_evidence(source_id: str, *, value: float, actor: str) -> dict:
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
        "direct_market_purchase_categories": ["Promoter"],
        "direct_market_purchase_names": [actor],
    }


def _prior_sessions() -> list[dict]:
    result = []
    cursor = date(2026, 9, 15)
    for _ in range(60):
        result.append(
            {
                "session_date": cursor.isoformat(),
                "source_url": (
                    "https://nsearchives.nseindia.com/content/cm/"
                    f"BhavCopy_NSE_CM_0_0_0_{cursor.strftime('%Y%m%d')}_F_0000.csv.zip"
                ),
                "raw_sha256": canonical_hash({"session": cursor.isoformat()}),
                "isin": "INE000A01001",
                "traded_value_inr": 30_000_000.0,
            }
        )
        cursor -= timedelta(days=1)
    return result


def _state_with_event() -> tuple[dict, dict, dict, dict, dict]:
    first = _source(app_id="A1", disseminated="16-Sep-2026 12:00:00")
    second = _source(app_id="A2", disseminated="16-Sep-2026 14:00:00")
    sources = new_source_ledger()
    evidence = new_evidence_ledger()
    signals = new_signal_ledger()
    for source, first_seen, value, actor in (
        (first, "2026-09-16T06:31:00Z", 30_000_000.0, "Alice Promoter"),
        (second, "2026-09-16T08:31:00Z", 40_000_000.0, "Bob Promoter"),
    ):
        sources = append_sources(sources, [source], first_seen_at_utc=first_seen)
        evidence = append_evidence(
            evidence,
            sources,
            _ready_evidence(source["source_id"], value=value, actor=actor),
            frozen_at_utc=first_seen,
        )
        signal = build_signal_record(
            source_ledger=sources,
            evidence_ledger=evidence,
            calendar=_calendar(),
            source_id=source["source_id"],
            frozen_at_utc=first_seen,
        )
        assert signal is not None
        signals = append_signal(signals, signal)

    investability = build_investability_evidence(
        symbol="ABC",
        planned_entry_session="2026-09-17",
        security_master_source_url="https://www.nseindia.com/api/reports?mode=single",
        security_master_sha256="a" * 64,
        security_master_fields={
            "TckrSymb": "ABC",
            "SctySrs": "EQ",
            "ISIN": "INE000A01001",
            "SctyTpFlg": "EQ",
            "PrtdToTrad": "1",
            "SctyStsNrmlMkt": "1",
            "ElgbltyNrmlMkt": "1",
            "DelFlg": "N",
        },
        prior_sessions=_prior_sessions(),
    )
    event = build_event_record(
        source_ledger=sources,
        evidence_ledger=evidence,
        signal_ledger=signals,
        symbol="ABC",
        planned_entry_session="2026-09-17",
        investability=investability,
        frozen_at_utc="2026-09-17T03:44:00Z",
    )
    events = append_event(new_event_ledger(), event)
    return sources, evidence, signals, events, event


def _session_ledger(count: int) -> dict:
    ledger = new_session_ledger()
    cursor = date(2026, 9, 17)
    observed = 0
    while observed < count:
        if cursor.weekday() < 5:
            day = cursor.isoformat()
            bar = {
                "benchmark_id": "nifty_500",
                "index_name": "Nifty 500",
                "session_date": day,
                "open_price": 1000.0 + observed,
                "close_price": 1005.0 + observed,
                "source_url": (
                    "https://archives.nseindia.com/content/indices/"
                    f"ind_close_all_{cursor.strftime('%d%m%Y')}.csv"
                ),
                "raw_sha256": canonical_hash({"index": day}),
            }
            ledger = append_session(
                ledger,
                build_session_record(
                    benchmark_bar=bar,
                    observed_at_utc=f"{day}T12:30:00Z",
                ),
            )
            observed += 1
        cursor += timedelta(days=1)
    return ledger


def test_empty_prospective_summary_is_insufficient_coverage() -> None:
    summary = build_prospective_summary(
        source_ledger=new_source_ledger(),
        evidence_ledger=new_evidence_ledger(),
        event_ledger=new_event_ledger(),
        session_ledger=new_session_ledger(),
        outcome_ledger=new_outcome_ledger(),
    )

    assert summary["primary_classification"] == "INSUFFICIENT_COVERAGE"
    assert summary["current_primary_event_count"] == 0
    assert summary["horizons"]["60"]["complete_count"] == 0
    assert summary["live_capital_allowed"] is False


def test_observed_mature_event_is_in_coverage_denominator_before_outcome_arrives() -> None:
    sources, evidence, _signals, events, _event = _state_with_event()
    report, diagnostics = build_prospective_evaluation_report(
        source_ledger=sources,
        evidence_ledger=evidence,
        event_ledger=events,
        session_ledger=_session_ledger(20),
        outcome_ledger=new_outcome_ledger(),
    )
    summary = build_prospective_summary(
        source_ledger=sources,
        evidence_ledger=evidence,
        event_ledger=events,
        session_ledger=_session_ledger(20),
        outcome_ledger=new_outcome_ledger(),
    )

    assert diagnostics["current_primary_event_count"] == 1
    assert report["records"][0]["horizons"]["20"]["status"] == "MATURE_OUTCOME_PENDING"
    assert summary["horizons"]["20"]["mature_event_count"] == 1
    assert summary["horizons"]["20"]["complete_count"] == 0
    assert summary["horizons"]["20"]["complete_share_of_mature"] == 0.0


def test_late_revision_recomputes_surviving_descriptive_value_without_rewriting_event() -> None:
    sources, evidence, _signals, events, event = _state_with_event()
    first_id = event["candidate_source_ids"][0]
    second_id = event["candidate_source_ids"][1]
    first_source = next(
        row["source"] for row in sources["records"] if row["source"]["source_id"] == first_id
    )
    second_source = next(
        row["source"] for row in sources["records"] if row["source"]["source_id"] == second_id
    )
    assert first_source["exchange_disseminated_at_utc"] < second_source[
        "exchange_disseminated_at_utc"
    ]
    revision = _source(
        app_id="R1",
        submission_type="Revision",
        disseminated="16-Sep-2026 13:00:00",
    )
    sources = append_sources(
        sources,
        [revision],
        first_seen_at_utc="2026-09-17T04:00:00Z",
    )

    report, diagnostics = build_prospective_evaluation_report(
        source_ledger=sources,
        evidence_ledger=evidence,
        event_ledger=events,
        session_ledger=_session_ledger(1),
        outcome_ledger=new_outcome_ledger(),
    )

    assert diagnostics["current_primary_event_count"] == 1
    assert diagnostics["provenance_drift_event_count"] == 1
    assert report["event_count"] == 1
    assert report["records"][0]["purchase_value_inr"] == 40_000_000.0
    assert event["direct_market_purchase_value_inr"] == 70_000_000.0


def test_late_revisions_that_block_all_candidates_remove_event_from_primary_population() -> None:
    sources, evidence, _signals, events, event = _state_with_event()
    for app_id, disseminated, seen in (
        ("R1", "16-Sep-2026 13:00:00", "2026-09-17T04:00:00Z"),
        ("R2", "16-Sep-2026 15:00:00", "2026-09-17T04:01:00Z"),
    ):
        sources = append_sources(
            sources,
            [_source(app_id=app_id, submission_type="Revision", disseminated=disseminated)],
            first_seen_at_utc=seen,
        )

    report, diagnostics = build_prospective_evaluation_report(
        source_ledger=sources,
        evidence_ledger=evidence,
        event_ledger=events,
        session_ledger=_session_ledger(1),
        outcome_ledger=new_outcome_ledger(),
    )

    assert event["status"] == "PRIMARY_ELIGIBLE"
    assert diagnostics["sealed_primary_event_count"] == 1
    assert diagnostics["current_primary_event_count"] == 0
    assert diagnostics["retroactive_preentry_revision_excluded_event_count"] == 1
    assert report["event_count"] == 0
