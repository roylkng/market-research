"""Future SEBI CAS clocks are audited, never backdated to October alpha."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.rm001_cas_future import (
    ICEBERG_EFFECTIVE,
    SEBI_EFFECTIVE,
    audit_2026_frozen_cas_transition,
    classify_future_market_clock,
)

CALENDAR = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/"
    "NSE-CM-FY27Q2-v1.json"
)


def test_original_dec04_regime_untouched_and_dec07_cas_not_before_1540():
    before = classify_future_market_clock(
        session_date="2026-12-04",
        instrument_kind="CASH_EQ",
        cas_eligibility_source_verified=True,
    )
    after = classify_future_market_clock(
        session_date="2026-12-07",
        instrument_kind="CASH_EQ",
        cas_eligibility_source_verified=True,
    )
    assert before["new_sebi_regime_applied"] is False
    assert before["conservative_full_CAS_order_window_elapsed_utc"] is None
    assert after["new_sebi_regime_applied"] is True
    assert after["conservative_full_CAS_order_window_elapsed_utc"] == (
        "2026-12-07T10:10:00+00:00"
    )
    assert after["source_available_for_alpha_without_original_document"] is False
    assert after["new_iceberg_transition_rule_applies"] is False
    assert SEBI_EFFECTIVE.isoformat() == "2026-12-07"


def test_cash_security_not_provably_fo_eligible_is_blocked():
    missing = classify_future_market_clock(
        session_date="2026-12-08",
        instrument_kind="CASH_EQ",
        cas_eligibility_source_verified=None,
    )
    assert missing["state"] == "BLOCKED_UNKNOWN_CAS_SECURITY_ELIGIBILITY"
    assert missing["conservative_full_CAS_order_window_elapsed_utc"] is None
    non_cas = classify_future_market_clock(
        session_date="2026-12-08",
        instrument_kind="CASH_EQ",
        cas_eligibility_source_verified=False,
    )
    assert non_cas["state"] == "CONTINUOUS_TRADING_STOCK_NOT_IN_CAS_PHASE_ONE"


def test_stock_and_index_derivative_end_and_vwap_basis_are_distinct():
    stock = classify_future_market_clock(
        session_date="2026-12-08",
        instrument_kind="STOCK_FUTURE",
        cas_eligibility_source_verified=True,
    )
    regular_index = classify_future_market_clock(
        session_date="2026-12-08",
        instrument_kind="INDEX_DERIVATIVE",
        cas_eligibility_source_verified=None,
    )
    expiring_index = classify_future_market_clock(
        session_date="2026-12-08",
        instrument_kind="INDEX_DERIVATIVE",
        cas_eligibility_source_verified=None,
        derivative_is_expiring_index=True,
    )
    assert stock["derivative_trading_end_utc"] == "2026-12-08T10:15:00+00:00"
    assert regular_index["derivative_trading_end_utc"] == (
        "2026-12-08T10:15:00+00:00"
    )
    assert expiring_index["derivative_trading_end_utc"] == (
        "2026-12-08T10:00:00+00:00"
    )
    assert "LAST_30_MINUTES" in expiring_index["expiry_settlement_source"]
    assert "LAST_30_MINUTES" in stock["expiry_settlement_source"]
    assert stock["source_available_for_alpha_without_original_document"] is False
    with pytest.raises(AlphaContractError, match="invalid expiring-index"):
        classify_future_market_clock(
            session_date="2026-12-08", instrument_kind="STOCK_FUTURE",
            cas_eligibility_source_verified=True,
            derivative_is_expiring_index=True,
        )


def test_original_calendar_frozen_before_future_change_and_no_2027_extension():
    calendar = load_calendar_snapshot(CALENDAR)
    audit = audit_2026_frozen_cas_transition(calendar)
    assert audit["frozen_2026_calendar_sha256"] == calendar.sha256
    assert audit["affected_frozen_2026_session_count"] == 18
    assert audit["future_2026_frozen_sessions"][0] == {
        "session_date": "2026-12-07",
        "legacy_calendar_close_utc": "2026-12-07T10:00:00+00:00",
        "conservative_full_CAS_order_window_elapsed_utc": (
            "2026-12-07T10:10:00+00:00"
        ),
        "legacy_close_is_not_future_CAS_publication_proof": True,
        "raw_NSE_CAS_quote_and_security_eligibility_needed": True,
    }
    assert audit["future_2026_frozen_sessions"][-1]["session_date"] == (
        "2026-12-31"
    )
    assert audit["original_SEBI_pdf_bytes_archived_in_repository"] is False
    assert audit["official_NSE_instrument_specific_operational_SOP_verified"] is False
    assert audit["prospective_amendment_required_before_new_rule_is_used"]
    assert audit["active_scoring_or_decision_protocol_changed"] is False
    assert audit["old_trial_predictions_or_dates_rewritten"] is False
    assert audit["live_capital_allowed"] is False
    unsigned = copy.deepcopy(audit)
    checksum = unsigned.pop("audit_sha256")
    assert checksum == digest(unsigned)


def test_separate_2027_iceberg_effective_date_must_not_be_moved_to_dec():
    december = classify_future_market_clock(
        session_date="2026-12-07",
        instrument_kind="CASH_EQ",
        cas_eligibility_source_verified=True,
    )
    february = classify_future_market_clock(
        session_date="2027-02-08",
        instrument_kind="CASH_EQ",
        cas_eligibility_source_verified=True,
    )
    assert ICEBERG_EFFECTIVE.isoformat() == "2027-02-08"
    assert december["new_iceberg_transition_rule_applies"] is False
    assert february["new_iceberg_transition_rule_applies"] is True


def test_unknown_stock_futures_eligibility_and_wrong_segment_fail_closed():
    with pytest.raises(AlphaContractError, match="must have cash F&O eligibility"):
        classify_future_market_clock(
            session_date="2026-12-07",
            instrument_kind="STOCK_FUTURE",
            cas_eligibility_source_verified=False,
        )
    with pytest.raises(AlphaContractError, match="unsupported segment"):
        classify_future_market_clock(
            session_date="2026-12-07",
            instrument_kind="UNKNOWN",
            cas_eligibility_source_verified=None,
        )
