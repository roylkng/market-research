from __future__ import annotations

from marketlab.hg006_terminal_labeling import (
    PRIMARY_CENSORED,
    PRIMARY_COMPLETED,
    PRIMARY_CONFLICT,
    label_episode,
)


def _episode(family: str = "SCHEME_REORGANISATION") -> dict:
    return {
        "episode_id": "EP1",
        "symbol": "TEST",
        "family": family,
        "chronology_id": "C1",
        "event_ids": ["E1"],
        "document_ids": ["D1"],
        "earliest_observed_at_utc": "2026-01-10T10:00:00Z",
    }


def _extraction(
    *,
    family: str = "SCHEME_REORGANISATION",
    stages: list[str] | None = None,
    terminal: str = "NO_EXPLICIT_TERMINAL_LANGUAGE",
    anchors: list[tuple[str, object]] | None = None,
    family_conflict: bool = False,
    event_ids: list[str] | None = None,
    document_id: str = "D1",
) -> dict:
    stages = stages or []
    anchors = anchors or []
    return {
        "chronology_id": "C1",
        "document_id": document_id,
        "event_ids": event_ids or ["E1"],
        "symbol": "TEST",
        "family": family,
        "stage_observations": [
            {
                "stage": stage,
                "evidence_segment_ids": [f"{document_id}:seg:{idx + 1}"],
            }
            for idx, stage in enumerate(stages)
        ],
        "explicit_terminal_language": terminal,
        "terminal_evidence_segment_ids": (
            [f"{document_id}:terminal"]
            if terminal != "NO_EXPLICIT_TERMINAL_LANGUAGE"
            else []
        ),
        "transaction_anchors": [
            {
                "anchor_type": anchor_type,
                "value": value,
                "evidence_segment_ids": [f"{document_id}:anchor:{idx + 1}"],
            }
            for idx, (anchor_type, value) in enumerate(anchors)
        ],
        "family_semantic_conflict": (
            {
                "description": "document economics differ from frozen family",
                "evidence_segment_ids": [f"{document_id}:family-conflict"],
            }
            if family_conflict
            else None
        ),
    }


def _dates(*document_ids: str) -> dict[str, dict[str, str]]:
    return {
        "C1": {
            document_id: f"2026-02-{index + 1:02d}"
            for index, document_id in enumerate(document_ids)
        }
    }


def test_scheme_regulatory_approval_alone_is_right_censored() -> None:
    result = label_episode(
        episode=_episode(),
        extractions=[
            _extraction(stages=["REGULATORY_OR_COURT_APPROVED"])
        ],
        document_dates=_dates("D1"),
    )
    assert result["primary_terminal_state"] == PRIMARY_CENSORED
    assert result["primary_terminal_date"] is None


def test_scheme_transaction_completed_is_completed() -> None:
    result = label_episode(
        episode=_episode(),
        extractions=[
            _extraction(stages=["TRANSACTION_COMPLETED"])
        ],
        document_dates=_dates("D1"),
    )
    assert result["primary_terminal_state"] == PRIMARY_COMPLETED
    assert result["primary_terminal_date"] == "2026-02-01"


def test_scheme_explicit_completion_plus_effective_date_is_completed() -> None:
    result = label_episode(
        episode=_episode(),
        extractions=[
            _extraction(
                terminal="EXPLICIT_COMPLETION_LANGUAGE",
                anchors=[("EFFECTIVE_DATE", "2026-01-31")],
            )
        ],
        document_dates=_dates("D1"),
    )
    assert result["primary_terminal_state"] == PRIMARY_COMPLETED


def test_completion_and_failure_evidence_is_conflict() -> None:
    episode = _episode()
    episode["document_ids"] = ["D1", "D2"]
    result = label_episode(
        episode=episode,
        extractions=[
            _extraction(
                stages=["TRANSACTION_COMPLETED"],
                document_id="D1",
            ),
            _extraction(
                stages=["CANCELLED_OR_WITHDRAWN"],
                document_id="D2",
            ),
        ],
        document_dates=_dates("D1", "D2"),
    )
    assert result["primary_terminal_state"] == PRIMARY_CONFLICT
    assert result["primary_terminal_date"] is None


def test_family_semantic_conflict_excludes_episode_from_outcome_denominator() -> None:
    result = label_episode(
        episode=_episode("PREFERENTIAL_WARRANT"),
        extractions=[
            _extraction(
                family="PREFERENTIAL_WARRANT",
                stages=["ALLOTMENT_COMPLETED"],
                family_conflict=True,
            )
        ],
        document_dates=_dates("D1"),
    )
    assert result["primary_terminal_state"] == PRIMARY_CONFLICT
    assert result["full_economic_exercise"]["terminal_state"] == PRIMARY_CONFLICT


def test_warrant_allotment_completes_issuance_not_full_exercise() -> None:
    result = label_episode(
        episode=_episode("PREFERENTIAL_WARRANT"),
        extractions=[
            _extraction(
                family="PREFERENTIAL_WARRANT",
                stages=["ALLOTMENT_COMPLETED"],
            )
        ],
        document_dates=_dates("D1"),
    )
    assert result["primary_terminal_state"] == PRIMARY_COMPLETED
    assert result["full_economic_exercise"]["terminal_state"] == PRIMARY_CENSORED


def test_warrant_full_exercise_is_separate_completed_track() -> None:
    episode = _episode("PREFERENTIAL_WARRANT")
    episode["document_ids"] = ["D1", "D2"]
    result = label_episode(
        episode=episode,
        extractions=[
            _extraction(
                family="PREFERENTIAL_WARRANT",
                stages=["ALLOTMENT_COMPLETED"],
                document_id="D1",
            ),
            _extraction(
                family="PREFERENTIAL_WARRANT",
                stages=["WARRANT_EXERCISE_OR_CONVERSION_COMPLETED"],
                document_id="D2",
            ),
        ],
        document_dates=_dates("D1", "D2"),
    )
    assert result["primary_terminal_state"] == PRIMARY_COMPLETED
    assert result["full_economic_exercise"]["terminal_state"] == PRIMARY_COMPLETED
    assert result["full_economic_exercise"]["terminal_date"] == "2026-02-02"


def test_cross_episode_document_is_excluded_not_used_for_terminal_label() -> None:
    result = label_episode(
        episode=_episode(),
        extractions=[
            _extraction(
                stages=["TRANSACTION_COMPLETED"],
                event_ids=["E1", "E2"],
            ),
            _extraction(
                stages=["REGULATORY_OR_COURT_APPROVED"],
                event_ids=["E1"],
            ),
        ],
        document_dates=_dates("D1"),
    )
    assert result["primary_terminal_state"] == PRIMARY_CENSORED
    assert result["excluded_cross_episode_document_ids"] == ["D1"]
