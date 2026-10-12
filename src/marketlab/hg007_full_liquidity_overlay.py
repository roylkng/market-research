"""Attach verified 20-session cash-market liquidity to 28 original HG007 cases.

The result is an ex-post descriptive execution-risk *source context*, not
an entry/exit model, market-cap upgrade, ranking or return forecast.
Off-EQ BE-series observations must NEVER be used to fill missing EQ days.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from marketlab.hg007_28_liquidity import validate_twenty_day_all_28
from marketlab.hg007_eq_absence_review import validate_missing_eq_series_review

AUDIT_ID = "HG007-P043-28-CASE-ORIGINAL-EQ-LIQUIDITY-OVERLAY-v1"
SOURCE_BLOBS = {
    "HG007_CAPITAL_CASEWORK": (
        "research/hg007/hg007-p009-28-case-capital-readiness-overlay-v1.json",
        "a502a582e93b408baba38dca7b95532836646700",
    ),
    "NSE_TWENTY_SESSION_ALL_28": (
        "research/hg007/twenty-session-liquidity/twenty-session-28-stock-v1.json",
        "a01b9823a29cdfe94f5e2f21e84159b66a949c75",
    ),
    "NSE_EQ_SERIES_ABSENCE_REVIEW": (
        "research/hg007/twenty-session-liquidity/eq-absence-series-review-v1.json",
        "dee98b4434f6c06209660d7675f6cf2085da5d8b",
    ),
}
INR_CRORE = 10_000_000
COMPARISON_TICKETS = (100_000, 1_000_000)
REFERENCE_PARTICIPATION = 0.01
BAND_KEYS = (
    "MEDIAN_DAILY_VALUE_BELOW_0_1_CR",
    "MEDIAN_DAILY_VALUE_0_1_TO_BELOW_1_CR",
    "MEDIAN_DAILY_VALUE_1_TO_BELOW_10_CR",
    "MEDIAN_DAILY_VALUE_AT_LEAST_10_CR",
    "INCOMPLETE_EQ_SERIES_WITH_SEPARATE_BE_OBSERVATIONS",
)


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_source_packets(repo_root: Path) -> tuple[dict, dict, dict, dict[str, dict]]:
    packets: dict[str, dict[str, Any]] = {}
    receipts: dict[str, dict] = {}
    for source, (path, expected_blob) in SOURCE_BLOBS.items():
        raw = (repo_root / path).read_bytes()
        actual = _git_blob(raw)
        if actual != expected_blob:
            raise ValueError(f"{source}: frozen original Git source blob changed")
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise TypeError(f"{source}: source is not a JSON object")
        packets[source] = obj
        receipts[source] = {
            "path": path,
            "git_blob_sha": actual,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    validate_twenty_day_all_28(packets["NSE_TWENTY_SESSION_ALL_28"])
    validate_missing_eq_series_review(packets["NSE_EQ_SERIES_ABSENCE_REVIEW"])
    return (
        packets["HG007_CAPITAL_CASEWORK"],
        packets["NSE_TWENTY_SESSION_ALL_28"],
        packets["NSE_EQ_SERIES_ABSENCE_REVIEW"],
        receipts,
    )


def _band(median: float) -> str:
    if median < 0.1:
        return BAND_KEYS[0]
    if median < 1:
        return BAND_KEYS[1]
    if median < 10:
        return BAND_KEYS[2]
    return BAND_KEYS[3]


def _finite_nonnegative_number(value: Any, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label}: invalid historical turnover number")
    return float(value)


def build_liquidity_readiness(
    original: dict[str, Any],
    all28: dict[str, Any],
    series: dict[str, Any],
    *,
    provenance: dict[str, dict],
) -> dict[str, Any]:
    if (
        original.get("overlay_id") != "HG007-P009-POST-QIP-28-CASE-CAPITAL-READINESS-v1"
        or original.get("original_hg007_cohort_count_preserved") != 28
        or original.get("live_capital_allowed") is not False
        or original.get("company_probabilities_published") != 0
    ):
        raise ValueError("original 28-company capitalization context changed")
    cases = original.get("casework_with_capital_readiness")
    if not isinstance(cases, list) or len(cases) != 28:
        raise ValueError("original 28-name HG007 casework absent")
    selected = [row.get("symbol") for row in cases if isinstance(row, dict)]
    if len(selected) != 28 or len(set(selected)) != 28:
        raise ValueError("original 28-company identities duplicated")

    if (
        all28.get("audit_id") != "HG007-P041-28-COMPANY-20-SESSION-ORIGINAL-NSE-TURNOVER-v1"
        or all28.get("original_outside_u001_symbol_count") != 28
        or all28.get("original_completed_sessions") != 20
        or all28.get("source_window_first_session") != "2026-09-10"
        or all28.get("source_window_last_session") != "2026-10-09"
        or all28.get("complete_20_session_equity_company_count") != 26
        or all28.get("incomplete_or_changed_identity_company_count") != 2
        or all28.get("source_returns_or_alpha_computed") is not False
        or all28.get("live_capital_allowed") is not False
    ):
        raise ValueError("source 20-session EQ comparison boundary changed")
    rows = all28.get("casework")
    if not isinstance(rows, list) or len(rows) != 28:
        raise ValueError("source NSE twenty-day per-company records missing")
    if [x.get("symbol") for x in rows] != all28.get("original_selected_symbol_order"):
        raise ValueError("source NSE liquidity cohort order changed")
    if set(selected) != set(all28["original_selected_symbol_order"]):
        raise ValueError("original 28 companies differ from historical source cohort")
    by_symbol = {row["symbol"]: row for row in rows}

    if (
        series.get("audit_id") != "HG007-P042-2026-10-12-ORIGINAL-NSE-ABSENT-EQ-SERIES-REVIEW-v1"
        or series.get("original_hg002_company_count_preserved") != 28
        or series.get("source_session_count") != 20
        or series.get("original_eq_missing_observations") != 16
        or series.get("off_equity_series_rows_counted_in_equity_turnover") is not False
        or series.get("missing_eq_days_treated_as_zero_turnover") is not False
        or series.get("executability_verified") is not False
    ):
        raise ValueError("original non-EQ series source scope changed")
    classified = series.get("findings")
    if not isinstance(classified, list) or len(classified) != 2:
        raise ValueError("NSE BE source findings for exactly two names required")
    alternate = {row["symbol"]: row for row in classified}
    if (
        len(alternate) != 2
        or set(alternate) != {"ORBTEXP", "RETAIL"}
        or series.get("examined_names_missing_equity_series") != ["ORBTEXP", "RETAIL"]
    ):
        raise ValueError("non-EQ series source identities changed")

    completed = []
    bands: dict[str, list[str]] = {key: [] for key in BAND_KEYS}
    thin_direct_cases: list[str] = []
    for selected_case in cases:
        symbol = selected_case["symbol"]
        source = by_symbol[symbol]
        eq_count = source.get("official_20_session_eq_rows_observed")
        if type(eq_count) is not int or not 0 <= eq_count <= 20:
            raise ValueError(f"{symbol}: invalid official EQ observation count")
        enriched = deepcopy(selected_case)
        if source.get("exact_20_session_coverage_complete") is True:
            if symbol in alternate or eq_count != 20 or source.get("missing_or_invalid_session_rows"):
                raise ValueError(f"{symbol}: source claims complete EQ but has missing days")
            if source.get("identity_continuous_in_original_window") is not True:
                raise ValueError(f"{symbol}: company ISIN continuity unverified")
            stat = source.get("turnover_statistics_if_complete")
            if not isinstance(stat, dict):
                raise TypeError(f"{symbol}: complete official NSE turnover statistics missing")
            median = _finite_nonnegative_number(
                stat.get("median_daily_traded_value_inr_crore"), "20-session median"
            )
            if median <= 0:
                raise ValueError(f"{symbol}: zero official median cannot imply a fill")
            ratios: dict[str, float] = {}
            original_ratios = stat.get("ticket_to_one_percent_of_median_turnover")
            if not isinstance(original_ratios, dict):
                raise TypeError(f"{symbol}: original published comparison ratios missing")
            for ticket in COMPARISON_TICKETS:
                illustrative_ratio = ticket / (REFERENCE_PARTICIPATION * median * INR_CRORE)
                original_ratio = original_ratios.get(str(ticket))
                if type(original_ratio) not in (int, float) or not math.isclose(
                    illustrative_ratio, original_ratio, rel_tol=1e-10, abs_tol=1e-10
                ):
                    raise ValueError(f"{symbol}: source ticket-to-turnover ratio changed")
                ratios[str(ticket)] = illustrative_ratio
            market_band = _band(median)
            bands[market_band].append(symbol)
            enriched["historical_eq_source_readiness"] = {
                "state": "COMPLETE_20_EQ_SESSIONS_HISTORICAL_ONLY",
                "source_eq_session_count": 20,
                "source_eq_isin": source["observed_isins"][0],
                "median_daily_cash_market_value_traded_inr_crore": median,
                "p10_daily_cash_market_value_traded_inr_crore": stat[
                    "p10_daily_traded_value_inr_crore"
                ],
                "oct09_original_cash_market_value_traded_inr_crore": stat[
                    "oct09_daily_traded_value_inr_crore"
                ],
                "historical_median_value_band": market_band,
                "illustrative_ticket_to_one_percent_historical_median_ratios": ratios,
                "ticket_quotients_predict_trading_days_or_fills": False,
                "current_bid_ask_depth_spread_slippage_verified": False,
                "new_investment_opportunity_ranking_from_liquidity": False,
            }
            if (
                enriched.get("hg003_thread_state")
                in {"ACTIVE_DIRECT_CATALYST", "PROCEDURAL_DIRECT_REVIEW"}
                and median < 1
            ):
                thin_direct_cases.append(symbol)
        else:
            review = alternate.get(symbol)
            if review is None or source.get("turnover_statistics_if_complete") is not None:
                raise ValueError(f"{symbol}: incomplete EQ series lacks verified BE review")
            if review.get("missing_eq_day_count") != 20 - eq_count:
                raise ValueError(f"{symbol}: inconsistent original EQ/BE day accounting")
            gaps = review.get("missing_eq_day_evidence")
            if not isinstance(gaps, list) or len(gaps) != 20 - eq_count:
                raise ValueError(f"{symbol}: missing official non-EQ day evidence")
            if len(source.get("missing_or_invalid_session_rows", [])) != len(gaps):
                raise ValueError(f"{symbol}: original EQ source missing dates altered")
            original_missing = {row["session"] for row in source["missing_or_invalid_session_rows"]}
            if original_missing != {row["session_date"] for row in gaps}:
                raise ValueError(f"{symbol}: alternative series not on missing EQ dates")
            non_eq = sorted({
                trade["exchange_series"]
                for gap in gaps
                for trade in gap["same_symbol_non_eq_rows"]
            })
            if non_eq != ["BE"] or not all(
                gap.get("non_eq_isin_matches_prior_eq_isin") is True
                and gap.get("classification")
                == "OFFICIAL_NON_EQ_SERIES_TURNOVER_OBSERVED_NOT_EQ_TRADE"
                for gap in gaps
            ):
                raise ValueError(f"{symbol}: non-EQ classification/ISIN not source-verified")
            bands[BAND_KEYS[4]].append(symbol)
            enriched["historical_eq_source_readiness"] = {
                "state": "PARTIAL_EQ_SESSIONS_WITH_SEPARATELY_VERIFIED_BE_SERIES",
                "source_eq_session_count": eq_count,
                "source_be_series_sessions_not_imputed": len(gaps),
                "source_be_series_tags": non_eq,
                "full_20day_eq_median_value_traded_inr_crore": None,
                "historical_median_value_band": BAND_KEYS[4],
                "illustrative_ticket_to_one_percent_historical_median_ratios": None,
                "be_series_order_execution_and_settlement_verified": False,
                "zero_trading_days_proven": False,
                "recent_stock_suspension_proven": False,
                "new_investment_opportunity_ranking_from_liquidity": False,
            }
        enriched["live_capital_allowed"] = False
        enriched["portfolio_eligibility_allowed"] = False
        enriched["company_expected_returns_calculated"] = False
        completed.append(enriched)

    if len(completed) != 28 or sum(len(values) for values in bands.values()) != 28:
        raise ValueError("20-session cohort classification accounting incomplete")
    if sum(len(bands[x]) for x in BAND_KEYS[:4]) != 26:
        raise ValueError("20-session complete source bucket accounting changed")

    return {
        "schema_version": 1,
        "overlay_id": AUDIT_ID,
        "classification": "POSTHOC_HISTORICAL_28_STOCK_LIQUIDITY_CONTEXT_NOT_EXECUTABILITY",
        "source_evidence_as_of_date_ist": "2026-10-09",
        "assembled_date_ist": "2026-10-13",
        "source_provenance": provenance,
        "original_hg002_selected_count_preserved": 28,
        "twenty_session_EQ_complete_company_count": 26,
        "twenty_session_EQ_partial_BE_verified_company_count": 2,
        "historical_cash_turnover_bands_not_investment_ranks": bands,
        "direct_or_procedural_with_median_daily_turnover_below_one_crore": (
            sorted(thin_direct_cases)
        ),
        "original_case_economics_prices_and_selection_unmodified": True,
        "company_cases": completed,
        "source_date_and_past_trading_are_not_forward_predictive": True,
        "bid_ask_depth_spread_and_actual_ticket_execution_verified": False,
        "total_return_corporate_action_dividend_basis_verified": False,
        "portfolio_eligibility_allowed": False,
        "investment_recommendations_generated": False,
        "alpha_discovery_or_forward_returns_calculated": False,
        "live_capital_allowed": False,
    }
