"""T012 scheduler operations must never repair a late prospective decision."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.preflight_ae001_t012_runner import (
    PreflightContractError,
    next_target_gate,
)

ROOT = Path(__file__).resolve().parents[1]


def _source():
    return {
        "calendar": {
            "sessions": [
                {
                    "session_date": "2026-10-15",
                    "close_timestamp_utc": "2026-10-15T10:00:00Z",
                },
                {
                    "session_date": "2026-10-16",
                    "close_timestamp_utc": "2026-10-16T10:00:00Z",
                },
                {
                    "session_date": "2026-10-19",
                    "close_timestamp_utc": "2026-10-19T10:00:00Z",
                },
            ]
        },
        "sc001_ledger": {
            "attempts": [{
                "session_date": "2026-10-15",
                "attempt_sha256": "a" * 64,
                "eligible_before_cutoff": True,
                "market": {"status": "READY"},
                "delivery": {"status": "READY"},
            }],
        },
        "sc003_ledger": {
            "attempts": [{
                "target_session_date": "2026-10-15",
                "captured_at_utc": "2026-10-15T19:22:55Z",
                "ready_before_preopen_cutoff": True,
                "source_status": "READY",
                "sc001_attempt_sha256": "a" * 64,
            }],
        },
        "decision_ledger": {"decisions": []},
    }


def _gate(inputs, now):
    return next_target_gate(
        now_utc=datetime.fromisoformat(now),
        **inputs,
    )


def test_oct15_original_source_can_start_before_oct16_preopen_cutoff():
    value = _gate(_source(), "2026-10-16T00:15:00+00:00")
    assert value["should_score"] is True
    assert value["state"] == "READY_FOR_AUTHORITATIVE_TRIAL_GATES"
    assert value["feature_session"] == "2026-10-15"
    assert value["entry_session"] == "2026-10-16"
    assert value["cutoff_utc"] == "2026-10-16T03:00:00+00:00"
    assert value["operational_preflight_not_scientific_evidence"]
    assert value["live_capital_allowed"] is False


def test_observed_oct16_delayed_github_schedule_cannot_backfill():
    value = _gate(_source(), "2026-10-16T04:36:06+00:00")
    assert value["should_score"] is False
    assert value["state"] == "MISSED_REMOTE_ANCHOR_MARGIN_NO_BACKFILL"
    near = _gate(_source(), "2026-10-16T02:59:00+00:00")
    assert near["should_score"] is False


def test_missing_source_or_source_not_anchored_has_no_prediction():
    empty = _source()
    empty["sc003_ledger"]["attempts"] = []
    assert _gate(empty, "2026-10-16T00:20:00Z")["state"] == (
        "NO_PROSPECTIVE_READY_FUTURES_SOURCE"
    )
    wrong = _source()
    wrong["sc003_ledger"]["attempts"][0][
        "sc001_attempt_sha256"
    ] = "b" * 64
    assert _gate(wrong, "2026-10-16T00:20:00Z")["state"] == (
        "SOURCE_NOT_YET_LINKED_AND_TIMELY"
    )
    prior = _source()
    prior["sc003_ledger"]["attempts"][0][
        "target_session_date"
    ] = "2026-10-14"
    assert _gate(prior, "2026-10-16T00:20:00Z")["state"] == (
        "NO_PROSPECTIVE_READY_FUTURES_SOURCE"
    )


def test_earlier_than_exchange_close_or_sealed_is_never_scored():
    assert _gate(_source(), "2026-10-15T09:30:00Z")["state"] == (
        "TARGET_EXCHANGE_SESSION_NOT_CLOSED"
    )
    full = _source()
    full["decision_ledger"]["decisions"] = [
        {"session_date": "2026-10-15"}
    ]
    assert _gate(full, "2026-10-16T00:30:00Z")["state"] == (
        "ALREADY_SEALED"
    )


def test_change_to_wrong_calendar_breaks_original_preopen_contract():
    wrong = _source()
    wrong["calendar"]["sessions"][1]["session_date"] = "2026-10-15"
    with pytest.raises(PreflightContractError, match="not strict"):
        _gate(wrong, "2026-10-16T00:15:00Z")


def test_real_oct15_source_was_ready_before_expiry_but_now_past():
    def _json(path):
        return json.loads((ROOT / path).read_text("utf-8"))

    sc001 = _json("research/prospective/ae001-sc001/source-ledger.json")
    sc003 = _json("research/prospective/ae001-sc003/source-ledger.json")
    sc001["attempts"] = [
        row for row in sc001["attempts"]
        if row.get("session_date", "") <= "2026-10-15"
    ]
    sc003["attempts"] = [
        row for row in sc003["attempts"]
        if row.get("target_session_date", "") <= "2026-10-15"
    ]
    value = next_target_gate(
        now_utc=datetime(2026, 10, 16, 0, 30, tzinfo=UTC),
        calendar=_json(
            "research/prospective/calendars/FY27-Q2-2026-09-06/"
            "NSE-CM-FY27Q2-v1.json"
        ),
        sc001_ledger=sc001,
        sc003_ledger=sc003,
        decision_ledger=_json(
            "research/prospective/ae001-t012/decision-ledger.json"
        ),
    )
    assert value["should_score"] is True
    actual_late = next_target_gate(
        now_utc=datetime(2026, 10, 16, 4, 36, tzinfo=UTC),
        calendar=_json(
            "research/prospective/calendars/FY27-Q2-2026-09-06/"
            "NSE-CM-FY27Q2-v1.json"
        ),
        sc001_ledger=sc001,
        sc003_ledger=sc003,
        decision_ledger=_json(
            "research/prospective/ae001-t012/decision-ledger.json"
        ),
    )
    assert actual_late["should_score"] is False


def test_standalone_preflight_cli_has_no_background_tasks():
    proc = subprocess.run(
        [sys.executable, "scripts/preflight_ae001_t012_runner.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    status = json.loads(proc.stdout)
    assert status["operational_preflight_not_scientific_evidence"]
    assert status["live_capital_allowed"] is False
    assert status["state"] in {
        "MISSED_REMOTE_ANCHOR_MARGIN_NO_BACKFILL",
        "READY_FOR_AUTHORITATIVE_TRIAL_GATES",
        "NO_PROSPECTIVE_READY_FUTURES_SOURCE",
        "ALREADY_SEALED",
        "SOURCE_NOT_YET_LINKED_AND_TIMELY",
    }
