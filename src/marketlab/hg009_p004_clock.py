"""HG009 P004 prospective observation horizons, frozen before first entry.

Calendar planning only: the source has zero post-entry returns and cannot
approve trading, backfill source time, or score outcome performance.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.calendar_snapshot import CalendarSnapshot, load_calendar_snapshot
from marketlab.hg009_controls import (
    load_hg009_inputs,
    verify_hg009_controls,
)

PROTOCOL_ID = "HG009-P004-FROZEN-OUTCOME-CLOCK-20261014-v1"
FROZEN_DATE = "2026-10-14"
FIRST_ENTRY = "2026-10-15"
CALENDAR_SHA = "2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce"
SELECTED_SHA = "e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5"
CONTROL_SHA = "8c8d9781adf7900addd28a1a60f1cfb33bed9a1e4985e6c410a010d2c819eef8"
HORIZONS = (1, 5, 20, 60)
PRIMARY = 20


def planned_horizon(
    calendar: CalendarSnapshot,
    *,
    first_entry: str,
    holding_sessions: int,
) -> dict[str, Any]:
    if calendar.sha256 != CALENDAR_SHA:
        raise AlphaContractError("HG009 P004 frozen NSE calendar changed")
    if first_entry != FIRST_ENTRY or holding_sessions not in HORIZONS:
        raise AlphaContractError("HG009 P004 first entry or frozen horizon drift")
    sessions = list(calendar.sessions)
    dates = [row.session_date for row in sessions]
    if first_entry not in dates:
        raise AlphaContractError("HG009 P004 first entry absent from NSE calendar")
    index = dates.index(first_entry)
    holding = dates[index:index + holding_sessions]
    if len(holding) < holding_sessions:
        state = "REQUIRES_NEW_OFFICIAL_FORWARD_CALENDAR"
        return {
            "holding_sessions": holding_sessions,
            "state": state,
            "first_entry_session": first_entry,
            "frozen_calendar_available_sessions": len(holding),
            "official_exit_session": None,
            "provisional_exit_if_unresolved": None,
            "date_scoped_holding_sessions": None,
            "unresolved_special_dates_in_window": [],
            "outcome_eligible": False,
        }
    unresolved = [
        date for date in calendar.unresolved_special_dates
        if first_entry <= date <= holding[-1]
    ]
    allowed = not unresolved
    return {
        "holding_sessions": holding_sessions,
        "state": (
            "FROZEN_TRADING_DAY_SEQUENCE_READY_TO_COLLECT_SOURCE"
            if allowed else "UNRESOLVED_EXCHANGE_SPECIAL_SESSION_BLOCKS_RESULT"
        ),
        "first_entry_session": first_entry,
        "frozen_calendar_available_sessions": len(holding),
        "official_exit_session": holding[-1] if allowed else None,
        "provisional_exit_if_unresolved": (
            None if allowed else holding[-1]
        ),
        "date_scoped_holding_sessions": holding if allowed else None,
        "unresolved_special_dates_in_window": unresolved,
        "outcome_eligible": False,
    }


def build_hg009_outcome_clock(
    *,
    calendar: CalendarSnapshot,
    original: dict[str, Any],
    selected: dict[str, Any],
    controls: dict[str, Any],
) -> dict[str, Any]:
    verify_hg009_controls(controls, source=original, selected=selected)
    if (
        selected.get("cohort_sha256") != SELECTED_SHA
        or controls.get("manifest_sha256") != CONTROL_SHA
    ):
        raise AlphaContractError("HG009 P004 300-company population changed")
    if any(
        x.get("selected_company_count") != 100
        for x in [controls]
    ):
        raise AlphaContractError("HG009 P004 100-name selected count drift")
    if (
        controls["zero_lane_control_company_count"] != 100
        or controls["one_lane_control_company_count"] != 100
        or controls["total_unique_observation_identities"] != 300
    ):
        raise AlphaContractError("HG009 P004 control identity count drift")
    plans = {
        str(h): planned_horizon(
            calendar,
            first_entry=FIRST_ENTRY,
            holding_sessions=h,
        )
        for h in HORIZONS
    }
    if plans["1"]["official_exit_session"] != FIRST_ENTRY:
        raise AlphaContractError("HG009 P004 official entry baseline mismatch")
    if plans["5"]["official_exit_session"] != "2026-10-22":
        raise AlphaContractError("HG009 P004 frozen NSE H5 sequence changed")
    if (
        plans["20"]["state"]
        != "UNRESOLVED_EXCHANGE_SPECIAL_SESSION_BLOCKS_RESULT"
        or plans["20"]["unresolved_special_dates_in_window"] != ["2026-11-08"]
    ):
        raise AlphaContractError("HG009 P004 H20 calendar issue must fail closed")
    if plans["60"]["state"] != "REQUIRES_NEW_OFFICIAL_FORWARD_CALENDAR":
        raise AlphaContractError("HG009 P004 H60 lacks 2027 official calendar")
    output: dict[str, Any] = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "registration_date": FROZEN_DATE,
        "first_eligible_entry_session": FIRST_ENTRY,
        "first_entry_basis": "OFFICIAL_NSE_EQ_OPEN_PROXY_NOT_EXECUTED_FILL",
        "close_basis": "OFFICIAL_EQ_LAST_HOLDING_TRADING_SESSION_CLOSE",
        "benchmark": "NIFTY500_PRICE_INDEX_NOT_TRI",
        "original_calendar_sha256": CALENDAR_SHA,
        "selected_cohort_sha256": SELECTED_SHA,
        "matched_control_manifest_sha256": CONTROL_SHA,
        "declared_arm_sizes": {
            "SELECTED": 100, "ONE_LANE": 100, "ZERO_LANE": 100
        },
        "predeclared_horizons_sessions": list(HORIZONS),
        "primary_descriptive_horizon_sessions": PRIMARY,
        "planned_horizon_status": plans,
        "primary_descriptive_endpoint": (
            "COVERAGE_PRESERVING_BAND_MATCHED_MEAN_AND_MEDIAN_PRICE_RETURNS"
        ),
        "mandatory_comparisons": (
            "SELECTED_MINUS_ONE_LANE_AND_SELECTED_MINUS_ZERO_LANE"
        ),
        "missing_source_identity_slots_must_remain_in_denominator": True,
        "no_survivor_only_exclusion": True,
        "corporate_action_and_dividend_adjustment_required_for_total_returns": True,
        "dividend_adjusted_equity_total_return_available": False,
        "source_return_labels_opened": False,
        "significance_or_causal_alpha_claim_authorized": False,
        "future_market_benchmark_return_calculated": False,
        "investable_order_or_fill_execution_verified": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["protocol_sha256"] = digest(output)
    return output


def validate_hg009_outcome_clock(
    value: dict[str, Any],
    *,
    calendar: CalendarSnapshot,
    original: dict[str, Any],
    selected: dict[str, Any],
    controls: dict[str, Any],
) -> None:
    unsigned = copy.deepcopy(value)
    expected_sha = unsigned.pop("protocol_sha256", None)
    if expected_sha != digest(unsigned):
        raise AlphaContractError("HG009 P004 outcome-clock SHA mismatch")
    other = build_hg009_outcome_clock(
        calendar=calendar,
        original=original,
        selected=selected,
        controls=controls,
    )
    if other != value:
        raise AlphaContractError("HG009 P004 protocol not source reproducible")


def load_p004_inputs(root: Path) -> tuple[CalendarSnapshot, dict, dict, dict]:
    import json

    calendar = load_calendar_snapshot(root / (
        "research/prospective/calendars/FY27-Q2-2026-09-06/"
        "NSE-CM-FY27Q2-v1.json"
    ))
    original, selected = load_hg009_inputs(root)
    controls = json.loads((root / (
        "research/hg009/hg009-p001-matched-300-company-controls-v1.json"
    )).read_text(encoding="utf-8"))
    return calendar, original, selected, controls
