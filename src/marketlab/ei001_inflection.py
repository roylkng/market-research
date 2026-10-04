from __future__ import annotations

import math
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest

ROUTER_ID = "EI001-S001-v1"
EXPECTED_PANEL_ID = "EI001-D002-v1"
EXPECTED_PANEL_SHA256 = "14fdc99444ff8c1c62cbef58db91e51cb4cb6730c1259bccb98df979366272cd"
EXPECTED_IDENTITY_COUNT = 2319

OPPORTUNITY_FLAGS = (
    "BROAD_GROWTH_LEVERAGE",
    "STRONG_GROWTH",
    "MARGIN_INFLECTION",
    "PROFIT_TURNAROUND",
)
CAUTION_FLAGS = (
    "LOW_BASE_PAT",
    "REVENUE_CONTRACTION",
    "CURRENT_LOSS",
)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _pair(comparable: dict[str, Any], family: str) -> tuple[float, float] | None:
    row = comparable.get(family)
    if not isinstance(row, dict) or row.get("status") != "COMPARABLE_READY":
        return None
    current = _number(row.get("current_value"))
    prior = _number(row.get("prior_value"))
    if current is None or prior is None:
        return None
    return current, prior


def _growth(pair: tuple[float, float] | None) -> float | None:
    if pair is None:
        return None
    current, prior = pair
    if prior <= 0:
        return None
    value = current / prior - 1.0
    return value if math.isfinite(value) else None


