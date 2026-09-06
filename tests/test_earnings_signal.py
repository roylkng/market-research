from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from marketlab.earnings_signal import (
    H002_EXPECTATION_MODEL,
    H002_FORMULA,
    H002_SIGNAL_VERSION,
    EarningsSignalError,
    EPSObservation,
    PriceObservation,
    compute_h002_seasonal_ue,
    eps_observation_from_event,
)
from marketlab.events import EventStore


def _eps(
    *,
    period_end: str,
    eps: float | None,
    published: str | None,
    basis_version: str | None = "as_reported_no_corporate_action_v1",
    symbol: str = "TEST",
    quarter: str = "First quarter",
    accounting_basis: str = "Consolidated",
    event_id: str = "event",
    version_id: str = "version",
) -> EPSObservation:
    return EPSObservation(
        symbol=symbol,
        reporting_period_end=period_end,
        reporting_quarter=quarter,
        accounting_basis=accounting_basis,
        basic_eps=eps,
        source_event_id=event_id,
        source_version_id=version_id,
        source_published_at_utc=published,
        eps_basis_version=basis_version,
    )


def _price(close: float | None = 100.0) -> PriceObservation:
    return PriceObservation(
        close=close,
        observed_at_utc="2026-07-23T10:00:00Z",
        source="fixture",
        price_basis_version="nse_unadjusted_close_v1",
    )


def _compute(actual_eps: float, prior_eps: float):
    return compute_h002_seasonal_ue(
        actual=_eps(
            period_end="2026-06-30",
            eps=actual_eps,
            published="2026-07-27T14:56:14Z",
            event_id="current",
            version_id="current-v1",
        ),
        prior_year=_eps(
            period_end="2025-06-30",
            eps=prior_eps,
            published="2025-07-28T12:00:00Z",
            event_id="prior",
            version_id="prior-v1",
        ),
        price_day_minus_2=_price(),
        decision_at_utc="2026-07-27T15:00:00Z",
    )


def test_positive_negative_and_zero_buckets_are_unoptimized_signs():
    positive = _compute(8.0, 6.0)
    negative = _compute(4.0, 6.0)
    zero = _compute(6.0, 6.0)

    assert positive.state == "POSITIVE"
    assert positive.ue == pytest.approx(0.02)
    assert negative.state == "NEGATIVE"
    assert negative.ue == pytest.approx(-0.02)
    assert zero.state == "ZERO"
    assert zero.ue == 0.0


def test_missing_prior_year_eps_is_explicit_no_signal():
    actual = _eps(
        period_end="2026-06-30",
        eps=8.0,
        published="2026-07-27T14:56:14Z",
    )
    result = compute_h002_seasonal_ue(
        actual=actual,
        prior_year=None,
        price_day_minus_2=_price(),
        decision_at_utc="2026-07-27T15:00:00Z",
    )
    assert result.state == "NO_SIGNAL"
    assert result.ue is None
    assert result.no_signal_reasons == ("PRIOR_YEAR_EPS_MISSING",)


def test_missing_prior_publication_timestamp_does_not_use_reconstruction_capture_time():
    actual = _eps(
        period_end="2026-06-30",
        eps=8.0,
        published="2026-07-27T14:56:14Z",
    )
    prior = _eps(period_end="2025-06-30", eps=6.0, published=None)
    result = compute_h002_seasonal_ue(
        actual=actual,
        prior_year=prior,
        price_day_minus_2=_price(),
        decision_at_utc="2026-07-27T15:00:00Z",
    )
    assert result.state == "NO_SIGNAL"
    assert result.no_signal_reasons == ("PRIOR_YEAR_PUBLICATION_TIMESTAMP_MISSING",)


def test_eps_basis_mismatch_is_no_signal_not_silently_adjusted():
    actual = _eps(
        period_end="2026-06-30",
        eps=8.0,
        published="2026-07-27T14:56:14Z",
        basis_version="split_adjusted_v2",
    )
    prior = _eps(
        period_end="2025-06-30",
        eps=6.0,
        published="2025-07-28T12:00:00Z",
        basis_version="as_reported_no_corporate_action_v1",
    )
    result = compute_h002_seasonal_ue(
        actual=actual,
        prior_year=prior,
        price_day_minus_2=_price(),
        decision_at_utc="2026-07-27T15:00:00Z",
    )
    assert result.state == "NO_SIGNAL"
    assert "EPS_BASIS_VERSION_MISMATCH" in result.no_signal_reasons


