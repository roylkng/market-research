from __future__ import annotations

from copy import deepcopy

import pytest

from marketlab.paperfund import new_fund
from marketlab.paperfund_state import state_sha256, validate_fund_state

POLICY_FROZEN_AT = "2026-09-11T18:46:13Z"


def test_new_fund_state_validates_and_hashes() -> None:
    state = new_fund(book="PROSPECTIVE_VALIDATION", policy_frozen_at=POLICY_FROZEN_AT)
    assert validate_fund_state(state) == []
    assert len(state_sha256(state)) == 64


def test_event_tampering_is_detected() -> None:
    state = new_fund(book="PROSPECTIVE_VALIDATION", policy_frozen_at=POLICY_FROZEN_AT)
    tampered = deepcopy(state)
    tampered["events"][0]["initial_nav"] = 900_000.0
    assert any("event hash mismatch" in error for error in validate_fund_state(tampered))
    with pytest.raises(ValueError, match="event hash mismatch"):
        state_sha256(tampered)


def test_whole_state_hash_detects_cash_tampering() -> None:
    state = new_fund(book="PROSPECTIVE_VALIDATION", policy_frozen_at=POLICY_FROZEN_AT)
    state["state_sha256"] = state_sha256(state)
    assert validate_fund_state(state) == []

    tampered = deepcopy(state)
    tampered["cash_net"] -= 1.0
    assert "state_sha256 does not match canonical fund state" in validate_fund_state(tampered)


def test_book_identity_mismatch_is_detected() -> None:
    state = new_fund(book="DEVELOPMENT", policy_frozen_at=POLICY_FROZEN_AT)
    state["fund_id"] = "PF001-v1-PROSPECTIVE_VALIDATION"
    assert "fund_id does not match policy/book" in validate_fund_state(state)
