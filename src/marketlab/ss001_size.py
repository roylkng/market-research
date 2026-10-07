from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes

PANEL_ID = "SS001-D003-v1"
EXPECTED_D001_ID = "SS001-D001-v1"
EXPECTED_D001_SHA = "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"
EXPECTED_IDENTITY_COUNT = 2319


class SS001SizeError(ValueError):
    """Raised when official NSE company-size evidence is ambiguous."""


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def parse_trade_info_market_cap(
    payload: dict[str, Any],
    *,
    symbol: str,
    raw: bytes,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("SS001 D003 quote payload must be an object")
    book = payload.get("marketDeptOrderBook")
    if not isinstance(book, dict):
        raise SS001SizeError("marketDeptOrderBook is unavailable")
    trade = book.get("tradeInfo")
    if not isinstance(trade, dict):
        raise SS001SizeError("marketDeptOrderBook.tradeInfo is unavailable")

    total = _finite_number(trade.get("totalMarketCap"))
    ffmc = _finite_number(trade.get("ffmc"))
    if total is None or total <= 0:
        raise SS001SizeError("totalMarketCap must be finite and positive")
    if ffmc is None or ffmc < 0:
        raise SS001SizeError("ffmc must be finite and nonnegative")
    if ffmc > total * 1.01:
        raise SS001SizeError("ffmc exceeds total market cap tolerance")

    return {
        "symbol": symbol.strip().upper(),
        "status": "READY",
        "total_market_cap_inr_crore": total,
        "free_float_market_cap_inr_crore": ffmc,
        "free_float_fraction": ffmc / total,
        "raw_sha256": sha256_bytes(raw),
        "error": None,
    }


def size_band(total_market_cap_inr_crore: object) -> str:
    value = _finite_number(total_market_cap_inr_crore)
    if value is None or value <= 0:
        return "SIZE_UNAVAILABLE"
    if value < 500:
        return "S1_BELOW_500CR"
    if value < 1_000:
        return "S2_500_TO_1000CR"
    if value < 2_500:
        return "S3_1000_TO_2500CR"
    if value < 5_000:
        return "S4_2500_TO_5000CR"
    if value < 10_000:
        return "S5_5000_TO_10000CR"
    if value < 25_000:
        return "S6_10000_TO_25000CR"
    return "S7_25000CR_PLUS"


def _validate_d001(census: dict[str, Any]) -> list[dict[str, Any]]:
    if census.get("census_id") != EXPECTED_D001_ID:
        raise AlphaContractError("SS001 D003 requires frozen D001 census")
    if census.get("census_sha256") != EXPECTED_D001_SHA:
        raise AlphaContractError("SS001 D003 D001 census SHA mismatch")
    if census.get("eq_identity_count") != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("SS001 D003 identity count mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if census.get(field) is not False:
            raise AlphaContractError(f"SS001 D003 requires D001 {field}=false")
    rows = census.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("SS001 D003 D001 rows unavailable")
    return rows


def build_company_size_panel(
    *,
    d001_census: dict[str, Any],
    acquired_rows: list[dict[str, Any]],
    captured_at_utc: str,
) -> dict[str, Any]:
    source_rows = _validate_d001(d001_census)
    source_by_symbol = {
        str(row.get("symbol") or "").upper(): row
        for row in source_rows
        if isinstance(row, dict)
    }
    if len(source_by_symbol) != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("SS001 D003 D001 symbols are not unique")

    acquired_by_symbol: dict[str, dict[str, Any]] = {}
    for row in acquired_rows:
        if not isinstance(row, dict):
            raise TypeError("SS001 D003 acquired rows must be objects")
        symbol = str(row.get("symbol") or "").upper()
        if not symbol or symbol in acquired_by_symbol:
            raise AlphaContractError("SS001 D003 acquired symbols must be unique")
        acquired_by_symbol[symbol] = row
    if set(acquired_by_symbol) != set(source_by_symbol):
        raise AlphaContractError("SS001 D003 source accounting mismatch")

    rows = []
    band_counts: Counter[str] = Counter()
    outside_band_counts: Counter[str] = Counter()
    financial_by_band: Counter[str] = Counter()
    action_by_band: Counter[str] = Counter()
    ready = 0
    outside_ready = 0
    outside_count = 0
    invalid_ffmc_count = 0
    failure_reasons: Counter[str] = Counter()
    turnover_by_band: dict[str, list[float]] = defaultdict(list)

    for symbol in sorted(source_by_symbol):
        context = source_by_symbol[symbol]
        acquired = acquired_by_symbol[symbol]
        in_u001 = bool(context.get("in_existing_u001"))
        if not in_u001:
            outside_count += 1

        is_ready = acquired.get("status") == "READY"
        total = (
            _finite_number(acquired.get("total_market_cap_inr_crore"))
            if is_ready
            else None
        )
        ffmc = (
            _finite_number(acquired.get("free_float_market_cap_inr_crore"))
            if is_ready
            else None
        )
        if is_ready:
            if total is None or total <= 0 or ffmc is None or ffmc < 0:
                raise AlphaContractError(f"{symbol}: READY size row is invalid")
            if ffmc > total * 1.01:
                invalid_ffmc_count += 1
            ready += 1
            if not in_u001:
                outside_ready += 1
        else:
            failure_reasons[str(acquired.get("error") or "UNKNOWN")] += 1

        band = size_band(total)
        band_counts[band] += 1
        if not in_u001:
            outside_band_counts[band] += 1

        financial = context.get("financial_source")
        if isinstance(financial, dict) and financial.get(
            "has_integrated_financial_filing"
        ) is True:
            financial_by_band[band] += 1

        actions = context.get("corporate_actions_1y")
        has_special_action = (
            isinstance(actions, dict)
            and any(
                int(actions.get(key) or 0) > 0
                for key in (
                    "rights",
                    "scheme_or_reorganisation",
                    "buyback",
                    "split_or_consolidation",
                    "bonus",
                    "delisting",
                )
            )
        )
        if has_special_action:
            action_by_band[band] += 1

        market = context.get("market")
        turnover = None
        if isinstance(market, dict):
            turnover = _finite_number(market.get("median_daily_turnover_inr"))
            if turnover is not None and turnover > 0:
                turnover_by_band[band].append(turnover)

        rows.append(
            {
                "symbol": symbol,
                "isin": context.get("isin"),
                "company_name": context.get("company_name"),
                "in_existing_u001": in_u001,
                "source_status": acquired.get("status"),
                "source_raw_sha256": acquired.get("raw_sha256"),
                "source_error": acquired.get("error"),
                "total_market_cap_inr_crore": total,
                "free_float_market_cap_inr_crore": ffmc,
                "free_float_fraction": (
                    ffmc / total
                    if total is not None and total > 0 and ffmc is not None
                    else None
                ),
                "size_band": band,
                "median_daily_turnover_inr": turnover,
                "has_integrated_financial_filing": (
                    financial.get("has_integrated_financial_filing")
                    if isinstance(financial, dict)
                    else None
                ),
                "has_special_action_1y": has_special_action,
                "return_outcomes_opened": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    ready_ratio = ready / EXPECTED_IDENTITY_COUNT
    outside_ready_ratio = outside_ready / outside_count if outside_count else 0.0
    threshold_passes = {
        "complete_identity_accounting": len(rows) == EXPECTED_IDENTITY_COUNT,
        "minimum_total_market_cap_coverage_90pct": ready_ratio >= 0.90,
        "minimum_outside_u001_market_cap_coverage_90pct": (
            outside_ready_ratio >= 0.90
        ),
        "ready_ffmc_within_total_cap_tolerance": invalid_ffmc_count == 0,
    }

    output = {
        "schema_version": 1,
        "panel_id": PANEL_ID,
        "classification": "CURRENT_COMPANY_SIZE_CONTEXT_NOT_ALPHA",
        "captured_at_utc": captured_at_utc,
        "source_d001_census_sha256": EXPECTED_D001_SHA,
        "identity_count": EXPECTED_IDENTITY_COUNT,
        "ready_market_cap_count": ready,
        "ready_market_cap_ratio": ready_ratio,
        "outside_u001_identity_count": outside_count,
        "outside_u001_ready_market_cap_count": outside_ready,
        "outside_u001_ready_market_cap_ratio": outside_ready_ratio,
        "size_band_counts": dict(sorted(band_counts.items())),
        "outside_u001_size_band_counts": dict(sorted(outside_band_counts.items())),
        "financial_source_count_by_size_band": dict(
            sorted(financial_by_band.items())
        ),
        "special_action_symbol_count_by_size_band": dict(
            sorted(action_by_band.items())
        ),
        "median_turnover_inr_by_size_band": {
            band: (
                sorted(values)[len(values) // 2]
                if values
                else None
            )
            for band, values in sorted(turnover_by_band.items())
        },
        "source_failure_reason_counts": dict(sorted(failure_reasons.items())),
        "invalid_ffmc_count": invalid_ffmc_count,
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_size_aware_research_routing": all(
            threshold_passes.values()
        ),
        "rows": rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["panel_sha256"] = digest(output)
    return output