def test_current_filing_comparability_identity_is_strict():
    actual = _eps(
        period_end="2026-06-30",
        eps=8.0,
        published="2026-07-27T14:56:14Z",
    )
    wrong_period = _eps(
        period_end="2025-03-31",
        eps=6.0,
        published="2025-04-25T12:00:00Z",
    )
    with pytest.raises(EarningsSignalError, match="same reporting-period end"):
        compute_h002_seasonal_ue(
            actual=actual,
            prior_year=wrong_period,
            price_day_minus_2=_price(),
            decision_at_utc="2026-07-27T15:00:00Z",
        )


def test_future_information_cannot_enter_expectation_or_decision():
    actual = _eps(
        period_end="2026-06-30",
        eps=8.0,
        published="2026-07-27T14:56:14Z",
    )
    prior = _eps(
        period_end="2025-06-30",
        eps=6.0,
        published="2026-07-27T14:57:00Z",
    )
    with pytest.raises(EarningsSignalError, match="not public before current filing"):
        compute_h002_seasonal_ue(
            actual=actual,
            prior_year=prior,
            price_day_minus_2=_price(),
            decision_at_utc="2026-07-27T15:00:00Z",
        )

    safe_prior = _eps(
        period_end="2025-06-30",
        eps=6.0,
        published="2025-07-28T12:00:00Z",
    )
    with pytest.raises(EarningsSignalError, match="decision timestamp precedes"):
        compute_h002_seasonal_ue(
            actual=actual,
            prior_year=safe_prior,
            price_day_minus_2=_price(),
            decision_at_utc="2026-07-27T14:00:00Z",
        )


def test_supplied_price_must_predate_current_filing():
    actual = _eps(
        period_end="2026-06-30",
        eps=8.0,
        published="2026-07-27T14:56:14Z",
    )
    prior = _eps(
        period_end="2025-06-30",
        eps=6.0,
        published="2025-07-28T12:00:00Z",
    )
    future_price = PriceObservation(
        close=100.0,
        observed_at_utc="2026-07-27T15:00:00Z",
        source="bad-fixture",
        price_basis_version="nse_unadjusted_close_v1",
    )
    with pytest.raises(EarningsSignalError, match="price must predate"):
        compute_h002_seasonal_ue(
            actual=actual,
            prior_year=prior,
            price_day_minus_2=future_price,
            decision_at_utc="2026-07-27T15:01:00Z",
        )


def test_event_adapter_normalizes_exchange_date_and_never_invents_publication_time(tmp_path):
    raw = Path("data/fixtures/filings/ccl_fy27_q1_consolidated_source_derived.html").read_bytes()
    event, _ = EventStore(tmp_path).reconstruct_bytes(
        raw,
        source_url="https://example.invalid/ccl",
    )

    unresolved = eps_observation_from_event(
        event,
        eps_basis_version="as_reported_no_corporate_action_v1",
    )
    assert unresolved.reporting_period_end == "2026-06-30"
    assert unresolved.source_published_at_utc is None

    grounded = eps_observation_from_event(
        event,
        eps_basis_version="as_reported_no_corporate_action_v1",
        source_published_at_utc="2026-07-27T14:56:14Z",
    )
    assert grounded.reporting_period_end == "2026-06-30"
    assert grounded.source_published_at_utc == "2026-07-27T14:56:14Z"


def test_registry_is_bound_to_code_constants_and_no_hidden_overlays():
    document = yaml.safe_load(Path("registry/hypotheses.yaml").read_text(encoding="utf-8"))
    h002 = next(item for item in document["hypotheses"] if item["id"] == "H002")
    signal = h002["signal"]

    assert h002["status"] == "FROZEN"
    assert h002["evidence_status"] == "INCONCLUSIVE"
    assert signal["version"] == H002_SIGNAL_VERSION
    assert signal["expectation_model"] == H002_EXPECTATION_MODEL
    assert signal["formula"] == H002_FORMULA
    assert signal["winsorization"] == "none"
    assert signal["analyst_consensus"] == "excluded_from_v1"
    assert signal["buckets"] == {
        "positive": "ue > 0",
        "negative": "ue < 0",
        "zero": "ue == 0",
        "no_signal": "required_input_missing_or_not_safely_comparable",
    }
    assert h002["live_capital"] is False
