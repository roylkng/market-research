from __future__ import annotations

from datetime import UTC, datetime

import pytest

from marketlab.evaluation import load_yaml
from marketlab.prospective import (
    ObservationStore,
    ProspectiveError,
    build_prospective_report,
    select_first_result_candidate,
    validate_runner_rule_document,
)


def test_runner_rule_hash_is_frozen():
    document = load_yaml("registry/h002_runner_rule.yaml")
    assert validate_runner_rule_document(document) == document["sha256"]
    assert document["live_capital"] is False


def test_result_selection_uses_earliest_official_filing_and_retains_revisions():
    payload = {
        "data": [
            {
                "type": "Integrated Filing- Financials",
                "symbol": "TEST",
                "consolidated": "Consolidated",
                "qe_Date": "30-Sep-2026",
                "broadcast_Date": "30-Oct-2026 18:00:00",
                "xbrl": "https://nsearchives.nseindia.com/second.xml",
            },
            {
                "type": "Integrated Filing- Financials",
                "symbol": "TEST",
                "consolidated": "Consolidated",
                "qe_Date": "30-Sep-2026",
                "broadcast_Date": "30-Oct-2026 17:00:00",
                "xbrl": "https://nsearchives.nseindia.com/first.xml",
            },
        ]
    }
    selection = select_first_result_candidate(
        payload,
        symbol="TEST",
        target_period_end="2026-09-30",
        accounting_basis="Consolidated",
    )
    assert selection is not None
    assert selection.first.source_url.endswith("first.xml")
    assert [item.source_url for item in selection.revisions] == [
        "https://nsearchives.nseindia.com/second.xml"
    ]


def test_result_selection_rejects_ambiguous_first_publication():
    payload = {
        "data": [
            {
                "type": "Integrated Filing- Financials",
                "symbol": "TEST",
                "consolidated": "Consolidated",
                "qe_Date": "30-Sep-2026",
                "broadcast_Date": "30-Oct-2026 17:00:00",
                "xbrl": "https://nsearchives.nseindia.com/a.xml",
            },
            {
                "type": "Integrated Filing- Financials",
                "symbol": "TEST",
                "consolidated": "Consolidated",
                "qe_Date": "30-Sep-2026",
                "broadcast_Date": "30-Oct-2026 17:00:00",
                "xbrl": "https://nsearchives.nseindia.com/b.xml",
            },
        ]
    }
    with pytest.raises(ProspectiveError, match="ambiguous first"):
        select_first_result_candidate(
            payload,
            symbol="TEST",
            target_period_end="2026-09-30",
            accounting_basis="Consolidated",
        )


def _position(status="COMPLETED", gross=10.0, nifty_excess=4.0, mom_excess=2.0):
    return {
        "status": status,
        "gross_return_pct": gross if status == "COMPLETED" else None,
        "cost_stressed_return_pct": (
            {"0": gross, "25": gross - 0.25, "50": gross - 0.5}
            if status == "COMPLETED"
            else None
        ),
        "benchmarks": [
            {
                "benchmark_id": "nifty_50",
                "excess_return_pct": nifty_excess if status == "COMPLETED" else None,
            },
            {
                "benchmark_id": "nifty_200_momentum_30",
                "excess_return_pct": mom_excess if status == "COMPLETED" else None,
            },
        ],
    }


def test_observation_ledger_is_hash_chained_and_deduplicates_identical_state(tmp_path):
    store = ObservationStore(tmp_path)
    now = datetime(2026, 10, 30, 12, tzinfo=UTC)
    first, created = store.append(
        cohort_id="C1",
        symbol="TEST",
        target_period_end="2026-09-30",
        recorded_at=now,
        state="PENDING",
        reason="exit_not_due",
        signal={"bucket": "POSITIVE"},
        paper_position=_position("PENDING"),
    )
    assert created is True
    repeated, created = store.append(
        cohort_id="C1",
        symbol="TEST",
        target_period_end="2026-09-30",
        recorded_at=datetime(2026, 10, 30, 13, tzinfo=UTC),
        state="PENDING",
        reason="exit_not_due",
        signal={"bucket": "POSITIVE"},
        paper_position=_position("PENDING"),
    )
    assert created is False
    assert repeated.snapshot_id == first.snapshot_id

    completed, created = store.append(
        cohort_id="C1",
        symbol="TEST",
        target_period_end="2026-09-30",
        recorded_at=datetime(2026, 11, 30, 13, tzinfo=UTC),
        state="COMPLETED",
        signal={"bucket": "POSITIVE"},
        paper_position=_position(),
    )
    assert created is True
    assert completed.parent_snapshot_id == first.snapshot_id
    snapshots = store.snapshots("C1", "TEST", "2026-09-30")
    assert [item.sequence for item in snapshots] == [1, 2]


def test_report_uses_only_completed_positions_for_returns(tmp_path):
    store = ObservationStore(tmp_path)
    now = datetime(2026, 12, 1, tzinfo=UTC)
    store.append(
        cohort_id="C1",
        symbol="A",
        target_period_end="2026-09-30",
        recorded_at=now,
        state="COMPLETED",
        signal={"bucket": "POSITIVE"},
        paper_position=_position(gross=10, nifty_excess=4, mom_excess=2),
    )
    store.append(
        cohort_id="C1",
        symbol="B",
        target_period_end="2026-09-30",
        recorded_at=now,
        state="PENDING",
        signal={"bucket": "NEGATIVE"},
        paper_position=_position("PENDING"),
    )
    report = build_prospective_report(store, cohort_id="C1", generated_at=now)
    assert report.paper_only is True
    assert report.live_capital_allowed is False
    assert report.completed_count == 1
    assert report.completed_statistics["mean_raw_return_pct"] == 10.0
    assert report.completed_statistics["mean_nifty50_excess_pct"] == 4.0
    assert report.latest_state_counts == {"COMPLETED": 1, "PENDING": 1}
