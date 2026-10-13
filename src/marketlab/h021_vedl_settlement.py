"""Outcome-blind H021 VEDL T+1/ex-dividend scenario before 14 October 2026.

Reconciles immutable original Oct 9 frozen H021 intent, exact Oct 12
official next-open source, exact Oct 13 post-close source, original Oct 8
issuer dividend announcement, original NSE Oct 14 ex-date, and frozen
cash-market calendar. No fill/settlement/entitlement is inferred.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021_daily_prices import validate_daily_source_observation
from marketlab.h021_entry_observation import validate_entry_observation
from marketlab.h021_first_entry_intent import (
    CALENDAR_PATH,
    COMPARISON_PATH,
    build_first_entry_intent,
    git_blob_sha,
    load_pinned_inputs,
)

AUDIT_ID = "H021-P022-2026-10-13-VEDL-PRE-EX-DATE-SETTLEMENT-REVIEW-v1"
SOURCE_REFS = {
    "frozen_intent": (
        "research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json",
        "e25f77e1c845456473e624899d4748e306b1225b",
    ),
    "entry_original_oct12": (
        "research/prospective/h021/entry-observations/2026-10-12-first-entry-v1.json",
        "172801c8a804f1c8a3f54ef759d12175980cc11e",
    ),
    "daily_original_oct13": (
        "research/prospective/h021/daily-prices/2026-10-13-v1.json",
        "a0aad217d171313426e00af6d234d5df02a45395",
    ),
    "nse_original_vedl_exdate": (
        "research/prospective/h021/dividend-evidence/vedl-2026-10-08/"
        "original-nse-exdate-v1.json",
        "140812e47548f27faa03612119d64c661ab1ed79",
    ),
    "original_vedl_issuer_dividend": (
        "research/prospective/h021/dividend-evidence/vedl-2026-10-08/"
        "source-receipt-v1.json",
        "de2d9889ec303067404ba62c136cd221288ac0ad",
    ),
    "frozen_nse_session_calendar": (
        "research/prospective/calendars/FY27-Q2-2026-09-06/"
        "NSE-CM-FY27Q2-v1.json",
        "9ac614820a67b0f7b20d8170d15b84df3c996b62",
    ),
}
EXCHANGE_T1_POLICY_URL = (
    "https://www.nseclearing.in/clearing-settlement/capital-market/settlement-cycle"
)
EX_DATE_RECORD_DATE_POLICY_URL = (
    "https://support.zerodha.com/category/console/corporate-actions/"
    "ca-others/articles/what-does-ex-date-and-record-date-mean"
)
VEDL = "VEDL"
ISIN = "INE205A01025"
EXPECTED_SOURCE_DAYS = ("2026-10-12", "2026-10-13", "2026-10-14")


def _canonical_hash(value: dict[str, Any]) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_exact_source_records(root: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    sources: dict[str, dict] = {}
    receipts: dict[str, dict] = {}
    for name, (filename, expected) in SOURCE_REFS.items():
        raw = (root / filename).read_bytes()
        actual = git_blob_sha(raw)
        if actual != expected:
            raise ValueError(f"original {name} Git blob changed")
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise TypeError(f"original {name} must be JSON object")
        sources[name] = obj
        receipts[name] = {
            "path": filename,
            "source_git_blob": expected,
            "source_raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    return sources, receipts


def build_pre_ex_date_settlement_review(
    originals: dict[str, dict],
    receipts: dict[str, dict],
    *,
    repo_root: Path,
) -> dict[str, Any]:
    if set(originals) != set(SOURCE_REFS) or set(receipts) != set(SOURCE_REFS):
        raise ValueError("all six original H021 dividend/source contracts required")
    frozen_comparison, source_calendar = load_pinned_inputs(
        comparison_path=repo_root / COMPARISON_PATH,
        calendar_path=repo_root / CALENDAR_PATH,
    )
    intent = originals["frozen_intent"]
    if intent != build_first_entry_intent(frozen_comparison, source_calendar):
        raise ValueError("H021 first intent no longer derived from preregistered comparison")
    selected = intent.get("selected_observations")
    if not isinstance(selected, list) or len(selected) != 10:
        raise ValueError("original ten H021 selections missing")
    if [item["symbol"] for item in selected] != [
        "VEDL", "ETERNAL", "DMART", "IDEA", "ADANIENSOL",
        "JSWSTEEL", "COALINDIA", "INFY", "GAIL", "POWERGRID",
    ]:
        raise ValueError("original H021 top decile was altered")
    planned_entry = intent.get("entry_plan", {})
    if (
        planned_entry.get("session_date_ist") != EXPECTED_SOURCE_DAYS[0]
        or planned_entry.get("calendar_open_timestamp_utc") != "2026-10-12T03:45:00Z"
        or intent.get("portfolio_eligibility_allowed") is not False
        or intent.get("live_capital_allowed") is not False
    ):
        raise ValueError("original first next-open decision or no-capital bound modified")

    entry = originals["entry_original_oct12"]
    daily = originals["daily_original_oct13"]
    validate_entry_observation(entry)
    validate_daily_source_observation(daily)
    if (
        entry.get("source_observation_status") != "FULL_OFFICIAL_OHLC_SOURCE_OBSERVED"
        or entry.get("session_date_ist") != EXPECTED_SOURCE_DAYS[0]
        or entry.get("source_intent_id") != intent["intent_id"]
        or entry.get("observed_official_stock_open_count") != 10
        or entry.get("dividends_and_total_return_basis_verified") is not False
        or daily.get("session_date_ist") != EXPECTED_SOURCE_DAYS[1]
        or daily.get("source_intent_id") != intent["intent_id"]
        or daily.get("capture_state") != "SOURCE_COMPLETE"
        or daily.get("observed_stock_count") != 10
        or daily.get("dividends_adjusted") is not False
    ):
        raise ValueError("original source days or official stock-price state changed")
    first = [row for row in entry["stock_observations"] if row.get("symbol") == VEDL]
    next_day = [row for row in daily["stock_rows"] if row.get("symbol") == VEDL]
    if len(first) != 1 or len(next_day) != 1:
        raise ValueError("VEDL original EPS-selected ISIN price row missing")
    first_row, second_row = first[0], next_day[0]
    if (
        first_row.get("isin") != ISIN
        or first_row.get("series") != "EQ"
        or first_row.get("status") != "OFFICIAL_OHLC_OBSERVED_NOT_EXECUTABLE_FILL"
        or first_row.get("actual_trade_fill_confirmed") is not False
        or first_row.get("open_price_inr") != 265.95
        or second_row.get("isin") != ISIN
        or second_row.get("series") != "EQ"
        or second_row.get("status") != "OFFICIAL_OHLC_NOT_EXECUTABLE_FILL"
        or second_row.get("trade_filled") is not False
    ):
        raise ValueError("VEDL official cash-equity source/entry proxy altered")

    exchange = originals["nse_original_vedl_exdate"]
    issuer = originals["original_vedl_issuer_dividend"]
    event = exchange.get("official_matching_row", {})
    first_issuer = issuer.get("issuer_reported_dividend_terms", {})
    provenance = issuer.get("first_original_announcement_provenance", {})
    if (
        exchange.get("review_id") != "H021-P021-2026-10-14-VEDL-OFFICIAL-EXDATE-v1"
        or exchange.get("original_exchange_ex_date_verified") is not True
        or exchange.get("dividend_cash_per_share_from_original_issuer_inr") != 5
        or exchange.get("selected_symbol") != VEDL
        or exchange.get("selected_isin") != ISIN
        or event.get("symbol") != VEDL
        or event.get("series") != "EQ"
        or event.get("exchange_ex_date") != EXPECTED_SOURCE_DAYS[2]
        or event.get("exchange_record_date_if_present") != EXPECTED_SOURCE_DAYS[2]
        or exchange.get("dividend_cash_entitlement_assessed_or_paid") is not False
        or issuer.get("source_id") != "H021-P012-VEDL-2026-10-08-ORIGINAL-NSE-DIVIDEND-v1"
        or issuer.get("original_pdf_sha256") != (
            "abdd026339469b9e51ab75fb2a37551be23812dcc037c875759cd79a8e6cb364"
        )
        or first_issuer.get("issuer_reported_dividend_per_share_inr") != 5
        or first_issuer.get("issuer_reported_record_date_ist") != EXPECTED_SOURCE_DAYS[2]
        or provenance.get("source_was_public_before_oct12_planned_entry") is not True
        or issuer.get("dividend_cash_payment_proven") is not False
    ):
        raise ValueError("verified original VEDL ex-date/issuer dividend source changed")

    snapshot = load_calendar_snapshot(repo_root / SOURCE_REFS[
        "frozen_nse_session_calendar"
    ][0])
    if snapshot.version != "NSE-CM-FY27Q2-v1":
        raise ValueError("unexpected exchange session calendar version")
    calendar_days = [row.session_date for row in snapshot.sessions]
    positions = [calendar_days.index(day) if day in calendar_days else -1 for day in EXPECTED_SOURCE_DAYS]
    if positions[0] < 0 or positions != list(range(positions[0], positions[0] + 3)):
        raise ValueError("Oct12/13/14 must be consecutive official NSE cash-market sessions")
    if any(
        "2026-10-12" <= special <= "2026-10-14"
        for special in snapshot.unresolved_special_dates
    ):
        raise ValueError("unverified special session might affect T+1 sequence")

    result: dict[str, Any] = {
        "schema_version": 1,
        "review_id": AUDIT_ID,
        "classification": "PRE_EX_DIVIDEND_CONDITIONAL_ENTITLEMENT_RISK_NOT_REALIZED_RETURN",
        "as_of_market_close_ist": "2026-10-13",
        "source_receipts": receipts,
        "security": {"symbol": VEDL, "isin": ISIN, "equity_series": "EQ"},
        "original_issuer_dividend_per_share_inr": 5,
        "issuer_original_notice_public_before_oct12_selection_entry": True,
        "original_issuer_record_date_ist": "2026-10-14",
        "official_nse_exchange_ex_date_ist": "2026-10-14",
        "official_nse_exchange_record_date_ist": "2026-10-14",
        "last_cum_dividend_regular_market_session_ist": "2026-10-13",
        "planned_research_entry_proxy_date_ist": "2026-10-12",
        "planned_research_entry_proxy_utc": "2026-10-12T03:45:00Z",
        "ordinary_t1_candidate_settlement_session_ist": "2026-10-13",
        "normal_cash_market_t1_reference": {
            "source_url": EXCHANGE_T1_POLICY_URL,
            "authority": "NSE_CLEARING_OFFICIAL_PUBLIC_GUIDANCE",
            "source_full_publication_timestamp_and_raw_snapshot_pinned": False,
            "actual_trade_clearing_completed_for_h021": False,
            "unexpected_settlement_holiday_or_short_delivery_excluded": False,
        },
        "ex_date_and_cum_entitlement_reference": {
            "source_url": EX_DATE_RECORD_DATE_POLICY_URL,
            "purpose": "EX_DATE_RECORD_DATE_DISTINCTION_UNDER_NORMAL_T1",
            "source_raw_snapshot_pinned": False,
        },
        "conditional_hypothetical_position_scenario": {
            "assumed_entry_executed_oct12_first_open": True,
            "assumed_normal_t1_delivery_by_oct13": True,
            "assumed_share_held_across_oct14_record_date": True,
            "paper_scenario_classification": (
                "POTENTIAL_DIVIDEND_ENTITLEMENT_IF_ALL_SETTLEMENT_AND_HOLDING_ASSUMPTIONS_HOLD"
            ),
            "actual_position_exist_confirmed": False,
            "actual_normal_t1_settlement_confirmed": False,
            "actual_record_date_demat_holder_confirmed": False,
            "actual_dividend_credit_confirmed": False,
            "cash_dividend_added_to_h021_return": False,
        },
        "undisputed_source_measurement_states": {
            "oct12_official_next_open_observed_not_tradable_fill": True,
            "oct13_official_eq_day_observed_not_trade": True,
            "nse_ex_and_record_date_matched_to_issuer": True,
            "index_is_nifty_500_price_index_not_total_return": True,
            "oct14_ex_dividend_price_not_yet_used_as_outcome": True,
            "all_h021_stocks_complete_action_dividend_audit": False,
        },
        "return_basis_action_required": (
            "CASH_DIVIDEND_ENTITLEMENT_AND_SHARE_ACTIONS_MUST_BE_RESOLVED_BEFORE "
            "STOCK_PRICE_ONLY_H021_EXCESS_RETURN_OR_TOTAL_RETURN_INTERPRETATION"
        ),
        "actual_buy_execution_and_slippage_verified": False,
        "cash_entitlement_independently_verified": False,
        "payable_cash_settlement_or_dividend_credit_verified": False,
        "realized_h021_returns_computed": False,
        "future_h021_20_or_60_session_outcomes_opened": False,
        "original_h021_top_decile_changed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["packet_sha256"] = _canonical_hash(result)
    return result


def validate_pre_ex_date_settlement_review(report: dict[str, Any]) -> None:
    if report.get("review_id") != AUDIT_ID:
        raise ValueError("wrong original H021 ex-dividend audit")
    digest = report.get("packet_sha256")
    unsigned = {k: v for k, v in report.items() if k != "packet_sha256"}
    if not isinstance(digest, str) or digest != _canonical_hash(unsigned):
        raise ValueError("H021 pre-ex cash/dividend scenario record changed")
    if (
        report.get("official_nse_exchange_ex_date_ist") != "2026-10-14"
        or report.get("last_cum_dividend_regular_market_session_ist") != "2026-10-13"
        or report.get("ordinary_t1_candidate_settlement_session_ist") != "2026-10-13"
    ):
        raise ValueError("original ex-date/settlement chronology changed")
    for key in (
        "actual_buy_execution_and_slippage_verified",
        "cash_entitlement_independently_verified",
        "payable_cash_settlement_or_dividend_credit_verified",
        "realized_h021_returns_computed",
        "future_h021_20_or_60_session_outcomes_opened",
        "original_h021_top_decile_changed",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if report.get(key) is not False:
            raise ValueError(f"ex-dividend source scenario cannot promote {key}")
