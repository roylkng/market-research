from __future__ import annotations

from marketlab.hg006_base_rates import SurvivalEpisode
from marketlab.hg006_p001_current_mapping import (
    _survivor_condition,
    build_p001_current_mapping,
)


def _sources(stage: str = "BOARD_APPROVED", family_match: bool = True):
    d001 = {
        "selection_sha256": (
            "9b82b337b02d5aa2c58164bf888f76ce50fcd34680077f87f13b0ff5cfc7c102"
        ),
        "event_links": [
            {
                "announcement_id": "EV1",
                "document_id": "DOC1",
                "exchange_published_at_utc": "2026-09-20T10:00:00Z",
            }
        ],
        "return_outcomes_opened": False,
    }
    l001 = {
        "run_sha256": (
            "a402b39a8890cd2fac3218bb94673f8b9c00b1f325315f9ec93863c22d9a1d12"
        ),
        "rows": [
            {
                "document_id": "DOC1",
                "validated_extraction": {
                    "event_ids": ["EV1"],
                    "symbols": ["TEST"],
                    "economic_relevance": "DIRECT_LISTED_SECURITY",
                    "transaction_families": (
                        ["PREFERENTIAL_WARRANT"] if family_match else ["FUND_RAISE_OTHER"]
                    ),
                    "transaction_stage": stage,
                },
            }
        ],
        "return_outcomes_opened": False,
    }
    l002 = {
        "synthesis_sha256": (
            "6bd1a43d29460fc18389dfdcb7241c95d1de0acb80b769a728946ef81c031683"
        ),
        "rows": [
            {
                "symbol": "TEST",
                "payoff_model_lanes": [
                    {
                        "economic_family": "DILUTION_FINANCING",
                        "readiness_state": "READY_DILUTION_FINANCING",
                        "evidence_document_ids": ["DOC1"],
                    }
                ],
            }
        ],
        "return_outcomes_opened": False,
    }
    d004 = {
        "base_rate_panel_sha256": (
            "08eddc18599b7dcd86c4a688ef46fc6161a1a52cb49b72cf6695ffbc43ce3084"
        ),
        "stage_surfaces": [
            {
                "family": "PREFERENTIAL_WARRANT",
                "track": "issuance_completion",
                "stage": "BOARD_APPROVED",
                "publication_state": "PUBLISHABLE_HISTORICAL_BASE_RATE",
                "support_count": 68,
            },
            {
                "family": "PREFERENTIAL_WARRANT",
                "track": "full_economic_exercise",
                "stage": "BOARD_APPROVED",
                "publication_state": "PUBLISHABLE_HISTORICAL_BASE_RATE",
                "support_count": 68,
            },
            {
                "family": "PREFERENTIAL_WARRANT",
                "track": "full_economic_exercise",
                "stage": "ALLOTMENT_COMPLETED",
                "publication_state": "PUBLISHABLE_HISTORICAL_BASE_RATE",
                "support_count": 93,
            },
        ],
        "current_company_probabilities_assigned": False,
        "return_outcomes_opened": False,
    }
    episodes = []
    for index in range(25):
        episodes.append(
            {
                "episode_id": f"E{index}",
                "family": "PREFERENTIAL_WARRANT",
                "entry_date": "2025-01-01",
                "primary_terminal_state": "RIGHT_CENSORED",
                "primary_terminal_date": None,
                "first_observed_stage_dates": {
                    "BOARD_APPROVED": "2025-01-10",
                    "ALLOTMENT_COMPLETED": "2025-03-01",
                },
                "full_economic_exercise": {
                    "terminal_state": "RIGHT_CENSORED",
                    "terminal_date": None,
                },
            }
        )
    labels = {
        "label_panel_sha256": (
            "545532620b409135bd867f633de708cfd441e2c532a5b790afeacef9c7de9874"
        ),
        "observation_cutoff": "2026-09-30",
        "episodes": episodes,
        "return_outcomes_opened": False,
    }
    return d001, l001, l002, d004, labels


def test_survivor_condition_requires_follow_up_beyond_elapsed_time():
    episodes = [
        SurvivalEpisode("a", 10, "COMPLETED"),
        SurvivalEpisode("b", 20, "RIGHT_CENSORED"),
        SurvivalEpisode("c", 30, "FAILED_OR_WITHDRAWN"),
    ]
    result = _survivor_condition(episodes, elapsed_days=20)
    assert [(row.episode_id, row.duration_days) for row in result] == [("c", 10)]


def test_current_case_refuses_probability_when_survivor_support_is_too_small():
    d001, l001, l002, d004, labels = _sources()
    result = build_p001_current_mapping(
        d001_selection=d001,
        l001_run=l001,
        l002_synthesis=l002,
        d004_panel=d004,
        historical_labels=labels,
    )
    states = {
        row["historical_track"]: row["mapping_state"]
        for row in result["cases"]
    }
    assert states["issuance_completion"] == "INSUFFICIENT_SURVIVOR_CONDITIONED_SUPPORT"
    assert states["full_economic_exercise"] == "INSUFFICIENT_SURVIVOR_CONDITIONED_SUPPORT"
    assert result["expected_returns_calculated"] is False


def test_allotment_is_deterministic_current_issuance_completion_not_probability():
    d001, l001, l002, d004, labels = _sources(stage="ALLOTMENT_COMPLETED")
    result = build_p001_current_mapping(
        d001_selection=d001,
        l001_run=l001,
        l002_synthesis=l002,
        d004_panel=d004,
        historical_labels=labels,
    )
    rows = {row["historical_track"]: row for row in result["cases"]}
    assert rows["issuance_completion"]["mapping_state"] == "CURRENT_TERMINAL_COMPLETED"
    assert rows["issuance_completion"]["probability_surface"] is None
    assert rows["full_economic_exercise"]["current_stage"] == "ALLOTMENT_COMPLETED"


def test_lane_without_exact_llm_family_match_gets_no_probability():
    d001, l001, l002, d004, labels = _sources(family_match=False)
    result = build_p001_current_mapping(
        d001_selection=d001,
        l001_run=l001,
        l002_synthesis=l002,
        d004_panel=d004,
        historical_labels=labels,
    )
    assert all(
        row["mapping_state"] == "NO_EXACT_HISTORICAL_FAMILY_MATCH"
        for row in result["cases"]
    )
