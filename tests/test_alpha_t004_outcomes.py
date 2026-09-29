from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_market import DailyEquityObservation
from marketlab.alpha_t004_outcomes import (
    append_t004_outcome,
    build_t004_horizon_outcome,
    finalize_t004_results,
    find_t004_primary_cohort,
    new_t004_outcome_ledger,
    validate_t004_outcome_ledger,
)
from marketlab.alpha_t004_prospective import (
    append_t004_decision,
    new_t004_decision_ledger,
)
from marketlab.alpha_trials import append_trial_event, new_trial_ledger
from marketlab.marketdata import IndexDailyPrice


def _decision_artifact(session="2026-09-30", count=10):
    base = []
    augmented = []
    for index in range(count):
        symbol = f"S{index:03d}"
        isin = f"INE{index:09d}"
        base.append(
            {"symbol": symbol, "isin": isin, "prediction": float(index)}
        )
        augmented.append(
            {"symbol": symbol, "isin": isin, "prediction": float(index) * 1.1}
        )
    return {
        "artifact_sha256": "d" * 64,
        "session_date": session,
        "base_predictions": base,
        "augmented_predictions": augmented,
        "outcomes_attached": False,
    }


def _market_sessions(decision="2026-09-30", count=5, stocks=10):
    start = date.fromisoformat(decision) + timedelta(days=1)
    sessions = []
    for day_index in range(count):
        day = start + timedelta(days=day_index)
        equities = []
        for stock_index in range(stocks):
            open_price = 100.0
            close_price = 100.0 + stock_index + day_index * 0.1
            equities.append(
                DailyEquityObservation(
                    session_date=day.isoformat(),
                    symbol=f"S{stock_index:03d}",
                    isin=f"INE{stock_index:09d}",
                    open_price=open_price,
                    high_price=max(open_price, close_price) + 1.0,
                    low_price=min(open_price, close_price) - 1.0,
                    close_price=close_price,
                    previous_close=100.0,
                    volume=100_000,
                    turnover_inr=30_000_000,
                    trade_count=1_000,
                ).__dict__
            )
        sessions.append(
            {
                "session_date": day.isoformat(),
                "udiff_sha256": f"{day_index + 1:064x}",
                "benchmark_sha256": f"{day_index + 101:064x}",
                "equities": equities,
                "benchmark": IndexDailyPrice(
                    benchmark_id="nifty_500",
                    index_name="Nifty 500",
                    session_date=day.isoformat(),
                    open_price=100.0,
                    close_price=100.0,
                ).__dict__,
            }
        )
    return sessions


def test_t004_h5_outcome_uses_next_session_open_to_fifth_close():
    artifact = build_t004_horizon_outcome(
        decision_artifact=_decision_artifact(),
        market_sessions=_market_sessions(),
        corporate_action_payload=[],
        corporate_action_raw=b"[]",
        horizon_sessions=5,
    )
    assert artifact["entry_session"] == "2026-10-01"
    assert artifact["exit_session"] == "2026-10-05"
    assert artifact["valid_outcome_row_count"] == 10
    assert artifact["base_metrics"]["session_count"] == 1
    assert artifact["augmented_metrics"]["session_count"] == 1
    assert artifact["valid_paired_ic"] is True


def test_t004_outcome_fails_closed_before_horizon_matures():
    with pytest.raises(AlphaContractError, match="not mature"):
        build_t004_horizon_outcome(
            decision_artifact=_decision_artifact(),
            market_sessions=_market_sessions(count=4),
            corporate_action_payload=[],
            corporate_action_raw=b"[]",
            horizon_sessions=5,
        )


def test_t004_outcome_ledger_is_unique_by_decision_and_horizon():
    artifact = build_t004_horizon_outcome(
        decision_artifact=_decision_artifact(),
        market_sessions=_market_sessions(),
        corporate_action_payload=[],
        corporate_action_raw=b"[]",
        horizon_sessions=5,
    )
    ledger = append_t004_outcome(
        new_t004_outcome_ledger(),
        outcome_artifact=artifact,
        artifact_path="x.json.gz",
    )
    validate_t004_outcome_ledger(ledger)
    with pytest.raises(AlphaContractError, match="already exists"):
        append_t004_outcome(
            ledger,
            outcome_artifact=artifact,
            artifact_path="y.json.gz",
        )


