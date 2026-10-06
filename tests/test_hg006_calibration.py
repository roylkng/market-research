from __future__ import annotations

import pytest

import marketlab.hg006_calibration as h
from marketlab.alpha import AlphaContractError


def _census(n=180):
    rows=[]
    for family in h.FAMILIES:
        for i in range(n):
            cid=f"{family}-{i:03d}"
            rows.append({
                "chronology_id":cid,
                "symbol":f"S{i:03d}",
                "family":family,
                "first_observed_at_utc":"2024-01-01T00:00:00Z",
                "last_observed_at_utc":"2024-02-01T00:00:00Z",
                "first_initiation_window_at_utc":"2024-01-01T00:00:00Z",
                "event_count":2,
                "initiation_window_event_count":1,
                "followup_event_count":1,
                "has_approved_attachment":i%2==0,
                "announcement_ids":[f"E-{family}-{i}-1",f"E-{family}-{i}-2"],
            })
    return {
        "census_id":"HG006-D001-v1",
        "census_sha256":h.EXPECTED_D001_SHA,
        "chronologies":rows,
        "completion_probabilities_assigned":False,
        "expected_returns_calculated":False,
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }


def test_selection_is_exact_balanced_and_deterministic():
    a=h.build_calibration_cohort(_census())
    b=h.build_calibration_cohort(_census())
    assert a["selected_chronology_count"]==300
    assert a["selected_chronology_counts_by_family"]=={
        "PREFERENTIAL_WARRANT":150,
        "SCHEME_REORGANISATION":150,
    }
    assert a["rows"]==b["rows"]
    assert a["selection_sha256"]==b["selection_sha256"]


def test_selection_does_not_require_attachment():
    result=h.build_calibration_cohort(_census())
    assert any(not row["has_approved_attachment"] for row in result["rows"])


def test_family_below_frozen_support_fails():
    with pytest.raises(AlphaContractError,match="has only"):
        h.build_calibration_cohort(_census(n=149))


def test_selection_key_is_stable():
    assert h.selection_key("abc")==h.selection_key("abc")
    assert h.selection_key("abc")!=h.selection_key("def")
