"""T012 calendar, original-source, maturity and confirmatory cohort gates."""

from __future__ import annotations

import copy
from datetime import date, timedelta
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_t012_decisions import new_t012_decision_ledger
from marketlab.alpha_t012_outcomes import (
    append_t012_outcome,
    build_t012_horizon_outcome,
    expected_t012_holding_dates,
    finalize_t012_results,
    find_t012_primary_cohort,
    new_t012_outcome_ledger,
    validate_t012_outcome_ledger,
)
from marketlab.alpha_trials import append_trial_event, new_trial_ledger
from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.marketdata import index_snapshot_url, udiff_url

ROOT = Path(__file__).resolve().parents[1]
CALENDAR = ROOT / (
    "research/prospective/calendars/FY27-Q2-2026-09-06/"
    "NSE-CM-FY27Q2-v1.json"
)


def _calendar():
    return load_calendar_snapshot(CALENDAR)


def _decision() -> dict:
    names = [f"S{i:03d}" for i in range(15)]
    item = {
        "schema_version": 1,
        "artifact_id": "AE001-T012-DECISION-v1",
        "trial_id": "AE001-T012",
        "session_date": "2026-10-15",
        "entry_session": "2026-10-16",
        "sealed_at_utc": "2026-10-16T02:55:00+00:00",
        "base_predictions": [
            {"symbol": name, "isin": f"INE{i:09d}", "prediction": i / 10}
            for i, name in enumerate(names)
        ],
        "augmented_predictions": [
            {"symbol": name, "isin": f"INE{i:09d}", "prediction": i / 11}
            for i, name in enumerate(names)
        ],
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    item["artifact_sha256"] = digest(item)
    return item


def _sessions(count: int = 5) -> list[dict]:
    calendar = _calendar()
    days = expected_t012_holding_dates(
        calendar, decision_session="2026-10-15", horizon=5
    )
    expected = []
    for pos, day in enumerate(days[:count]):
        prices = [
            {
                "session_date": day,
                "symbol": f"S{i:03d}",
                "isin": f"INE{i:09d}",
                "open_price": 90.0 + i + pos,
                "close_price": 90.3 + i + pos + 0.07 * i,
                "high_price": 91.0 + i + pos,
                "low_price": 89.5 + i + pos,
                "previous_close": 89.0 + i + pos,
                "volume": 10000.0,
                "turnover_inr": 1000000.0,
                "trade_count": 1000.0,
            }
            for i in range(15)
        ]
        expected.append({
            "session_date": day,
            "udiff_url": udiff_url(date.fromisoformat(day)),
            "benchmark_url": index_snapshot_url(date.fromisoformat(day)),
            "udiff_sha256": f"{pos + 1:064x}",
            "benchmark_sha256": f"{pos + 100:064x}",
            "original_market_raw_path": f"research/synthetic/{day}.zip",
            "original_index_raw_path": f"research/synthetic/{day}.csv",
            "captured_at_utc": f"{day}T11:00:00+00:00",
            "equities": prices,
            "benchmark": {
                "benchmark_id": "nifty_500",
                "index_name": "Nifty 500",
                "session_date": day,
                "open_price": 20000.0 + pos,
                "close_price": 20001.0 + pos,
            },
        })
    return expected


def _evaluate(rows: list[dict], *, capture: str = "2026-10-23T11:45:00+00:00"):
    return build_t012_horizon_outcome(
        decision_artifact=_decision(),
        market_sessions=rows,
        corporate_action_payload=[],
        corporate_action_raw=b"[]",
        horizon_sessions=5,
        calendar=_calendar(),
        captured_at_utc=capture,
    )


def test_calendar_freeze_skips_holiday_and_preserves_exact_fifth_session():
    expected = expected_t012_holding_dates(
        _calendar(), decision_session="2026-10-15", horizon=5
    )
    assert expected == [
        "2026-10-16", "2026-10-19", "2026-10-21",
        "2026-10-22", "2026-10-23",
    ]
    assert "2026-10-20" not in expected


def test_outcome_reuses_fixed_evaluator_but_anchors_only_t012():
    artifact = _evaluate(_sessions())
    assert artifact["trial_id"] == "AE001-T012"
    assert artifact["entry_session"] == "2026-10-16"
    assert artifact["exit_session"] == "2026-10-23"
    assert artifact["expected_holding_sessions"][2] == "2026-10-21"
    assert artifact["decision_artifact_sha256"] == _decision()["artifact_sha256"]
    assert artifact["valid_outcome_row_count"] == 15
    assert artifact["fill_executed"] is False
    assert artifact["live_capital_allowed"] is False
    assert artifact["artifact_sha256"] == digest({
        k: v for k, v in artifact.items() if k != "artifact_sha256"
    })
    ledger = append_t012_outcome(
        new_t012_outcome_ledger(),
        outcome_artifact=artifact,
        artifact_path="research/prospective/ae001-t012/outcomes/fake-h5.json.gz",
    )
    validate_t012_outcome_ledger(ledger)
    with pytest.raises(AlphaContractError, match="duplicate"):
        append_t012_outcome(
            ledger, outcome_artifact=artifact, artifact_path="same",
        )


def test_missing_oct21_cannot_shift_five_session_exit_into_oct24():
    bad = _sessions()
    del bad[2]
    with pytest.raises(AlphaContractError, match="missing/duplicate/shifted"):
        _evaluate(bad)


def test_future_or_preclose_captures_are_rejected():
    with pytest.raises(AlphaContractError, match="before frozen exit close"):
        _evaluate(_sessions(), capture="2026-10-23T09:59:00+00:00")
    bad = _sessions()
    bad[0]["captured_at_utc"] = "2026-10-16T09:59:00+00:00"
    with pytest.raises(AlphaContractError, match="captured before its close"):
        _evaluate(bad)


def test_missing_index_or_wrong_entry_rejected():
    bad = _sessions()
    bad[3]["benchmark"] = None
    with pytest.raises(AlphaContractError, match="missing exact NSE"):
        _evaluate(bad)
    d = _decision()
    d["entry_session"] = "2026-10-19"
    d.pop("artifact_sha256")
    d["artifact_sha256"] = digest(d)
    with pytest.raises(AlphaContractError, match="entry does not match"):
        build_t012_horizon_outcome(
            decision_artifact=d,
            market_sessions=_sessions(),
            corporate_action_payload=[],
            corporate_action_raw=b"[]",
            horizon_sessions=5,
            calendar=_calendar(),
            captured_at_utc="2026-10-23T11:45:00Z",
        )


def test_empty_outcome_ledger_is_hash_bound():
    import json

    initial = json.loads(
        (ROOT / "research/prospective/ae001-t012/outcome-ledger.json")
        .read_text(encoding="utf-8")
    )
    assert initial == new_t012_outcome_ledger()
    damaged = copy.deepcopy(initial)
    damaged["live_capital_allowed"] = True
    with pytest.raises(AlphaContractError, match="authorizes live capital"):
        validate_t012_outcome_ledger(damaged)


def _fake_decision_ledger(n: int) -> dict:
    ledger = new_t012_decision_ledger()
    for index in range(n):
        feature_day = date(2026, 10, 15) + timedelta(days=index)
        next_day = feature_day + timedelta(days=1)
        feature = feature_day.isoformat()
        entry = next_day.isoformat()
        row = {
            "seq": index + 1,
            "session_date": feature,
            "entry_session": entry,
            "sealed_at_utc": f"{entry}T02:30:00+00:00",
            "artifact_path": f"synthetic/{feature}.json.gz",
            "artifact_sha256": f"{index + 1:064x}",
            "admission_sha256": "1" * 64,
            "common_row_count": 125,
            "sc001_attempt_sha256": "2" * 64,
            "sc003_attempt_sha256": "3" * 64,
            "frozen_model_artifact_sha256": (
                "da1ce462b5d9c59fb5bea2f4b69c574c8ecbf1f728c44b23af8f3e73bd5de091"
            ),
            "live_capital_allowed": False,
        }
        row["decision_entry_sha256"] = digest(row)
        ledger["decisions"].append(row)
    ledger["decision_count"] = n
    unsigned = dict(ledger)
    unsigned.pop("ledger_sha256")
    ledger["ledger_sha256"] = digest(unsigned)
    return ledger


def _fake_outcomes(decisions: dict, *, missing: int | None = None) -> dict:
    ledger = new_t012_outcome_ledger()
    for index, row in enumerate(decisions["decisions"]):
        if index == missing:
            continue
        d = row["session_date"]
        for horizon in (1, 5):
            a = {
                "trial_id": "AE001-T012",
                "decision_session": d,
                "horizon_sessions": horizon,
                "entry_session": row["entry_session"],
                "exit_session": row["entry_session"],
                "captured_at_utc": f"{row['entry_session']}T14:00:00Z",
                "decision_artifact_sha256": row["artifact_sha256"],
                "valid_outcome_row_count": 125,
                "valid_paired_ic": index < 49 or index == 60,
                "base_metrics": {
                    "session_metrics": [{
                        "feature_session": d, "rank_ic": 0.01,
                        "top_minus_bottom_spread": 0.001,
                        "top_decile_mean_excess": 0.0005,
                    }]
                },
                "augmented_metrics": {
                    "session_metrics": [{
                        "feature_session": d, "rank_ic": 0.02,
                        "top_minus_bottom_spread": 0.002,
                        "top_decile_mean_excess": 0.001,
                    }]
                },
                "live_capital_allowed": False,
            }
            a["artifact_sha256"] = digest(a)
            ledger = append_t012_outcome(
                ledger, outcome_artifact=a,
                artifact_path=f"synthetic/{d}-h{horizon}.json.gz",
            )
    return ledger


def test_primary_cohort_cannot_skip_missing_h5():
    decisions = _fake_decision_ledger(61)
    outcomes = _fake_outcomes(decisions, missing=12)
    assert find_t012_primary_cohort(
        decision_ledger=decisions,
        outcome_ledger=outcomes,
    ) is None


def test_primary_cohort_waits_for_50_valid_pairs():
    decisions = _fake_decision_ledger(61)
    outcomes = _fake_outcomes(decisions)
    expected = find_t012_primary_cohort(
        decision_ledger=decisions,
        outcome_ledger=outcomes,
    )
    assert expected == [
        row["session_date"] for row in decisions["decisions"]
    ]


def test_primary_only_after_sixty_complete_and_secondary_nonrescuing(
    monkeypatch: pytest.MonkeyPatch,
):
    decisions = _fake_decision_ledger(61)
    outcomes = _fake_outcomes(decisions)
    articles = []
    for row in outcomes["outcomes"]:
        d = row["decision_session"]
        h = row["horizon_sessions"]
        art = {
            "decision_session": d,
            "horizon_sessions": h,
            "valid_paired_ic": row["valid_paired_ic"],
            "base_metrics": {
                "session_metrics": [{"feature_session": d, "rank_ic": 0.01,
                                     "top_minus_bottom_spread": 0.001}]
            },
            "augmented_metrics": {
                "session_metrics": [{"feature_session": d, "rank_ic": 0.02,
                                     "top_minus_bottom_spread": 0.002}]
            },
        }
        art["artifact_sha256"] = digest(art)
        # The ledger's mock artifact hash must correspond to our mock source.
        row["artifact_sha256"] = art["artifact_sha256"]
        row.pop("outcome_entry_sha256")
        row["outcome_entry_sha256"] = digest(row)
        articles.append(art)
    outcomes.pop("ledger_sha256")
    outcomes["ledger_sha256"] = digest(outcomes)

    ledger = append_trial_event(
        new_trial_ledger(),
        event_type="TRIAL_REGISTERED",
        trial_id="AE001-T012",
        recorded_at_utc="2026-10-13T18:29:42.424+00:00",
        payload={"status": "FROZEN_BEFORE_FIRST_ELIGIBLE_PREOPEN_DECISION"},
    )
    counter = {"count": 0}

    def fake_inference(augmented, base, *, max_lag):
        counter["count"] += 1
        fail_primary = counter["count"] == 1
        return {
            "metrics": {
                "rank_ic": {
                    "mean": 0.01,
                    "p_value_two_sided": 0.15 if fail_primary else 0.001,
                },
                "top_minus_bottom_spread": {
                    "mean": 0.002, "p_value_two_sided": 0.01,
                },
            }
        }

    monkeypatch.setattr(
        "marketlab.alpha_t012_outcomes.paired_report_difference_inference",
        fake_inference,
    )
    done, events = finalize_t012_results(
        trial_ledger=ledger,
        decision_ledger=decisions,
        outcome_ledger=outcomes,
        outcome_artifacts=articles,
        recorded_at_utc="2027-01-20T12:00:00+00:00",
    )
    assert [row["payload"]["result_kind"] for row in events] == [
        "PRIMARY_5D", "SECONDARY_1D"
    ]
    assert events[0]["payload"]["status"] == "PRIMARY_NOT_SUPPORTED"
    assert events[1]["payload"]["rescues_failed_primary"] is False
    again, second = finalize_t012_results(
        trial_ledger=done,
        decision_ledger=decisions,
        outcome_ledger=outcomes,
        outcome_artifacts=articles,
        recorded_at_utc="2027-01-21T12:00:00+00:00",
    )
    assert not second
    assert again == done
