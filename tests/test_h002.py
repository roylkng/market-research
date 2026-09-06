from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from marketlab.events import PROSPECTIVE, SourceProvenance, parse_indas_html, sha256_bytes
from marketlab.h002 import (
    H002SignalError,
    PriceReference,
    build_seasonal_expectation,
    load_and_validate_rule,
    score_h002,
)

FIXTURE = Path("data/fixtures/filings/ccl_fy27_q1_consolidated_source_derived.html")


def _parsed_event(*, mode: str = PROSPECTIVE):
    raw = FIXTURE.read_bytes()
    event = parse_indas_html(
        raw.decode(),
        source_url="https://example.invalid/ccl",
        raw_sha256=sha256_bytes(raw),
        raw_path="raw/ccl.html",
        captured_at_utc="2026-07-27T14:31:00Z",
        mode=mode,
        exchange_published_at_utc=("2026-07-27T14:30:00Z" if mode == PROSPECTIVE else None),
        cohort_id=("FY27-Q1-TEST" if mode == PROSPECTIVE else None),
        universe_rule_version=("U001-test" if mode == PROSPECTIVE else None),
        universe_snapshot_sha256=("a" * 64 if mode == PROSPECTIVE else None),
    )
    return event


def _baseline(*, eps: float | None = 6.5):
    current = _parsed_event(mode="HISTORICAL_RECONSTRUCTION")
    return replace(
        current,
        economic_event_id="baseline-event",
        version_id="baseline-version",
        financial_year_start="01-04-2025",
        financial_year_end="31-03-2026",
        reporting_period_start="01-04-2025",
        reporting_period_end="30-06-2025",
        basic_eps=eps,
        diluted_eps=eps,
        provenance=SourceProvenance(
            source_url="https://example.invalid/ccl-prior",
            captured_at_utc="2026-09-06T00:00:00Z",
            raw_sha256="b" * 64,
            raw_path="raw/ccl-prior.html",
            content_type="text/html",
            source_mode="NSE_INTEGRATED_FILING_IXBRL",
            exchange_published_at_utc="2025-07-28T14:30:00Z",
        ),
    )


def _expectation(*, baseline_eps: float | None = 6.5, factor: float = 1.0):
    return build_seasonal_expectation(
        _baseline(eps=baseline_eps),
        target_period_end="2026-06-30",
        target_quarter="First quarter",
        target_accounting_basis="Consolidated",
        baseline_available_at_utc=None,
        expectation_as_of_utc="2026-07-26T12:00:00Z",
        corporate_action_factor=factor,
        corporate_action_version="CA-2026-07-26-v1",
    )


def _price(value: float | None = 900.0, *, timestamp: str = "2026-07-23T10:00:00Z"):
    return PriceReference(
        symbol="CCL",
        role="price_day_minus_2",
        trading_date="2026-07-23",
        close_timestamp_utc=timestamp,
        close_price=value,
        source="TEST",
        corporate_action_version="CA-2026-07-23-v1",
    )


def test_frozen_rule_hash_validates():
    document = load_and_validate_rule("registry/h002_signal_rule.yaml")
    assert document["id"] == "H002-R001"
    assert document["decision"]["live_capital"] is False


def test_expectation_uses_prior_year_same_quarter_eps_and_corporate_action_factor():
    expectation = _expectation(baseline_eps=6.5, factor=2.0)
    assert expectation.status == "READY"
    assert expectation.baseline_basic_eps == 6.5
    assert expectation.expected_eps == 13.0
    assert expectation.target_period_end == "2026-06-30"


def test_missing_prior_eps_returns_no_signal_expectation():
    expectation = _expectation(baseline_eps=None)
    assert expectation.status == "NO_SIGNAL"
    assert expectation.expected_eps is None
    assert expectation.no_signal_reason == "missing_baseline_basic_eps"


def test_historical_capture_time_cannot_substitute_for_baseline_availability():
    baseline = _baseline()
    baseline = replace(
        baseline,
        provenance=replace(baseline.provenance, exchange_published_at_utc=None),
    )
    with pytest.raises(H002SignalError, match="baseline availability is required"):
        build_seasonal_expectation(
            baseline,
            target_period_end="2026-06-30",
            target_quarter="First quarter",
            target_accounting_basis="Consolidated",
            baseline_available_at_utc=None,
            expectation_as_of_utc="2026-07-26T12:00:00Z",
            corporate_action_factor=1.0,
            corporate_action_version="CA-v1",
        )


def test_expectation_rejects_wrong_seasonal_baseline():
    baseline = replace(_baseline(), reporting_period_end="31-03-2025")
    with pytest.raises(H002SignalError, match="same quarter exactly one year"):
        build_seasonal_expectation(
            baseline,
            target_period_end="2026-06-30",
            target_quarter="First quarter",
            target_accounting_basis="Consolidated",
            baseline_available_at_utc=None,
            expectation_as_of_utc="2026-07-26T12:00:00Z",
            corporate_action_factor=1.0,
            corporate_action_version="CA-v1",
        )


def test_positive_ue_is_deterministic_and_does_not_open_a_position():
    event = _parsed_event()
    expectation = _expectation(baseline_eps=6.5)
    result = score_h002(
        event,
        expectation,
        _price(900.0),
        scored_at_utc="2026-07-27T14:31:00Z",
    )
    assert result.bucket == "POSITIVE"
    assert result.surprise_eps == pytest.approx(2.27)
    assert result.ue == pytest.approx(2.27 / 900.0)
    assert "entry" not in result.to_dict()
    assert "position" not in result.to_dict()


@pytest.mark.parametrize(
    ("actual_eps", "expected_eps", "bucket"),
    [(5.0, 6.5, "NEGATIVE"), (6.5, 6.5, "ZERO")],
)
def test_signal_buckets_are_frozen(actual_eps: float, expected_eps: float, bucket: str):
    event = replace(_parsed_event(), basic_eps=actual_eps)
    expectation = _expectation(baseline_eps=expected_eps)
    result = score_h002(
        event,
        expectation,
        _price(),
        scored_at_utc="2026-07-27T14:31:00Z",
    )
    assert result.bucket == bucket


def test_missing_price_produces_no_signal_not_imputation():
    result = score_h002(
        _parsed_event(),
        _expectation(),
        _price(None),
        scored_at_utc="2026-07-27T14:31:00Z",
    )
    assert result.bucket == "NO_SIGNAL"
    assert result.no_signal_reason == "missing_price_day_minus_2"
    assert result.ue is None


def test_post_filing_price_is_rejected_as_leakage():
    with pytest.raises(H002SignalError, match="strictly before current filing"):
        score_h002(
            _parsed_event(),
            _expectation(),
            _price(timestamp="2026-07-27T14:30:01Z"),
            scored_at_utc="2026-07-27T14:31:00Z",
        )


def test_expectation_created_after_filing_is_rejected_as_leakage():
    expectation = replace(_expectation(), expectation_as_of_utc="2026-07-27T14:30:00Z")
    with pytest.raises(H002SignalError, match="expectation_as_of must be strictly before"):
        score_h002(
            _parsed_event(),
            expectation,
            _price(),
            scored_at_utc="2026-07-27T14:31:00Z",
        )


def test_non_prospective_actual_event_cannot_be_scored():
    event = replace(_parsed_event(), mode="HISTORICAL_RECONSTRUCTION")
    with pytest.raises(H002SignalError, match="actual event must be PROSPECTIVE"):
        score_h002(
            event,
            _expectation(),
            _price(),
            scored_at_utc="2026-07-27T14:31:00Z",
        )