def _decision_ledger(count):
    ledger = new_t004_decision_ledger()
    start = date(2026, 10, 1)
    for index in range(count):
        session = (start + timedelta(days=index)).isoformat()
        artifact = {
            "session_date": session,
            "artifact_sha256": f"{index + 1:064x}",
            "sealed_at_utc": f"{session}T12:00:00+00:00",
            "common_row_count": 800,
            "sc001_attempt_sha256": f"{index + 101:064x}",
            "base_model_sha256": "b" * 64,
            "augmented_model_sha256": "c" * 64,
            "outcomes_attached": False,
        }
        ledger = append_t004_decision(
            ledger,
            decision_artifact=artifact,
            artifact_path=f"{session}.json.gz",
        )
    return ledger


def _outcome_ledger(decision_ledger, *, valid_count=None):
    ledger = new_t004_outcome_ledger()
    decisions = decision_ledger["decisions"]
    if valid_count is None:
        valid_count = len(decisions)
    for index, decision in enumerate(decisions):
        artifact = {
            "decision_session": decision["session_date"],
            "horizon_sessions": 5,
            "artifact_sha256": f"{index + 500:064x}",
            "entry_session": decision["session_date"],
            "exit_session": decision["session_date"],
            "valid_outcome_row_count": 700,
            "valid_paired_ic": index < valid_count,
        }
        ledger = append_t004_outcome(
            ledger,
            outcome_artifact=artifact,
            artifact_path=f"o{index}.json.gz",
        )
    return ledger


def test_t004_primary_cohort_is_smallest_qualifying_prefix():
    decisions = _decision_ledger(61)
    outcomes = _outcome_ledger(decisions, valid_count=50)
    cohort = find_t004_primary_cohort(
        decisions=decisions["decisions"],
        outcome_ledger=outcomes,
    )
    assert cohort is not None
    assert len(cohort) == 60

    outcomes_49 = _outcome_ledger(decisions, valid_count=49)
    cohort_61 = find_t004_primary_cohort(
        decisions=decisions["decisions"],
        outcome_ledger=outcomes_49,
    )
    assert cohort_61 is None


def _trial_ledger():
    ledger = append_trial_event(
        new_trial_ledger(),
        event_type="TRIAL_REGISTERED",
        trial_id="AE001-T004",
        recorded_at_utc="2026-09-29T10:00:00+00:00",
        payload={"status": "FROZEN_BEFORE_FIRST_ELIGIBLE_DECISION_SESSION"},
    )
    return append_trial_event(
        ledger,
        event_type="TRIAL_PROTOCOL_AMENDED",
        trial_id="AE001-T004",
        recorded_at_utc="2026-09-29T10:01:00+00:00",
        payload={"protocol_id": "AE001-T004-P2"},
    )


def _metric_artifact(session, index):
    base_ic = 0.01 + index * 0.0001
    aug_ic = base_ic + 0.02 + index * 0.00001
    base_spread = 0.001 + index * 0.00001
    aug_spread = base_spread + 0.003 + index * 0.000001

    def report(ic, spread):
        return {
            "session_metrics": [
                {
                    "feature_session": session,
                    "observation_count": 700,
                    "rank_ic": ic,
                    "top_decile_mean_excess": spread / 2,
                    "bottom_decile_mean_excess": -spread / 2,
                    "top_minus_bottom_spread": spread,
                }
            ]
        }

    return {
        "decision_session": session,
        "horizon_sessions": 5,
        "valid_paired_ic": True,
        "base_metrics": report(base_ic, base_spread),
        "augmented_metrics": report(aug_ic, aug_spread),
    }


def test_t004_finalizer_opens_primary_only_after_p2_gates():
    decisions = _decision_ledger(60)
    outcomes = _outcome_ledger(decisions, valid_count=60)
    artifacts = [
        _metric_artifact(row["session_date"], index)
        for index, row in enumerate(decisions["decisions"])
    ]
    updated, emitted = finalize_t004_results(
        trial_ledger=_trial_ledger(),
        decision_ledger=decisions,
        outcome_ledger=outcomes,
        outcome_artifacts=artifacts,
        recorded_at_utc="2027-01-01T00:00:00+00:00",
    )
    assert len(emitted) == 1
    assert emitted[0]["payload"]["result_kind"] == "PRIMARY_5D"
    assert emitted[0]["payload"]["cohort_size"] == 60
    assert emitted[0]["payload"]["status"] == "SUPPORTED"
    assert updated["events"][-1]["event_sha256"] == emitted[0]["event_sha256"]
