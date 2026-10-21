"""Future SEBI CAS 2026 market-clock risk audit; no historical clock rewrite.

The Oct 15 circular changes CAS, F&O trading and expiry settlement rules
starting Dec 7. This module *only identifies* frozen protocol conflicts.
It cannot modify NSE official session calendar, manufacture original data,
change T006/T012/HG009/PF001 outcome methodology, or authorize trading.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.calendar_snapshot import CalendarSnapshot

IST = ZoneInfo("Asia/Kolkata")
SEBI_CIRCULAR_DATE = date(2026, 10, 15)
SEBI_EFFECTIVE = date(2026, 12, 7)
ICEBERG_EFFECTIVE = date(2027, 2, 8)
SEBI_ORIGINAL_CIRCULAR = (
    "https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/"
    "1792079571420.pdf"
)
SEBI_CIRCULAR_ID = "HO/47/11/11(3)2025-MRD-POD2/I/23843/2026"
ORIGINAL_2026_NSE_CALENDAR_SHA256 = (
    "2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce"
)
AUDIT_ID = "RM001-CAS-20261021-DEC07-FUTURE-CLOCK-AUDIT-v1"


def _ist_to_utc(day: date, hour: int, minute: int) -> str:
    return datetime.combine(
        day, time(hour, minute), tzinfo=IST
    ).astimezone(UTC).isoformat()


def classify_future_market_clock(
    *,
    session_date: str,
    instrument_kind: str,
    cas_eligibility_source_verified: bool | None,
    derivative_is_expiring_index: bool = False,
) -> dict[str, Any]:
    """Describe only regulator-defined future cutoffs and unmet source proof."""
    day = date.fromisoformat(session_date)
    if instrument_kind not in {
        "CASH_EQ", "STOCK_FUTURE", "INDEX_DERIVATIVE"
    }:
        raise AlphaContractError("CAS unsupported segment: no inferred hours")
    if instrument_kind != "INDEX_DERIVATIVE" and derivative_is_expiring_index:
        raise AlphaContractError("CAS invalid expiring-index flag")
    if day < SEBI_EFFECTIVE:
        return {
            "session_date": session_date,
            "state": "PRE_EFFECTIVE_KEEP_ORIGINAL_MARKET_AND_EVIDENCE_CLOCK",
            "minimum_auction_complete_utc": None,
            "derivative_trading_end_utc": None,
            "expiry_settlement_source": None,
            "new_sebi_regime_applied": False,
            "source_available_for_alpha_without_original_document": False,
        }
    if instrument_kind == "CASH_EQ":
        if cas_eligibility_source_verified is None:
            state = "BLOCKED_UNKNOWN_CAS_SECURITY_ELIGIBILITY"
            cas_clock = None
        elif cas_eligibility_source_verified is False:
            state = "CONTINUOUS_TRADING_STOCK_NOT_IN_CAS_PHASE_ONE"
            cas_clock = None
        else:
            state = "CAS_AUCTION_PRICE_NOT_PUBLIC_BEFORE_AFTER_1540_IST"
            cas_clock = _ist_to_utc(day, 15, 40)
        expiry_source = None
        derivatives_end = None
    else:
        if instrument_kind == "STOCK_FUTURE" and (
            cas_eligibility_source_verified is False
        ):
            raise AlphaContractError("CAS stock futures must have cash F&O eligibility")
        if instrument_kind == "INDEX_DERIVATIVE":
            expiry_source = (
                "EXPIRING_INDEX_LAST_30_MINUTES_CASH_CTS_CONSTITUENT_VWAP"
                if derivative_is_expiring_index
                else None
            )
            derivatives_end = _ist_to_utc(
                day, 15, 30 if derivative_is_expiring_index else 15, 45
            )
        else:
            expiry_source = (
                "IF_EXPIRING_STOCK_LAST_30_MINUTES_CASH_CTS_VWAP"
            )
            derivatives_end = _ist_to_utc(day, 15, 45)
        state = "FUTURE_DERIVATIVES_CLOCK_ORIGINAL_SOURCE_PROOF_REQUIRED"
        cas_clock = None
    return {
        "session_date": session_date,
        "state": state,
        "minimum_auction_complete_utc": cas_clock,
        "derivative_trading_end_utc": derivatives_end,
        "expiry_settlement_source": expiry_source,
        "new_sebi_regime_applied": True,
        "source_available_for_alpha_without_original_document": False,
        "new_iceberg_transition_rule_applies": day >= ICEBERG_EFFECTIVE,
    }


def audit_2026_frozen_cas_transition(
    calendar: CalendarSnapshot,
) -> dict[str, Any]:
    """Report prospective frozen clock assumptions needing a new source rule."""
    if calendar.sha256 != ORIGINAL_2026_NSE_CALENDAR_SHA256:
        raise AlphaContractError("CAS original NSE 2026 calendar changed")
    affected = [
        s for s in calendar.sessions
        if s.session_date >= SEBI_EFFECTIVE.isoformat()
    ]
    if not affected or affected[0].session_date != "2026-12-07":
        raise AlphaContractError("CAS old 2026 calendar lacks first effective session")
    rows = []
    for s in affected:
        day = date.fromisoformat(s.session_date)
        frozen_close = datetime.fromisoformat(
            s.close_timestamp_utc
        ).astimezone(UTC)
        earliest_cas_complete = datetime.combine(
            day, time(15, 40), tzinfo=IST
        ).astimezone(UTC)
        if earliest_cas_complete <= frozen_close:
            raise AlphaContractError("CAS original close already accounts for new rule")
        rows.append({
            "session_date": s.session_date,
            "legacy_calendar_close_utc": frozen_close.isoformat(),
            "not_before_new_CAS_order_entry_completion_utc": (
                earliest_cas_complete.isoformat()
            ),
            "legacy_close_is_not_future_CAS_publication_proof": True,
            "raw_NSE_CAS_quote_and_security_eligibility_needed": True,
        })
    result = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "circular_id": SEBI_CIRCULAR_ID,
        "sebi_original_document_url": SEBI_ORIGINAL_CIRCULAR,
        "circular_publication_date": SEBI_CIRCULAR_DATE.isoformat(),
        "future_regime_effective_date": SEBI_EFFECTIVE.isoformat(),
        "future_iceberg_rule_effective_date": ICEBERG_EFFECTIVE.isoformat(),
        "frozen_2026_calendar_sha256": calendar.sha256,
        "affected_frozen_2026_session_count": len(rows),
        "future_2026_frozen_sessions": rows,
        "new_cas_auction_order_entry_period_IST": "15:30-15:40",
        "new_derivative_stock_end_IST": "15:45",
        "new_index_derivative_end_IST_non_expiry": "15:45",
        "new_index_derivative_end_IST_expiring": "15:30",
        "new_derivatives_expiry_settlement_basis": (
            "VWAP_OF_UNDERLYING_DURING_LAST_30_MINUTES_OF_CASH_CTS"
        ),
        "official_NSE_instrument_specific_operational_SOP_verified": False,
        "original_SEBI_pdf_bytes_archived_in_repository": False,
        "active_scoring_or_decision_protocol_changed": False,
        "old_trial_predictions_or_dates_rewritten": False,
        "new_clock_is_enough_to_claim_observation_source": False,
        "prospective_amendment_required_before_new_rule_is_used": True,
        "live_capital_allowed": False,
    }
    result["audit_sha256"] = digest(result)
    return result
