"""Synthetic exchange clocks only; no novel HG008 event or market prediction."""

from __future__ import annotations

import gzip
import hashlib
import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from marketlab.hg008_intraday_discovery import (
    build_intraday_discovery,
    expected_window,
    validate_discovery_packet,
)
from marketlab.nse import NSEAcquisitionError
from scripts import capture_hg008_intraday as collector

OBSERVED = "2026-10-14T10:00:00Z"


def _announcements() -> dict:
    return {
        "data": [
            {
                "symbol": "FIRST",
                "seq_id": "100",
                "exchdisstime": "14-Oct-2026 12:00:00",
                "desc": "Preferential allotment of warrants",
                "attchmntText": "Issuer update; unknown whether this is a first stage",
                "attchmntFile": "https://nsearchives.nseindia.com/corporate/first.pdf",
            },
            {
                "symbol": "LATE",
                "seq_id": "101",
                "exchdisstime": "14-Oct-2026 06:00:00",
                "desc": "Scheme of Arrangement",
                "attchmntText": "Original business agreement not verified",
                "attchmntFile": "https://nsearchives.nseindia.com/corporate/late.pdf",
            },
            {
                "symbol": "OLD",
                "seq_id": "102",
                "exchdisstime": "13-Oct-2026 18:00:00",
                "desc": "Preferential issue",
                "attchmntText": "",
                "attchmntFile": "https://nsearchives.nseindia.com/corporate/old.pdf",
            },
            {
                "symbol": "FUTURE",
                "seq_id": "103",
                "exchdisstime": "14-Oct-2026 18:00:00",
                "desc": "Allotment of Warrants",
                "attchmntText": "",
                "attchmntFile": "https://example.invalid/future.pdf",
            },
            {
                "symbol": "NONCAT",
                "seq_id": "104",
                "exchdisstime": "14-Oct-2026 12:00:00",
                "desc": "General Update",
                "attchmntText": "ordinary meeting results",
                "attchmntFile": "",
            },
        ]
    }


def _build(source: dict | None = None) -> dict:
    payload = _announcements() if source is None else source
    raw = json.dumps(payload, sort_keys=True).encode()
    return build_intraday_discovery(
        source=payload,
        original_raw=raw,
        request_start=date(2026, 10, 13),
        request_end=date(2026, 10, 14),
        observed_at_utc=OBSERVED,
    )


def test_source_clock_is_not_a_first_seen_stage_prediction() -> None:
    packet = _build()
    validate_discovery_packet(packet)
    assert packet["full_source_event_count"] == 5
    assert packet["category_candidate_count"] == 4
    by_symbol = {x["symbol"]: x for x in packet["candidates"]}
    assert by_symbol["FIRST"]["source_clock_state"] == (
        "POSSIBLE_STAGE_REVIEW_WITHIN_8H_NOT_VERIFIED"
    )
    assert by_symbol["LATE"]["source_clock_state"] == (
        "SOURCE_CAPTURE_AFTER_8H_NO_FIRST_SEEN_FORECAST"
    )
    assert by_symbol["OLD"]["source_clock_state"] == "BEFORE_PROSPECTIVE_START"
    assert by_symbol["FUTURE"]["source_clock_state"] == (
        "EXCHANGE_TIMESTAMP_AFTER_OBSERVATION_BLOCKED"
    )
    assert by_symbol["FUTURE"]["source_original_pdf_url_if_approved"] is None
    assert packet["hg008_valid_forecasts_frozen"] == 0
    assert packet["first_seen_stage_independently_certified_count"] == 0
    assert packet["portfolio_eligibility_allowed"] is False
    assert packet["live_capital_allowed"] is False
    assert all(
        row["candidate_eligible_for_hg008_forecast"] is False
        and row["source_original_pdf_sha256"] is None
        and row["stage_semantic_review_approved"] is False
        for row in packet["candidates"]
    )


def test_frozen_future_start_and_request_date_cannot_be_backdated() -> None:
    with pytest.raises(ValueError, match="outside frozen"):
        expected_window("2026-10-13T23:59:59Z")
    assert expected_window(OBSERVED) == (
        date(2026, 10, 13), date(2026, 10, 14)
    )
    raw = json.dumps(_announcements()).encode()
    with pytest.raises(ValueError, match="query date window"):
        build_intraday_discovery(
            source=_announcements(), original_raw=raw,
            request_start=date(2026, 10, 14), request_end=date(2026, 10, 14),
            observed_at_utc=OBSERVED,
        )


