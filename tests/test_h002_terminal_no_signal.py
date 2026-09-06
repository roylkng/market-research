from __future__ import annotations

from types import SimpleNamespace

import pytest

from marketlab.h002 import (
    H002SignalError,
    _validate_expectation,
    build_terminal_no_signal_expectation,
)


def _baseline():
    return SimpleNamespace(
        symbol="OLD",
        economic_event_id="event-old",
        version_id="version-old",
        reporting_period_end="2025-09-30",
        reporting_quarter="Second quarter",
        accounting_basis="Consolidated",
        basic_eps=12.5,
        provenance=SimpleNamespace(exchange_published_at_utc="2025-10-20T12:00:00Z"),
    )


@pytest.mark.parametrize(
    "reason", ["unresolved_corporate_action", "baseline_identity_mismatch"]
)
def test_terminal_no_signal_retains_baseline_but_never_computes_expected_eps(reason):
    expectation = build_terminal_no_signal_expectation(
        _baseline(),
        canonical_symbol="NEW",
        target_period_end="2026-09-30",
        target_quarter="Second quarter",
        target_accounting_basis="Consolidated",
        baseline_available_at_utc=None,
        expectation_as_of_utc="2026-09-06T12:00:00Z",
        no_signal_reason=reason,
        corporate_action_version="EVIDENCE-v1",
    )
    _validate_expectation(expectation)
    assert expectation.schema_version == 3
    assert expectation.symbol == "NEW"
    assert expectation.baseline_basic_eps == 12.5
    assert expectation.expected_eps is None
    assert expectation.status == "NO_SIGNAL"
    assert expectation.no_signal_reason == reason


def test_terminal_no_signal_rejects_unregistered_reason():
    with pytest.raises(H002SignalError, match="unsupported terminal NO_SIGNAL reason"):
        build_terminal_no_signal_expectation(
            _baseline(),
            canonical_symbol="NEW",
            target_period_end="2026-09-30",
            target_quarter="Second quarter",
            target_accounting_basis="Consolidated",
            baseline_available_at_utc=None,
            expectation_as_of_utc="2026-09-06T12:00:00Z",
            no_signal_reason="make_it_fit",
            corporate_action_version="EVIDENCE-v1",
        )
