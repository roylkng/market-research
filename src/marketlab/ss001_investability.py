from __future__ import annotations

import math
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest

CONTEXT_ID = "SS001-I001-v1"
EXPECTED_D001_ID = "SS001-D001-v1"
EXPECTED_D001_SHA = "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"
EXPECTED_IDENTITY_COUNT = 2319

CRORE = 10_000_000.0
LAKH = 100_000.0
PARTICIPATION_SURFACES = (0.025, 0.05, 0.10)
ORDER_SURFACES_INR = (
    5 * LAKH,
    10 * LAKH,
    25 * LAKH,
    50 * LAKH,
    1 * CRORE,
)


def _finite_positive(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def liquidity_band(
    *,
    observed_session_count: object,
    median_daily_turnover_inr: object,
) -> str:
    if (
        not isinstance(observed_session_count, int)
        or isinstance(observed_session_count, bool)
        or observed_session_count < 15
    ):
        return "OBSERVATION_INSUFFICIENT"
    adv = _finite_positive(median_daily_turnover_inr)
    if adv is None:
        return "OBSERVATION_INSUFFICIENT"
    if adv >= 10 * CRORE:
        return "L1_10CR_PLUS"
    if adv >= 5 * CRORE:
        return "L2_5_TO_10CR"
    if adv >= 2 * CRORE:
        return "L3_2_TO_5CR"
    if adv >= 1 * CRORE:
        return "L4_1_TO_2CR"
    if adv >= 20 * LAKH:
        return "L5_20L_TO_1CR"
    return "L6_BELOW_20L"


def _validate_census(census: dict[str, Any]) -> list[dict[str, Any]]:
    if census.get("census_id") != EXPECTED_D001_ID:
        raise AlphaContractError("SS001 I001 requires frozen D001 census")
    if census.get("census_sha256") != EXPECTED_D001_SHA:
        raise AlphaContractError("SS001 I001 D001 census SHA mismatch")
    if census.get("eq_identity_count") != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("SS001 I001 identity count mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if census.get(field) is not False:
            raise AlphaContractError(f"SS001 I001 requires D001 {field}=false")
    rows = census.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("SS001 I001 D001 rows unavailable")
    return rows


def build_investability_context(census: dict[str, Any]) -> dict[str, Any]:
    rows = _validate_census(census)
    output_rows = []
    bands = Counter()
    state_counts = Counter()

    for row in rows:
        symbol = str(row.get("symbol") or "").upper()
        isin = str(row.get("isin") or "").upper()
        market = row.get("market")
        if not symbol or not isin or not isinstance(market, dict):
            raise AlphaContractError("SS001 I001 row identity/market context is invalid")

        observed = market.get("observed_session_count")
        adv = market.get("median_daily_turnover_inr")
        band = liquidity_band(
            observed_session_count=observed,
            median_daily_turnover_inr=adv,
        )
        bands[band] += 1

        one_day_capacity = None
        days_at_5pct = None
        state = "RESEARCH_ONLY_CAPACITY_UNRESOLVED"
        adv_value = _finite_positive(adv)
        if band != "OBSERVATION_INSUFFICIENT" and adv_value is not None:
            one_day_capacity = {
                "2_5pct_adv_inr": adv_value * 0.025,
                "5pct_adv_inr": adv_value * 0.05,
                "10pct_adv_inr": adv_value * 0.10,
            }
            daily_5pct = adv_value * 0.05
            days_at_5pct = {
                "5_lakh": (5 * LAKH) / daily_5pct,
                "10_lakh": (10 * LAKH) / daily_5pct,
                "25_lakh": (25 * LAKH) / daily_5pct,
                "50_lakh": (50 * LAKH) / daily_5pct,
                "1_crore": (1 * CRORE) / daily_5pct,
            }
            state = "RESEARCH_AND_CAPACITY_CONTEXT_AVAILABLE"
        state_counts[state] += 1

        output_rows.append(
            {
                "symbol": symbol,
                "isin": isin,
                "in_existing_u001": bool(row.get("in_existing_u001")),
                "observed_session_count": observed,
                "median_daily_turnover_inr": adv_value,
                "liquidity_band": band,
                "one_day_capacity": one_day_capacity,
                "execution_days_at_5pct_adv": days_at_5pct,
                "research_capacity_state": state,
                "return_outcomes_opened": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    output = {
        "schema_version": 1,
        "context_id": CONTEXT_ID,
        "classification": "SMALL_SUM_CAPACITY_CONTEXT_NOT_ALPHA",
        "source": {
            "census_id": EXPECTED_D001_ID,
            "census_sha256": EXPECTED_D001_SHA,
            "identity_count": EXPECTED_IDENTITY_COUNT,
            "as_of_completed_session": "2026-10-01",
        },
        "liquidity_band_definitions": {
            "L1_10CR_PLUS": "median ADV >= INR 10 crore",
            "L2_5_TO_10CR": "INR 5 crore <= median ADV < INR 10 crore",
            "L3_2_TO_5CR": "INR 2 crore <= median ADV < INR 5 crore",
            "L4_1_TO_2CR": "INR 1 crore <= median ADV < INR 2 crore",
            "L5_20L_TO_1CR": "INR 20 lakh <= median ADV < INR 1 crore",
            "L6_BELOW_20L": "0 < median ADV < INR 20 lakh",
            "OBSERVATION_INSUFFICIENT": "<15 sessions or nonpositive/unavailable median ADV",
        },
        "participation_surfaces": list(PARTICIPATION_SURFACES),
        "order_surfaces_inr": list(ORDER_SURFACES_INR),
        "liquidity_band_counts": dict(sorted(bands.items())),
        "research_capacity_state_counts": dict(sorted(state_counts.items())),
        "rows": sorted(output_rows, key=lambda item: item["symbol"]),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["context_sha256"] = digest(output)
    return output