def test_forged_or_malformed_official_original_json_is_blocked() -> None:
    good = _announcements()
    raw = json.dumps(good).encode()
    fake = deepcopy(good)
    fake["data"][0]["desc"] = "different disclosed stage"
    with pytest.raises(ValueError, match="differs from exact"):
        build_intraday_discovery(
            source=fake, original_raw=raw,
            request_start=date(2026, 10, 13), request_end=date(2026, 10, 14),
            observed_at_utc=OBSERVED,
        )
    with pytest.raises(TypeError, match="explicit announcement rows"):
        _build({"error": "HTTP BLOCKED"})
    with pytest.raises(ValueError, match="malformed or unbounded"):
        _build({"data": [None]})
    with pytest.raises(ValueError, match="altered"):
        packet = _build()
        packet["candidates"][0]["candidate_eligible_for_hg008_forecast"] = True
        validate_discovery_packet(packet)


def test_capture_retains_raw_bytes_and_no_fake_forecast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _announcements()
    raw = json.dumps(payload, sort_keys=True).encode()
    calls = []

    def acquire(**kwargs):
        calls.append(kwargs)
        return payload, raw

    monkeypatch.setattr(collector, "_now", lambda: OBSERVED)
    record = collector.capture_once(
        observed_at_utc=OBSERVED, acquire=acquire, out_dir=tmp_path
    )
    assert calls == [{"from_date": "13-10-2026", "to_date": "14-10-2026"}]
    assert record["state"] == "ORIGINAL_NSE_INTRADAY_ANNOUNCEMENTS_CAPTURED_SOURCE_ONLY"
    assert record["candidate_count"] == 4
    assert record["first_seen_forecast_published"] is False
    assert record["live_capital_allowed"] is False
    sha = hashlib.sha256(raw).hexdigest()
    retained = tmp_path / "original" / "sha256" / f"{sha}.json.gz"
    assert gzip.decompress(retained.read_bytes()) == raw
    captured = json.loads((tmp_path / "source-clock.json").read_text())
    validate_discovery_packet(captured)
    assert json.loads((tmp_path / "receipt.json").read_text()) == record


def test_official_network_failure_retains_explicit_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def unavailable(**kwargs):
        raise NSEAcquisitionError("HTTP 403: do not bypass")

    monkeypatch.setattr(collector, "_now", lambda: OBSERVED)
    receipt = collector.capture_once(
        observed_at_utc=OBSERVED,
        acquire=unavailable,
        out_dir=tmp_path,
    )
    assert receipt["state"] == "SOURCE_UNAVAILABLE_OR_SCHEMA_BLOCKED_NO_FORECAST"
    assert "NSEAcquisitionError" in receipt["failure_reason"]
    assert not (tmp_path / "source-clock.json").exists()
    assert not (tmp_path / "original").exists()
    assert receipt["first_seen_forecast_published"] is False



def test_source_schema_failure_still_preserves_exact_original_response(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A malformed NSE schema must be auditable from its original bytes,
    # but never exposed as a valid first-seen announcement or probability.
    payload = {"error": "unrecognized official NSE envelope"}
    raw = json.dumps(payload, sort_keys=True).encode()

    def acquire(**kwargs):
        return payload, raw

    monkeypatch.setattr(collector, "_now", lambda: OBSERVED)
    receipt = collector.capture_once(
        observed_at_utc=OBSERVED, acquire=acquire, out_dir=tmp_path
    )
    assert receipt["state"] == "SOURCE_UNAVAILABLE_OR_SCHEMA_BLOCKED_NO_FORECAST"
    sha = hashlib.sha256(raw).hexdigest()
    assert receipt["original_source_sha256"] == sha
    retained = tmp_path / "original" / "sha256" / f"{sha}.json.gz"
    assert gzip.decompress(retained.read_bytes()) == raw
    assert receipt["packet_sha256"] is None
    assert not (tmp_path / "source-clock.json").exists()
    assert receipt["first_seen_forecast_published"] is False
    assert receipt["live_capital_allowed"] is False
