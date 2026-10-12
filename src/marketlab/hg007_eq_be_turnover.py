"""Source-bound mixed NSE EQ/BE *historical traded-value* context.

P041 preserves 26 complete EQ-only observations and two incomplete EQ-only
names; P042 proved 11 ORBTEXP and five RETAIL missing EQ days had positive
same-ISIN NSE BE trade-for-trade turnover. Combine ONLY recorded traded value
for a separate descriptive mixed-settlement view, never execution or alpha.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from copy import deepcopy
from pathlib import Path
from typing import Any

from marketlab.hg007_28_liquidity import validate_twenty_day_all_28
from marketlab.hg007_eq_absence_review import validate_missing_eq_series_review
from marketlab.hg007_liquidity_history import _nearest_rank

AUDIT_ID = "HG007-P043-28-COMPANY-MIXED-EQ-BE-SETTLEMENT-CONTEXT-v1"
P041_PATH = Path(
    "research/hg007/twenty-session-liquidity/twenty-session-28-stock-v1.json"
)
P041_BLOB = "a01b9823a29cdfe94f5e2f21e84159b66a949c75"
P042_PATH = Path(
    "research/hg007/twenty-session-liquidity/eq-absence-series-review-v1.json"
)
P042_BLOB = "dee98b4434f6c06209660d7675f6cf2085da5d8b"
FULL_COHORT_COUNT = 28
SESSIONS = 20
SERIES_TFT_EXPLANATION = (
    "NSE BE is trade-for-trade for fully-paid equity; individual "
    "settlement and no netting. Historical traded value does not "
    "represent EQ rolling-settlement fills or executable ticket capacity."
)
NSE_SERIES_LEGEND = "https://www.nseindia.com/static/market-data/legend-of-series"
NSE_TFT_RULES = "https://www.nseindia.com/regulations/movement-securities-periodic-review"
INR_CRORE = 10_000_000
REFERENCE_TICKET_INR = (100_000, 1_000_000)
REFERENCE_TURNOVER_PARTICIPATION = 0.01
MIXED_COMPANIES = {"ORBTEXP": (9, 11), "RETAIL": (15, 5)}


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _hash(obj: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            obj, sort_keys=True, separators=(",", ":"), allow_nan=False,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def load_frozen_sources(root: Path) -> tuple[dict, dict, dict]:
    receipt: dict[str, dict] = {}
    inputs = []
    for label, path, blob in [
        ("original_all_28", P041_PATH, P041_BLOB),
        ("original_eq_absence_review", P042_PATH, P042_BLOB),
    ]:
        raw = (root / path).read_bytes()
        if _git_blob(raw) != blob:
            raise ValueError(f"{label}: original source Git blob no longer matches")
        packet = json.loads(raw)
        if not isinstance(packet, dict):
            raise TypeError(f"{label}: exact original packet must be JSON object")
        receipt[label] = {
            "path": str(path), "git_blob_sha": blob,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        inputs.append(packet)
    source_28, missing = inputs
    validate_twenty_day_all_28(source_28)
    validate_missing_eq_series_review(missing)
    return source_28, missing, receipt


def _source_number(value: object, field: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field}: official reported turnover must be finite positive")
    return float(value)


def build_mixed_series_context(
    all28: dict[str, Any],
    missing: dict[str, Any],
    *,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    selected = all28.get("original_selected_symbol_order")
    old_cases = all28.get("casework")
    findings = missing.get("findings")
    if (
        not isinstance(selected, list)
        or len(selected) != FULL_COHORT_COUNT
        or len(set(selected)) != FULL_COHORT_COUNT
        or not isinstance(old_cases, list)
        or len(old_cases) != FULL_COHORT_COUNT
        or not isinstance(findings, list)
        or len(findings) != len(MIXED_COMPANIES)
        or missing.get("examined_names_missing_equity_series") != sorted(MIXED_COMPANIES)
        or missing.get("original_eq_missing_observations") != 16
        or all28.get("source_window_last_session") != "2026-10-09"
    ):
        raise ValueError("historical 28-name / 16-day original study identity changed")
    by_missing = {item["symbol"]: item for item in findings}
    if set(by_missing) != set(MIXED_COMPANIES):
        raise ValueError("missing-EQ cohort not the original two selected names")

    result = []
    for old in old_cases:
        symbol = old["symbol"]
        assert symbol in selected
        if old.get("live_capital_allowed") is not False:
            raise ValueError("original stock source cannot authorize capital")
        days = old.get("daily_source_rows")
        if not isinstance(days, list) or len(days) != SESSIONS:
            raise ValueError(f"{symbol}: original 20 sessions missing")
        if symbol not in MIXED_COMPANIES:
            if old.get("exact_20_session_coverage_complete") is not True:
                raise ValueError("non-mixed company lost original EQ source coverage")
            ref = deepcopy(old["turnover_statistics_if_complete"])
            if not isinstance(ref, dict):
                raise TypeError("EQ original liquidity statistics absent")
            result.append({
                "symbol": symbol,
                "settlement_regime": "ONLY_EQ_ORIGINAL_20_DAY_SOURCE",
                "source_eq_count": SESSIONS,
                "source_be_count": 0,
                "company_original_eq_20day_statistics_unmodified": ref,
                "mixed_series_turnover_statistics": None,
                "source_day_values": None,
                "mixed_settlement_fill_simulation_authorized": False,
                "real_position_capacity_verified": False,
                "live_capital_allowed": False,
            })
            continue

        eq_expected, be_expected = MIXED_COMPANIES[symbol]
        if (
            old.get("official_20_session_eq_rows_observed") != eq_expected
            or old.get("exact_20_session_coverage_complete") is not False
            or old.get("turnover_statistics_if_complete") is not None
            or len(old.get("observed_isins", [])) != 1
        ):
            raise ValueError(f"{symbol}: original EQ history/count no longer agrees")
        case = by_missing[symbol]
        if (
            case.get("missing_eq_day_count") != be_expected
            or case.get("current_tradability_proven") is not False
            or case.get("source_classification_counts") != {
                "OFFICIAL_NON_EQ_SERIES_TURNOVER_OBSERVED_NOT_EQ_TRADE": be_expected
            }
        ):
            raise ValueError(f"{symbol}: earlier non-EQ source status changed")
        gap_days = case.get("missing_eq_day_evidence")
        if not isinstance(gap_days, list) or len(gap_days) != be_expected:
            raise ValueError(f"{symbol}: original BE day source missing")
        by_gap = {row["session_date"]: row for row in gap_days}
        if len(by_gap) != be_expected:
            raise ValueError(f"{symbol}: duplicate original BE source date")

        matched_rows = []
        count_eq = count_be = 0
        original_isin = old["observed_isins"][0]
        for day in days:
            day_id = day["session"]
            state = day.get("state")
            if state == "EXACT_NSE_EQ_OHLC_AND_TURNOVER_OBSERVED":
                if day_id in by_gap or day.get("isin") != original_isin:
                    raise ValueError(f"{symbol}/{day_id}: original EQ/ISIN source conflict")
                value = _source_number(day["traded_value_inr"], "EQ traded value")
                series = "EQ"
                count_eq += 1
            elif state == "OFFICIAL_EQ_ROW_MISSING_NO_SUBSTITUTION":
                record = by_gap.get(day_id)
                if record is None:
                    raise ValueError(f"{symbol}/{day_id}: missing original source BE event")
                candidates = record.get("same_symbol_non_eq_rows")
                if (
                    record.get("classification") != (
                        "OFFICIAL_NON_EQ_SERIES_TURNOVER_OBSERVED_NOT_EQ_TRADE"
                    )
                    or record.get("non_eq_isin_matches_prior_eq_isin") is not True
                    or record.get("observed_original_non_eq_isins") != [original_isin]
                    or not isinstance(candidates, list)
                    or len(candidates) != 1
                ):
                    raise ValueError(f"{symbol}/{day_id}: BE source proof/identity insufficient")
                candidate = candidates[0]
                if (
                    candidate.get("exchange_series") != "BE"
                    or candidate.get("isin") != original_isin
                    or candidate.get("symbol") != symbol
                    or candidate.get("valid_positive_executed_turnover") is not True
                ):
                    raise ValueError(f"{symbol}/{day_id}: not a valid original BE stock event")
                value = _source_number(
                    candidate["reported_traded_value_inr"], "BE traded value"
                )
                if (
                    _source_number(candidate["reported_shares_traded"], "BE traded volume") <= 0
                    or _source_number(candidate["reported_transaction_count"], "BE trade count")
                    <= 0
                ):
                    raise ValueError("reported BE transaction counts must be positive")
                series = "BE"
                count_be += 1
            else:
                raise ValueError(f"{symbol}/{day_id}: unsupported source trading state")
            matched_rows.append({
                "session_date": day_id,
                "source_series": series,
                "isin": original_isin,
                "reported_value_traded_inr": value,
                "paper_equity_execution_price_substituted": False,
            })

        if count_eq != eq_expected or count_be != be_expected or len(matched_rows) != SESSIONS:
            raise ValueError(f"{symbol}: EQ and BE original 20-day reconciliation failed")
        if set(by_gap) != {x["session_date"] for x in matched_rows if x["source_series"] == "BE"}:
            raise ValueError(f"{symbol}: not all original BE source dates used")
        daily_values = [x["reported_value_traded_inr"] for x in matched_rows]
        median = statistics.median(daily_values)
        p10 = _nearest_rank(daily_values, 10)
        mixed_stats = {
            "source_count": SESSIONS,
            "median_mixed_eq_be_daily_value_inr_crore": median / INR_CRORE,
            "p10_mixed_eq_be_daily_value_inr_crore": p10 / INR_CRORE,
            "p25_mixed_eq_be_daily_value_inr_crore": (
                _nearest_rank(daily_values, 25) / INR_CRORE
            ),
            "min_mixed_eq_be_daily_value_inr_crore": min(daily_values) / INR_CRORE,
            "max_mixed_eq_be_daily_value_inr_crore": max(daily_values) / INR_CRORE,
            "illustrative_ticket_to_one_pct_of_mixed_median": {
                str(ticket): ticket / (REFERENCE_TURNOVER_PARTICIPATION * median)
                for ticket in REFERENCE_TICKET_INR
            },
            "mixed_series_median_is_executable_capacity": False,
            "be_turnover_is_equivalent_to_eq_fill_or_netting": False,
            "multiple_settlement_regimes_in_window": True,
        }
        result.append({
            "symbol": symbol,
            "settlement_regime": "MIXED_EQ_AND_BE_TRADE_FOR_TRADE_HISTORICAL_TURNOVER",
            "source_eq_count": count_eq,
            "source_be_count": count_be,
            "original_eq_only_20day_statistics_still_blocked": True,
            "company_original_eq_20day_statistics_unmodified": None,
            "mixed_series_turnover_statistics": mixed_stats,
            "source_day_values": matched_rows,
            "cash_market_source_traded_for_all_20_days": True,
            "broker_be_eligibility_verified": False,
            "bid_ask_spread_market_depth_verified": False,
            "mixed_settlement_fill_simulation_authorized": False,
            "real_position_capacity_verified": False,
            "live_capital_allowed": False,
        })

    if [row["symbol"] for row in result] != selected:
        raise ValueError("HG002 original 28-name ordering changed")
    out = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "SOURCE_PINNED_EQ_BE_SETTLEMENT_MIX_NOT_AN_INVESTABLE_RETURN",
        "original_company_selection_count": FULL_COHORT_COUNT,
        "original_company_order": selected,
        "original_eq_only_complete_company_count": 26,
        "original_mixed_eq_be_company_count": 2,
        "source_original_market_sessions": SESSIONS,
        "source_first_session": "2026-09-10",
        "source_last_session": "2026-10-09",
        "source_receipts": provenance,
        "nse_public_series_legend": NSE_SERIES_LEGEND,
        "nse_trade_for_trade_rules": NSE_TFT_RULES,
        "nse_be_settlement_interpretation": SERIES_TFT_EXPLANATION,
        "company_context": result,
        "original_eq_only_research_record_overwritten": False,
        "historical_data_measured_after_stock_selection": True,
        "source_alpha_or_equity_returns_calculated": False,
        "broker_netting_execution_slippage_verified": False,
        "future_trade_size_or_trade_probability_published": False,
        "investment_recommendations_created": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    out["packet_sha256"] = _hash(out)
    return out


def validate_mixed_series_context(packet: dict[str, Any]) -> None:
    if (
        packet.get("audit_id") != AUDIT_ID
        or packet.get("original_company_selection_count") != FULL_COHORT_COUNT
        or len(packet.get("company_context", [])) != FULL_COHORT_COUNT
        or packet.get("original_mixed_eq_be_company_count") != 2
    ):
        raise ValueError("unrecognized original HG007 mixed-settlement study")
    digest = packet.get("packet_sha256")
    if not isinstance(digest, str) or _hash({
        k: v for k, v in packet.items() if k != "packet_sha256"
    }) != digest:
        raise ValueError("historical NSE settlement source packet digest changed")
    if [row.get("symbol") for row in packet["company_context"]] != packet.get(
        "original_company_order"
    ):
        raise ValueError("historical source company order no longer frozen")
    observed_mixed = {
        row["symbol"]: row for row in packet["company_context"]
        if row["settlement_regime"] == "MIXED_EQ_AND_BE_TRADE_FOR_TRADE_HISTORICAL_TURNOVER"
    }
    if set(observed_mixed) != set(MIXED_COMPANIES):
        raise ValueError("mixed-settlement cohort selection changed")
    for symbol, (eq, be) in MIXED_COMPANIES.items():
        case = observed_mixed[symbol]
        if case["source_eq_count"] != eq or case["source_be_count"] != be:
            raise ValueError("original EQ/BE trading series observation counts changed")
        if len(case.get("source_day_values", [])) != SESSIONS:
            raise ValueError("original 20 completed trade-series sessions missing")
    for field in (
        "original_eq_only_research_record_overwritten",
        "source_alpha_or_equity_returns_calculated",
        "broker_netting_execution_slippage_verified",
        "future_trade_size_or_trade_probability_published",
        "investment_recommendations_created",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if packet.get(field) is not False:
            raise ValueError(f"mixed-settlement historical source cannot enable {field}")
