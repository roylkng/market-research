from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from marketlab.paperfund import new_fund
from marketlab.paperfund_state import state_sha256
from marketlab.pf001_schedule import next_pending_pf001_session


def _calendar():
    return SimpleNamespace(
        sessions=(
            SimpleNamespace(
                session_date="2026-09-30",
                close_timestamp_utc="2026-09-30T10:00:00Z",
            ),
            SimpleNamespace(
                session_date="2026-10-01",
                close_timestamp_utc="2026-10-01T10:00:00Z",
            ),
            SimpleNamespace(
                session_date="2026-10-05",
                close_timestamp_utc="2026-10-05T10:00:00Z",
            ),
            SimpleNamespace(
                session_date="2026-10-06",
                close_timestamp_utc="2026-10-06T10:00:00Z",
            ),
        )
    )


def _state(book: str, last_session: str | None):
    state = new_fund(
        book=book,
        policy_frozen_at="2026-09-11T18:46:13+00:00",
    )
    state["last_session_date"] = last_session
    state["state_sha256"] = state_sha256(state)
    return state


def test_pf001_holiday_run_catches_prior_completed_session():
    session = next_pending_pf001_session(
        _calendar(),
        states=[
            _state("DEVELOPMENT", "2026-09-30"),
            _state("PROSPECTIVE_VALIDATION", "2026-09-30"),
        ],
        now=datetime(2026, 10, 2, 12, 0, tzinfo=UTC),
    )
    assert session == "2026-10-01"


def test_pf001_returns_oldest_pending_session_instead_of_skipping_history():
    session = next_pending_pf001_session(
        _calendar(),
        states=[
            _state("DEVELOPMENT", "2026-09-30"),
            _state("PROSPECTIVE_VALIDATION", "2026-09-30"),
        ],
        now=datetime(2026, 10, 6, 12, 0, tzinfo=UTC),
    )
    assert session == "2026-10-01"


def test_pf001_caught_up_state_is_idempotent():
    session = next_pending_pf001_session(
        _calendar(),
        states=[
            _state("DEVELOPMENT", "2026-10-01"),
            _state("PROSPECTIVE_VALIDATION", "2026-10-01"),
        ],
        now=datetime(2026, 10, 3, 12, 0, tzinfo=UTC),
    )
    assert session is None


def test_pf001_does_not_process_session_before_frozen_close():
    session = next_pending_pf001_session(
        _calendar(),
        states=[
            _state("DEVELOPMENT", "2026-10-01"),
            _state("PROSPECTIVE_VALIDATION", "2026-10-01"),
        ],
        now=datetime(2026, 10, 5, 9, 59, tzinfo=UTC),
    )
    assert session is None


def test_pf001_refuses_to_advance_divergent_books():
    with pytest.raises(ValueError, match="out of sync"):
        next_pending_pf001_session(
            _calendar(),
            states=[
                _state("DEVELOPMENT", "2026-09-30"),
                _state("PROSPECTIVE_VALIDATION", "2026-10-01"),
            ],
            now=datetime(2026, 10, 3, 12, 0, tzinfo=UTC),
        )
