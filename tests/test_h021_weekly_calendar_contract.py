from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketlab.h021_stockanalysis_acquisition import (
    CAPTURE,
    NO_SESSION,
    NOT_FINAL_SESSION,
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
