"""Late H021 EPS capture is skipped, never reclassified as on-time alpha."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from scripts.h021s001_next_open_gate import (
    ANCHOR_SAFETY_MARGIN,
    CALENDAR,
    assess_next_open,
)

ROOT = Path(__file__).resolve().parents[1]


def _calendar() -> dict:
    return json.loads((ROOT / CALENDAR).read_text(encoding="utf-8"))


def _check(now: str, day: str = "2026-10-16") -> dict:
    return assess_next_open(
        calendar=_calendar(),
        comparison_date=day,
        as_of_utc=datetime.fromisoformat(now),
    )


def test_canonical_oct16_comparison_is_irrecoverably_late_on_oct21():
    state = _check("2026-10-21T18:16:00+00:00")
    assert state["state"] == "SKIP_MISSED_NEXT_OPEN_NO_BACKFILL"
    assert state["planned_open_utc"] == "2026-10-19T03:45:00+00:00"
    assert state["entry_session"] == "2026-10-19"
    assert state["can_seal"] is False


def test_before_real_next_open_with_safety_margin_eligible_not_postdated():
    allowed = _check("2026-10-18T12:00:00Z")
    assert allowed["state"] == "CAPTURE"
    assert allowed["can_seal"] is True
    margin_edge = _check("2026-10-19T03:43:00Z")
    assert margin_edge["state"] == "SKIP_MISSED_NEXT_OPEN_NO_BACKFILL"
    assert margin_edge["can_seal"] is False
    assert ANCHOR_SAFETY_MARGIN == timedelta(minutes=2)


def test_before_completion_cannot_build_a_fake_future_release():
    before = _check("2026-10-16T09:00:00Z")
    assert before["state"] == "SKIP_COMPARISON_SESSION_NOT_CLOSED"
    assert before["can_seal"] is False
    old = _check("2026-10-09T13:00:00Z", day="2026-10-09")
    assert old["state"] == "SKIP_BEFORE_SEPARATE_TRIAL_FROZEN_START"
    assert old["can_seal"] is False


def test_unresolved_original_special_market_halts_instead_of_guessing_entry():
    unresolved = _check("2026-11-06T12:00:00Z", day="2026-11-06")
    assert unresolved["state"] == "SKIP_FROZEN_CALENDAR_UNRESOLVED"
    assert "Muhurat" in unresolved["reason"]
    assert unresolved["can_seal"] is False


def test_missing_timezone_rejected():
    with pytest.raises(ValueError, match="must be aware"):
        assess_next_open(
            calendar=_calendar(),
            comparison_date="2026-10-16",
            as_of_utc=datetime(2026, 10, 16, 12),
        )


def test_direct_command_skips_stale_comparison_with_unchanged_calendar():
    p = subprocess.run(
        [
            sys.executable,
            "scripts/h021s001_next_open_gate.py",
            "--comparison-date", "2026-10-16",
        ],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    status = json.loads(p.stdout)
    assert status["state"] == "SKIP_MISSED_NEXT_OPEN_NO_BACKFILL"
    assert status["can_seal"] is False
