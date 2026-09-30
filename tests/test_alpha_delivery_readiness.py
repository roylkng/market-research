import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_delivery_readiness import (
    delivery_source_warmup_readiness,
)


def _sessions(statuses):
    return [
        {
            "session_date": f"2026-09-{index + 1:02d}",
            "source_quality": {"status": status},
            "raw_sha256": f"{index + 1:064x}",
        }
        for index, status in enumerate(statuses)
    ]


def test_delivery_warmup_ready_requires_all_twenty_prior_sessions_ready():
    report = delivery_source_warmup_readiness(
        _sessions(["READY"] * 20)
    )
    assert report["state"] == "READY"
    assert report["blocking_session_count"] == 0
    assert report["consecutive_clean_prior_sessions"] == 20
    assert report["additional_clean_prior_sessions_needed"] == 0
    assert report["feature_eligibility_changed"] is False


def test_delivery_warmup_reports_clean_sessions_after_last_blocker():
    statuses = ["READY"] * 8 + [
        "EXCLUDE_SESSION_INTERNAL_FIELD_INCONSISTENCY"
    ] + ["READY"] * 11
    report = delivery_source_warmup_readiness(_sessions(statuses))
    assert report["state"] == "WARMUP_BLOCKED"
    assert report["blocking_session_count"] == 1
    assert report["blocking_sessions"][0]["session_date"] == "2026-09-09"
    assert report["consecutive_clean_prior_sessions"] == 11
    assert report["additional_clean_prior_sessions_needed"] == 9


def test_delivery_warmup_rejects_wrong_window_length():
    with pytest.raises(AlphaContractError, match="exact frozen prior-session window"):
        delivery_source_warmup_readiness(_sessions(["READY"] * 19))
