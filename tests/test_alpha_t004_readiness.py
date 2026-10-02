import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_t004_readiness import (
    build_t004_readiness,
    validate_t004_readiness,
)


def _warmup():
    return {
        "state": "WARMUP_BLOCKED",
        "required_prior_sessions": 20,
        "prior_session_count": 20,
        "blocking_session_count": 1,
        "blocking_sessions": [
            {
                "session_date": "2026-09-11",
                "status": "EXCLUDE_SESSION_INTERNAL_FIELD_INCONSISTENCY",
                "raw_sha256": "b" * 64,
            }
        ],
        "consecutive_clean_prior_sessions": 12,
        "additional_clean_prior_sessions_needed": 8,
        "first_prior_session": "2026-09-02",
        "last_prior_session": "2026-09-30",
        "feature_eligibility_changed": False,
        "live_capital_allowed": False,
    }


def test_t004_readiness_hashes_warmup_state():
    readiness = build_t004_readiness(
        session_date="2026-10-01",
        state="DELIVERY_SOURCE_WARMUP_BLOCKED",
        sc001_attempt_sha256="a" * 64,
        support_market_panel_sha256="c" * 64,
        support_delivery_panel_sha256="d" * 64,
        delivery_warmup=_warmup(),
        source_workflow_run_id=123,
    )
    validate_t004_readiness(readiness)
    assert readiness["delivery_warmup"][
        "additional_clean_prior_sessions_needed"
    ] == 8
    assert len(readiness["readiness_sha256"]) == 64


def test_t004_readiness_rejects_warmup_without_remaining_sessions():
    warmup = _warmup()
    warmup["additional_clean_prior_sessions_needed"] = 0
    with pytest.raises(AlphaContractError, match="positive additional"):
        build_t004_readiness(
            session_date="2026-10-01",
            state="DELIVERY_SOURCE_WARMUP_BLOCKED",
            sc001_attempt_sha256="a" * 64,
            delivery_warmup=warmup,
        )


def test_t004_sealed_readiness_requires_artifact_sha():
    with pytest.raises(AlphaContractError, match="decision artifact"):
        build_t004_readiness(
            session_date="2026-10-01",
            state="SEALED",
            sc001_attempt_sha256="a" * 64,
        )
