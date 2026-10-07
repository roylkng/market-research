from __future__ import annotations

from marketlab.hg006_d004_execution import (
    TRACK_SPECS,
    _stage_surface,
    _supported_horizons,
    build_d004_base_rates,
)
from marketlab.hg006_base_rates import SurvivalEpisode


def _row(index: int, family: str, *, conflict: bool = True) -> dict:
    entry = "2024-01-01"
    state = "UNRESOLVED_SOURCE_CONFLICT" if conflict else "RIGHT_CENSORED"
    return {
        "episode_id": f"E{index:04d}",
        "family": family,
        "entry_date": entry,
        "primary_terminal_state": state,
        "primary_terminal_date": None,
        "first_observed_stage_dates": {
            "BOARD_APPROVED": "2024-01-10",
            "ALLOTMENT_COMPLETED": "2024-06-01",
        },
        "full_economic_exercise": (
            {
                "terminal_state": state,
                "terminal_date": None,
            }
            if family == "PREFERENTIAL_WARRANT"
            else None
        ),
    }


def _panel() -> dict:
    rows = []
    for idx in range(151):
        rows.append(_row(idx, "PREFERENTIAL_WARRANT"))
    for idx in range(151, 333):
        rows.append(_row(idx, "SCHEME_REORGANISATION"))
    return {
        "labeler_id": "HG006-D002-P1-v1",
        "label_panel_sha256": (
            "545532620b409135bd867f633de708cfd441e2c532a5b790afeacef9c7de9874"
        ),
        "episode_count": 333,
        "observation_cutoff": "2026-09-30",
        "episodes": rows,
        "historical_terminal_labels_opened": True,
        "completion_probabilities_assigned": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_warrant_allotment_stage_is_excluded_from_issuance_but_kept_for_exercise():
    issuance = TRACK_SPECS[("PREFERENTIAL_WARRANT", "issuance_completion")]
    exercise = TRACK_SPECS[
        ("PREFERENTIAL_WARRANT", "full_economic_exercise")
    ]
    assert "ALLOTMENT_COMPLETED" not in issuance["stages"]
    assert "ALLOTMENT_COMPLETED" in exercise["stages"]


def test_supported_horizon_requires_actual_follow_up():
    episodes = [
        SurvivalEpisode("a", 89, "RIGHT_CENSORED"),
        SurvivalEpisode("b", 365, "RIGHT_CENSORED"),
    ]
    assert _supported_horizons(episodes) == (90, 180, 365)


def test_stage_surface_does_not_publish_small_risk_set():
    rows = [
        {
            **_row(index, "SCHEME_REORGANISATION", conflict=False),
            "primary_terminal_state": "RIGHT_CENSORED",
        }
        for index in range(20)
    ]
    result = _stage_surface(
        rows,
        family="SCHEME_REORGANISATION",
        track_name="transaction_completion",
        terminal_source="primary",
        stage="BOARD_APPROVED",
        observation_cutoff="2026-09-30",
    )
    assert result["support_count"] == 20
    assert result["publication_state"] == "INSUFFICIENT_HISTORICAL_SUPPORT"
    assert all(
        row["state"] == "NOT_PUBLISHED_SUPPORT"
        for row in result["horizons"].values()
    )


def test_full_builder_excludes_conflicts_and_never_assigns_current_probability():
    result = build_d004_base_rates(_panel())
    surfaces = {
        (row["family"], row["track"]): row
        for row in result["family_surfaces"]
    }
    assert surfaces[
        ("PREFERENTIAL_WARRANT", "issuance_completion")
    ]["conflict_excluded_count"] == 151
    assert surfaces[
        ("PREFERENTIAL_WARRANT", "full_economic_exercise")
    ]["conflict_excluded_count"] == 151
    assert surfaces[
        ("SCHEME_REORGANISATION", "transaction_completion")
    ]["conflict_excluded_count"] == 182
    assert result["current_company_probabilities_assigned"] is False
    assert result["return_outcomes_opened"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False
    assert result["feasibility_pass"] is True
