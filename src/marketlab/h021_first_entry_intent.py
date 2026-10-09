"""Freeze H021's first research-only next-open intention before any return labels.

This is NOT a portfolio order. No price is read or model re-ranked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

INTENT_ID = "H021-P003-2026-10-09-FIRST-COHORT-v1"
COMPARISON_PATH = Path(
    "research/prospective/h021/comparisons/2026-10-09-primary-revision-v1.json"
)
CALENDAR_PATH = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json"
)
COMPARISON_GIT_BLOB_SHA = "99c94c9d98284076bf1a7c34ee43e602b741b15b"
CALENDAR_GIT_BLOB_SHA = "9ac614820a67b0f7b20d8170d15b84df3c996b62"
CALENDAR_PAYLOAD_SHA256 = "2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce"
PRIMARY_SIGNAL = "28-35 day same-period consensus EPS revision"


def git_blob_sha(raw: bytes) -> str:
    """Git SHA-1 object digest for an exact, versioned source blob."""
    header = b"blob " + str(len(raw)).encode("ascii") + b"\x00"
    return hashlib.sha1(header + raw).hexdigest()


def load_pinned_inputs(
    comparison_path: Path = COMPARISON_PATH,
    calendar_path: Path = CALENDAR_PATH,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reject any silent source replacement, even with the same filename."""
    comparison_raw = comparison_path.read_bytes()
    calendar_raw = calendar_path.read_bytes()
    if git_blob_sha(comparison_raw) != COMPARISON_GIT_BLOB_SHA:
        raise ValueError("pinned H021 comparison Git blob SHA mismatch")
    if git_blob_sha(calendar_raw) != CALENDAR_GIT_BLOB_SHA:
        raise ValueError("pinned NSE calendar Git blob SHA mismatch")
    comparison = json.loads(comparison_raw)
    calendar = json.loads(calendar_raw)
    if not isinstance(comparison, dict) or not isinstance(calendar, dict):
        raise TypeError("H021 first-cohort sources must be JSON objects")
    return comparison, calendar


