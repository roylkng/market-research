"""Prospective health must distinguish T012 registration from SC003 readiness."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_t012_decisions import (
    append_t012_decision,
    new_t012_decision_ledger,
)
from marketlab.alpha_t012_outcomes import (
    append_t012_outcome,
    new_t012_outcome_ledger,
)
from marketlab.alpha_trials import append_trial_event
from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.prospective_health import _t012_state

ROOT = Path(__file__).resolve().parents[1]


def _files() -> dict:
    prefix = "research/prospective/"
    files = {
        "calendar": (
            prefix + "calendars/FY27-Q2-2026-09-06/"
            "NSE-CM-FY27Q2-v1.json"
        ),
        "trial_ledger": "research/ae001/trial-ledger.json",
        "decision_ledger": prefix + "ae001-t012/decision-ledger.json",
        "outcome_ledger": prefix + "ae001-t012/outcome-ledger.json",
    }
    result = {}
    for key, path in files.items():
        if key == "calendar":
            result[key] = load_calendar_snapshot(ROOT / path)
        else:
            result[key] = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return result


def test_t012_health_detects_registered_zero_decisions_and_2027_gap():
    args = _files()
    # Zero-decision case is a synthetic isolated fixture. Do not silently
    # rely on production T012 decision and outcome ledgers staying empty.
    args["decision_ledger"] = new_t012_decision_ledger()
    args["outcome_ledger"] = new_t012_outcome_ledger()
    health = _t012_state(**args)
    assert health["trial_id"] == "AE001-T012"
    assert health["trial_registered"] is True
    assert health["state"] == "PREREGISTERED_AWAITING_FIRST_DECISION"
    assert health["decision_count"] == 0
    assert health["outcome_count"] == 0
    assert health["calendar_last_session"] == "2026-12-31"
    assert health["frozen_calendar_max_possible_feature_sessions"] == 52
    assert health["calendar_minimum_60_session_shortfall"] == 8
    assert health["forward_only_calendar_extension_required"] is True
    assert health["source_readiness_not_equivalent_to_prediction"] is True
    assert health["live_capital_allowed"] is False


def _future_decision() -> dict:
    artifact = {
        "artifact_id": "AE001-T012-DECISION-v1",
        "session_date": "2026-10-15",
        "entry_session": "2026-10-16",
        "sealed_at_utc": "2026-10-16T02:45:00Z",
        "common_row_count": 120,
        "admission_sha256": "f" * 64,
        "sc001_attempt_sha256": "a" * 64,
        "sc003_attempt_sha256": "b" * 64,
        "frozen_model_artifact_sha256": (
            "da1ce462b5d9c59fb5bea2f4b69c574c8ecbf1f728c44b23af8f3e73bd5de091"
        ),
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def test_t012_health_uses_future_predictions_only_when_genuinely_registered():
    args = _files()
    decision = _future_decision()
    args["outcome_ledger"] = new_t012_outcome_ledger()
    args["decision_ledger"] = append_t012_decision(
        new_t012_decision_ledger(),
        artifact=decision,
        artifact_path="synthetic/t012-future-decision.json.gz",
    )
    status = _t012_state(**args)
    assert status["state"] == "PROSPECTIVE_DECISIONS_ACCUMULATING"
    assert status["decision_count"] == 1
    assert status["outcome_count"] == 0

    outcome = {
        "trial_id": "AE001-T012",
        "decision_session": decision["session_date"],
        "horizon_sessions": 1,
        "entry_session": decision["entry_session"],
        "exit_session": decision["entry_session"],
        "captured_at_utc": "2026-10-16T12:00:00Z",
        "decision_artifact_sha256": decision["artifact_sha256"],
        "valid_outcome_row_count": 120,
        "valid_paired_ic": True,
        "live_capital_allowed": False,
    }
    outcome["artifact_sha256"] = digest(outcome)
    args["outcome_ledger"] = append_t012_outcome(
        new_t012_outcome_ledger(),
        outcome_artifact=outcome,
        artifact_path="synthetic/t012-future-h1-outcome.json.gz",
    )
    progressed = _t012_state(**args)
    assert progressed["state"] == "PROSPECTIVE_OUTCOMES_ACCUMULATING"
    assert progressed["h1_outcome_count"] == 1
    assert progressed["h5_outcome_count"] == 0
    assert progressed["primary_assessed"] is False

    # Synthetic primary completion tests state plumbing only. It does not
    # claim any actual NSE observation or legitimate numerical significance.
    args["trial_ledger"] = append_trial_event(
        args["trial_ledger"],
        event_type="TRIAL_RESULT_RECORDED",
        trial_id="AE001-T012",
        recorded_at_utc="2027-02-01T12:00:00+00:00",
        payload={
            "result_kind": "PRIMARY_5D",
            "status": "PRIMARY_NOT_SUPPORTED",
            "live_capital_allowed": False,
        },
    )
    assessed = _t012_state(**args)
    assert assessed["state"] == "PRIMARY_ASSESSED"
    assert assessed["primary_status"] == "PRIMARY_NOT_SUPPORTED"


def test_t012_health_rejects_tampered_registration_source():
    args = _files()
    corrupted = copy.deepcopy(args["trial_ledger"])
    target = next(
        row for row in corrupted["events"]
        if row["trial_id"] == "AE001-T012"
        and row["event_type"] == "TRIAL_REGISTERED"
    )
    target["payload"]["calendar_sha256"] = "x" * 64
    args["trial_ledger"] = corrupted
    with pytest.raises(AlphaContractError, match="hash mismatch"):
        _t012_state(**args)