def derive_inflection(comparable: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(comparable, dict):
        return {
            "metrics": {},
            "opportunity_flags": [],
            "caution_flags": [],
            "business_model_context_required": True,
        }

    revenue = _pair(comparable, "revenue")
    pat = _pair(comparable, "pat")
    pbt = _pair(comparable, "pbt")
    eps = _pair(comparable, "basic_eps")

    revenue_growth = _growth(revenue)
    pat_growth = _growth(pat)
    pbt_growth = _growth(pbt)
    eps_growth = _growth(eps)

    current_pat_margin = prior_pat_margin = pat_margin_delta_bps = None
    current_pbt_margin = prior_pbt_margin = pbt_margin_delta_bps = None
    if revenue is not None:
        current_revenue, prior_revenue = revenue
        if current_revenue > 0 and prior_revenue > 0:
            if pat is not None:
                current_pat, prior_pat = pat
                current_pat_margin = current_pat / current_revenue
                prior_pat_margin = prior_pat / prior_revenue
                pat_margin_delta_bps = (
                    current_pat_margin - prior_pat_margin
                ) * 10_000.0
            if pbt is not None:
                current_pbt, prior_pbt = pbt
                current_pbt_margin = current_pbt / current_revenue
                prior_pbt_margin = prior_pbt / prior_revenue
                pbt_margin_delta_bps = (
                    current_pbt_margin - prior_pbt_margin
                ) * 10_000.0

    opportunity: list[str] = []
    caution: list[str] = []

    if (
        revenue_growth is not None
        and pat_growth is not None
        and pat_margin_delta_bps is not None
        and revenue_growth >= 0.15
        and pat_growth >= 0.30
        and pat_margin_delta_bps >= 100.0
    ):
        opportunity.append("BROAD_GROWTH_LEVERAGE")

    if (
        revenue_growth is not None
        and pat_growth is not None
        and revenue_growth >= 0.25
        and pat_growth >= 0.25
    ):
        opportunity.append("STRONG_GROWTH")

    if (
        revenue_growth is not None
        and pat is not None
        and pat_margin_delta_bps is not None
        and pat[0] > 0
        and pat[1] > 0
        and revenue_growth >= 0.05
        and pat_margin_delta_bps >= 300.0
    ):
        opportunity.append("MARGIN_INFLECTION")

    if (
        revenue is not None
        and pat is not None
        and revenue_growth is not None
        and revenue[0] > 0
        and revenue[1] > 0
        and pat[1] <= 0
        and pat[0] > 0
        and revenue_growth >= -0.10
    ):
        opportunity.append("PROFIT_TURNAROUND")

    if prior_pat_margin is not None and 0 < prior_pat_margin < 0.01:
        caution.append("LOW_BASE_PAT")
    if revenue_growth is not None and revenue_growth <= -0.10:
        caution.append("REVENUE_CONTRACTION")
    if pat is not None and pat[0] <= 0:
        caution.append("CURRENT_LOSS")

    return {
        "metrics": {
            "revenue_growth_pct": (
                revenue_growth * 100.0 if revenue_growth is not None else None
            ),
            "pat_growth_pct": pat_growth * 100.0 if pat_growth is not None else None,
            "pbt_growth_pct": pbt_growth * 100.0 if pbt_growth is not None else None,
            "basic_eps_growth_pct": (
                eps_growth * 100.0 if eps_growth is not None else None
            ),
            "current_pat_margin_pct": (
                current_pat_margin * 100.0
                if current_pat_margin is not None
                else None
            ),
            "prior_pat_margin_pct": (
                prior_pat_margin * 100.0
                if prior_pat_margin is not None
                else None
            ),
            "pat_margin_delta_bps": pat_margin_delta_bps,
            "current_pbt_margin_pct": (
                current_pbt_margin * 100.0
                if current_pbt_margin is not None
                else None
            ),
            "prior_pbt_margin_pct": (
                prior_pbt_margin * 100.0
                if prior_pbt_margin is not None
                else None
            ),
            "pbt_margin_delta_bps": pbt_margin_delta_bps,
        },
        "opportunity_flags": opportunity,
        "caution_flags": caution,
        "business_model_context_required": True,
    }


def build_inflection_router(panel: dict[str, Any]) -> dict[str, Any]:
    if panel.get("panel_id") != EXPECTED_PANEL_ID:
        raise AlphaContractError("EI001 S001 requires frozen D002 panel")
    if panel.get("panel_sha256") != EXPECTED_PANEL_SHA256:
        raise AlphaContractError("EI001 S001 D002 panel SHA mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if panel.get(field) is not False:
            raise AlphaContractError(f"EI001 S001 requires D002 {field}=false")

    source_rows = panel.get("rows")
    if not isinstance(source_rows, list) or len(source_rows) != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("EI001 S001 requires frozen 2,319-row D002 panel")

    rows: list[dict[str, Any]] = []
    opportunity_counts: Counter[str] = Counter()
    caution_counts: Counter[str] = Counter()
    any_opportunity = 0
    comparable_ready = 0

    for source in source_rows:
        if not isinstance(source, dict):
            raise TypeError("EI001 S001 source rows must be objects")
        symbol = str(source.get("symbol") or "").upper()
        if not symbol:
            raise AlphaContractError("EI001 S001 source row lacks symbol")
        comparable = source.get("comparable")
        derived = derive_inflection(comparable if isinstance(comparable, dict) else None)
        if source.get("status") == "PAIR_READY":
            comparable_ready += 1
        if derived["opportunity_flags"]:
            any_opportunity += 1
        for flag in derived["opportunity_flags"]:
            opportunity_counts[flag] += 1
        for flag in derived["caution_flags"]:
            caution_counts[flag] += 1

        rows.append(
            {
                "symbol": symbol,
                "isin": source.get("isin"),
                "company_name": source.get("company_name"),
                "in_existing_u001": bool(source.get("in_existing_u001")),
                "source_state": source.get("status"),
                "source_reason": source.get("reason"),
                "current": source.get("current"),
                "prior": source.get("prior"),
                **derived,
                "return_outcomes_opened": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    if len({row["symbol"] for row in rows}) != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("EI001 S001 symbols must be unique")

    output = {
        "schema_version": 1,
        "router_id": ROUTER_ID,
        "classification": "FULL_MARKET_EARNINGS_INFLECTION_ROUTING_NOT_ALPHA",
        "source_panel_id": EXPECTED_PANEL_ID,
        "source_panel_sha256": EXPECTED_PANEL_SHA256,
        "identity_count": EXPECTED_IDENTITY_COUNT,
        "pair_ready_count": comparable_ready,
        "opportunity_flag_counts": dict(sorted(opportunity_counts.items())),
        "caution_flag_counts": dict(sorted(caution_counts.items())),
        "any_opportunity_flag_count": any_opportunity,
        "rows": sorted(rows, key=lambda row: row["symbol"]),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["router_sha256"] = digest(output)
    return output
