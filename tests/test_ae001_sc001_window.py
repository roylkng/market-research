from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from marketlab.ae001_sc001_window import resolve_sc001_source_window

WORKFLOW_PATH = Path(".github/workflows/ae001-sc001-prospective-source-timing.yml")


@pytest.mark.parametrize(
    ("utc_iso", "event_name", "branch", "expected"),
    [
        ("2026-10-13T10:59:59+00:00", "workflow_run", "main", "OUTSIDE_PROSPECTIVE_WINDOW"),
        ("2026-10-13T11:00:00+00:00", "workflow_run", "main", "READY"),
        ("2026-10-13T12:59:59+00:00", "workflow_run", "main", "READY"),
        ("2026-10-13T13:00:00+00:00", "workflow_run", "main", "OUTSIDE_PROSPECTIVE_WINDOW"),
        ("2026-10-13T12:59:59+00:00", "workflow_run", "feature/untrusted", "UNTRUSTED_UPSTREAM"),
        ("2026-10-13T12:59:59+00:00", "schedule", None, "READY"),
        ("2026-10-13T13:00:00+00:00", "schedule", None, "OUTSIDE_PROSPECTIVE_WINDOW"),
        ("2026-10-13T10:55:00+00:00", "push", None, "OUTSIDE_PROSPECTIVE_WINDOW"),
        ("2026-10-13T11:15:00+00:00", "push", None, "READY"),
        ("2026-10-13T16:00:00+00:00", "workflow_dispatch", None, "READY"),
        ("2026-09-29T11:30:00+00:00", "workflow_run", "main", "BEFORE_START"),
    ],
)
def test_source_gate_uses_actual_runtime_not_request_or_upstream_time(
    utc_iso: str,
    event_name: str,
    branch: str | None,
    expected: str,
) -> None:
    result = resolve_sc001_source_window(
        observed_at_utc=datetime.fromisoformat(utc_iso),
        event_name=event_name,
        upstream_head_branch=branch,
    )
    assert result["state"] == expected
    assert result["date_ist"] == utc_iso[:10]
    assert result["nse_source_retrieved"] is False
    assert result["data_available_before_1830_ist"] is False
    assert result["prospective_market_decision_authorized"] is False
    assert result["missed_past_market_cutoff_backfill_authorized"] is False
    assert result["live_capital_allowed"] is False


def test_runner_clock_timezone_required_and_events_explicit() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        resolve_sc001_source_window(
            observed_at_utc=datetime(2026, 10, 14, 11, 0),
            event_name="schedule",
        )
    with pytest.raises(ValueError, match="unrecognized"):
        resolve_sc001_source_window(
            observed_at_utc=datetime(2026, 10, 14, 11, 0, tzinfo=UTC),
            event_name="fake_webhook",
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        resolve_sc001_source_window(
            observed_at_utc=None,
            event_name="schedule",
        )


def test_utc_to_ist_date_rollover_applies_at_actual_clock() -> None:
    result = resolve_sc001_source_window(
        observed_at_utc=datetime.fromisoformat("2026-10-13T20:00:00+00:00"),
        event_name="workflow_run",
        upstream_head_branch="main",
    )
    assert result["date_ist"] == "2026-10-14"
    assert result["observed_clock_ist"] == "0130"
    assert result["state"] == "OUTSIDE_PROSPECTIVE_WINDOW"


def test_yaml_has_exact_independent_scheduled_workflow_backstops() -> None:
    original = WORKFLOW_PATH.read_text(encoding="utf-8")
    workflow = yaml.safe_load(original)
    events = workflow.get("on", workflow.get(True))
    assert isinstance(events, dict)
    assert set(events["workflow_run"]["workflows"]) == {
        "H022 P001 prospective stream",
        "Company intelligence v2 prospective news capture",
        "HG008 original NSE hourly first-seen discovery clock",
    }
    assert events["workflow_run"]["branches"] == ["main"]
    assert events["workflow_run"]["types"] == ["completed"]
    assert len(events["schedule"]) == 6
    job = workflow["jobs"]["probe"]
    assert "github.event.workflow_run.head_branch == 'main'" in job["if"]
    assert "run_started_at, 'T11:'" in job["if"]
    assert "run_started_at, 'T12:'" in job["if"]
    names = [item.get("name") for item in job["steps"]]
    assert "Resolve observed runner window, not upstream event timestamp" in names
    assert "Probe same-session official NSE sources" in names
    assert original.index("Resolve observed runner window") < original.index(
        "Probe same-session official NSE sources"
    )
    assert "scripts/resolve_ae001_sc001_runner_window.py" in original
    assert "src/marketlab/ae001_sc001_window.py" in original
    assert "scripts/probe_ae001_sc001.py" in original


def test_source_gate_cli_cannot_promote_untrusted_workflow_completion(
    tmp_path: Path,
) -> None:
    output = tmp_path / "gha-output.txt"
    result = subprocess.run(
        [sys.executable, "scripts/resolve_ae001_sc001_runner_window.py"],
        env={
            **os.environ,
            "GITHUB_EVENT_NAME": "workflow_run",
            "SC001_UPSTREAM_HEAD_BRANCH": "feature/other-repo",
            "GITHUB_OUTPUT": str(output),
        },
        check=True,
        capture_output=True,
        text=True,
    )
    packet = json.loads(result.stdout)
    assert packet["state"] == "UNTRUSTED_UPSTREAM"
    assert packet["missed_past_market_cutoff_backfill_authorized"] is False
    assert "state=UNTRUSTED_UPSTREAM\n" in output.read_text(encoding="utf-8")
