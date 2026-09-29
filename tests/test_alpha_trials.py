import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_trials import (
    append_trial_event,
    new_trial_ledger,
    require_protocol_amendment,
    require_unopened_registered_trial,
    validate_trial_ledger,
)


def test_trial_ledger_requires_registration_before_result():
    ledger = new_trial_ledger()
    with pytest.raises(AlphaContractError, match="precedes registration"):
        append_trial_event(
            ledger,
            event_type="TRIAL_RESULT_RECORDED",
            trial_id="AE001-T999",
            recorded_at_utc="2026-09-27T08:00:00+00:00",
            payload={"result": "x"},
        )


def test_trial_ledger_is_append_only_and_hash_valid():
    ledger = append_trial_event(
        new_trial_ledger(),
        event_type="TRIAL_REGISTERED",
        trial_id="AE001-T003",
        recorded_at_utc="2026-09-27T08:00:00+00:00",
        payload={"status": "FROZEN_BEFORE_OUTCOME_RUN"},
    )
    ledger = append_trial_event(
        ledger,
        event_type="TRIAL_RESULT_RECORDED",
        trial_id="AE001-T003",
        recorded_at_utc="2026-09-27T09:00:00+00:00",
        payload={"status": "COMPLETE_DEVELOPMENT"},
    )
    validate_trial_ledger(ledger)
    assert ledger["event_count"] == 2
    assert len(ledger["ledger_sha256"]) == 64



def test_trial_protocol_amendment_is_bound_before_result():
    ledger = append_trial_event(
        new_trial_ledger(),
        event_type="TRIAL_REGISTERED",
        trial_id="AE001-T003",
        recorded_at_utc="2026-09-27T07:48:00+00:00",
        payload={"status": "FROZEN_BEFORE_DELIVERY_OUTCOME_RUN"},
    )
    ledger = append_trial_event(
        ledger,
        event_type="TRIAL_PROTOCOL_AMENDED",
        trial_id="AE001-T003",
        recorded_at_utc="2026-09-27T07:49:00+00:00",
        payload={"protocol_id": "AE001-T003-P1"},
    )
    registration = require_unopened_registered_trial(
        ledger,
        trial_id="AE001-T003",
        required_status="FROZEN_BEFORE_DELIVERY_OUTCOME_RUN",
    )
    protocol = require_protocol_amendment(
        ledger,
        trial_id="AE001-T003",
        protocol_id="AE001-T003-P1",
    )
    assert registration["trial_id"] == "AE001-T003"
    assert protocol["payload"]["protocol_id"] == "AE001-T003-P1"
