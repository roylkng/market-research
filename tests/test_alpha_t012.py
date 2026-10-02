from datetime import UTC, datetime

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_t012 import (
    append_t012_decision,
    build_t012_decision_artifact,
    eligible_sc002_t012_attempt,
    freeze_t012_cutoff,
    new_t012_cutoff_freeze,
    new_t012_decision_ledger,
    session_is_post_timing_basis,
    t012_cutoff_utc,
    validate_t012_cutoff_freeze,
    validate_t012_decision_ledger,
)


def _summary(*, cutoff="23:30:00", offset=0):
    return {
        "schema_version": 1,
        "analysis_id": "AE001-SC002-PUBLICATION-TIMING-v1",
        "source_ledger_sha256": "a" * 64,
        "minimum_distinct_ready_sessions": 3,
        "distinct_ready_session_count": 3,
        "observations": [
            {
                "session_date": "2026-09-30",
                "captured_at_ist": "2026-09-30T21:09:27+05:30",
            },
            {
                "session_date": "2026-10-01",
                "captured_at_ist": "2026-10-01T22:50:52+05:30",
            },
            {
                "session_date": "2026-10-02",
                "captured_at_ist": "2026-10-02T22:55:00+05:30",
            },
        ],
        "candidate_rule": (
            "LATEST_FIRST_READY_PLUS_30_MINUTES_ROUNDED_UP_TO_NEXT_15_MINUTES"
        ),
        "safety_buffer_minutes": 30,
        "rounding_minutes": 15,
        "uses_stock_return_or_alpha_outcomes": False,
        "successor_trial_cutoff_frozen": False,
        "state": "SOURCE_TIMING_READY_FOR_SUCCESSOR_DESIGN",
        "additional_distinct_ready_sessions_needed": 0,
        "latest_first_ready_at_ist": "2026-10-02T22:55:00+05:30",
        "candidate_cutoff_ist": cutoff,
        "candidate_cutoff_session_offset_days": offset,
        "candidate_cutoff_basis_session": "2026-10-02",
        "median_first_ready_local_seconds": 82000.0,
        "summary_sha256": "b" * 64,
        "live_capital_allowed": False,
    }


def test_t012_freezes_source_only_cutoff_and_excludes_basis_sessions():
    frozen = freeze_t012_cutoff(
        new_t012_cutoff_freeze(),
        timing_summary=_summary(),
        frozen_at_utc="2026-10-02T18:00:00+00:00",
    )
    validate_t012_cutoff_freeze(frozen)
    assert frozen["state"] == "FROZEN"
    assert frozen["timing_basis_sessions"] == [
        "2026-09-30",
        "2026-10-01",
        "2026-10-02",
    ]
    assert frozen["latest_timing_basis_session"] == "2026-10-02"
    assert session_is_post_timing_basis("2026-10-02", frozen) is False
    assert session_is_post_timing_basis("2026-10-03", frozen) is True


def test_t012_cutoff_handles_cross_midnight_session_offset():
    frozen = freeze_t012_cutoff(
        new_t012_cutoff_freeze(),
        timing_summary=_summary(cutoff="00:30:00", offset=1),
        frozen_at_utc="2026-10-02T18:00:00+00:00",
    )
    cutoff = t012_cutoff_utc("2026-10-05", frozen)
    # 00:30 IST on session-date + 1 = 19:00 UTC on session date.
    assert cutoff == datetime(2026, 10, 5, 19, 0, tzinfo=UTC)


def test_t012_attempt_selection_uses_custom_cutoff_not_t006_flag():
    frozen = freeze_t012_cutoff(
        new_t012_cutoff_freeze(),
        timing_summary=_summary(),
        frozen_at_utc="2026-10-02T18:00:00+00:00",
    )
    ledger = {
        "schema_version": 1,
        "ledger_id": "AE001-SC002-FUTURES-SOURCE-LEDGER-v1",
        "attempt_count": 2,
        "attempts": [
            {
                "seq": 1,
                "session_date": "2026-10-05",
                "captured_at_utc": "2026-10-05T17:40:00+00:00",
                "decision_cutoff_utc": "2026-10-05T13:00:00+00:00",
                "captured_before_or_at_cutoff": False,
                "eligible_before_cutoff": False,
                "futures": {
                    "status": "READY",
                    "raw_sha256": "c" * 64,
                    "raw_repo_path": "x",
                },
                "live_capital_allowed": False,
            },
            {
                "seq": 2,
                "session_date": "2026-10-05",
                "captured_at_utc": "2026-10-05T18:10:00+00:00",
                "decision_cutoff_utc": "2026-10-05T13:00:00+00:00",
                "captured_before_or_at_cutoff": False,
                "eligible_before_cutoff": False,
                "futures": {
                    "status": "READY",
                    "raw_sha256": "d" * 64,
                    "raw_repo_path": "y",
                },
                "live_capital_allowed": False,
            },
        ],
        "live_capital_allowed": False,
    }
    # Rehash using the source-ledger canonical contract.
    from marketlab.alpha import digest

    for attempt in ledger["attempts"]:
        attempt["attempt_sha256"] = digest(attempt)
    ledger["ledger_sha256"] = digest(ledger)

    selected = eligible_sc002_t012_attempt(
        ledger,
        session_date="2026-10-05",
        cutoff_freeze=frozen,
    )
    assert selected["seq"] == 1
    assert selected["eligible_before_cutoff"] is False


