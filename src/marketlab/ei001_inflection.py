from __future__ import annotations

import math
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest

ROUTER_ID = "EI001-S001-v1"
EXPECTED_PANEL_ID = "EI001-D002-v1"
EXPECTED_PANEL_SHA = "14fdc99444ff8c1c62cbef58db91e51cb4cb6730c1259bccb98df979366272cd"
EXPECTED_IDENTITY_COUNT = 2319
EPSILON = 1e-12

CORE_POSITIVE_FLAGS = (
    "REVENUE_GROWTH_15",
    "PAT_GROWTH_25",
    "PBT_MARGIN_EXPANSION_200BPS",
    "LOSS_TO_PROFIT_TURNAROUND",
    "EPS_GROWTH_25",
)
SUPPORT_FLAG = "FINANCE_COST_RELIEF_15"


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _pair(row: dict[str, Any], family: str) -> tuple[float | None, float | None]:
    comparable = row.get("comparable")
    if not isinstance(comparable, dict):
        return None, None
    block = comparable.get(family)
    if not isinstance(block, dict) or block.get("status") != "COMPARABLE_READY":
        return None, None
    return _number(block.get("current_value")), _number(block.get("prior_value"))


def _growth(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or prior <= 0:
        return None
    value = current / prior - 1.0
    return value if math.isfinite(value) else None


def evaluate_inflection_row(row: dict[str, Any]) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "").strip().upper()
    if not symbol:
        raise AlphaContractError("EI001 S001 row lacks symbol")

    revenue_cur, revenue_prior = _pair(row, "revenue")
    pat_cur, pat_prior = _pair(row, "pat")
    pbt_cur, pbt_prior = _pair(row, "pbt")
    eps_cur, eps_prior = _pair(row, "basic_eps")
    fin_cur, fin_prior = _pair(row, "finance_costs")

    revenue_growth = _growth(revenue_cur, revenue_prior)
    pat_growth = _growth(pat_cur, pat_prior)
    eps_growth = _growth(eps_cur, eps_prior)
    finance_growth = _growth(fin_cur, fin_prior)

    current_margin = (
        pbt_cur / revenue_cur
        if pbt_cur is not None
        and revenue_cur is not None
        and revenue_cur > 0
        else None
    )
    prior_margin = (
        pbt_prior / revenue_prior
        if pbt_prior is not None
        and revenue_prior is not None
        and revenue_prior > 0
        else None
    )
    margin_delta_pp = (
        100.0 * (current_margin - prior_margin)
        if current_margin is not None and prior_margin is not None
        else None
    )

    positive: list[str] = []
    if revenue_growth is not None and revenue_growth >= 0.15 - EPSILON:
        positive.append("REVENUE_GROWTH_15")
    if (
        pat_prior is not None
        and pat_prior > 0
        and pat_cur is not None
        and pat_cur > 0
        and pat_growth is not None
        and pat_growth >= 0.25 - EPSILON
    ):
        positive.append("PAT_GROWTH_25")
    if (
        pbt_prior is not None
        and pbt_prior > 0
        and pbt_cur is not None
        and pbt_cur > 0
        and margin_delta_pp is not None
        and margin_delta_pp >= 2.0 - EPSILON
    ):
        positive.append("PBT_MARGIN_EXPANSION_200BPS")
    if pat_prior is not None and pat_prior < 0 and pat_cur is not None and pat_cur > 0:
        positive.append("LOSS_TO_PROFIT_TURNAROUND")
    if (
        eps_prior is not None
        and eps_prior > 0
        and eps_cur is not None
        and eps_cur > 0
        and eps_growth is not None
        and eps_growth >= 0.25 - EPSILON
    ):
        positive.append("EPS_GROWTH_25")
    finance_relief = (
        fin_prior is not None
        and fin_prior > 0
        and fin_cur is not None
        and fin_cur >= 0
        and finance_growth is not None
        and finance_growth <= -0.15 + EPSILON
        and revenue_prior is not None
        and revenue_prior > 0
        and revenue_cur is not None
        and revenue_cur >= 0.95 * revenue_prior
    )
    if finance_relief:
        positive.append(SUPPORT_FLAG)

    negative: list[str] = []
    if revenue_growth is not None and revenue_growth <= -0.10 + EPSILON:
        negative.append("REVENUE_CONTRACTION_10")
    if (
        pat_prior is not None
        and pat_prior > 0
        and pat_cur is not None
        and (pat_cur <= 0 or (pat_growth is not None and pat_growth <= -0.25 + EPSILON))
    ):
        negative.append("PROFIT_BREAKDOWN")
    if (
        pbt_prior is not None
        and pbt_prior > 0
        and pbt_cur is not None
        and pbt_cur > 0
        and margin_delta_pp is not None
        and margin_delta_pp <= -2.0 + EPSILON
    ):
        negative.append("PBT_MARGIN_COMPRESSION_200BPS")

    core = [flag for flag in positive if flag in CORE_POSITIVE_FLAGS]
    core_set = set(core)
    strong = (
        "LOSS_TO_PROFIT_TURNAROUND" in core_set
        or {"REVENUE_GROWTH_15", "PAT_GROWTH_25"}.issubset(core_set)
        or {"PAT_GROWTH_25", "PBT_MARGIN_EXPANSION_200BPS"}.issubset(core_set)
    )
    supported = (
        not strong
        and (
            len(core) >= 2
            or (len(core) >= 1 and SUPPORT_FLAG in positive)
        )
    )
    if strong:
        state = "STRONG_INFLECTION"
    elif supported:
        state = "SUPPORTED_INFLECTION"
    elif len(core) == 1:
        state = "SINGLE_POSITIVE_SIGNAL"
    else:
        state = "NO_POSITIVE_INFLECTION"

    return {
        "symbol": symbol,
        "company_name": row.get("company_name"),
        "isin": row.get("isin"),
        "in_existing_u001": bool(row.get("in_existing_u001")),
        "source_status": row.get("status"),
        "inflection_state": state,
        "positive_flags": sorted(positive),
        "negative_flags": sorted(set(negative)),
        "metrics": {
            "revenue_yoy_pct": None if revenue_growth is None else 100.0 * revenue_growth,
            "pat_yoy_pct": None if pat_growth is None else 100.0 * pat_growth,
            "basic_eps_yoy_pct": None if eps_growth is None else 100.0 * eps_growth,
            "finance_cost_yoy_pct": (
                None if finance_growth is None else 100.0 * finance_growth
            ),
            "current_pbt_margin_pct": (
                None if current_margin is None else 100.0 * current_margin
            ),
            "prior_pbt_margin_pct": (
                None if prior_margin is None else 100.0 * prior_margin
            ),
            "pbt_margin_delta_pp": margin_delta_pp,
        },
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def build_inflection_router(panel: dict[str, Any]) -> dict[str, Any]:
    if panel.get("panel_id") != EXPECTED_PANEL_ID:
        raise AlphaContractError("EI001 S001 requires frozen D002 panel")
    if panel.get("panel_sha256") != EXPECTED_PANEL_SHA:
        raise AlphaContractError("EI001 S001 source panel SHA mismatch")
    if panel.get("identity_count") != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("EI001 S001 identity count mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if panel.get(field) is not False:
            raise AlphaContractError(f"EI001 S001 requires {field}=false")

    rows = panel.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("EI001 S001 source rows unavailable")

    routed = [evaluate_inflection_row(row) for row in rows]
    symbols = [row["symbol"] for row in routed]
    if len(symbols) != len(set(symbols)):
        raise AlphaContractError("EI001 S001 symbols must be unique")

    state_counts = Counter(row["inflection_state"] for row in routed)
    positive_counts = Counter(
        flag for row in routed for flag in row["positive_flags"]
    )
    negative_counts = Counter(
        flag for row in routed for flag in row["negative_flags"]
    )
    active_count = sum(
        row["inflection_state"] in {"STRONG_INFLECTION", "SUPPORTED_INFLECTION"}
        for row in routed
    )

    output = {
        "schema_version": 1,
        "router_id": ROUTER_ID,
        "classification": "FULL_MARKET_EARNINGS_INFLECTION_RESEARCH_ROUTER_NOT_ALPHA",
        "source_panel_id": EXPECTED_PANEL_ID,
        "source_panel_sha256": EXPECTED_PANEL_SHA,
        "identity_count": EXPECTED_IDENTITY_COUNT,
        "active_inflection_count": active_count,
        "state_counts": dict(sorted(state_counts.items())),
        "positive_flag_counts": dict(sorted(positive_counts.items())),
        "negative_flag_counts": dict(sorted(negative_counts.items())),
        "rows": sorted(routed, key=lambda row: row["symbol"]),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["router_sha256"] = digest(output)
    return output