def _check_comparison(comparison: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    if comparison.get("schema_version") != 1 or comparison.get("hypothesis_id") != "H021":
        raise ValueError("invalid H021 comparison identity")
    if comparison.get("primary_signal") != PRIMARY_SIGNAL:
        raise ValueError("unexpected H021 primary signal")
    if comparison.get("prior_capture_date_ist") != "2026-09-11":
        raise ValueError("first cohort prior capture changed")
    if comparison.get("current_capture_date_ist") != "2026-10-09":
        raise ValueError("first cohort current capture changed")
    if comparison.get("capture_interval_days") != 28:
        raise ValueError("first cohort capture interval changed")
    for flag in ("outcomes_opened", "live_capital_allowed"):
        if comparison.get(flag) is not False:
            raise ValueError(f"comparison {flag} must be false")
    observations = comparison.get("revision_observations")
    if not isinstance(observations, list) or len(observations) != 100:
        raise ValueError("first cohort must preserve all 100 observation rows")
    by_symbol = {}
    for row in observations:
        if not isinstance(row, dict) or not isinstance(row.get("symbol"), str):
            raise TypeError("invalid H021 symbol record")
        symbol = row["symbol"]
        if not symbol or symbol in by_symbol:
            raise ValueError("duplicate or empty H021 symbol")
        if type(row.get("primary_signal_available")) is not bool:
            raise ValueError("invalid primary eligibility")
        by_symbol[symbol] = row
    eligible = [row for row in observations if row["primary_signal_available"]]
    if len(eligible) != 97 or comparison.get("primary_signal_available_count") != 97:
        raise ValueError("first primary eligibility denominator changed")
    selected = comparison.get("primary_top_decile_symbols")
    if not isinstance(selected, list) or len(selected) != 10 or len(set(selected)) != 10:
        raise ValueError("first primary decile membership changed")
    if comparison.get("primary_top_decile_count") != 10:
        raise ValueError("first primary decile count mismatch")
    for symbol in selected:
        row = by_symbol.get(symbol)
        if row is None or row["primary_signal_available"] is not True:
            raise ValueError("first decile contains a missing or ineligible symbol")
        if row.get("primary_signal_reason") != "ELIGIBLE":
            raise ValueError("top-decile primary reason changed")
        revision = row.get("eps_revision_pct")
        if type(revision) not in (int, float):
            raise ValueError("top-decile primary revision missing")
    # This checks frozen ranking consistency, not a new selection.
    selected_min = min(by_symbol[s]["eps_revision_pct"] for s in selected)
    for row in eligible:
        if row["symbol"] not in selected and row.get("eps_revision_pct") >= selected_min:
            raise ValueError("frozen top decile missing eligible higher/tied revision")
    ineligible = [row for row in observations if not row["primary_signal_available"]]
    if {row["symbol"] for row in ineligible} != {
        "ADANIENT", "BOSCHLTD", "TRENT"
    }:
        raise ValueError("first cohort ineligible identities changed")
    return [by_symbol[s] for s in selected], ineligible


def _next_session(calendar: dict[str, Any]) -> dict[str, str]:
    if calendar.get("version") != "NSE-CM-FY27Q2-v1":
        raise ValueError("NSE calendar version changed")
    if calendar.get("sha256") != CALENDAR_PAYLOAD_SHA256:
        raise ValueError("NSE calendar digest changed")
    sessions = calendar.get("sessions")
    if not isinstance(sessions, list):
        raise TypeError("NSE calendar sessions missing")
    dates = [session.get("session_date") for session in sessions]
    if len(dates) != len(set(dates)) or dates != sorted(dates):
        raise ValueError("calendar has duplicate or unordered sessions")
    later = [session for session in sessions if session["session_date"] > "2026-10-09"]
    if not later or later[0].get("session_date") != "2026-10-12":
        raise ValueError("unexpected next NSE trading session")
    future_dates = [session["session_date"] for session in later]
    if not all(isinstance(value, str) and value for value in future_dates):
        raise ValueError("calendar has malformed future dates")
    entry = later[0]
    if entry.get("open_timestamp_utc") != "2026-10-12T03:45:00Z":
        raise ValueError("first H021 decision calendar open time changed")
    date.fromisoformat(entry["session_date"])
    return entry


def build_first_entry_intent(comparison: dict, calendar: dict) -> dict[str, Any]:
    top_rows, excluded_rows = _check_comparison(comparison)
    entry = _next_session(calendar)
    return {
        "schema_version": 1,
        "intent_id": INTENT_ID,
        "classification": "PRE_ENTRY_OUTCOME_BLIND_H021_RESEARCH_ONLY_NOT_PORTFOLIO",
        "source": {
            "comparison_path": str(COMPARISON_PATH),
            "comparison_git_blob_sha": COMPARISON_GIT_BLOB_SHA,
            "calendar_path": str(CALENDAR_PATH),
            "calendar_git_blob_sha": CALENDAR_GIT_BLOB_SHA,
            "calendar_payload_sha256": CALENDAR_PAYLOAD_SHA256,
            "calendar_version": calendar["version"],
            "primary_signal": PRIMARY_SIGNAL,
            "prior_capture_date_ist": comparison["prior_capture_date_ist"],
            "current_capture_date_ist": comparison["current_capture_date_ist"],
            "capture_interval_days": comparison["capture_interval_days"],
        },
        "universe_symbol_count": 100,
        "primary_signal_eligible_count": 97,
        "excluded_symbol_count": 3,
        "primary_top_decile_count": 10,
        "primary_top_decile_cutoff_eps_revision_pct": comparison[
            "primary_top_decile_cutoff_eps_revision_pct"
        ],
        "selected_observations": [
            {
                "symbol": row["symbol"],
                "eps_revision_pct": row["eps_revision_pct"],
                "analyst_count_prior": row["analyst_count_prior"],
                "analyst_count_current": row["analyst_count_current"],
                "entry_price": None,
                "entry_execution_status": "UNOBSERVED_NEXT_OPEN",
                "capital_allocation": None,
            }
            for row in top_rows
        ],
        "ineligible_symbols": [
            {"symbol": row["symbol"], "reason": row["primary_signal_reason"]}
            for row in sorted(excluded_rows, key=lambda row: row["symbol"])
        ],
        "entry_plan": {
            "session_date_ist": entry["session_date"],
            "calendar_open_timestamp_utc": entry["open_timestamp_utc"],
            "price_proxy": "NEXT_COMPLETED_SESSION_FIRST_EXECUTABLE_OPEN",
            "status": "RESEARCH_INTENT_ONLY_NO_MARKET_FILL_OBSERVED",
            "nontrading_or_no_executable_open_policy": "EXPLICIT_MISSED_OBSERVATION_NO_HINDSIGHT_FILL",
        },
        "outcome_plan": {
            "primary_horizon_completed_sessions": 60,
            "secondary_horizon_completed_sessions": 20,
            "benchmark_family": "NIFTY_500",
            "benchmark_price_series": "PENDING_INDEPENDENT_SOURCE_AND_BASIS_VALIDATION",
            "entry_and_exit_prices_observed": False,
            "return_outcomes_opened": False,
            "require_corporate_action_adjustment": True,
            "missing_market_prices_policy": "RETAIN_MISSING_NEVER_FILL",
            "sixty_session_exit_date_verified": False,
            "sixty_session_calendar_extension_required": True,
        },
        "frozen_primary_selection_unchanged": True,
        "no_position_orders_created": True,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    comparison, calendar = load_pinned_inputs()
    plan = build_first_entry_intent(comparison, calendar)
    raw = json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
    if args.output is None:
        print(raw)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
