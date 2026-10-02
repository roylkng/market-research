from datetime import UTC, datetime

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001_v3_prospective import (
    append_prospective_v3_state,
    latest_activation_target,
    new_prospective_v3_ledger,
    validate_prospective_v3_ledger,
)


def _size_ledger(count=3):
    attempts = []
    for index in range(count):
        target = f"2026-10-{5 + index:02d}"
        observation = f"2026-10-{6 + index:02d}"
        row = {
            "seq": index + 1,
            "target_session_date": target,
            "observation_date": observation,
            "captured_at_utc": f"{observation}T02:00:00+00:00",
            "preopen_cutoff_utc": f"{observation}T03:00:00+00:00",
            "captured_before_or_at_preopen_cutoff": True,
            "sc001_attempt_sha256": f"s{index}" * 32,
            "source_url": "https://nsearchives.nseindia.com/security.gz",
            "source_status": "READY",
            "raw_sha256": f"a{index}" * 32,
            "raw_repo_path": "x",
            "market_raw_sha256": f"m{index}" * 32,
            "diagnostics": {},
            "ready_before_preopen_cutoff": True,
            "live_capital_allowed": False,
        }
        row["attempt_sha256"] = digest(row)
        attempts.append(row)
    ledger = {
        "schema_version": 1,
        "ledger_id": "RM001-SC001-SIZE-PREOPEN-SOURCE-LEDGER-v1",
        "attempt_count": len(attempts),
        "attempts": attempts,
        "live_capital_allowed": False,
    }
    unsigned = dict(ledger)
    ledger["ledger_sha256"] = digest(unsigned)
    return ledger


def _summary(count, ledger):
    return {
        "source_ledger_sha256": ledger["ledger_sha256"],
        "distinct_ready_before_cutoff_session_count": count,
        "prospective_size_source_timing_ready": count >= 3,
    }


def test_activation_waits_for_three_ready_size_sessions():
    ledger2 = _size_ledger(2)
    assert latest_activation_target(
        size_ledger=ledger2,
        readiness_summary=_summary(2, ledger2),
    ) is None
    ledger3 = _size_ledger(3)
    target = latest_activation_target(
        size_ledger=ledger3,
        readiness_summary=_summary(3, ledger3),
    )
    assert target is not None
    assert target["target_session_date"] == "2026-10-07"


def test_append_state_fails_after_frozen_0905_cutoff():
    size = _size_ledger(3)["attempts"][-1]
    sc001 = {
        "session_date": size["target_session_date"],
        "attempt_sha256": size["sc001_attempt_sha256"],
        "eligible_before_cutoff": True,
        "market": {"raw_sha256": "m" * 64},
    }
    state = {
        "as_of_session": size["target_session_date"],
        "parent_v2_risk_state_sha256": "r" * 64,
        "parent_v2_factor_history_sha256": "h" * 64,
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    with pytest.raises(AlphaContractError, match="09:05"):
        append_prospective_v3_state(
            new_prospective_v3_ledger(),
            target_session_date=size["target_session_date"],
            observation_date=size["observation_date"],
            size_attempt=size,
            sc001_attempt=sc001,
            v2_exposure_panel_sha256="e" * 64,
            v2_factor_history_sha256="h" * 64,
            v2_risk_state_sha256="r" * 64,
            v3_risk_state=state,
            state_artifact_path="state.gz",
            state_artifact_bytes=b"state",
            support_hashes={"market": "x" * 64},
            sealed_at_utc=f"{size['observation_date']}T03:35:01+00:00",
        )


def test_append_state_is_hash_valid_and_unique():
    size = _size_ledger(3)["attempts"][-1]
    sc001 = {
        "session_date": size["target_session_date"],
        "attempt_sha256": size["sc001_attempt_sha256"],
        "eligible_before_cutoff": True,
        "market": {"raw_sha256": "m" * 64},
    }
    state = {
        "as_of_session": size["target_session_date"],
        "parent_v2_risk_state_sha256": "r" * 64,
        "parent_v2_factor_history_sha256": "h" * 64,
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    ledger = append_prospective_v3_state(
        new_prospective_v3_ledger(),
        target_session_date=size["target_session_date"],
        observation_date=size["observation_date"],
        size_attempt=size,
        sc001_attempt=sc001,
        v2_exposure_panel_sha256="e" * 64,
        v2_factor_history_sha256="h" * 64,
        v2_risk_state_sha256="r" * 64,
        v3_risk_state=state,
        state_artifact_path="state.gz",
        state_artifact_bytes=b"state",
        support_hashes={"market": "x" * 64},
        sealed_at_utc=f"{size['observation_date']}T03:30:00+00:00",
    )
    validate_prospective_v3_ledger(ledger)
    assert ledger["state_count"] == 1
    with pytest.raises(AlphaContractError, match="already sealed"):
        append_prospective_v3_state(
            ledger,
            target_session_date=size["target_session_date"],
            observation_date=size["observation_date"],
            size_attempt=size,
            sc001_attempt=sc001,
            v2_exposure_panel_sha256="e" * 64,
            v2_factor_history_sha256="h" * 64,
            v2_risk_state_sha256="r" * 64,
            v3_risk_state=state,
            state_artifact_path="state.gz",
            state_artifact_bytes=b"state",
            support_hashes={"market": "x" * 64},
            sealed_at_utc=f"{size['observation_date']}T03:30:00+00:00",
        )



def test_activation_rejects_readiness_summary_from_other_size_ledger():
    ledger = _size_ledger(3)
    summary = _summary(3, ledger)
    summary["source_ledger_sha256"] = "0" * 64
    with pytest.raises(AlphaContractError, match="binding mismatch"):
        latest_activation_target(
            size_ledger=ledger,
            readiness_summary=summary,
        )
