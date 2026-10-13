from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from marketlab.hg008_event_forecast import (
    _digest,
    build_first_seen_baselines,
    freeze_new_event_forecast,
    load_baseline_sources,
)
from marketlab.hg008_event_score import (
    score_matured_event,
    summarize_prospective_scores,
)


def _source() -> tuple[dict, dict, dict]:
    return load_baseline_sources(Path("."))


def _base() -> dict:
    d004,p001,source=_source()
    return build_first_seen_baselines(d004,p001,source)


def _raw() -> bytes:
    return b"%PDF-1.7\n" + b"this is a synthetic event with test-only data" * 15 + b"\n%%EOF\n"


def _new_event(*, stage: str="BOARD_APPROVED",track:str="issuance_completion",
               family:str="PREFERENTIAL_WARRANT",horizon:int=90) -> dict:
    raw=_raw()
    return {
        "symbol":"NEWRESEARCH",
        "isin":"INE123A01010",
        "issuer_episode_id":"TEST-EXCHANGE-EPISODE-20261020",
        "family":family,"track":track,"stage":stage,"horizon_days":horizon,
        "source_url":"https://nsearchives.nseindia.com/corporate/EXAMPLE_20261020.pdf",
        "original_notice_sha256":hashlib.sha256(raw).hexdigest(),
        "independent_stage_semantic_review_id":"REVIEW-SOURCE-01",
        "first_stage_public_utc":"2026-10-20T13:00:00Z",
        "completion_already_observed_at_forecast":False,
        "company_in_original_survivor_cases":False,
    }


def _forecast() -> dict:
    return freeze_new_event_forecast(
        _base(),event=_new_event(),
        original_notice_bytes=_raw(),
        forecast_at_utc="2026-10-20T14:00:00Z",
    )


def test_frozen_333_episode_original_source_baselines_are_exact() -> None:
    d004,p001,source=_source()
    board=build_first_seen_baselines(d004,p001,source)
    assert board["stage_baseline_count"]==5
    assert board["historical_fitted_sample_is_not_out_of_sample_validation"] is True
    assert board["existing_case_current_probability_count"]==0
    assert len(board["existing_company_survivor_abstentions"])==6
    assert {x["symbol"] for x in board["existing_company_survivor_abstentions"]}=={
        "ANANTRAJ","DEVX","INOXGREEN","SAMBHV"
    }
    assert all(x["conditional_current_probability"] is None
               for x in board["existing_company_survivor_abstentions"])
    forecasts={(x["family"],x["track"],x["stage"],x["horizon_days"]):x
               for x in board["stage_baselines"]}
    assert forecasts[("PREFERENTIAL_WARRANT","issuance_completion","BOARD_APPROVED",90)]["probability"]==pytest.approx(0.7066176470588235)
    assert forecasts[("PREFERENTIAL_WARRANT","full_economic_exercise","BOARD_APPROVED",90)]["probability"]==pytest.approx(0.3088235294117647)
    assert forecasts[("PREFERENTIAL_WARRANT","full_economic_exercise","ALLOTMENT_COMPLETED",90)]["probability"]==pytest.approx(0.5913978494623656)
    assert forecasts[("SCHEME_REORGANISATION","transaction_completion","REGULATORY_OR_COURT_APPROVED",90)]["probability"]==pytest.approx(0.24297984279918863)
    assert forecasts[("SCHEME_REORGANISATION","transaction_completion","REGULATORY_OR_COURT_APPROVED",180)]["probability"]==pytest.approx(0.25626089818867653)
    assert all(not x["existing_months_old_survivor_probability_allowed"]
               for x in board["stage_baselines"])
    assert board["live_capital_allowed"] is False


def test_future_stage_is_mechanical_forecast_with_no_stock_return() -> None:
    result=_forecast()
    assert result["probability"]==pytest.approx(0.7066176470588235)
    assert result["historical_interval_95_lower"]==pytest.approx(0.5914976335361731)
    assert result["historical_interval_95_upper"]==pytest.approx(0.8112745098039216)
    assert result["resolution_deadline_utc"]=="2027-01-18T13:00:00Z"
    assert result["forecast_kind"]=="MECHANICAL_FIRST_SEEN_HISTORICAL_BASELINE_NOT_COMPANY_CALIBRATED"
    assert result["outcome_known_or_scored"] is False
    assert result["prospective_git_commit_before_outcome_verified"] is False
    assert result["stock_price_return_forecast"] is None
    assert result["live_capital_allowed"] is False


def test_current_hg006_survivor_and_backdated_source_not_eligible() -> None:
    for mutate in (
        {"first_stage_public_utc":"2026-10-13T12:00:00Z"},
        {"first_stage_public_utc":"2026-10-17T10:00:00Z"},
        {"completion_already_observed_at_forecast":True},
        {"company_in_original_survivor_cases":True},
        {"source_url":"https://nsearchives.nseindia.com.evil.invalid/f.pdf"},
        {"original_notice_sha256":"0"*64},
        {"family":"UNREGISTERED_FAMILY"},
        {"stage":"COMPLETED_OLD_STAGE"},
        {"horizon_days":45},
    ):
        event=_new_event()
        event.update(mutate)
        with pytest.raises(ValueError):
            freeze_new_event_forecast(
                _base(),event=event,original_notice_bytes=_raw(),
                forecast_at_utc="2026-10-20T14:00:00Z",
            )
    with pytest.raises(ValueError, match="outside first-seen chronology"):
        freeze_new_event_forecast(
            _base(),event=_new_event(),original_notice_bytes=_raw(),
            forecast_at_utc="2026-10-21T15:00:00Z",
        )


