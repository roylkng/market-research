from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from marketlab.h021_stockanalysis_acquisition import (
    BEFORE_POST_CLOSE_WINDOW,
    CAPTURE,
    NO_SESSION,
    NOT_FINAL_SESSION,
    post_close_weekly_session_decision,
    weekly_session_decision,
)

CALENDAR_PATH = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json"
)
WORKFLOW_PATH = Path(".github/workflows/h021-weekly-consensus-capture.yml")


def _frozen_calendar() -> dict:
    payload = json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_actual_frozen_calendar_drives_weekly_h021_cadence() -> None:
    calendar = _frozen_calendar()
    assert weekly_session_decision("2026-09-14", calendar).state == NO_SESSION
    assert weekly_session_decision("2026-09-17", calendar).state == NOT_FINAL_SESSION
    assert weekly_session_decision("2026-09-18", calendar).state == CAPTURE
    assert weekly_session_decision("2026-10-01", calendar).state == CAPTURE


def test_h021_weekly_gate_fails_closed_on_unresolved_special_session_week() -> None:
    with pytest.raises(ValueError, match="unresolved NSE special-session"):
        weekly_session_decision("2026-11-06", _frozen_calendar())


def test_h021_weekly_gate_stops_when_frozen_calendar_expires() -> None:
    with pytest.raises(ValueError, match="outside frozen calendar coverage"):
        weekly_session_decision("2027-01-01", _frozen_calendar())


def test_h021_anchor_guard_ignores_unrelated_main_movements_only() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert 'git diff --name-only "$START_SHA" "$CURRENT_MAIN"' in workflow
    assert "frozen H021 inputs changed during acquisition" in workflow
    assert "main moved only outside frozen H021 inputs" in workflow
    assert "git merge --ff-only origin/main" in workflow
    for critical_path in (
        ".github/workflows/h021-weekly-consensus-capture.yml",
        "research/H021_PROSPECTIVE_PROTOCOL_V1.md",
        "research/H021_COMPARISON_CONTRACT_V1.md",
        "research/H021_WEEKLY_ACQUISITION_CONTRACT_V1.md",
        "research/prospective/h021",
        "research/prospective/universes/FY27-Q2-2026-09-06.json",
        "research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json",
        "src/marketlab/h021_capture.py",
        "src/marketlab/h021_stockanalysis_acquisition.py",
    ):
        assert f'"{critical_path}"' in workflow


def test_h021_workflow_artifact_retains_machine_sealed_bytes() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert '"$WORK/sealed-capture.json.gz"' in workflow
    assert '"$WORK/sealed-capture.manifest.json"' in workflow
    assert '"$WORK/sealed-capture.md"' in workflow


def test_h021_workflow_has_redundant_idempotent_schedule() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    for cron in (
        "45 12 * * 1-5",
        "15 13 * * 1-5",
        "45 13 * * 1-5",
    ):
        assert f"cron: '{cron}'" in workflow
    assert 'git fetch origin main' in workflow
    assert 'git cat-file -e "origin/main:${CAPTURE_PATH}"' in workflow
    assert 'STATE="ALREADY_CAPTURED"' in workflow


def test_delayed_thursday_cron_cannot_capture_friday_before_market_close() -> None:
    decision = post_close_weekly_session_decision(
        "2026-10-09",
        _frozen_calendar(),
        observed_at_utc=datetime(2026, 10, 8, 19, 0, tzinfo=UTC),
    )
    assert decision.state == BEFORE_POST_CLOSE_WINDOW
    assert decision.final_session_date == "2026-10-09"


def test_actual_friday_post_close_window_may_capture() -> None:
    decision = post_close_weekly_session_decision(
        "2026-10-09",
        _frozen_calendar(),
        observed_at_utc=datetime(2026, 10, 9, 13, 0, tzinfo=UTC),
    )
    assert decision.state == CAPTURE


def test_thursday_after_close_is_not_last_session() -> None:
    decision = post_close_weekly_session_decision(
        "2026-10-08",
        _frozen_calendar(),
        observed_at_utc=datetime(2026, 10, 8, 13, 0, tzinfo=UTC),
    )
    assert decision.state == NOT_FINAL_SESSION


def test_capture_date_cannot_differ_from_real_india_date() -> None:
    with pytest.raises(ValueError, match="current India date"):
        post_close_weekly_session_decision(
            "2026-10-09",
            _frozen_calendar(),
            observed_at_utc=datetime(2026, 10, 8, 12, 50, tzinfo=UTC),
        )


def test_post_close_gate_rejects_naive_clock() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        post_close_weekly_session_decision(
            "2026-10-09",
            _frozen_calendar(),
            observed_at_utc=datetime(2026, 10, 9, 13, 0),
        )
