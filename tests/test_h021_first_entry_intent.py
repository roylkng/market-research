from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.h021_first_entry_intent import (
    CALENDAR_GIT_BLOB_SHA,
    CALENDAR_PATH,
    COMPARISON_GIT_BLOB_SHA,
    COMPARISON_PATH,
    build_first_entry_intent,
    git_blob_sha,
    load_pinned_inputs,
)

ARTIFACT = Path(
    "research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json"
)


def test_pinned_sources_and_committed_intent_reproduce() -> None:
    assert git_blob_sha(COMPARISON_PATH.read_bytes()) == COMPARISON_GIT_BLOB_SHA
    assert git_blob_sha(CALENDAR_PATH.read_bytes()) == CALENDAR_GIT_BLOB_SHA

    comparison, calendar = load_pinned_inputs()
    unchanged_comparison = deepcopy(comparison)
    unchanged_calendar = deepcopy(calendar)
    built = build_first_entry_intent(comparison, calendar)
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert committed == built
    assert comparison == unchanged_comparison
    assert calendar == unchanged_calendar

    assert committed["universe_symbol_count"] == 100
    assert committed["primary_signal_eligible_count"] == 97
    assert committed["primary_top_decile_count"] == 10
    assert committed["excluded_symbol_count"] == 3
    assert [row["symbol"] for row in committed["selected_observations"]] == [
        "VEDL",
        "ETERNAL",
        "DMART",
        "IDEA",
        "ADANIENSOL",
        "JSWSTEEL",
        "COALINDIA",
        "INFY",
        "GAIL",
        "POWERGRID",
    ]
    assert committed["entry_plan"]["session_date_ist"] == "2026-10-12"
    assert committed["entry_plan"]["calendar_open_timestamp_utc"] == (
        "2026-10-12T03:45:00Z"
    )
    assert all(
        row["entry_price"] is None and row["capital_allocation"] is None
        for row in committed["selected_observations"]
    )
    assert committed["outcome_plan"]["return_outcomes_opened"] is False
    assert committed["outcome_plan"]["sixty_session_calendar_extension_required"] is True
    assert committed["portfolio_eligibility_allowed"] is False
    assert committed["live_capital_allowed"] is False


@pytest.mark.parametrize("flag,value", [
    ("outcomes_opened", True),
    ("live_capital_allowed", True),
    ("capture_interval_days", 27),
    ("current_capture_date_ist", "2026-10-08"),
])
def test_rejects_changed_comparison_or_capital(flag: str, value: object) -> None:
    comparison, calendar = load_pinned_inputs()
    comparison[flag] = value
    with pytest.raises(ValueError):
        build_first_entry_intent(comparison, calendar)


def test_rejects_unapproved_decile_substitution() -> None:
    comparison, calendar = load_pinned_inputs()
    comparison["primary_top_decile_symbols"][0] = "TRENT"
    with pytest.raises(ValueError, match="ineligible"):
        build_first_entry_intent(comparison, calendar)


def test_rejects_missing_or_duplicate_universe_name() -> None:
    comparison, calendar = load_pinned_inputs()
    comparison["revision_observations"][0]["symbol"] = comparison[
        "revision_observations"
    ][1]["symbol"]
    with pytest.raises(ValueError, match="duplicate"):
        build_first_entry_intent(comparison, calendar)


def test_rejects_tampered_source_files(tmp_path: Path) -> None:
    comparison_path = tmp_path / "comparison.json"
    comparison_path.write_bytes(COMPARISON_PATH.read_bytes() + b" ")
    with pytest.raises(ValueError, match="comparison Git blob SHA"):
        load_pinned_inputs(comparison_path=comparison_path)

    calendar_path = tmp_path / "calendar.json"
    calendar_path.write_bytes(CALENDAR_PATH.read_bytes() + b" ")
    with pytest.raises(ValueError, match="calendar Git blob SHA"):
        load_pinned_inputs(calendar_path=calendar_path)


def test_rejects_calendar_retroactive_change() -> None:
    comparison, calendar = load_pinned_inputs()
    calendar["sessions"] = [
        row for row in calendar["sessions"] if row["session_date"] != "2026-10-12"
    ]
    with pytest.raises(ValueError, match="next NSE"):
        build_first_entry_intent(comparison, calendar)


def test_cli_reproduces_committed_first_intent(tmp_path: Path) -> None:
    path = tmp_path / "intent.json"
    subprocess.run(
        [sys.executable, "-m", "marketlab.h021_first_entry_intent", "--output", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(path.read_text(encoding="utf-8")) == json.loads(
        ARTIFACT.read_text(encoding="utf-8")
    )
