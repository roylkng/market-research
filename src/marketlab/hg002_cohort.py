from __future__ import annotations

from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest

COHORT_ID = "HG002-D001-v1"
EXPECTED_ROUTER_ID = "HG001-D001-v1"
EXPECTED_ROUTER_SHA = "79e6b068f95c890e4ef88be62ffe2e8dfb94fabbf293770804e64aaa82d6e5ff"
EXPECTED_IDENTITY_COUNT = 2319
EXPECTED_COHORT_COUNT = 28

REQUIRED_LANES = {
    "EARNINGS_INFLECTION",
    "ASSET_OR_CAPACITY_ANOMALY",
    "CURRENT_SPECIAL_SITUATION",
}

L001_P1_VALIDATED_FAMILIES = {
    "BUYBACK",
    "OPEN_OFFER_CONTROL",
    "TENDER_OFFER",
    "DELISTING",
    "ASSET_SALE_DIVESTMENT",
}


def _validate_router(router: dict[str, Any]) -> list[dict[str, Any]]:
    if router.get("router_id") != EXPECTED_ROUTER_ID:
        raise AlphaContractError("HG002 requires frozen HG001 router")
    if router.get("router_sha256") != EXPECTED_ROUTER_SHA:
        raise AlphaContractError("HG002 HG001 router SHA mismatch")
    if router.get("identity_count") != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("HG002 HG001 identity count mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if router.get(field) is not False:
            raise AlphaContractError(f"HG002 requires HG001 {field}=false")
    rows = router.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("HG002 HG001 rows unavailable")
    return rows


def _qualifies(row: dict[str, Any]) -> bool:
    lanes = row.get("active_opportunity_lanes")
    cautions = row.get("asset_caution_flags")
    return (
        row.get("active_opportunity_lane_count") == 3
        and isinstance(lanes, list)
        and set(lanes) == REQUIRED_LANES
        and row.get("governance_caution_count") == 0
        and isinstance(cautions, list)
        and len(cautions) == 0
        and row.get("in_existing_u001") is False
    )


def build_underwriting_cohort(router: dict[str, Any]) -> dict[str, Any]:
    rows = _validate_router(router)
    selected = [row for row in rows if isinstance(row, dict) and _qualifies(row)]
    if len(selected) != EXPECTED_COHORT_COUNT:
        raise AlphaContractError(
            f"HG002 expected {EXPECTED_COHORT_COUNT} qualifying rows, observed {len(selected)}"
        )

    symbols = [str(row.get("symbol") or "").upper() for row in selected]
    if any(not symbol for symbol in symbols) or len(symbols) != len(set(symbols)):
        raise AlphaContractError("HG002 cohort symbols must be unique and non-empty")

    output_rows = []
    validated_ready = 0
    unvalidated_families: Counter[str] = Counter()
    liquidity_counts: Counter[str] = Counter()
    earnings_state_counts: Counter[str] = Counter()

    for row in sorted(selected, key=lambda item: str(item.get("symbol") or "")):
        categories = row.get("special_situation_categories")
        if not isinstance(categories, list):
            raise AlphaContractError("HG002 special-situation categories unavailable")
        category_set = {str(value) for value in categories}
        validated = sorted(category_set & L001_P1_VALIDATED_FAMILIES)
        unvalidated = sorted(category_set - L001_P1_VALIDATED_FAMILIES)
        if validated:
            validated_ready += 1
        unvalidated_families.update(unvalidated)

        liquidity = str(row.get("liquidity_band") or "UNKNOWN")
        liquidity_counts[liquidity] += 1
        earnings_state = str(row.get("earnings_inflection_state") or "UNKNOWN")
        earnings_state_counts[earnings_state] += 1

        output_rows.append(
            {
                "symbol": str(row["symbol"]).upper(),
                "isin": row.get("isin"),
                "earnings_inflection_state": row.get("earnings_inflection_state"),
                "earnings_positive_flags": row.get("earnings_positive_flags"),
                "earnings_negative_flags": row.get("earnings_negative_flags"),
                "earnings_metrics": row.get("earnings_metrics"),
                "asset_opportunity_flags": row.get("asset_opportunity_flags"),
                "special_situation_event_count": row.get(
                    "special_situation_event_count"
                ),
                "special_situation_categories": sorted(category_set),
                "l001_p1_validated_families": validated,
                "l001_p1_validated_family_present": bool(validated),
                "l001_unvalidated_families": unvalidated,
                "promoter_percentage": row.get("promoter_percentage"),
                "promoter_delta_pp": row.get("promoter_delta_pp"),
                "liquidity_band": row.get("liquidity_band"),
                "median_daily_turnover_inr": row.get("median_daily_turnover_inr"),
                "research_capacity_state": row.get("research_capacity_state"),
                "deep_research_workstreams": [
                    "EARNINGS_NORMALIZATION",
                    "ASSET_CAPACITY_VERIFICATION",
                    "SPECIAL_SITUATION_ECONOMICS",
                ],
                "return_outcomes_opened": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    output = {
        "schema_version": 1,
        "cohort_id": COHORT_ID,
        "classification": "TRIPLE_CONVERGENCE_HIDDEN_GEM_UNDERWRITING_COHORT_NOT_ALPHA",
        "source_router_id": EXPECTED_ROUTER_ID,
        "source_router_sha256": EXPECTED_ROUTER_SHA,
        "cohort_count": len(output_rows),
        "l001_p1_validated_family_ready_count": validated_ready,
        "l001_p1_unvalidated_family_counts": dict(
            sorted(unvalidated_families.items())
        ),
        "liquidity_band_counts": dict(sorted(liquidity_counts.items())),
        "earnings_inflection_state_counts": dict(
            sorted(earnings_state_counts.items())
        ),
        "rows": output_rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["cohort_sha256"] = digest(output)
    return output