def test_exact_historical_baseline_source_mutations_are_detected(tmp_path:Path) -> None:
    from marketlab.hg008_event_forecast import D004_PATH,P001_PATH
    for path in (D004_PATH,P001_PATH):
        dest=tmp_path/path
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(path.read_bytes())
    load_baseline_sources(tmp_path)
    changed=tmp_path/D004_PATH
    changed.write_bytes(changed.read_bytes()+b" ")
    with pytest.raises(ValueError,match="original Git blob changed"):
        load_baseline_sources(tmp_path)


def _outcome(y:int) -> dict:
    base={
        "issuer_episode_id":"TEST-EXCHANGE-EPISODE-20261020",
        "state":"COMPLETED_BY_DEADLINE" if y else "NO_COMPLETION_BY_DEADLINE",
        "prospective_git_anchor_independently_verified":True,
        "independent_original_source_review_approved":True,
        "terminal_evidence_sha256":hashlib.sha256(b"source original result").hexdigest(),
        "terminal_evidence_url":"https://nsearchives.nseindia.com/corporate/TEST_RESOLUTION.pdf",
        "terminal_review_receipt_id":"HUMAN-INDEPENDENT-PDF-REVIEW-01",
    }
    if y:
        base["completion_first_public_utc"]="2026-12-01T12:00:00Z"
    else:
        base.update(
            official_complete_interval_source_coverage_approved=True,
            coverage_start_utc="2026-10-20T12:00:00Z",
            coverage_end_utc="2027-01-19T12:00:00Z",
            terminal_event_omission_reviewed=True,
        )
    return base


def test_matured_forecasts_are_scored_only_with_independent_outcome_evidence() -> None:
    forecast=_forecast()
    result=score_matured_event(
        forecast,_outcome(1),evaluated_at_utc="2027-01-20T12:00:00Z"
    )
    assert result["event_label"]==1
    assert result["brier_score"]==pytest.approx((forecast["probability"]-1)**2)
    assert result["noninformative_half_baseline_brier"]==0.25
    result0=score_matured_event(
        forecast,_outcome(0),evaluated_at_utc="2027-01-20T12:00:00Z"
    )
    assert result0["event_label"]==0
    assert result0["brier_score"]==pytest.approx(forecast["probability"]**2)
    assert result0["live_capital_allowed"] is False
    with pytest.raises(ValueError,match="not mature"):
        score_matured_event(
            forecast,_outcome(1),evaluated_at_utc="2026-12-25T12:00:00Z"
        )


def test_event_absence_cannot_be_inferred_from_missing_source() -> None:
    forecast=_forecast()
    y0=_outcome(0)
    y0["official_complete_interval_source_coverage_approved"]=False
    with pytest.raises(ValueError,match="absence is not proof"):
        score_matured_event(forecast,y0,evaluated_at_utc="2027-01-20T12:00:00Z")
    y0=_outcome(0)
    y0["coverage_end_utc"]="2027-01-10T00:00:00Z"
    with pytest.raises(ValueError,match="not independently complete"):
        score_matured_event(forecast,y0,evaluated_at_utc="2027-01-20T12:00:00Z")
    with pytest.raises(ValueError,match="independent original"):
        y1=_outcome(1)
        y1["independent_original_source_review_approved"]=False
        score_matured_event(forecast,y1,evaluated_at_utc="2027-01-20T12:00:00Z")


def test_right_censored_event_does_not_count_as_failure() -> None:
    f=_forecast()
    y={"issuer_episode_id":f["issuer_episode_id"],
       "state":"RIGHT_CENSORED_OR_UNVERIFIED",
       "prospective_git_anchor_independently_verified":True}
    result=score_matured_event(f,y,evaluated_at_utc="2027-01-20T12:00:00Z")
    assert result["event_label"] is None and result["brier_score"] is None
    assert summarize_prospective_scores([result])["matured_verified_scored_observation_count"]==0


def test_no_calibration_claim_on_small_or_duplicated_samples() -> None:
    f=_forecast()
    first=score_matured_event(
        f,_outcome(1),evaluated_at_utc="2027-01-20T12:00:00Z"
    )
    result=summarize_prospective_scores([first])
    assert result["groups"][0]["sample_readiness"]=="INSUFFICIENT_INDEPENDENT_MATURED_EVENTS"
    assert result["groups"][0]["accuracy_or_calibration_credibly_established"] is False
    assert result["groups"][0]["mean_forecast_brier"]==pytest.approx((f["probability"]-1)**2)
    with pytest.raises(ValueError,match="duplicate outcome"):
        summarize_prospective_scores([first,deepcopy(first)])


def test_no_prospective_forecast_identity_edits_after_recording() -> None:
    f=_forecast()
    modified=deepcopy(f)
    modified["probability"]=0.99
    with pytest.raises(ValueError,match="modified after publication"):
        score_matured_event(modified,_outcome(1),evaluated_at_utc="2027-01-20T12:00:00Z")
