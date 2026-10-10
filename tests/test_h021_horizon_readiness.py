from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021_first_entry_intent import CALENDAR_PATH
from marketlab.h021_horizon_readiness import (
    first_cohort_horizon_readiness,
    require_horizon_calendar_ready,
)
from scripts.acquire_h021_first_entry import load_and_verify_sources


def _inputs() -> tuple[dict, object]:
    intent, _ = load_and_verify_sources()
    return intent, load_calendar_snapshot(CALENDAR_PATH)


def test_first_h021_cohort_requires_official_muhurat_and_2027_calendar() -> None:
    intent, snapshot = _inputs()
    old = deepcopy(intent)
    result = first_cohort_horizon_readiness(intent, snapshot)

    assert result["calendar_end_date"] == "2026-12-31"
    assert result["unresolved_special_dates"] == ["2026-11-08"]
    assert result["all_horizon_calendars_ready"] is False
    short = result["horizons"]["20"]
    assert short["holding_sessions"] == 20
    assert short["state"] == "BLOCKED"
    assert short["weekday_only_candidate_date_not_verified"] == "2026-11-09"
    assert short["verified_exit_session_date"] is None
    assert short["unresolved_special_dates_in_horizon"] == ["2026-11-08"]
    assert short["blockers"] == ["UNRESOLVED_OFFICIAL_SPECIAL_SESSION"]
    long = result["horizons"]["60"]
    assert long["state"] == "BLOCKED"
    assert long["weekday_only_candidate_date_not_verified"] is None
    assert long["verified_exit_session_date"] is None
    assert long["provisional_session_count_available"] == 55
    assert long["minimum_additional_sessions_before_unresolved_adjustment"] == 5
    assert long["blockers"] == [
        "UNRESOLVED_OFFICIAL_SPECIAL_SESSION",
        "FUTURE_VERIFIED_SESSION_CALENDAR_MISSING",
    ]
    assert result["return_outcomes_opened"] is False
    assert result["live_capital_allowed"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert intent == old

    with pytest.raises(ValueError, match="calendar not ready"):
        require_horizon_calendar_ready(result, 20)
    with pytest.raises(ValueError, match="calendar not ready"):
        require_horizon_calendar_ready(result, 60)


def test_calendar_requires_source_rehash_and_rejects_silent_special_date_removal() -> None:
    intent, snapshot = _inputs()
    altered = replace(snapshot, unresolved_special_dates=())
    with pytest.raises(ValueError, match="contents changed"):
        first_cohort_horizon_readiness(intent, altered)


def test_does_not_accept_different_holding_rule_or_capital_elevation() -> None:
    intent, snapshot = _inputs()
    intent["outcome_plan"]["primary_horizon_completed_sessions"] = 30
    with pytest.raises(ValueError, match="horizons changed"):
        first_cohort_horizon_readiness(intent, snapshot)
    intent, snapshot = _inputs()
    intent["portfolio_eligibility_allowed"] = True
    with pytest.raises(ValueError, match="portfolio eligibility"):
        first_cohort_horizon_readiness(intent, snapshot)


def test_cannot_query_arbitrary_unregistered_horizon() -> None:
    intent, snapshot = _inputs()
    result = first_cohort_horizon_readiness(intent, snapshot)
    with pytest.raises(ValueError, match="horizon not declared"):
        require_horizon_calendar_ready(result, 90)


def test_cli_materializes_only_non_capital_calendar_state(tmp_path: Path) -> None:
    path = tmp_path / "h021-readiness.json"
    subprocess.run(
        [
            sys.executable, "scripts/check_h021_horizon_readiness.py",
            "--out", str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["all_horizon_calendars_ready"] is False
    assert payload["horizons"]["20"]["verified_exit_session_date"] is None

    result = subprocess.run(
        [
            sys.executable, "scripts/check_h021_horizon_readiness.py",
            "--require-horizon", "20",
        ],
        check=False, capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "calendar not ready" in result.stderr
