from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from marketlab.events import HISTORICAL_RECONSTRUCTION, SourceProvenance, parse_indas_html, sha256_bytes
from marketlab.h002 import PriceReference, build_seasonal_expectation
from marketlab.h002_historical import (
    HistoricalReplayError,
    historical_freeze_at,
    score_h002_historical_replay,
    select_historical_filing_pair,
    validate_historical_replay_rule,
)

FIXTURES = Path("data/fixtures/filings")


def _actual_event():
    raw = (FIXTURES / "ccl_fy27_q1_consolidated_source_derived.html").read_bytes()
    return parse_indas_html(
        raw.decode(),
        source_url="https://nsearchives.nseindia.com/example-ccl.xml",
        raw_sha256=sha256_bytes(raw),
        raw_path="raw/ccl.xml",
        captured_at_utc="2026-09-07T06:00:00Z",
        mode=HISTORICAL_RECONSTRUCTION,
        exchange_published_at_utc="2026-07-27T14:56:14Z",
        discovery_sha256="a" * 64,
        discovery_path="discovery/a.json",
    )


def _baseline_event(actual):
    provenance = SourceProvenance(
        source_url="https://nsearchives.nseindia.com/example-ccl-baseline.xml",
        captured_at_utc="2026-09-07T06:00:00Z",
        raw_sha256="b" * 64,
        raw_path="raw/b.xml",
        content_type="application/xml",
        source_mode="NSE_INTEGRATED_FILING_XBRL",
        exchange_published_at_utc="2025-07-25T12:00:00Z",
    )
    return replace(
        actual,
        economic_event_id="baseline-event",
        version_id="baseline-event-v1",
        reporting_period_end="30-06-2025",
        basic_eps=4.0,
        diluted_eps=4.0,
        provenance=provenance,
    )


def test_historical_replay_rule_hash_is_valid():
    document = yaml.safe_load(Path("registry/h002_historical_replay_rule.yaml").read_text())
    assert validate_historical_replay_rule(document) == document["sha256"]


def test_historical_freeze_matches_live_offset_convention():
    assert historical_freeze_at("2026-06-30") == "2026-06-06T18:29:59Z"
    assert historical_freeze_at("2026-03-31") == "2026-03-07T18:29:59Z"


def test_pair_selection_uses_first_target_and_latest_baseline_available_at_freeze():
    payload = {
        "data": [
            {
                "type": "Integrated Filing- Financials",
                "symbol": "ABC",
                "consolidated": "Consolidated",
                "qe_Date": "30-Jun-2025",
                "broadcast_Date": "25-Jul-2025 10:00:00",
                "xbrl": "https://nsearchives.nseindia.com/baseline-original.xml",
            },
            {
                "type": "Integrated Filing- Financials",
                "symbol": "ABC",
                "consolidated": "Consolidated",
                "qe_Date": "30-Jun-2025",
                "broadcast_Date": "10-May-2026 10:00:00",
                "xbrl": "https://nsearchives.nseindia.com/baseline-pre-freeze-revision.xml",
            },
            {
                "type": "Integrated Filing- Financials",
                "symbol": "ABC",
                "consolidated": "Consolidated",
                "qe_Date": "30-Jun-2025",
                "broadcast_Date": "20-Jun-2026 10:00:00",
                "xbrl": "https://nsearchives.nseindia.com/baseline-post-freeze-revision.xml",
            },
            {
                "type": "Integrated Filing- Financials",
                "symbol": "ABC",
                "consolidated": "Consolidated",
                "qe_Date": "30-Jun-2026",
                "broadcast_Date": "25-Jul-2026 10:00:00",
                "xbrl": "https://nsearchives.nseindia.com/target-first.xml",
            },
            {
                "type": "Integrated Filing- Financials",
                "symbol": "ABC",
                "consolidated": "Consolidated",
                "qe_Date": "30-Jun-2026",
                "broadcast_Date": "27-Jul-2026 10:00:00",
                "xbrl": "https://nsearchives.nseindia.com/target-revision.xml",
            },
        ]
    }
    pair = select_historical_filing_pair(
        payload,
        symbol="ABC",
        target_period_end="2026-06-30",
        baseline_period_end="2025-06-30",
        freeze_at_utc="2026-06-06T18:29:59Z",
    )
    assert pair is not None
    assert pair.accounting_basis == "Consolidated"
    assert pair.target.source_url.endswith("target-first.xml")
    assert pair.baseline.source_url.endswith("baseline-pre-freeze-revision.xml")


