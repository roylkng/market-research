"""H021 first cohort: source-proven Muhurat calendar amendment, not returns.

The October 9 H021 decision and its October 12 first-session entry are
immutable. NSE circular CMTR/76941, published October 19 and archived by
HG009 on October 20, resolves the November 8 Sunday special session
*before* the session occurs. Its original-PDF review is reused verbatim.
Do not recast the old H021 P006 as prospective trading performance.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

from marketlab.alpha import digest
from marketlab.calendar_snapshot import CalendarSnapshot
from marketlab.h021_horizon_readiness import (
    FIRST_INTENT_ID,
    FROZEN_CALENDAR_SHA256,
    HORIZON_READINESS_ID,
    first_cohort_horizon_readiness,
)
from marketlab.hg009_p004_a1_muhurat import (
    AMENDMENT_ID as HG009_AMENDMENT_ID,
)
from marketlab.hg009_p004_a1_muhurat import SOURCE_URL, SPECIAL_DATE

AMENDMENT_ID = "H021-P023-2026-11-08-OFFICIAL-MUHURAT-H20-CLOCK-v1"
SOURCE_PDF_SHA256 = (
    "ce94ee1c54d98eccdf3c30fa0673ae2b6a49ea4ed4a72fb83d826f4359f71d58"
)
SOURCE_RECEIPT_SHA256 = (
    "432180257cd21010ca8df4192c6277c5e2bcccfd1f0b309050bb95d65e9c08bc"
)
HG009_AMENDMENT_SHA256 = (
    "b5e98a058b0fb97f4442ecd4aba386c1528f753aa47cfb16ddc5b04637e5b688"
)
H021_ENTRY_DATE = "2026-10-12"
NEW_H20_EXIT = "2026-11-08"
OLD_WEEKDAY_ONLY_H20 = "2026-11-09"
SAFE_ORIGINAL_MARKET_DATA_AFTER_UTC = "2026-11-08T10:45:00+00:00"


def _time(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("source chronological evidence requires an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid source chronological ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("source timestamp cannot omit timezone")
    return parsed.astimezone(UTC)


def build_h021_muhurat_calendar_amendment(
    intent: dict[str, Any],
    original_calendar: CalendarSnapshot,
    hg009_original_amendment: dict[str, Any],
) -> dict[str, Any]:
    """Retain all H021/HG009 original contracts; source-date-only correction."""
    original_h021 = first_cohort_horizon_readiness(intent, original_calendar)
    if (
        intent.get("intent_id") != FIRST_INTENT_ID
        or intent.get("entry_plan", {}).get("session_date_ist") != H021_ENTRY_DATE
        or original_h021["readiness_id"] != HORIZON_READINESS_ID
        or original_h021["calendar_sha256"] != FROZEN_CALENDAR_SHA256
        or original_h021["horizons"]["20"]["state"] != "BLOCKED"
        or original_h021["horizons"]["20"]["weekday_only_candidate_date_not_verified"]
        != OLD_WEEKDAY_ONLY_H20
        or original_h021["horizons"]["20"]["blockers"]
        != ["UNRESOLVED_OFFICIAL_SPECIAL_SESSION"]
        or original_h021["horizons"]["60"]["state"] != "BLOCKED"
        or original_calendar.unresolved_special_dates != (SPECIAL_DATE,)
    ):
        raise ValueError("immutable H021 first cohort/muhurat blockage changed")

    original_amendment = copy.deepcopy(hg009_original_amendment)
    original_sha = original_amendment.pop("amendment_sha256", None)
    if original_sha != HG009_AMENDMENT_SHA256 or digest(original_amendment) != original_sha:
        raise ValueError("NSE source-verified HG009 amendment hash or contents changed")
    source = hg009_original_amendment.get("prospective_special_session")
    if not isinstance(source, dict):
        raise TypeError("original 19 October NSE special-session evidence missing")
    if (
        hg009_original_amendment.get("amendment_id") != HG009_AMENDMENT_ID
        or hg009_original_amendment.get("source_url") != SOURCE_URL
        or hg009_original_amendment.get("original_source_pdf_sha256") != SOURCE_PDF_SHA256
        or hg009_original_amendment.get("original_receipt_sha256") != SOURCE_RECEIPT_SHA256
        or hg009_original_amendment.get("source_circular") != "NSE/CMTR/76941"
        or hg009_original_amendment.get("source_circular_issued") != "2026-10-19"
        or hg009_original_amendment.get("original_2026_calendar_sha256")
        != FROZEN_CALENDAR_SHA256
        or hg009_original_amendment.get("original_H20_state_retained")
        != "UNRESOLVED_EXCHANGE_SPECIAL_SESSION_BLOCKS_RESULT"
        or hg009_original_amendment.get("H20_new_outcomes_observed_or_calculated") is not False
        or hg009_original_amendment.get("H60_still_requires_official_2027_calendar")
        is not True
        or hg009_original_amendment.get("live_capital_allowed") is not False
        or source.get("session_date") != SPECIAL_DATE
        or source.get("is_sunday") is not True
        or source.get("regular_trading_open_ist") != "14:20"
        or source.get("non_CAS_regular_market_close_ist") != "15:30"
        or source.get("closing_auction_matching_end_ist") != "15:35"
        or source.get("market_last_modification_cutoff_ist") != "16:15"
        or source.get("conservative_original_postmarket_source_minimum_utc")
        != SAFE_ORIGINAL_MARKET_DATA_AFTER_UTC
    ):
        raise ValueError("HG009 original NSE exchange circular source/protocol changed")
    archived = _time(hg009_original_amendment.get("original_source_captured_at_utc"))
    amendment_timestamp = _time(hg009_original_amendment.get("protocol_registration_date"))
    if (
        archived != amendment_timestamp
        or not _time("2026-10-19T00:00:00Z")
        <= archived
        < _time("2026-11-08T08:50:00Z")
    ):
        raise ValueError("NSE source was not archived before Muhurat first trade")
    if hg009_original_amendment.get("amended_H20_last_session") != "2026-11-12":
        raise ValueError("independent HG009 20-session calendar baseline altered")

    regular = [item.session_date for item in original_calendar.sessions]
    if regular != sorted(regular) or len(regular) != len(set(regular)):
        raise ValueError("frozen NSE regular session dates invalid")
    if SPECIAL_DATE in regular or SPECIAL_DATE not in original_calendar.unresolved_special_dates:
        raise ValueError("special date was pre-inserted or not original unresolved date")
    amended = sorted([*regular, SPECIAL_DATE])
    if len(amended) != len(regular) + 1:
        raise ValueError("repaired trading sessions must add exactly one official date")
    tail = amended[amended.index(H021_ENTRY_DATE):]
    h20 = tail[:20]
    if len(h20) != 20 or h20[-1] != NEW_H20_EXIT or h20[-2] != "2026-11-06":
        raise ValueError("H021 original 20-session exit re-count invalid")
    h60_available = len(tail)
    if h60_available != 56:
        raise ValueError("H021 still requires four or more official 2027 sessions")
    result: dict[str, Any] = {
        "schema_version": 1,
        "amendment_id": AMENDMENT_ID,
        "classification": "NEW_OFFICIAL_SESSION_SOURCE_CALENDAR_ONLY_NO_STOCK_OUTCOMES",
        "frozen_h021_p003_intent_id": FIRST_INTENT_ID,
        "original_h021_p006_readiness_id": HORIZON_READINESS_ID,
        "original_frozen_calendar_sha256": FROZEN_CALENDAR_SHA256,
        "original_2026_calendar_immutably_retained": True,
        "first_entry_session_date_ist": H021_ENTRY_DATE,
        "original_20_session_calendar_state_retained": "BLOCKED",
        "original_unverified_weekday_only_20_session_exit": OLD_WEEKDAY_ONLY_H20,
        "independent_hg009_p004_a1_amendment_id": HG009_AMENDMENT_ID,
        "independent_hg009_p004_a1_original_sha256": HG009_AMENDMENT_SHA256,
        "official_source_url": SOURCE_URL,
        "official_source_circular": "NSE/CMTR/76941",
        "official_source_published_date": "2026-10-19",
        "original_source_retrieved_at_utc": archived.isoformat().replace("+00:00", "Z"),
        "official_original_pdf_sha256": SOURCE_PDF_SHA256,
        "official_original_receipt_sha256": SOURCE_RECEIPT_SHA256,
        "newly_verified_special_trading_session_date_ist": SPECIAL_DATE,
        "normal_market_first_trade_ist": "14:20",
        "non_CAS_regular_trading_last_time_ist": "15:30",
        "CAS_price_discovery_final_match_time_ist": "15:35",
        "last_trade_modification_deadline_ist": "16:15",
        "safest_original_source_capture_not_before_utc":
            SAFE_ORIGINAL_MARKET_DATA_AFTER_UTC,
        "H021_20_completed_sessions_count_entry_as_one": h20,
        "H021_20_completed_sessions_calendar_exit_ist": NEW_H20_EXIT,
        "H021_20_calendar_date_source_verified": True,
        "H021_20_market_session_completed_as_of_circular": False,
        "H021_20_stock_and_Nifty500_original_price_source_verified": False,
        "H021_20_CAS_security_eligibility_and_price_method_verified": False,
        "H021_20_corporate_actions_dividend_and_cost_basis_verified": False,
        "H021_60_verified_2026_sessions_available_from_entry": h60_available,
        "H021_60_minimum_2027_additional_sessions": 60 - h60_available,
        "H021_60_official_2027_calendar_verified": False,
        "H021_60_exit_date_ist": None,
        "h021_original_stock_selection_or_entry_date_changed": False,
        "h021_holding_horizon_or_benchmark_family_changed": False,
        "h021_forward_return_outcomes_opened": False,
        "h021_expected_alpha_claim_published": False,
        "live_capital_allowed": False,
        "portfolio_eligibility_allowed": False,
    }
    result["amendment_sha256"] = digest(result)
    return result


def validate_h021_muhurat_amendment(report: dict[str, Any]) -> None:
    original = copy.deepcopy(report)
    stored = original.pop("amendment_sha256", None)
    if not isinstance(stored, str) or stored != digest(original):
        raise ValueError("H021 source-only amendment digest mismatch")
    if (
        report.get("amendment_id") != AMENDMENT_ID
        or report.get("official_original_pdf_sha256") != SOURCE_PDF_SHA256
        or report.get("H021_20_completed_sessions_calendar_exit_ist") != NEW_H20_EXIT
        or report.get("H021_60_exit_date_ist") is not None
    ):
        raise ValueError("H021 amended calendar provenance/horizon modified")
    for forbidden in (
        "H021_20_market_session_completed_as_of_circular",
        "H021_20_stock_and_Nifty500_original_price_source_verified",
        "H021_20_CAS_security_eligibility_and_price_method_verified",
        "H021_20_corporate_actions_dividend_and_cost_basis_verified",
        "H021_60_official_2027_calendar_verified",
        "h021_original_stock_selection_or_entry_date_changed",
        "h021_holding_horizon_or_benchmark_family_changed",
        "h021_forward_return_outcomes_opened",
        "h021_expected_alpha_claim_published",
        "live_capital_allowed",
        "portfolio_eligibility_allowed",
    ):
        if report.get(forbidden) is not False:
            raise ValueError(f"H021 calendar cannot authorize {forbidden}")


def verified_h021_20_calendar_date_only(report: dict[str, Any]) -> str:
    """Return a SOURCE-CLOCK date, not a price outcome or approved trade."""
    validate_h021_muhurat_amendment(report)
    if report.get("H021_20_calendar_date_source_verified") is not True:
        raise ValueError("H021 20-session date is not source verified")
    return NEW_H20_EXIT
