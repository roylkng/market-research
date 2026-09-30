from datetime import date, timedelta

from marketlab.alpha_t006_outcomes import (
    append_t006_outcome,
    finalize_t006_results,
    find_t006_primary_cohort,
    new_t006_outcome_ledger,
)
from marketlab.alpha_t006_prospective import (
    append_t006_decision,
    new_t006_decision_ledger,
)
from marketlab.alpha_trials import append_trial_event, new_trial_ledger


def _dates(count: int) -> list[str]:
    start = date(2026, 10, 1)
    return [
        (start + timedelta(days=index)).isoformat()
        for index in range(count)
    ]


def _decision_ledger(count: int):
    ledger = new_t006_decision_ledger()
    for index, session in enumerate(_dates(count)):
        artifact = {
            "session_date": session,
            "artifact_sha256": f"{index + 1:064x}",
            "sealed_at_utc": f"{session}T12:45:00+00:00",
            "common_row_count": 150,
            "sc001_attempt_sha256": f"{index + 101:064x}",
            "sc002_attempt_sha256": f"{index + 201:064x}",
            "base_model_sha256": "a" * 64,
            "augmented_model_sha256": "b" * 64,
            "outcomes_attached": False,
        }
        ledger = append_t006_decision(
            ledger,
            decision_artifact=artifact,
            artifact_path=(
                "research/prospective/ae001-t006/decisions/"
                f"{session}-v1.json.gz"
            ),
        )
    return ledger


def _append_outcome(
    ledger,
    *,
    session: str,
    horizon: int,
    valid_paired_ic: bool,
    index: int,
):
    artifact = {
        "decision_session": session,
        "horizon_sessions": horizon,
        "artifact_sha256": f"{index + 500:064x}",
        "entry_session": f"{session}-ENTRY",
        "exit_session": f"{session}-EXIT-H{horizon}",
        "valid_outcome_row_count": 120,
        "valid_paired_ic": valid_paired_ic,
    }
    return append_t006_outcome(
        ledger,
        outcome_artifact=artifact,
        artifact_path=(
            "research/prospective/ae001-t006/outcomes/"
            f"{session}-h{horizon}-v1.json.gz"
        ),
    )


def test_primary_cohort_uses_smallest_chronological_prefix():
    decisions = [{"session_date": value} for value in _dates(61)]
    outcomes = new_t006_outcome_ledger()
    for index, session in enumerate(_dates(61)):
        # First 60 contain only 49 valid paired-IC sessions. Session 61 makes 50.
        valid = index < 49 or index == 60
        outcomes = _append_outcome(
            outcomes,
            session=session,
            horizon=5,
            valid_paired_ic=valid,
            index=index,
        )

    cohort = find_t006_primary_cohort(
        decisions=decisions,
        outcome_ledger=outcomes,
    )
    assert cohort == _dates(61)


def test_primary_cohort_is_not_selected_before_all_prefix_h5_outcomes_mature():
    decisions = [{"session_date": value} for value in _dates(60)]
    outcomes = new_t006_outcome_ledger()
    for index, session in enumerate(_dates(59)):
        outcomes = _append_outcome(
            outcomes,
            session=session,
            horizon=5,
            valid_paired_ic=True,
            index=index,
        )

    assert (
        find_t006_primary_cohort(
            decisions=decisions,
            outcome_ledger=outcomes,
        )
        is None
    )


def _trial_ledger():
    ledger = append_trial_event(
        new_trial_ledger(),
        event_type="TRIAL_REGISTERED",
        trial_id="AE001-T006",
        recorded_at_utc="2026-09-30T10:44:49+00:00",
        payload={
            "status": "FROZEN_BEFORE_FIRST_ELIGIBLE_DECISION_SESSION",
        },
    )
    return append_trial_event(
        ledger,
        event_type="TRIAL_PROTOCOL_AMENDED",
        trial_id="AE001-T006",
        recorded_at_utc="2026-09-30T10:58:10+00:00",
        payload={
            "protocol_id": "AE001-T006-P2",
            "primary_minimum_decision_sessions": 60,
            "primary_minimum_valid_paired_ic_sessions": 50,
        },
    )


def _metric(session: str, *, rank_ic: float, spread: float):
    return {
        "feature_session": session,
        "observation_count": 120,
        "rank_ic": rank_ic,
        "top_decile_mean_excess": spread / 2.0,
        "bottom_decile_mean_excess": -spread / 2.0,
        "top_minus_bottom_spread": spread,
    }


