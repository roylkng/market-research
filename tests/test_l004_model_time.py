"""L004 test matrix: current-model historical predictions are not alpha."""

from dataclasses import replace
from hashlib import sha256

from marketlab.l004_model_time import ModelInformationRecord, assess_model_time


def item(**changes):
    source = b"archived original filing before the decision"
    prompt = b"extract statements, do not use later outcomes"
    values = {
        "symbol": "TEST",
        "isin": "INE000000001",
        "task_kind": "PROSPECTIVE_PREDICTIVE",
        "model_id": "checkpoint-test-model",
        "model_version": "v1",
        "model_first_available_utc": "2026-10-16T12:00:00Z",
        "decision_cutoff_utc": "2026-10-17T10:00:00Z",
        "source_published_utc": "2026-10-17T04:00:00Z",
        "source_first_seen_utc": "2026-10-17T04:01:00Z",
        "source_bytes": source,
        "source_sha256": sha256(source).hexdigest(),
        "prompt_bytes": prompt,
        "prompt_sha256": sha256(prompt).hexdigest(),
        "request_started_utc": "2026-10-17T09:00:00Z",
        "response_completed_utc": "2026-10-17T09:01:00Z",
    }
    values.update(changes)
    return ModelInformationRecord(**values)


def test_prospective_only_passes_time_contract():
    out = assess_model_time(item())
    assert out["status"] == "PROSPECTIVE_TIME_CONTRACT_PASSED"
    assert out["historical_alpha_eligible"] is False
    assert out["return_prediction_validated"] is False


def test_response_later_on_same_day_rejected():
    out = assess_model_time(item(response_completed_utc="2026-10-17T10:01:00Z"))
    assert out["status"] == "ABSTAIN"


def test_source_post_decision_rejected():
    out = assess_model_time(item(source_published_utc="2026-10-17T11:00:00Z"))
    assert "source_not_available_by_cutoff" in out["reasons"]


def test_post_decision_capture_rejected():
    out = assess_model_time(item(source_first_seen_utc="2026-10-17T11:00:00Z"))
    assert out["status"] == "ABSTAIN"


def test_mutated_original_source_denied():
    out = assess_model_time(item(source_bytes=b"modified"))
    assert "source_blob_not_authenticated" in out["reasons"]


def test_changed_prompt_denied():
    out = assess_model_time(item(prompt_bytes=b"new prompt"))
    assert "prompt_blob_not_authenticated" in out["reasons"]


def test_future_outcomes_poisoning_denied():
    assert assess_model_time(item(future_outcome_attached=True))["status"] == "ABSTAIN"


def test_historical_current_model_denied_despite_old_filings():
    out = assess_model_time(item(
        task_kind="HISTORICAL_PREDICTIVE",
        decision_cutoff_utc="2025-10-17T10:00:00Z",
        source_published_utc="2025-10-17T04:00:00Z",
        source_first_seen_utc="2025-10-17T04:01:00Z",
    ))
    assert "historical_model_checkpoint_not_proven" in out["reasons"]


def test_historical_checkpoint_metadata_not_proof_of_alpha():
    out = assess_model_time(item(
        task_kind="HISTORICAL_PREDICTIVE",
        decision_cutoff_utc="2025-10-17T10:00:00Z",
        source_published_utc="2025-10-17T04:00:00Z",
        source_first_seen_utc="2025-10-17T04:01:00Z",
        model_first_available_utc="2025-01-01T00:00:00Z",
        known_training_end_utc="2024-12-31T00:00:00Z",
        checkpoint_created_utc="2025-01-01T00:00:00Z",
        checkpoint_artifact_sha256="a" * 64,
        checkpoint_independently_audited=True,
    ))
    assert out["status"] == "HISTORICAL_CHECKPOINT_METADATA_ACCEPTED"
    assert out["historical_alpha_eligible"] is False
    assert out["training_corpus_and_weights_verified_by_code"] is False


def test_extraction_only_can_be_backfilled_but_never_alpha():
    out = assess_model_time(item(
        task_kind="EXTRACTION_ONLY",
        request_started_utc="2026-11-10T10:00:00Z",
        response_completed_utc="2026-11-10T10:01:00Z",
    ))
    assert out["status"] == "EXTRACTION_ONLY"
    assert out["historical_alpha_eligible"] is False
    assert out["investment_authorized"] is False


def test_no_model_release_timestamp_is_not_prospective_verified():
    assert assess_model_time(item(model_first_available_utc=None))["status"] == "ABSTAIN"


def test_invalid_clock_timezone_rejected():
    assert assess_model_time(item(decision_cutoff_utc="2026-10-17T10:00:00"))["status"] == "ABSTAIN"


def test_invalid_mode_rejected():
    out = assess_model_time(item(task_kind="EXTRAPOLATE_STOCK_PRICE"))
    assert out["status"] == "ABSTAIN"


def test_record_immutability():
    base = item()
    new = replace(base, symbol="OTHER")
    assert base.symbol == "TEST"
    assert new.symbol == "OTHER"
