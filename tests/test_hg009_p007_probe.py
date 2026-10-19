"""Synthetic NSE source probes demonstrate missing coverage cannot become alpha."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p007_actions import load_original_hg009_sources
from marketlab.hg009_p007_probe import (
    H5_EXIT,
    build_p007_probe,
    replay_all_probes,
    validate_p007_probe,
)

ROOT = Path(__file__).resolve().parents[1]


def _clock(when: str):
    value = datetime.fromisoformat(when)
    return lambda: value


def _make(
    source: bytes | None,
    *,
    when: str,
    fail: bool = False,
):
    if fail:
        def fetcher():
            raise RuntimeError("test-only unavailable NSE endpoint")
    else:
        def fetcher():
            return {"original": True}, source
    return build_p007_probe(
        repo_root=ROOT, attempt_id="test-capture-001",
        fetcher=fetcher, clock=_clock(when),
    )


def test_source_before_h5_end_is_not_full_return_clearance():
    raw = json.dumps({"data": []}).encode()
    attempt, data = _make(
        raw, when="2026-10-19T12:00:00+00:00",
    )
    assert data == raw
    assert attempt["source_receipt"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert attempt["source_receipt"]["status"] == "OK"
    assert attempt["screen"]["source_state"] == (
        "BLOCKED_SOURCE_CAPTURE_BEFORE_INTERVAL_END"
    )
    assert attempt["original_300_identity_count"] == 300
    assert attempt["original_h5_exit"] == H5_EXIT
    assert len(attempt["screen"]["company_hazards"]) == 300
    assert attempt["issuer_dividends_total_return_cleared_count"] == 0
    assert attempt["market_price_return_promoted_to_economic_return"] is False
    validate_p007_probe(attempt, repo_root=ROOT, source_raw=data)


def test_empty_original_data_after_h5_still_cannot_certify_no_actions():
    raw = json.dumps({"data": []}).encode()
    attempt, data = _make(
        raw, when="2026-10-23T13:00:00+00:00",
    )
    assert attempt["screen"]["source_state"] == (
        "SOURCE_SCREENED_COVERAGE_NOT_CERTIFIED"
    )
    assert attempt["screen"]["observed_hazard_count"] == 0
    assert all(
        row["economic_total_return_eligible"] is False
        for row in attempt["screen"]["company_hazards"]
    )
    validate_p007_probe(attempt, repo_root=ROOT, source_raw=data)


def test_original_nse_dividend_hazard_blocks_specific_frozen_issuer():
    _original, selected, _controls = load_original_hg009_sources(ROOT)
    first = selected["selected"][0]
    raw = json.dumps({
        "data": [{
            "symbol": first["symbol"],
            "isin": first["isin"],
            "subject": "Interim Dividend INR 5 per equity share",
            "exDate": "16-Oct-2026",
        }],
    }).encode()
    probe, data = _make(raw, when="2026-10-23T13:00:00+00:00")
    assert probe["screen"]["observed_hazard_count"] == 1
    company = next(
        row for row in probe["screen"]["company_hazards"]
        if row["symbol"] == first["symbol"]
    )
    assert company["action_screen_state"] == "BLOCKED_ACTION_OR_IDENTITY_HAZARD"
    assert company["economic_total_return_eligible"] is False
    validate_p007_probe(probe, repo_root=ROOT, source_raw=data)


def test_source_fetch_failure_preserves_reason_without_inventing_zero_events():
    attempt, data = _make(
        None, fail=True, when="2026-10-19T12:00:00+00:00",
    )
    assert data is None
    assert attempt["source_receipt"]["status"] == "FETCH_FAILED"
    assert attempt["source_receipt"]["error"] == "RuntimeError"
    assert attempt["screen"]["source_state"] == "BLOCKED_FETCH_FAILED"
    assert attempt["source_raw_repo_path"] is None
    assert attempt["source_bytes"] is None
    validate_p007_probe(attempt, repo_root=ROOT, source_raw=None)


def test_resigned_source_sha_and_response_replay_do_not_rescue_economic_return():
    raw = json.dumps({"data": []}).encode()
    attempt, data = _make(raw, when="2026-10-23T13:00:00+00:00")
    tampered = copy.deepcopy(attempt)
    tampered["source_receipt"]["raw_sha256"] = "a" * 64
    tampered.pop("envelope_sha256")
    tampered["envelope_sha256"] = digest(tampered)
    with pytest.raises(AlphaContractError, match="original NSE source bytes modified"):
        validate_p007_probe(tampered, repo_root=ROOT, source_raw=data)
    damaged = copy.deepcopy(attempt)
    damaged["screen"]["company_hazards"][0]["economic_total_return_eligible"] = True
    damaged.pop("envelope_sha256")
    damaged["envelope_sha256"] = digest(damaged)
    with pytest.raises(AlphaContractError, match="source screen cannot replay"):
        validate_p007_probe(damaged, repo_root=ROOT, source_raw=data)


def test_probe_ids_dates_and_clocks_must_remain_original():
    raw = json.dumps({"records": []}).encode()
    with pytest.raises(AlphaContractError, match="capture window"):
        build_p007_probe(
            repo_root=ROOT, attempt_id="valid-1",
            fetcher=lambda: ({"data": []}, raw),
            clock=_clock("2026-10-14T14:00:00Z"),
        )
    with pytest.raises(AlphaContractError, match="attempt ID"):
        build_p007_probe(
            repo_root=ROOT, attempt_id="../bad",
            fetcher=lambda: ({"data": []}, raw),
            clock=_clock("2026-10-19T12:00:00Z"),
        )
    initial = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    ticks = iter([initial, initial - timedelta(minutes=2)])
    with pytest.raises(AlphaContractError, match="predates original source"):
        build_p007_probe(
            repo_root=ROOT, attempt_id="clock-test",
            fetcher=lambda: ({"data": []}, raw),
            clock=lambda: next(ticks),
        )


def test_standalone_verify_command_checks_future_archive_without_network():
    run = subprocess.run(
        [sys.executable, "scripts/probe_hg009_p007_actions.py", "--verify"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    result = json.loads(run.stdout)
    assert result["live_capital_allowed"] is False
    assert result["original_300_identity_count"] == 300
    assert result["verified_attempt_count"] >= 0
    assert result["economic_return_clearance_count"] == 0
    assert replay_all_probes(ROOT)["verified_attempt_count"] >= 0