def _outcome_artifact(
    session: str,
    horizon: int,
    *,
    index: int,
):
    # Positive augmented-minus-base differences. Inference is monkeypatched in
    # the tests below so the test isolates T006 cohort/result sequencing.
    return {
        "decision_session": session,
        "horizon_sessions": horizon,
        "valid_paired_ic": True,
        "base_metrics": {
            "session_metrics": [
                _metric(session, rank_ic=0.01, spread=0.001)
            ]
        },
        "augmented_metrics": {
            "session_metrics": [
                _metric(
                    session,
                    rank_ic=0.02 + index * 1e-6,
                    spread=0.002 + index * 1e-6,
                )
            ]
        },
    }


def _complete_outcome_ledger(count: int):
    ledger = new_t006_outcome_ledger()
    for index, session in enumerate(_dates(count)):
        ledger = _append_outcome(
            ledger,
            session=session,
            horizon=5,
            valid_paired_ic=True,
            index=index,
        )
        ledger = _append_outcome(
            ledger,
            session=session,
            horizon=1,
            valid_paired_ic=True,
            index=index + 100,
        )
    return ledger


def test_finalize_primary_then_non_rescuing_secondary(monkeypatch):
    decisions = _decision_ledger(60)
    outcomes = _complete_outcome_ledger(60)
    artifacts = []
    for index, session in enumerate(_dates(60)):
        artifacts.append(
            _outcome_artifact(session, 5, index=index)
        )
        artifacts.append(
            _outcome_artifact(session, 1, index=index)
        )

    monkeypatch.setattr(
        "marketlab.alpha_t006_outcomes.paired_report_difference_inference",
        lambda augmented, base, max_lag: {
            "metrics": {
                "rank_ic": {
                    "mean": 0.01,
                    "p_value_two_sided": 0.01,
                },
                "top_minus_bottom_spread": {
                    "mean": 0.002,
                    "p_value_two_sided": 0.02,
                },
            }
        },
    )

    updated, emitted = finalize_t006_results(
        trial_ledger=_trial_ledger(),
        decision_ledger=decisions,
        outcome_ledger=outcomes,
        outcome_artifacts=artifacts,
        recorded_at_utc="2027-01-15T12:00:00+00:00",
    )

    assert len(emitted) == 2
    primary = emitted[0]["payload"]
    secondary = emitted[1]["payload"]
    assert primary["result_kind"] == "PRIMARY_5D"
    assert primary["status"] == "SUPPORTED"
    assert primary["cohort_size"] == 60
    assert secondary["result_kind"] == "SECONDARY_1D"
    assert secondary["status"] == "REPORTED_NON_RESCUING_SECONDARY"
    assert secondary["rescues_failed_primary"] is False
    assert secondary["cohort_decision_sessions"] == primary[
        "cohort_decision_sessions"
    ]

    t006_results = [
        event
        for event in updated["events"]
        if event["trial_id"] == "AE001-T006"
        and event["event_type"] == "TRIAL_RESULT_RECORDED"
    ]
    assert len(t006_results) == 2


def test_secondary_cannot_rescue_failed_primary(monkeypatch):
    decisions = _decision_ledger(60)
    outcomes = _complete_outcome_ledger(60)
    artifacts = []
    for index, session in enumerate(_dates(60)):
        artifacts.append(
            _outcome_artifact(session, 5, index=index)
        )
        artifacts.append(
            _outcome_artifact(session, 1, index=index)
        )

    calls = {"count": 0}

    def fake_inference(augmented, base, max_lag):
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "metrics": {
                    "rank_ic": {
                        "mean": 0.01,
                        "p_value_two_sided": 0.20,
                    },
                    "top_minus_bottom_spread": {
                        "mean": 0.002,
                        "p_value_two_sided": 0.01,
                    },
                }
            }
        return {
            "metrics": {
                "rank_ic": {
                    "mean": 0.03,
                    "p_value_two_sided": 0.001,
                },
                "top_minus_bottom_spread": {
                    "mean": 0.004,
                    "p_value_two_sided": 0.001,
                },
            }
        }

    monkeypatch.setattr(
        "marketlab.alpha_t006_outcomes.paired_report_difference_inference",
        fake_inference,
    )

    _, emitted = finalize_t006_results(
        trial_ledger=_trial_ledger(),
        decision_ledger=decisions,
        outcome_ledger=outcomes,
        outcome_artifacts=artifacts,
        recorded_at_utc="2027-01-15T12:00:00+00:00",
    )

    assert emitted[0]["payload"]["status"] == "NOT_SUPPORTED"
    assert emitted[1]["payload"]["status"] == (
        "REPORTED_NON_RESCUING_SECONDARY"
    )
    assert emitted[1]["payload"]["rescues_failed_primary"] is False
