from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from marketlab.alpha import AlphaContractError

BOOTSTRAP_RESAMPLES=2000
BOOTSTRAP_SEED=606001
HORIZONS=(90,180,365,730)
TERMINAL_COMPLETED="COMPLETED"
TERMINAL_FAILED="FAILED_OR_WITHDRAWN"
TERMINAL_CENSORED="RIGHT_CENSORED"


@dataclass(frozen=True)
class SurvivalEpisode:
    episode_id:str
    duration_days:int
    terminal_state:str


def _iso_day(value:object,field:str)->date:
    if not isinstance(value,str) or not value:
        raise AlphaContractError(f"{field} must be ISO date")
    try:
        parsed=date.fromisoformat(value)
    except ValueError as exc:
        raise AlphaContractError(f"{field} must be ISO date") from exc
    return parsed


def episode_from_dates(
    *,
    episode_id:str,
    entry_date:str,
    terminal_state:str,
    terminal_date:str|None,
    observation_cutoff:str,
)->SurvivalEpisode:
    if not episode_id:
        raise AlphaContractError("HG006 episode_id is required")
    entry=_iso_day(entry_date,"entry_date")
    cutoff=_iso_day(observation_cutoff,"observation_cutoff")
    if entry>cutoff:
        raise AlphaContractError("HG006 entry is after observation cutoff")
    if terminal_state not in {
        TERMINAL_COMPLETED,TERMINAL_FAILED,TERMINAL_CENSORED
    }:
        raise AlphaContractError("HG006 invalid terminal state")

    if terminal_state==TERMINAL_CENSORED:
        if terminal_date is not None:
            raise AlphaContractError("HG006 censored episode must not carry terminal date")
        end=cutoff
    else:
        if terminal_date is None:
            raise AlphaContractError("HG006 terminal episode requires terminal date")
        end=_iso_day(terminal_date,"terminal_date")
        if end<entry or end>cutoff:
            raise AlphaContractError("HG006 terminal date outside risk interval")

    return SurvivalEpisode(
        episode_id=episode_id,
        duration_days=(end-entry).days,
        terminal_state=terminal_state,
    )


def _aj_points(
    episodes:list[SurvivalEpisode],
    *,
    horizons:tuple[int,...]=HORIZONS,
)->dict[int,dict[str,float]]:
    if not episodes:
        raise AlphaContractError("HG006 Aalen-Johansen requires episodes")
    if any(row.duration_days<0 for row in episodes):
        raise AlphaContractError("HG006 negative episode duration")

    times=sorted({row.duration_days for row in episodes})
    survival=1.0
    cif_completed=0.0
    cif_failed=0.0
    snapshots:dict[int,dict[str,float]]={}
    next_horizons=sorted(set(horizons))
    h_index=0

    for t in times:
        while h_index<len(next_horizons) and next_horizons[h_index]<t:
            h=next_horizons[h_index]
            snapshots[h]={
                "completion_cif":cif_completed,
                "failure_cif":cif_failed,
                "event_free_survival":survival,
            }
            h_index+=1

        n=sum(row.duration_days>=t for row in episodes)
        if n<=0:
            raise AlphaContractError("HG006 empty risk set")
        d_completed=sum(
            row.duration_days==t and row.terminal_state==TERMINAL_COMPLETED
            for row in episodes
        )
        d_failed=sum(
            row.duration_days==t and row.terminal_state==TERMINAL_FAILED
            for row in episodes
        )
        d_total=d_completed+d_failed
        if d_total:
            before=survival
            cif_completed+=before*d_completed/n
            cif_failed+=before*d_failed/n
            survival*=1.0-d_total/n

        while h_index<len(next_horizons) and next_horizons[h_index]==t:
            h=next_horizons[h_index]
            snapshots[h]={
                "completion_cif":cif_completed,
                "failure_cif":cif_failed,
                "event_free_survival":survival,
            }
            h_index+=1

    while h_index<len(next_horizons):
        h=next_horizons[h_index]
        snapshots[h]={
            "completion_cif":cif_completed,
            "failure_cif":cif_failed,
            "event_free_survival":survival,
        }
        h_index+=1
    return snapshots


