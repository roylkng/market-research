from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg006_base_rates import (
    SurvivalEpisode,
    episode_from_dates,
    estimate_competing_risk_base_rate,
    publication_gate,
    wilson_interval,
)


def test_censored_episode_is_not_counted_as_failure():
    episodes=[
        SurvivalEpisode("a",30,"COMPLETED"),
        SurvivalEpisode("b",40,"FAILED_OR_WITHDRAWN"),
        SurvivalEpisode("c",100,"RIGHT_CENSORED"),
    ]
    result=estimate_competing_risk_base_rate(
        episodes,
        horizons=(30,60,120),
        bootstrap_resamples=50,
        bootstrap_seed=606001,
    )
    assert result["completed_count"]==1
    assert result["failed_count"]==1
    assert result["right_censored_count"]==1
    assert result["resolved_completion_fraction"]==pytest.approx(0.5)


def test_aalen_johansen_competing_risk_mass_is_coherent():
    episodes=[
        SurvivalEpisode("a",10,"COMPLETED"),
        SurvivalEpisode("b",10,"FAILED_OR_WITHDRAWN"),
        SurvivalEpisode("c",30,"RIGHT_CENSORED"),
        SurvivalEpisode("d",20,"COMPLETED"),
    ]
    result=estimate_competing_risk_base_rate(
        episodes,
        horizons=(10,20,30),
        bootstrap_resamples=30,
    )
    h30=result["aalen_johansen"]["30"]
    assert 0<=h30["completion_cif"]<=1
    assert 0<=h30["failure_cif"]<=1
    assert h30["completion_cif"]+h30["failure_cif"]+h30["event_free_survival"]==pytest.approx(1)


def test_episode_dates_use_cutoff_for_right_censoring():
    episode=episode_from_dates(
        episode_id="x",
        entry_date="2025-01-01",
        terminal_state="RIGHT_CENSORED",
        terminal_date=None,
        observation_cutoff="2025-01-31",
    )
    assert episode.duration_days==30


def test_terminal_episode_requires_valid_terminal_date():
    with pytest.raises(AlphaContractError,match="requires terminal date"):
        episode_from_dates(
            episode_id="x",
            entry_date="2025-01-01",
            terminal_state="COMPLETED",
            terminal_date=None,
            observation_cutoff="2025-01-31",
        )


def test_wilson_and_publication_gate():
    lo,hi=wilson_interval(20,30)
    assert lo<20/30<hi
    assert publication_gate(support_count=30,terminal_count=10)=="PUBLISHABLE_HISTORICAL_BASE_RATE"
    assert publication_gate(support_count=29,terminal_count=20)=="INSUFFICIENT_HISTORICAL_SUPPORT"