def test_t012_attempt_selection_rejects_timing_basis_session():
    frozen = freeze_t012_cutoff(
        new_t012_cutoff_freeze(),
        timing_summary=_summary(),
        frozen_at_utc="2026-10-02T18:00:00+00:00",
    )
    ledger = {
        "schema_version": 1,
        "ledger_id": "AE001-SC002-FUTURES-SOURCE-LEDGER-v1",
        "attempt_count": 0,
        "attempts": [],
        "live_capital_allowed": False,
    }
    from marketlab.alpha import digest

    ledger["ledger_sha256"] = digest(ledger)
    with pytest.raises(AlphaContractError, match="timing-basis session"):
        eligible_sc002_t012_attempt(
            ledger,
            session_date="2026-10-02",
            cutoff_freeze=frozen,
        )


def test_t012_decision_must_seal_before_custom_cutoff(monkeypatch):
    frozen = freeze_t012_cutoff(
        new_t012_cutoff_freeze(),
        timing_summary=_summary(),
        frozen_at_utc="2026-10-02T18:00:00+00:00",
    )
    rows = [
        {
            "symbol": f"S{index:03d}",
            "isin": f"INE{index:09d}",
            "values": {"x": 0.5},
        }
        for index in range(100)
    ]
    monkeypatch.setattr(
        "marketlab.alpha_t012.validate_frozen_t006_models",
        lambda artifact: None,
    )
    monkeypatch.setattr(
        "marketlab.alpha_t012.build_t006_current_feature_rows",
        lambda **kwargs: (
            rows,
            {
                "feature_rows_sha256": "f" * 64,
                "exclusions": {},
                "futures_parser": {},
            },
        ),
    )
    monkeypatch.setattr(
        "marketlab.alpha_t012._score_model",
        lambda model, rows: [
            {
                "symbol": row["symbol"],
                "isin": row["isin"],
                "prediction": 0.1,
            }
            for row in rows
        ],
    )
    sc001 = {
        "session_date": "2026-10-05",
        "eligible_before_cutoff": True,
        "attempt_sha256": "1" * 64,
        "captured_at_utc": "2026-10-05T12:00:00+00:00",
    }
    sc002 = {
        "session_date": "2026-10-05",
        "attempt_sha256": "2" * 64,
        "captured_at_utc": "2026-10-05T17:40:00+00:00",
    }
    models = {
        "artifact_sha256": "3" * 64,
        "base_model": {"model_sha256": "4" * 64},
        "augmented_model": {"model_sha256": "5" * 64},
    }
    with pytest.raises(AlphaContractError, match="missed frozen late-evening cutoff"):
        build_t012_decision_artifact(
            session_date="2026-10-05",
            cutoff_freeze=frozen,
            sc001_attempt=sc001,
            sc002_attempt=sc002,
            prior_market_sessions=[],
            current_market_raw=b"m",
            prior_delivery_sessions=[],
            current_delivery_raw=b"d",
            current_futures_raw=b"f",
            corporate_action_payload=[],
            corporate_action_raw=b"a",
            frozen_models=models,
            sealed_at_utc="2026-10-05T18:01:00+00:00",
        )


def test_t012_decision_ledger_is_append_only():
    artifact = {
        "session_date": "2026-10-05",
        "artifact_sha256": "a" * 64,
        "sealed_at_utc": "2026-10-05T17:50:00+00:00",
        "decision_cutoff_utc": "2026-10-05T18:00:00+00:00",
        "common_row_count": 150,
        "cutoff_freeze_sha256": "b" * 64,
        "sc001_attempt_sha256": "c" * 64,
        "sc002_attempt_sha256": "d" * 64,
        "base_model_sha256": "e" * 64,
        "augmented_model_sha256": "f" * 64,
        "outcomes_attached": False,
    }
    ledger = append_t012_decision(
        new_t012_decision_ledger(),
        decision_artifact=artifact,
        artifact_path=(
            "research/prospective/ae001-t012/decisions/2026-10-05-v1.json.gz"
        ),
    )
    validate_t012_decision_ledger(ledger)
    assert ledger["decision_count"] == 1
    with pytest.raises(AlphaContractError, match="already exists"):
        append_t012_decision(
            ledger,
            decision_artifact=artifact,
            artifact_path="duplicate",
        )
