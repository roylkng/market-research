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
