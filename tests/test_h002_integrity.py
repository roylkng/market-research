"""Synthetic model-level regressions. Existing test_h002 covers parsed filings."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from marketlab.h002 import (
    H002SignalError,
    PriceReference,
    _expectation_digest,
    build_seasonal_expectation,
    score_h002,
)


def _event(*, baseline=False, eps=8.77):
    return SimpleNamespace(
        mode="HISTORICAL_RECONSTRUCTION" if baseline else "PROSPECTIVE",
        symbol="CCL", economic_event_id="base" if baseline else "actual",
        version_id="base-v1" if baseline else "actual-v1",
        reporting_period_end="2025-06-30" if baseline else "2026-06-30",
        reporting_quarter="First quarter", accounting_basis="Consolidated", basic_eps=eps,
        provenance=SimpleNamespace(
            exchange_published_at_utc="2025-07-28T14:30:00Z" if baseline
            else "2026-07-27T14:30:00Z",
            captured_at_utc="2026-09-06T00:00:00Z" if baseline
            else "2026-07-27T14:31:00Z",
        ),
    )


def _expectation(*, eps=6.5, factor=1.0):
    return build_seasonal_expectation(
        _event(baseline=True, eps=eps), target_period_end="2026-06-30",
        target_quarter="First quarter", target_accounting_basis="Consolidated",
        baseline_available_at_utc=None, expectation_as_of_utc="2026-07-26T12:00:00Z",
        corporate_action_factor=factor, corporate_action_version="CA-2026-07-26-v1",
    )


def _price(value=900.0):
    return PriceReference(
        symbol="CCL", role="price_day_minus_2", trading_date="2026-07-23",
        close_timestamp_utc="2026-07-23T10:00:00Z", close_price=value,
        source="SYNTHETIC-TEST", corporate_action_version="CA-2026-07-23-v1",
    )


def _score(*, event=None, expectation=None, price=None, at="2026-07-27T14:31:00Z"):
    return score_h002(
        _event() if event is None else event,
        _expectation() if expectation is None else expectation,
        _price() if price is None else price,
        scored_at_utc=at,
    )


def test_cannot_score_between_publication_and_local_capture():
    with pytest.raises(H002SignalError, match="captur"):
        _score(at="2026-07-27T14:30:30Z")


def test_capture_boundary_is_accepted():
    assert _score().bucket == "POSITIVE"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, False, "1"])
def test_invalid_corporate_action_factor_rejected(value):
    with pytest.raises(H002SignalError):
        _expectation(factor=value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, "6.5"])
def test_invalid_baseline_eps_rejected(value):
    with pytest.raises(H002SignalError):
        _expectation(eps=value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, "8.77"])
def test_invalid_actual_eps_rejected(value):
    with pytest.raises(H002SignalError):
        _score(event=_event(eps=value))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, "900", 0, -1])
def test_invalid_price_cannot_produce_a_bucket(value):
    with pytest.raises(H002SignalError):
        _score(price=_price(value))


def test_expected_eps_float_overflow_rejected():
    with pytest.raises(H002SignalError):
        _expectation(eps=6.5, factor=1e308)


def test_ue_float_overflow_rejected():
    with pytest.raises(H002SignalError):
        _score(price=_price(1e-320))


def test_changed_baseline_value_changes_expectation_identity():
    first, changed = _expectation(eps=6.5), _expectation(eps=7.5)
    assert first.baseline_event_version_id == changed.baseline_event_version_id
    assert first.expectation_id != changed.expectation_id


@pytest.mark.parametrize("change", [
    {"expected_eps": 1.0}, {"baseline_basic_eps": 1.0},
    {"corporate_action_factor": 2.0}, {"corporate_action_version": "OTHER"},
    {"status": "NO_SIGNAL", "no_signal_reason": "invented"},
    {"expectation_id": "0" * 24}, {"baseline_period_end": "2025-03-31"},
])
def test_modified_expectation_is_not_silently_trusted(change):
    with pytest.raises(H002SignalError):
        _score(expectation=replace(_expectation(), **change))


@pytest.mark.parametrize("change", [
    {"schema_version": 999}, {"model_version": "unregistered"}, {"rule_id": "H999"},
])
def test_unknown_expectation_contract_rejected(change):
    with pytest.raises(H002SignalError):
        _score(expectation=replace(_expectation(), **change))


@pytest.mark.parametrize("change", [
    {"trading_date": "2026-07-22"}, {"trading_date": "not-a-date"}, {"source": ""},
])
def test_price_reference_metadata_consistency(change):
    with pytest.raises(H002SignalError):
        _score(price=replace(_price(), **change))


def test_timezone_equivalent_price_date_is_valid():
    result = _score(price=replace(_price(), close_timestamp_utc="2026-07-23T15:30:00+05:30"))
    assert result.ue == pytest.approx(2.27 / 900)


def test_missing_values_remain_no_signal_not_numeric_errors():
    assert _score(expectation=_expectation(eps=None)).no_signal_reason == "missing_baseline_basic_eps"
    assert _score(event=_event(eps=None)).no_signal_reason == "missing_actual_basic_eps"
    assert _score(price=_price(None)).no_signal_reason == "missing_price_day_minus_2"


def test_zero_and_negative_eps_remain_valid():
    assert _score(event=_event(eps=0)).bucket == "NEGATIVE"
    assert _score(expectation=_expectation(eps=-1)).bucket == "POSITIVE"


def test_missing_capture_timestamp_is_not_accepted():
    event = _event()
    event.provenance.captured_at_utc = None
    with pytest.raises(H002SignalError):
        _score(event=event)


def test_expected_eps_float_underflow_is_not_reported_as_zero():
    with pytest.raises(H002SignalError, match="underflows"):
        _expectation(eps=1e-320, factor=1e-320)


def test_ue_float_underflow_is_not_reported_as_zero():
    with pytest.raises(H002SignalError, match="underflows"):
        _score(event=_event(eps=1e-320), expectation=_expectation(eps=0), price=_price(1e308))


def test_arithmetic_is_verified_even_when_a_payload_is_rehashed():
    changed = replace(_expectation(), expected_eps=1.0)
    changed = replace(changed, expectation_id=_expectation_digest(changed))
    with pytest.raises(H002SignalError, match="frozen EPS calculation"):
        _score(expectation=changed)