def test_pair_selection_falls_back_to_standalone_only_when_no_consolidated_pair_exists():
    payload = {
        "data": [
            {
                "type": "Integrated Filing- Financials",
                "symbol": "ABC",
                "consolidated": "Consolidated",
                "qe_Date": "30-Jun-2026",
                "broadcast_Date": "25-Jul-2026 10:00:00",
                "xbrl": "https://nsearchives.nseindia.com/consolidated-target.xml",
            },
            {
                "type": "Integrated Filing- Financials",
                "symbol": "ABC",
                "consolidated": "Standalone",
                "qe_Date": "30-Jun-2025",
                "broadcast_Date": "25-Jul-2025 10:00:00",
                "xbrl": "https://nsearchives.nseindia.com/standalone-baseline.xml",
            },
            {
                "type": "Integrated Filing- Financials",
                "symbol": "ABC",
                "consolidated": "Standalone",
                "qe_Date": "30-Jun-2026",
                "broadcast_Date": "25-Jul-2026 11:00:00",
                "xbrl": "https://nsearchives.nseindia.com/standalone-target.xml",
            },
        ]
    }
    pair = select_historical_filing_pair(
        payload,
        symbol="ABC",
        target_period_end="2026-06-30",
        baseline_period_end="2025-06-30",
        freeze_at_utc="2026-06-06T18:29:59Z",
    )
    assert pair is not None
    assert pair.accounting_basis == "Standalone"


def test_historical_signal_matches_frozen_h002_arithmetic_without_relabeling_event():
    actual = _actual_event()
    baseline = _baseline_event(actual)
    freeze = historical_freeze_at("2026-06-30")
    expectation = build_seasonal_expectation(
        baseline,
        target_period_end="2026-06-30",
        target_quarter=actual.reporting_quarter or "",
        target_accounting_basis=actual.accounting_basis,
        baseline_available_at_utc=None,
        expectation_as_of_utc=freeze,
        corporate_action_factor=1.0,
        corporate_action_version="EPSCA-test",
    )
    reference = PriceReference(
        symbol="CCL",
        role="price_day_minus_2",
        trading_date="2026-07-23",
        close_timestamp_utc="2026-07-23T10:00:00Z",
        close_price=100.0,
        source="https://nsearchives.nseindia.com/bhavcopy.zip",
        corporate_action_version="PB-test",
    )
    result = score_h002_historical_replay(
        actual,
        expectation,
        reference,
        reconstructed_at_utc="2026-09-07T06:01:00Z",
    )
    assert actual.mode == HISTORICAL_RECONSTRUCTION
    assert result.replay_rule_id == "H002-HR001"
    assert result.source_signal_rule_id == "H002-R001"
    assert result.bucket == "POSITIVE"
    assert result.surprise_eps == pytest.approx(4.77)
    assert result.ue == pytest.approx(0.0477)


def test_historical_scorer_refuses_prospective_relabeling():
    actual = replace(_actual_event(), mode="PROSPECTIVE")
    baseline = _baseline_event(actual)
    expectation = build_seasonal_expectation(
        baseline,
        target_period_end="2026-06-30",
        target_quarter=actual.reporting_quarter or "",
        target_accounting_basis=actual.accounting_basis,
        baseline_available_at_utc=None,
        expectation_as_of_utc=historical_freeze_at("2026-06-30"),
        corporate_action_factor=1.0,
        corporate_action_version="EPSCA-test",
    )
    reference = PriceReference(
        symbol="CCL",
        role="price_day_minus_2",
        trading_date="2026-07-23",
        close_timestamp_utc="2026-07-23T10:00:00Z",
        close_price=100.0,
        source="https://nsearchives.nseindia.com/bhavcopy.zip",
        corporate_action_version="PB-test",
    )
    with pytest.raises(HistoricalReplayError, match="must remain HISTORICAL_RECONSTRUCTION"):
        score_h002_historical_replay(
            actual,
            expectation,
            reference,
            reconstructed_at_utc="2026-09-07T06:01:00Z",
        )
