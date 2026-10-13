"""Outcome-only audit for first-seen HG008 transaction milestone predictions.

Brier scores are admitted ONLY on matured, independently attested source
outcomes. No prices, P&L, probability refitting or issuer investment claims.
No-event is not synonymous with missing announcements or HTTP 403.
"""

from __future__ import annotations

import math
from typing import Any

from marketlab.hg008_event_forecast import FORECAST_ID, _digest, _official_url, _utc

SCORE_ID = "HG008-P001-MATURED-EVENT-BRIER-v1"
OUTCOMES = frozenset({"COMPLETED_BY_DEADLINE","NO_COMPLETION_BY_DEADLINE","RIGHT_CENSORED_OR_UNVERIFIED"})


def score_matured_event(
    forecast:dict[str,Any],
    outcome:dict[str,Any],
    *,
    evaluated_at_utc:str,
) -> dict[str,Any]:
    if forecast.get("forecast_id")!=FORECAST_ID:
        raise ValueError("only first-seen HG008 forecast may be evaluated")
    digest=forecast.get("packet_sha256")
    if not isinstance(digest,str) or digest!=_digest({k:v for k,v in forecast.items() if k!="packet_sha256"}):
        raise ValueError("HG008 forecast modified after publication")
    if (
        forecast.get("outcome_known_or_scored") is not False
        or forecast.get("live_capital_allowed") is not False
        or forecast.get("portfolio_eligibility_allowed") is not False
        or forecast.get("prospective_git_commit_before_outcome_verified") is not False
    ):
        raise ValueError("forecast has unverifiable or elevated prospective status")
    if not isinstance(outcome,dict):
        raise TypeError("outcome evidence must be a dictionary")
    if outcome.get("issuer_episode_id")!=forecast["issuer_episode_id"]:
        raise ValueError("event episode identity differs from frozen forecast")
    asof=_utc(evaluated_at_utc)
    deadline=_utc(forecast["resolution_deadline_utc"])
    forecast_time=_utc(forecast["forecast_frozen_at_utc"])
    if not forecast_time<deadline<=asof:
        raise ValueError("HG008 outcome not mature or prediction was backdated")
    if outcome.get("prospective_git_anchor_independently_verified") is not True:
        raise ValueError("original forecast Git publication chronology not verified")
    state=outcome.get("state")
    if state not in OUTCOMES:
        raise ValueError("invalid scored event outcome state")
    probability=forecast.get("probability")
    if type(probability) not in (float,int) or not math.isfinite(probability) or not 0<=probability<=1:
        raise ValueError("invalid frozen 90/180-day event probability")
    label=None
    reason="SOURCE_EVENT_RIGHT_CENSORED_NOT_SCORABLE"
    if state in ("COMPLETED_BY_DEADLINE","NO_COMPLETION_BY_DEADLINE"):
        if outcome.get("independent_original_source_review_approved") is not True:
            raise ValueError("terminal attestation lacks independent original document review")
        evidence_sha=outcome.get("terminal_evidence_sha256")
        evidence_url=outcome.get("terminal_evidence_url")
        if not isinstance(evidence_sha,str) or len(evidence_sha)!=64 or not all(x in "0123456789abcdef" for x in evidence_sha) or not _official_url(evidence_url):
            raise ValueError("terminal original exchange source SHA and URL required")
        if not isinstance(outcome.get("terminal_review_receipt_id"),str) or not outcome["terminal_review_receipt_id"]:
            raise ValueError("independent terminal review record missing")
        first_seen=_utc(forecast["first_stage_public_utc"])
        if state=="COMPLETED_BY_DEADLINE":
            completed_at=_utc(outcome.get("completion_first_public_utc"))
            if not forecast_time < completed_at<=deadline:
                raise ValueError("completed terminal event observed before prediction or after deadline")
            label=1
        else:
            if outcome.get("official_complete_interval_source_coverage_approved") is not True:
                raise ValueError("absence is not proof without complete interval source coverage")
            covered_from=_utc(outcome.get("coverage_start_utc"))
            covered_until=_utc(outcome.get("coverage_end_utc"))
            if not covered_from <= first_seen or covered_until < deadline or covered_until>asof:
                raise ValueError("negative terminal coverage period not independently complete")
            if outcome.get("terminal_event_omission_reviewed") is not True:
                raise ValueError("negative absence must have independent omission review")
            label=0
        reason="SOURCE_ATTESTED_MATURED_EVENT_BRIER_SCORABLE"
    brier=(probability-label)**2 if label is not None else None
    result={
        "schema_version":1,
        "score_id":SCORE_ID,
        "issuer_episode_id":forecast["issuer_episode_id"],
        "symbol":forecast["symbol"],
        "family":forecast["family"],
        "track":forecast["track"],
        "stage":forecast["stage"],
        "horizon_days":forecast["horizon_days"],
        "forecast_packet_sha256":digest,
        "forecast_probability":probability,
        "evaluated_at_utc":asof.isoformat().replace("+00:00","Z"),
        "outcome_status":state,
        "event_label":label,
        "brier_score":brier,
        "noninformative_half_baseline_brier":(0.5-label)**2 if label is not None else None,
        "score_state":reason,
        "historical_hg006_fitted_source_not_external_validation":True,
        "prospective_sample_calibration_proven":False,
        "score_is_a_stock_return":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    result["packet_sha256"]=_digest(result)
    return result


def summarize_prospective_scores(scored:list[dict[str,Any]]) -> dict[str,Any]:
    """Do not call small correlated event samples calibrated predictions."""
    if not isinstance(scored,list):
        raise TypeError("independent scored list required")
    valid=[]
    seen=set()
    for item in scored:
        if item.get("score_id")!=SCORE_ID or item.get("packet_sha256")!=_digest({k:v for k,v in item.items() if k!="packet_sha256"}):
            raise ValueError("reviewed HG008 score packet tampered")
        if item.get("live_capital_allowed") is not False:
            raise ValueError("research score cannot enable capital")
        if item.get("event_label") not in (None,0,1):
            raise ValueError("invalid event resolution")
        if item.get("event_label") is None:
            continue
        key=(item["issuer_episode_id"],item["family"],item["track"],item["stage"],item["horizon_days"])
        if key in seen:
            raise ValueError("duplicate outcome episode/track would inflate calibration sample")
        seen.add(key)
        valid.append(item)
    grouped={}
    for item in valid:
        k=(item["family"],item["track"],item["stage"],item["horizon_days"])
        grouped.setdefault(k,[]).append(item)
    groups=[]
    for (family,track,stage,horizon),rows in sorted(grouped.items()):
        # Multiple tracks from same corporate episode are correlated.
        independent=len({x["issuer_episode_id"] for x in rows})
        count=len(rows)
        groups.append({
            "family":family,"track":track,"stage":stage,"horizon_days":horizon,
            "verified_matured_observation_count":count,
            "distinct_episode_count":independent,
            "mean_forecast_brier":sum(x["brier_score"] for x in rows)/count,
            "mean_half_baseline_brier":sum(x["noninformative_half_baseline_brier"] for x in rows)/count,
            "accuracy_or_calibration_credibly_established":False,
            "sample_readiness":"READY_FOR_INDEPENDENT_DESCRIPTIVE_CALIBRATION_REVIEW" if independent>=30 else "INSUFFICIENT_INDEPENDENT_MATURED_EVENTS",
        })
    return {
        "schema_version":1,
        "summary_id":"HG008-P001-OUT_OF_SAMPLE_EVENT_SCORECARD-v1",
        "matured_verified_scored_observation_count":len(valid),
        "minimum_independent_matured_episodes_before_review":30,
        "groups":groups,
        "historical_HG006_fit_is_not_validation":True,
        "research_only_no_equity_alpha_claim":True,
        "live_capital_allowed":False,
    }
