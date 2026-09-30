import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_t006_prospective import (
    append_t006_decision,
    build_t006_decision_artifact,
    eligible_sc002_attempt,
    new_t006_decision_ledger,
    validate_t006_decision_ledger,
)


def _sc_attempt(prefix: str):
    return {
        "session_date": "2026-10-01",
        "eligible_before_cutoff": True,
        "attempt_sha256": prefix * 64,
        "captured_at_utc": "2026-10-01T12:00:00+00:00",
    }


def test_t006_requires_sc002_eligible_attempt():
    ledger = {
        "attempts": [
            {
                "seq": 1,
                "session_date": "2026-10-01",
                "eligible_before_cutoff": False,
                "captured_at_utc": "2026-10-01T12:00:00+00:00",
            }
        ]
    }
    with pytest.raises(AlphaContractError, match="no SC002 eligible"):
        eligible_sc002_attempt(
            ledger,
            session_date="2026-10-01",
        )


def test_t006_prediction_seal_requires_dual_sources_and_cutoff(monkeypatch):
    rows = [
        {
            "symbol": f"S{index:03d}",
            "isin": f"INE{index:09d}",
            "values": {"x": 0.5},
        }
        for index in range(100)
    ]
    monkeypatch.setattr(
        "marketlab.alpha_t006_prospective.validate_frozen_t006_models",
        lambda artifact: None,
    )
    monkeypatch.setattr(
        "marketlab.alpha_t006_prospective.build_t006_current_feature_rows",
        lambda **kwargs: (
            rows,
            {
                "common_row_count": 100,
                "feature_rows_sha256": "f" * 64,
                "exclusions": {},
                "futures_parser": {"accepted_contract_row_count": 200},
            },
        ),
    )
    monkeypatch.setattr(
        "marketlab.alpha_t006_prospective._score_model",
        lambda model, rows: [
            {
                "symbol": row["symbol"],
                "isin": row["isin"],
                "prediction": 0.01,
            }
            for row in rows
        ],
    )
    models = {
        "artifact_sha256": "a" * 64,
        "base_model": {"model_sha256": "b" * 64},
        "augmented_model": {"model_sha256": "c" * 64},
    }
    artifact = build_t006_decision_artifact(
        session_date="2026-10-01",
        sc001_attempt=_sc_attempt("d"),
        sc002_attempt=_sc_attempt("e"),
        prior_market_sessions=[{"session_date": "2026-09-30"}],
        current_market_raw=b"m",
        prior_delivery_sessions=[{"session_date": "2026-09-30"}],
        current_delivery_raw=b"d",
        current_futures_raw=b"f",
        corporate_action_payload=[],
        corporate_action_raw=b"a",
        frozen_models=models,
        sealed_at_utc="2026-10-01T12:59:59+00:00",
    )
    assert artifact["common_row_count"] == 100
    assert artifact["sc001_attempt_sha256"] == "d" * 64
    assert artifact["sc002_attempt_sha256"] == "e" * 64
    assert artifact["outcomes_attached"] is False

    with pytest.raises(AlphaContractError, match="missed decision cutoff"):
        build_t006_decision_artifact(
            session_date="2026-10-01",
            sc001_attempt=_sc_attempt("d"),
            sc002_attempt=_sc_attempt("e"),
            prior_market_sessions=[{"session_date": "2026-09-30"}],
            current_market_raw=b"m",
            prior_delivery_sessions=[{"session_date": "2026-09-30"}],
            current_delivery_raw=b"d",
            current_futures_raw=b"f",
            corporate_action_payload=[],
            corporate_action_raw=b"a",
            frozen_models=models,
            sealed_at_utc="2026-10-01T13:00:01+00:00",
        )


def test_t006_rejects_source_session_mismatch(monkeypatch):
    monkeypatch.setattr(
        "marketlab.alpha_t006_prospective.validate_frozen_t006_models",
        lambda artifact: None,
    )
    sc002 = _sc_attempt("e")
    sc002["session_date"] = "2026-10-02"
    with pytest.raises(AlphaContractError, match="session mismatch"):
        build_t006_decision_artifact(
            session_date="2026-10-01",
            sc001_attempt=_sc_attempt("d"),
            sc002_attempt=sc002,
            prior_market_sessions=[],
            current_market_raw=b"m",
            prior_delivery_sessions=[],
            current_delivery_raw=b"d",
            current_futures_raw=b"f",
            corporate_action_payload=[],
            corporate_action_raw=b"a",
            frozen_models={},
        )


def test_t006_decision_ledger_is_unique_and_hash_verified():
    artifact = {
        "session_date": "2026-10-01",
        "artifact_sha256": "a" * 64,
        "sealed_at_utc": "2026-10-01T12:45:00+00:00",
        "common_row_count": 150,
        "sc001_attempt_sha256": "b" * 64,
        "sc002_attempt_sha256": "c" * 64,
        "base_model_sha256": "d" * 64,
        "augmented_model_sha256": "e" * 64,
        "outcomes_attached": False,
    }
    ledger = append_t006_decision(
        new_t006_decision_ledger(),
        decision_artifact=artifact,
        artifact_path=(
            "research/prospective/ae001-t006/decisions/"
            "2026-10-01-v1.json.gz"
        ),
    )
    validate_t006_decision_ledger(ledger)
    assert ledger["decision_count"] == 1
    with pytest.raises(AlphaContractError, match="already exists"):
        append_t006_decision(
            ledger,
            decision_artifact=artifact,
            artifact_path="duplicate",
        )



def test_t006_decision_ledger_rejects_out_of_order_session():
    first = {
        "session_date": "2026-10-02",
        "artifact_sha256": "1" * 64,
        "sealed_at_utc": "2026-10-02T12:45:00+00:00",
        "common_row_count": 150,
        "sc001_attempt_sha256": "2" * 64,
        "sc002_attempt_sha256": "3" * 64,
        "base_model_sha256": "4" * 64,
        "augmented_model_sha256": "5" * 64,
        "outcomes_attached": False,
    }
    ledger = append_t006_decision(
        new_t006_decision_ledger(),
        decision_artifact=first,
        artifact_path=(
            "research/prospective/ae001-t006/decisions/"
            "2026-10-02-v1.json.gz"
        ),
    )
    earlier = {
        **first,
        "session_date": "2026-10-01",
        "artifact_sha256": "6" * 64,
        "sealed_at_utc": "2026-10-01T12:45:00+00:00",
    }
    with pytest.raises(AlphaContractError, match="strictly increasing"):
        append_t006_decision(
            ledger,
            decision_artifact=earlier,
            artifact_path=(
                "research/prospective/ae001-t006/decisions/"
                "2026-10-01-v1.json.gz"
            ),
        )
