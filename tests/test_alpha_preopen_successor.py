from types import SimpleNamespace

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_preopen_successor import (
    CANDIDATE_TRIAL_ID,
    preopen_successor_readiness,
    require_preopen_successor_freeze_ready,
)
from marketlab.alpha_sc003_preopen import (
    SC003_P1_PROTOCOL,
    new_sc003_ledger,
    preopen_cutoff_utc,
)


def _calendar():
    sessions = (
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
        SimpleNamespace(
            session_date="2026-10-07",
            close_timestamp_utc="2026-10-07T10:00:00Z",
        ),
    )
    return SimpleNamespace(
        sessions=sessions,
        version="NSE-CM-FY27Q2-v1",
        sha256="c" * 64,
    )


def _p1_attempt(
    *,
    seq: int,
    target: str,
    observation: str,
    cutoff: str,
    captured: str,
):
    attempt = {
        "seq": seq,
        "target_session_date": target,
        "observation_date": observation,
        "captured_at_utc": captured,
        "preopen_cutoff_utc": preopen_cutoff_utc(cutoff).isoformat(),
        "captured_before_or_at_preopen_cutoff": True,
        "sc001_attempt_sha256": f"{seq}" * 64,
        "source_url": "https://nsearchives.nseindia.com/fo.zip",
        "source_status": "READY",
        "raw_sha256": f"{seq + 3}" * 64,
        "raw_repo_path": f"research/prospective/ae001-sc003/raw/{target}/fo.zip",
        "diagnostics": {"accepted_contract_row_count": 600},
        "ready_before_preopen_cutoff": True,
        "live_capital_allowed": False,
        "protocol": SC003_P1_PROTOCOL,
        "cutoff_session_date": cutoff,
        "frozen_calendar_sha256": "c" * 64,
        "frozen_calendar_version": "NSE-CM-FY27Q2-v1",
        "target_close_timestamp_utc": f"{target}T10:00:00Z",
    }
    attempt["attempt_sha256"] = digest(attempt)
    return attempt


def _ledger(count: int):
    attempts = [
        _p1_attempt(
            seq=1,
            target="2026-10-01",
            observation="2026-10-02",
            cutoff="2026-10-05",
            captured="2026-10-02T09:17:15+00:00",
        ),
        _p1_attempt(
            seq=2,
            target="2026-10-05",
            observation="2026-10-05",
            cutoff="2026-10-06",
            captured="2026-10-05T11:00:00+00:00",
        ),
        _p1_attempt(
            seq=3,
            target="2026-10-06",
            observation="2026-10-06",
            cutoff="2026-10-07",
            captured="2026-10-06T11:00:00+00:00",
        ),
    ][:count]
    ledger = new_sc003_ledger()
    ledger.pop("ledger_sha256")
    ledger["attempts"] = attempts
    ledger["attempt_count"] = len(attempts)
    ledger["ledger_sha256"] = digest(ledger)
    return ledger


def test_preopen_successor_waits_for_three_source_timing_sessions():
    summary = preopen_successor_readiness(
        _ledger(1),
        calendar=_calendar(),
    )
    assert summary["candidate_trial_id"] == CANDIDATE_TRIAL_ID
    assert summary["state"] == "WAITING_FOR_SC003_TIMING_EVIDENCE"
    assert summary["ready_target_session_count"] == 1
    assert summary["additional_ready_sessions_needed"] == 2
    assert summary["successor_trial_registration_permitted"] is False
    assert summary["source_timing_sessions_may_be_backfilled_as_predictions"] is False
    assert summary["uses_return_or_alpha_outcomes"] is False


def test_preopen_successor_gate_opens_after_three_valid_distinct_targets():
    summary = require_preopen_successor_freeze_ready(
        _ledger(3),
        calendar=_calendar(),
    )
    assert summary["state"] == "READY_TO_FREEZE_SUCCESSOR_TRIAL"
    assert summary["ready_target_sessions"] == [
        "2026-10-01",
        "2026-10-05",
        "2026-10-06",
    ]
    assert summary["additional_ready_sessions_needed"] == 0
    assert summary["successor_trial_registration_permitted"] is True
    assert summary["successor_trial_frozen"] is False


def test_preopen_successor_refuses_freeze_before_source_gate():
    with pytest.raises(AlphaContractError, match="three distinct"):
        require_preopen_successor_freeze_ready(
            _ledger(2),
            calendar=_calendar(),
        )


def test_preopen_successor_rejects_wrong_frozen_calendar_binding():
    ledger = _ledger(1)
    ledger.pop("ledger_sha256")
    attempt = ledger["attempts"][0]
    attempt.pop("attempt_sha256")
    attempt["frozen_calendar_sha256"] = "d" * 64
    attempt["attempt_sha256"] = digest(attempt)
    ledger["ledger_sha256"] = digest(ledger)

    with pytest.raises(AlphaContractError, match="calendar SHA"):
        preopen_successor_readiness(
            ledger,
            calendar=_calendar(),
        )


def test_preopen_successor_rejects_non_next_trading_cutoff():
    ledger = _ledger(1)
    ledger.pop("ledger_sha256")
    attempt = ledger["attempts"][0]
    attempt.pop("attempt_sha256")
    attempt["cutoff_session_date"] = "2026-10-06"
    attempt["preopen_cutoff_utc"] = preopen_cutoff_utc(
        "2026-10-06"
    ).isoformat()
    attempt["attempt_sha256"] = digest(attempt)
    ledger["ledger_sha256"] = digest(ledger)

    with pytest.raises(AlphaContractError, match="cutoff"):
        preopen_successor_readiness(
            ledger,
            calendar=_calendar(),
        )
