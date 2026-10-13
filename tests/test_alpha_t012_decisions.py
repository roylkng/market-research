"""T012 decision scoring is a causal clock seal, never an outcome test."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_t012_decisions import (
    append_t012_decision,
    build_t012_decision_artifact,
    new_t012_decision_ledger,
    reseal_t012_decision_artifact,
    validate_t012_decision_ledger,
)
from marketlab.events import sha256_bytes

ROOT = Path(__file__).resolve().parents[1]
MODEL_FILE = ROOT / "research/prospective/ae001-t006/frozen-models-v1.json"


def _models() -> dict:
    return json.loads(MODEL_FILE.read_text(encoding="utf-8"))


def _admission(*, sealed_at: str = "2026-10-16T02:30:00+00:00") -> dict:
    obj = {
        "schema_version": 1,
        "trial_id": "AE001-T012",
        "feature_session": "2026-10-15",
        "entry_session": "2026-10-16",
        "decision_deadline_utc": "2026-10-16T03:00:00+00:00",
        "sealed_at_utc": sealed_at,
        "sc001_attempt_sha256": "a" * 64,
        "sc003_attempt_sha256": "b" * 64,
        "cash_market_raw_sha256": sha256_bytes(b"cash"),
        "delivery_raw_sha256": sha256_bytes(b"delivery"),
        "futures_raw_sha256": sha256_bytes(b"futures"),
        "frozen_model_artifact_sha256": _models()["artifact_sha256"],
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    obj["admission_sha256"] = digest(obj)
    return obj


def _build(monkeypatch: pytest.MonkeyPatch, n: int = 100) -> dict:
    models = _models()
    names = models["augmented_model"]["feature_names"]
    rows = [
        {
            "symbol": f"S{i:05d}",
            "isin": f"INE{i:09d}",
            "values": {key: 0.12 + i / 10000 for key in names},
        }
        for i in range(n)
    ]
    diagnostics = {
        "feature_rows_sha256": digest(rows),
        "exclusions": {"test_only": 0},
        "futures_parser": {"test_only": True},
    }
    monkeypatch.setattr(
        "marketlab.alpha_t012_decisions.build_t006_current_feature_rows",
        lambda **kwargs: (rows, diagnostics),
    )
    return build_t012_decision_artifact(
        admission=_admission(),
        prior_market_sessions=[{"session_date": "2026-10-14"}],
        current_market_raw=b"cash",
        prior_delivery_sessions=[{"session_date": "2026-10-14"}],
        current_delivery_raw=b"delivery",
        current_futures_raw=b"futures",
        corporate_action_payload=[],
        corporate_action_raw=b"[]",
        frozen_models=models,
    )


def test_empty_decision_ledger_is_sealed_and_valid() -> None:
    stored = json.loads(
        (ROOT / "research/prospective/ae001-t012/decision-ledger.json")
        .read_text(encoding="utf-8")
    )
    assert stored == new_t012_decision_ledger()
    validate_t012_decision_ledger(stored)
    assert stored["decision_count"] == 0


def test_fixed_model_decision_artifact_and_final_seal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _build(monkeypatch)
    assert artifact["common_row_count"] == 100
    assert len(artifact["base_predictions"]) == 100
    assert len(artifact["augmented_predictions"]) == 100
    assert artifact["outcomes_attached"] is False
    assert artifact["live_capital_allowed"] is False

    late = _admission(sealed_at="2026-10-16T02:52:00+00:00")
    final = reseal_t012_decision_artifact(artifact, final_admission=late)
    assert final["sealed_at_utc"] == late["sealed_at_utc"]
    assert final["artifact_sha256"] != artifact["artifact_sha256"]

    ledger = append_t012_decision(
        new_t012_decision_ledger(), artifact=final,
        artifact_path="research/prospective/ae001-t012/decisions/test.json.gz",
    )
    assert ledger["decision_count"] == 1
    validate_t012_decision_ledger(ledger)
    with pytest.raises(AlphaContractError, match="already sealed"):
        append_t012_decision(
            ledger, artifact=final,
            artifact_path="research/prospective/ae001-t012/decisions/test.json.gz",
        )

    modified = copy.deepcopy(ledger)
    modified["decisions"][0]["sc003_attempt_sha256"] = "x" * 64
    with pytest.raises(AlphaContractError, match="entry hash mismatch"):
        validate_t012_decision_ledger(modified)


def test_reseal_refuses_late_or_different_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _build(monkeypatch)
    too_late = _admission(sealed_at="2026-10-16T03:00:01+00:00")
    with pytest.raises(AlphaContractError, match="missed pre-open cutoff"):
        reseal_t012_decision_artifact(artifact, final_admission=too_late)
    wrong = _admission(sealed_at="2026-10-16T02:40:00+00:00")
    wrong.pop("admission_sha256")
    wrong["futures_raw_sha256"] = "f" * 64
    wrong["admission_sha256"] = digest(wrong)
    with pytest.raises(AlphaContractError, match="source/model drift"):
        reseal_t012_decision_artifact(artifact, final_admission=wrong)


def test_fails_closed_on_raw_change_and_low_common_row_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _build(monkeypatch, n=100)
    with pytest.raises(AlphaContractError, match="cash_market raw source hash"):
        build_t012_decision_artifact(
            admission=_admission(),
            prior_market_sessions=[],
            current_market_raw=b"wrong",
            prior_delivery_sessions=[],
            current_delivery_raw=b"delivery",
            current_futures_raw=b"futures",
            corporate_action_payload=[],
            corporate_action_raw=b"[]",
            frozen_models=_models(),
        )
    with pytest.raises(AlphaContractError, match="common row count below"):
        _build(monkeypatch, n=99)


def test_new_ledger_cannot_authorize_live_capital() -> None:
    data = new_t012_decision_ledger()
    data["live_capital_allowed"] = True
    with pytest.raises(AlphaContractError, match="live capital"):
        validate_t012_decision_ledger(data)


def test_source_clock_lookup_respects_frozen_market_close() -> None:
    from datetime import UTC, datetime

    from scripts.score_ae001_t012_preopen import _latest_closed_session

    calendar = SimpleNamespace(
        sessions=(
            SimpleNamespace(
                session_date="2026-10-15",
                close_timestamp_utc="2026-10-15T10:00:00Z",
            ),
            SimpleNamespace(
                session_date="2026-10-16",
                close_timestamp_utc="2026-10-16T10:00:00Z",
            ),
        )
    )
    before = datetime(2026, 10, 15, 9, 59, tzinfo=UTC)
    after = datetime(2026, 10, 16, 2, 55, tzinfo=UTC)
    assert _latest_closed_session(calendar, before) is None
    assert _latest_closed_session(calendar, after) == "2026-10-15"
