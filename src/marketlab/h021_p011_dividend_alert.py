"""Outcome-blind preregistered VEDL dividend measurement alert for H021.

The original ten Oct9 H021 EPS selections are immutable. A known Oct8
dividend announcement for VEDL is an *unresolved return-basis hazard*,
NOT a new stock filter or an economic return. Original NSE dividends
and full-horizon stock/share actions still require independent review.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from marketlab.h021_entry_observation import EXPECTED_SELECTION, _validate_intent
from marketlab.h021_first_entry_intent import (
    build_first_entry_intent,
    git_blob_sha,
    load_pinned_inputs,
)

INTENT_PATH = Path("research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json")
UNIVERSE_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")
INTENT_GIT_BLOB = "e25f77e1c845456473e624899d4748e306b1225b"
UNIVERSE_GIT_BLOB = "8026e81faee3e913d2fba1dba72d60603b69fa07"
RISK_ID = "H021-P011-FIRST-ENTRY-KNOWN-DIVIDEND-BOUNDARY-v1"
KNOWN_EVENTS = (
    {
        "symbol": "VEDL",
        "event": "INTERIM_DIVIDEND_DECLARED",
        "announcement_date": "2026-10-08",
        "issuer_reported_per_share_inr": 5.0,
        "reported_ex_date_ist": "2026-10-14",
        "reported_record_date_ist": "2026-10-14",
        "reference_sources": [
            {
                "url": "https://www.businesstoday.in/markets/stocks/story/vedanta-approves-rs-5-interim-dividend-for-fy27-check-record-date-560377-2026-10-08",
                "kind": "DATED_MEDIA_QUOTING_ISSUER",
                "dated": "2026-10-08",
                "supports": "Rs5 cash dividend, Oct14 record date",
            },
            {
                "url": "https://groww.in/stocks/vedanta-ltd",
                "kind": "SECONDARY_EX_DATE_TABLE",
                "dated": "2026-10-11",
                "supports": "Oct14 ex-date and record date, Rs5 declared",
            },
        ],
        "original_nse_corporate_action_pdf_sha256": None,
        "official_exchange_dividend_terms_semantically_audited": False,
        "cash_payment_and_shareholder_entitlement_verified": False,
        "distribution_receipt_amount_in_portfolio_inr": None,
        "risk_state": "KNOWN_PUBLIC_DIVIDEND_UNVERIFIED_RETURN_ELIGIBILITY",
    },
)


def build_preentry_risk(intent: dict[str, Any], universe: dict[str, Any]) -> dict:
    """No prices, no holdings, and no hindsight edits to the original cohort."""
    by_symbol = _validate_intent(intent, universe)
    original = [r["symbol"] for r in intent["selected_observations"]]
    if tuple(original) != EXPECTED_SELECTION or len(by_symbol) != 10:
        raise ValueError("original frozen first H021 cohort changed")
    if intent["source"]["current_capture_date_ist"] != "2026-10-09":
        raise ValueError("original H021 decision date changed")
    if intent["entry_plan"]["calendar_open_timestamp_utc"] != "2026-10-12T03:45:00Z":
        raise ValueError("original H021 next-open changed")
    events = [dict(event) for event in KNOWN_EVENTS]
    if any(event["announcement_date"] > intent["source"]["current_capture_date_ist"] for event in events):
        raise ValueError("pre-entry action cannot be inferred from post-capture announcement")
    case_names = {event["symbol"] for event in events}
    if not case_names.issubset(by_symbol):
        raise ValueError("dividend case outside frozen H021 selection")

    risk_rows = []
    for sym in original:
        event = next((ev for ev in events if ev["symbol"] == sym), None)
        risk_rows.append({
            "symbol": sym,
            "isin": by_symbol[sym],
            "known_preentry_dividend_event": event,
            "source_coverage_status": (
                "ONE_KNOWN_EVENT_SECONDARY_SOURCE_NOT_TOTAL_RETURN_APPROVAL"
                if event else "COMPLETE_INTERVAL_OFFICIAL_ACTION_CENSUS_NOT_PERFORMED"
            ),
            "ex_date_and_entitlement_vetted_by_official_source": False,
            "20_session_total_return_comparable": False,
            "60_session_total_return_comparable": False,
            "market_open_proxy_is_executed_position": False,
        })
    return {
        "schema_version": 1,
        "risk_id": RISK_ID,
        "classification": "PUBLIC_PRE_ENTRY_RETURN_BASIS_ALERT_NOT_H021_ALPHA",
        "original_intent_git_blob_sha": INTENT_GIT_BLOB,
        "original_universe_git_blob_sha": UNIVERSE_GIT_BLOB,
        "source_selection_date_ist": "2026-10-09",
        "planned_observation_entry_session": "2026-10-12",
        "planned_observation_entry_utc": "2026-10-12T03:45:00Z",
        "nse_index_benchmark_basis": "PRICE_INDEX_NOT_TRI",
        "frozen_selected_symbols": original,
        "original_h021_selection_unchanged": True,
        "publicly_identified_pre_entry_dividend_count": len(events),
        "publicly_identified_pre_entry_dividend_symbols": sorted(case_names),
        "other_symbols_complete_corporate_action_audit_performed": False,
        "original_exchange_filing_pdfs_verified_for_dividends": False,
        "stock_dividend_cashflows_accounted_for": False,
        "actual_dividend_entitlement_calculated": False,
        "stock_total_return_basis_approved": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
        "source_risk_rows": risk_rows,
        "interpretation": (
            "A Rs5 VEDL dividend announced 8 Oct with reported Oct14 ex/record date "
            "overlaps H021's planned Oct12 official-open price proxy. "
            "It must be source-verified and handled on the same economic return basis "
            "as Nifty500; neither the cash entitlement nor adjusted holding-period "
            "returns can be inferred from the declaration or from raw stock prices."
        ),
    }


def replay_first_cohort(root: Path) -> dict:
    # Original P003 and U001 Git blobs were frozen before today's open.
    comparison, calendar = load_pinned_inputs()
    intent_raw = (root / INTENT_PATH).read_bytes()
    if git_blob_sha(intent_raw) != INTENT_GIT_BLOB:
        raise ValueError("H021 P003 Git blob no longer matches pre-entry decision")
    intent = json.loads(intent_raw)
    if intent != build_first_entry_intent(comparison, calendar):
        raise ValueError("H021 first intent not reproducible from original comparison/calendar")
    universe_raw = (root / UNIVERSE_PATH).read_bytes()
    if git_blob_sha(universe_raw) != UNIVERSE_GIT_BLOB:
        raise ValueError("original U001 Git blob no longer matches source")
    return build_preentry_risk(intent, json.loads(universe_raw))