def wilson_interval(successes:int,total:int,z:float=1.959963984540054)->tuple[float,float]:
    if total<=0 or successes<0 or successes>total:
        raise AlphaContractError("HG006 invalid Wilson counts")
    p=successes/total
    z2=z*z
    denominator=1.0+z2/total
    centre=(p+z2/(2.0*total))/denominator
    half=z*math.sqrt((p*(1-p)+z2/(4.0*total))/total)/denominator
    return max(0.0,centre-half),min(1.0,centre+half)


def estimate_competing_risk_base_rate(
    episodes:list[SurvivalEpisode],
    *,
    horizons:tuple[int,...]=HORIZONS,
    bootstrap_resamples:int=BOOTSTRAP_RESAMPLES,
    bootstrap_seed:int=BOOTSTRAP_SEED,
)->dict[str,Any]:
    if len(episodes)<1:
        raise AlphaContractError("HG006 estimator requires episodes")
    if len({row.episode_id for row in episodes})!=len(episodes):
        raise AlphaContractError("HG006 episode IDs must be unique")
    if bootstrap_resamples<1:
        raise AlphaContractError("HG006 bootstrap_resamples must be positive")

    completed=sum(row.terminal_state==TERMINAL_COMPLETED for row in episodes)
    failed=sum(row.terminal_state==TERMINAL_FAILED for row in episodes)
    censored=sum(row.terminal_state==TERMINAL_CENSORED for row in episodes)
    resolved=completed+failed

    resolved_fraction=None
    resolved_interval=None
    if resolved:
        resolved_fraction=completed/resolved
        lo,hi=wilson_interval(completed,resolved)
        resolved_interval={"lower":lo,"upper":hi}

    point=_aj_points(episodes,horizons=horizons)
    rng=np.random.default_rng(bootstrap_seed)
    samples={
        h:{"completion":[],"failure":[]}
        for h in sorted(set(horizons))
    }
    n=len(episodes)
    for _ in range(bootstrap_resamples):
        indices=rng.integers(0,n,size=n)
        boot=[
            SurvivalEpisode(
                episode_id=f"bootstrap-{i}-{position}",
                duration_days=episodes[int(i)].duration_days,
                terminal_state=episodes[int(i)].terminal_state,
            )
            for position,i in enumerate(indices)
        ]
        values=_aj_points(boot,horizons=horizons)
        for h in samples:
            samples[h]["completion"].append(values[h]["completion_cif"])
            samples[h]["failure"].append(values[h]["failure_cif"])

    horizons_out={}
    for h in sorted(set(horizons)):
        completion=np.asarray(samples[h]["completion"],dtype=float)
        failure=np.asarray(samples[h]["failure"],dtype=float)
        horizons_out[str(h)]={
            "completion_cif":point[h]["completion_cif"],
            "completion_ci95":{
                "lower":float(np.quantile(completion,0.025)),
                "upper":float(np.quantile(completion,0.975)),
            },
            "failure_cif":point[h]["failure_cif"],
            "failure_ci95":{
                "lower":float(np.quantile(failure,0.025)),
                "upper":float(np.quantile(failure,0.975)),
            },
            "event_free_survival":point[h]["event_free_survival"],
        }

    return {
        "support_count":n,
        "completed_count":completed,
        "failed_count":failed,
        "right_censored_count":censored,
        "resolved_count":resolved,
        "resolved_completion_fraction":resolved_fraction,
        "resolved_completion_wilson95":resolved_interval,
        "aalen_johansen":horizons_out,
        "bootstrap":{
            "resamples":bootstrap_resamples,
            "seed":bootstrap_seed,
            "method":"EPISODE_LEVEL_NONPARAMETRIC_PERCENTILE",
        },
    }


def publication_gate(
    *,
    support_count:int,
    terminal_count:int,
)->str:
    if support_count<30 or terminal_count<10:
        return "INSUFFICIENT_HISTORICAL_SUPPORT"
    return "PUBLISHABLE_HISTORICAL_BASE_RATE"
