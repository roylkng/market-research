import copy

import pytest

from marketlab.earnings_signal import (
    H002_RULE,
    H002_RULE_SHA256,
    EarningsSignalError,
    H002SignalInput,
    canonical_rule_sha256,
    compute_h002_signal,
    validate_frozen_rule,
)


def _valid_input(**overrides):
    values = {
        "symbol": "TEST",
        "current_event_id": "current-event",
        "current_exchange_published_at_utc": "2026-10-20T12:00:00Z",
        "current_accounting_basis": "Consolidated",
        "current_reporting_quarter": "Second quarter",
        "actual_basic_eps": 12.0,
        "prior_event_id": "prior-event",
        "prior_exchange_published_at_utc": "2025-10-20T12:00:00Z",
        "prior_accounting_basis": "Consolidated",
        "prior_reporting_quarter": "Second quarter",
        "prior_year_basic_eps": 10.0,
        "price_day_minus_2": 100.0,
        "price_reference_session": "2026-10-16",
        "price_source": "NSE_EOD",
        "corporate_action_comparable": True,
        "corporate_action_version": "NONE-v1",
    }
    values.update(overrides)
    return H002SignalInput(**values)


def test_frozen_rule_hash_is_exact():
    assert canonical_rule_sha256() == H002_RULE_SHA256
    validate_frozen_rule()


def test_rule_mutation_requires_new_version():
    changed = copy.deepcopy(H002_RULE)
    changed["winsorization"] = "1%"
    assert canonical_rule_sha256(changed) != H002_RULE_SHA256


def test_positive_ue_is_deterministic():
    one = compute_h002_signal(_valid_input())
    two = compute_h002_signal(_valid_input())
    assert one == two
    assert one.eligible is True
    assert one.expected_eps == 10.0
    assert one.unexpected_eps == 2.0
    assert one.ue == pytest.approx(0.02)
    assert one.bucket == "POSITIVE"
    assert one.no_signal_reasons == ()


def test_negative_and_zero_buckets():
    negative = compute_h002_signal(_valid_input(actual_basic_eps=8.0))
    zero = compute_h002_signal(_valid_input(actual_basic_eps=10.0))
    assert negative.bucket == "NEGATIVE"
    assert negative.ue == pytest.approx(-0.02)
    assert zero.bucket == "ZERO"
    assert zero.ue == 0.0


def test_missing_prior_eps_returns_no_signal():
    result = compute_h002_signal(_valid_input(prior_year_basic_eps=None))
    assert result.eligible is False
    assert result.bucket == "NO_SIGNAL"
    assert "missing_prior_year_basic_eps" in result.no_signal_reasons
    assert result.ue is None


def test_post_event_prior_source_is_rejected_as_leakage():
    with pytest.raises(EarningsSignalError, match="not public before"):
        compute_h002_signal(
            _valid_input(prior_exchange_published_at_utc="2026-10-21T12:00:00Z")
        )


def test_accounting_or_quarter_mismatch_returns_no_signal():
    result = compute_h002_signal(
        _valid_input(
            prior_accounting_basis="Standalone",
            prior_reporting_quarter="First quarter",
        )
    )
    assert result.eligible is False
    assert "accounting_basis_mismatch" in result.no_signal_reasons
    assert "reporting_quarter_mismatch" in result.no_signal_reasons


def test_corporate_action_comparability_is_mandatory():
    result = compute_h002_signal(
        _valid_input(corporate_action_comparable=False, corporate_action_version=None)
    )
    assert result.eligible is False
    assert "eps_not_comparable_across_corporate_action" in result.no_signal_reasons


def test_comparability_version_is_required_even_when_marked_comparable():
    result = compute_h002_signal(_valid_input(corporate_action_version=None))
    assert result.eligible is False
    assert "missing_corporate_action_version" in result.no_signal_reasons


def test_invalid_price_does_not_create_signal():
    result = compute_h002_signal(_valid_input(price_day_minus_2=0.0))
    assert result.eligible is False
    assert "invalid_price_day_minus_2" in result.no_signal_reasons


def test_timestamps_must_be_timezone_aware():
    with pytest.raises(EarningsSignalError, match="include timezone"):
        compute_h002_signal(
            _valid_input(current_exchange_published_at_utc="2026-10-20T12:00:00")
        )
