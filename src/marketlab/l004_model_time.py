"""L004: distinguish PIT retrieval from PIT *model knowledge*.

The source timestamp cannot prove that a contemporary LLM forgot future facts.
Historical use of an unrestricted model is extraction-only, never predictive
alpha. This module records a bounded contract, not independent model auditing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256


@dataclass(frozen=True)
class ModelInformationRecord:
    symbol: str
    isin: str
    task_kind: str  # EXTRACTION_ONLY, HISTORICAL_PREDICTIVE, PROSPECTIVE_PREDICTIVE
    model_id: str
    model_version: str
    model_first_available_utc: str | None
    decision_cutoff_utc: str
    source_published_utc: str
    source_first_seen_utc: str
    source_bytes: bytes
    source_sha256: str
    prompt_bytes: bytes
    prompt_sha256: str
    request_started_utc: str
    response_completed_utc: str
    future_outcome_attached: bool = False
    known_training_end_utc: str | None = None
    checkpoint_created_utc: str | None = None
    checkpoint_artifact_sha256: str | None = None
    checkpoint_independently_audited: bool = False


def _utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        observed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if observed.tzinfo is None or observed.utcoffset() != timedelta(0):
        return None
    return observed


def assess_model_time(record: ModelInformationRecord) -> dict:
    """Return explicit reasons for refusing historical/prospective claims."""
    reasons: list[str] = []
    cutoff = _utc(record.decision_cutoff_utc)
    source_pub = _utc(record.source_published_utc)
    source_seen = _utc(record.source_first_seen_utc)
    model_release = _utc(record.model_first_available_utc)
    started = _utc(record.request_started_utc)
    finished = _utc(record.response_completed_utc)
    if not record.symbol or not record.isin or not record.model_id or not record.model_version:
        reasons.append("identity_or_version_missing")
    if record.task_kind not in {
        "EXTRACTION_ONLY", "HISTORICAL_PREDICTIVE", "PROSPECTIVE_PREDICTIVE"
    }:
        reasons.append("unsupported_task_kind")
    if not isinstance(record.source_bytes, bytes) or not record.source_bytes or (
        sha256(record.source_bytes).hexdigest() != record.source_sha256
    ):
        reasons.append("source_blob_not_authenticated")
    if not isinstance(record.prompt_bytes, bytes) or not record.prompt_bytes or (
        sha256(record.prompt_bytes).hexdigest() != record.prompt_sha256
    ):
        reasons.append("prompt_blob_not_authenticated")
    if cutoff is None:
        reasons.append("exact_utc_decision_cutoff_missing")
    if source_pub is None or source_seen is None:
        reasons.append("exact_source_timestamps_missing")
    elif cutoff is not None and not source_pub <= source_seen <= cutoff:
        reasons.append("source_not_available_by_cutoff")
    if started is None or finished is None or started > finished:
        reasons.append("inference_clock_invalid")
    if record.future_outcome_attached:
        reasons.append("future_outcomes_attached")
    if reasons:
        return _denied(record, reasons)

    assert cutoff is not None
    assert started is not None and finished is not None
    if record.task_kind == "EXTRACTION_ONLY":
        # A new model processing an old source cannot time-travel its own
        # judgment into a historical feature vector.
        return {
            **_denied(record, ["llm_extraction_not_historical_prediction"]),
            "status": "EXTRACTION_ONLY",
            "permitted_use": "DOCUMENT_QA_OR_POST_HOC_EXTRACTION_WITH_CITATION",
        }
    if record.task_kind == "PROSPECTIVE_PREDICTIVE":
        if (
            model_release is None or model_release > cutoff
            or not started <= finished <= cutoff
        ):
            return _denied(record, ["model_or_inference_not_available_by_decision"])
        return {
            "status": "PROSPECTIVE_TIME_CONTRACT_PASSED",
            "symbol": record.symbol,
            "model": f"{record.model_id}:{record.model_version}",
            "source_hash_checked": True,
            "prompt_hash_checked": True,
            "temporal_source_and_response_checked": True,
            "model_weights_or_tooling_independently_audited": False,
            "investment_authorized": False,
            "return_prediction_validated": False,
            "historical_alpha_eligible": False,
        }
    # Retrospective predictive claims need a model that already existed as of
    # the old decision and independent checkpoint lineage. A present-day
    # model's latest known training end date is not a historical checkpoint.
    training_end = _utc(record.known_training_end_utc)
    checkpoint = _utc(record.checkpoint_created_utc)
    if (
        model_release is None or model_release > cutoff
        or training_end is None or training_end > cutoff
        or checkpoint is None or checkpoint > cutoff
        or not record.checkpoint_independently_audited
        or not _sha256_hex(record.checkpoint_artifact_sha256)
    ):
        return _denied(record, ["historical_model_checkpoint_not_proven"])
    return {
        "status": "HISTORICAL_CHECKPOINT_METADATA_ACCEPTED",
        "symbol": record.symbol,
        "model": f"{record.model_id}:{record.model_version}",
        "source_hash_checked": True,
        "checkpoint_lineage_is_external_assertion": True,
        "training_corpus_and_weights_verified_by_code": False,
        "historical_alpha_eligible": False,
        "needs_historical_outcome_independent_blind_audit": True,
        "investment_authorized": False,
        "return_prediction_validated": False,
    }


def _sha256_hex(value: str | None) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _denied(record: ModelInformationRecord, reasons: list[str]) -> dict:
    return {
        "status": "ABSTAIN",
        "symbol": record.symbol,
        "reasons": sorted(set(reasons)),
        "historical_alpha_eligible": False,
        "investment_authorized": False,
    }
