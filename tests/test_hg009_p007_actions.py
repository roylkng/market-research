"""P007 disallows assuming all 300 companies have clean corporate actions."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p007_actions import (
    build_action_hazard_audit,
    load_original_hg009_sources,
    validate_action_hazard_audit,
)

ROOT = Path(__file__).resolve().parents[1]
OPEN = "2026-10-15"
EXIT = "2026-10-22"
PREPARED = "2026-10-22T12:15:00Z"
CAPTURED = "2026-10-22T12:00:00Z"


def _input():
    source, selected, controls = load_original_hg009_sources(ROOT)
    return {"original": source, "selected": selected, "controls": controls}


def _run(raw: bytes | None, receipt: dict | None) -> dict:
    return build_action_hazard_audit(
        **_input(),
        start_session=OPEN, end_session=EXIT,
        original_action_raw=raw,
        action_receipt=receipt,
        prepared_at_utc=PREPARED,
    )


def _receipt(raw: bytes) -> dict:
    return {
        "url": "https://www.nseindia.com/api/corporates-corporateActions",
        "captured_at_utc": CAPTURED,
        "status": "OK",
        "http_status": 200,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }


def test_three_source_arms_still_retain_300_unpriced_unadjusted_companies():
    output = _run(None, None)
    assert output["original_declared_identity_count"] == 300
    assert output["original_fixed_arm_counts"] == {
        "SELECTED": 100, "ONE_LANE": 100, "ZERO_LANE": 100,
    }
    assert len(output["company_hazards"]) == 300
    assert output["source_state"] == "NO_ORIGINAL_SOURCE"
    assert output["exhaustive_action_coverage_certified"] is False
    assert output["fully_action_adjusted_investable_equity_returns_count"] == 0
    assert output["empty_action_API_response_proves_no_event"] is False
    assert output["live_capital_allowed"] is False
    assert all(
        row["economic_total_return_eligible"] is False
        and row["full_interval_coverage_verified"] is False
        for row in output["company_hazards"]
    )
    validate_action_hazard_audit(output)


def test_empty_official_action_API_response_is_not_issuer_clearance():
    data = json.dumps({"data": []}).encode()
    output = _run(data, _receipt(data))
    assert output["source_state"] == "SOURCE_SCREENED_COVERAGE_NOT_CERTIFIED"
    assert output["observed_hazard_count"] == 0
    assert output["fully_action_adjusted_investable_equity_returns_count"] == 0
    assert all(
        row["action_screen_state"]
        == "BLOCKED_MISSING_OR_UNVERIFIED_COMPLETE_SOURCE"
        for row in output["company_hazards"]
    )


def test_known_dividend_exdate_detected_without_inventing_total_return():
    controls = _input()["selected"]
    selected = controls["selected"][0]
    event = {
        "data": [{
            "symbol": selected["symbol"],
            "isin": selected["isin"],
            "series": "EQ",
            "subject": "Final dividend Rs 5",
            "exDate": "16-Oct-2026",
        }]
    }
    raw = json.dumps(event).encode()
    output = _run(raw, _receipt(raw))
    matched = next(
        x for x in output["company_hazards"]
        if x["symbol"] == selected["symbol"]
    )
    assert output["observed_hazard_count"] == 1
    assert matched["action_screen_state"] == "BLOCKED_ACTION_OR_IDENTITY_HAZARD"
    assert matched["original_action_source_hazards"][0][
        "classification"
    ] == "CASH_DIVIDEND_ACTION"
    assert matched["economic_total_return_eligible"] is False


def test_hash_and_time_tamper_fails_closed():
    raw = json.dumps({"records": []}).encode()
    receipt = _receipt(raw)
    receipt["raw_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="bytes SHA-256"):
        _run(raw, receipt)

    receipt = _receipt(raw)
    receipt["captured_at_utc"] = "2026-10-22T09:00:00+00:00"
    output = _run(raw, receipt)
    assert output["source_state"] == (
        "BLOCKED_SOURCE_CAPTURE_BEFORE_INTERVAL_END"
    )

    output = _run(None, None)
    output["company_hazards"][0]["economic_total_return_eligible"] = True
    with pytest.raises(AlphaContractError, match="packet hash changed"):
        validate_action_hazard_audit(output)


def test_cohort_or_calendar_change_cannot_be_amended_after_future_returns():
    kwargs = _input()
    source = copy.deepcopy(kwargs["selected"])
    source["selected"][0]["symbol"] = "FUTURE_WINNER"
    with pytest.raises(AlphaContractError, match="cohort seal SHA mismatch"):
        build_action_hazard_audit(
            **{**kwargs, "selected": source},
            start_session=OPEN, end_session=EXIT,
            original_action_raw=None, action_receipt=None,
            prepared_at_utc=PREPARED,
        )
    with pytest.raises(AlphaContractError, match="original frozen action calendar"):
        build_action_hazard_audit(
            **kwargs, start_session=OPEN, end_session="2027-01-10",
            original_action_raw=None, action_receipt=None,
            prepared_at_utc=PREPARED,
        )


def test_sha_reproduction_is_strict_with_nulls():
    data = _run(None, None)
    assert data["packet_sha256"] == digest({
        k: v for k, v in data.items() if k != "packet_sha256"
    })


def test_resigned_hazard_packet_still_cannot_promote_one_issuer():
    report = _run(None, None)
    row = report["company_hazards"][0]
    row["economic_total_return_eligible"] = True
    unsigned = {key: value for key, value in report.items() if key != "packet_sha256"}
    report["packet_sha256"] = digest(unsigned)
    with pytest.raises(AlphaContractError, match="issuer not cleared"):
        validate_action_hazard_audit(report)

    report = _run(None, None)
    report["company_hazards"][0]["isin"] = "INE000000000"
    unsigned = {key: value for key, value in report.items() if key != "packet_sha256"}
    report["packet_sha256"] = digest(unsigned)
    # A resigner cannot assert that an altered ISIN is the original issuer.
    # The CLI's full-source rebuild additionally compares all identities.
    original, selected, controls = load_original_hg009_sources(ROOT)
    replay = build_action_hazard_audit(
        original=original, selected=selected, controls=controls,
        start_session=OPEN, end_session=EXIT,
        original_action_raw=None, action_receipt=None,
        prepared_at_utc=PREPARED,
    )
    assert report != replay
