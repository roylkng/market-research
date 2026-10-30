from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021_calendar_supersession import (
    BASE_GIT_BLOB,
    BASE_SHA256,
    NOV08_AMENDMENT_SHA256,
    NOV08_GIT_BLOB,
    NOV08_SHA256,
    expected_calendar_git_blob,
    expected_calendar_path,
    validate_effective_h021_calendar,
)
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
            observed_at_utc=datetime(2026, 10, 9, 13, 0, tzinfo=UTC).replace(tzinfo=None),
        )


NOV08_CALENDAR_PATH = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/"
    "NSE-CM-FY27Q2-v2-Nov08-Muhurat.json"
)


def _nov08_calendar() -> dict:
    payload = json.loads(NOV08_CALENDAR_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_source_pinned_calendar_supersession_preserves_frozen_original() -> None:
    original = _frozen_calendar()
    amended = _nov08_calendar()
    assert original["version"] == "NSE-CM-FY27Q2-v1"
    assert original["sha256"] == BASE_SHA256
    assert original["unresolved_special_dates"] == ["2026-11-08"]
    assert not any(row["session_date"] == "2026-11-08" for row in original["sessions"])
    assert load_calendar_snapshot(CALENDAR_PATH).sha256 == BASE_SHA256
    assert load_calendar_snapshot(NOV08_CALENDAR_PATH).sha256 == NOV08_SHA256
    assert amended["supersession"]["immutable_base_calendar_sha256"] == BASE_SHA256
    assert amended["supersession"]["reviewed_h021_source_amendment_sha256"] == NOV08_AMENDMENT_SHA256
    assert amended["supersession"]["individual_CAS_price_basis_verified"] is False
    assert amended["holidays"] == original["holidays"]
    assert len(amended["sessions"]) == len(original["sessions"]) + 1
    assert expected_calendar_git_blob("2026-10-30") == BASE_GIT_BLOB
    assert expected_calendar_git_blob("2026-11-08") == NOV08_GIT_BLOB
    assert expected_calendar_path("2026-10-30") == str(CALENDAR_PATH)
    assert expected_calendar_path("2026-11-08") == str(NOV08_CALENDAR_PATH)
    validate_effective_h021_calendar(original, capture_date_ist="2026-10-30")
    validate_effective_h021_calendar(amended, capture_date_ist="2026-11-08")


def test_november_calendar_weekly_final_session_and_clock() -> None:
    original = _frozen_calendar()
    amended = _nov08_calendar()
    assert weekly_session_decision("2026-10-30", original).state == CAPTURE
    assert weekly_session_decision("2026-11-06", amended).state == NOT_FINAL_SESSION
    assert weekly_session_decision("2026-11-08", amended).state == CAPTURE
    assert weekly_session_decision("2026-11-09", amended).state == NOT_FINAL_SESSION
    assert post_close_weekly_session_decision(
        "2026-11-08", amended,
        observed_at_utc=datetime(2026, 11, 8, 11, 45, tzinfo=UTC),
    ).state == BEFORE_POST_CLOSE_WINDOW
    assert post_close_weekly_session_decision(
        "2026-11-08", amended,
        observed_at_utc=datetime(2026, 11, 8, 13, 0, tzinfo=UTC),
    ).state == CAPTURE
    with pytest.raises(ValueError, match="unresolved NSE special-session"):
        weekly_session_decision("2026-11-06", original)


def test_calendar_supersession_rejects_drift_and_retroactive_use() -> None:
    original = _frozen_calendar()
    amended = _nov08_calendar()
    with pytest.raises(ValueError, match="version/digest"):
        validate_effective_h021_calendar(amended, capture_date_ist="2026-10-30")
    with pytest.raises(ValueError, match="version/digest"):
        validate_effective_h021_calendar(original, capture_date_ist="2026-11-08")
    amended["supersession"]["individual_CAS_price_basis_verified"] = True
    with pytest.raises(ValueError, match="provenance"):
        validate_effective_h021_calendar(amended, capture_date_ist="2026-11-08")


def test_workflow_uses_effective_calendar_and_idempotent_sunday_gate() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "NSE-CM-FY27Q2-v1.json" in workflow
    assert "NSE-CM-FY27Q2-v2-Nov08-Muhurat.json" in workflow
    assert 'if [[ "$CAPTURE_DATE" > "2026-11-01" ]]' in workflow
    assert '--calendar "$CALENDAR"' in workflow
    assert 'echo "calendar_path=$CALENDAR" >> "$GITHUB_OUTPUT"' in workflow
    assert workflow.count('--calendar "${{ steps.gate.outputs.calendar_path }}"') == 2
    for cron in ("15 11 * * 0", "45 12 * * 0", "15 13 * * 0", "45 13 * * 0"):
        assert f"cron: '{cron}'" in workflow
    assert 'STATE="ALREADY_CAPTURED"' in workflow
    assert 'cancel-in-progress: false' in workflow
