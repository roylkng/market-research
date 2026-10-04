from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss001_investability import liquidity_band

ROUTER_ID = "OR001-D001-v1"
IDENTITY_COUNT = 2319

SS001_ID = "SS001-D001-v1"
SS001_SHA = "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"
EI_ID = "EI001-S001-v1"
EI_SHA = "fa1e0df536402088f5c3d822c77295f576f77beba1908155cdfed10f83ca716b"
HA_ID = "HA001-D001-v1"
HA_SHA = "81651ebbac5a3102bb2dda9f2931dc10157583bfe2753cc610585811204f5bb3"
GF_ID = "GF001-D002-v1"
GF_SHA = "dd338cd91f44396278300e27e8cdac1506dae11b63dd31ce827505fe62e8abe7"
SS002_ID = "SS002-D001-P2-v1"
SS002_SHA = "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071"


def _require_false(payload: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    for field in fields:
        if payload.get(field) is not False:
            raise AlphaContractError(f"OR001 requires {label} {field}=false")


def _index(rows: object, *, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) != IDENTITY_COUNT:
        raise AlphaContractError(f"OR001 requires {label} 2,319 rows")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError(f"OR001 {label} rows must be objects")
        symbol = str(row.get("symbol") or "").upper()
        if not symbol or symbol in result:
            raise AlphaContractError(f"OR001 {label} symbols must be unique")
        result[symbol] = row
    return result


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _validate_inputs(
    ss001: dict[str, Any],
    ei001: dict[str, Any],
    ha001: dict[str, Any],
    gf001: dict[str, Any],
    ss002: dict[str, Any],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    if ss001.get("census_id") != SS001_ID or ss001.get("census_sha256") != SS001_SHA:
        raise AlphaContractError("OR001 SS001 source mismatch")
    if ei001.get("router_id") != EI_ID or ei001.get("router_sha256") != EI_SHA:
        raise AlphaContractError("OR001 EI001 source mismatch")
    if ha001.get("panel_id") != HA_ID or ha001.get("panel_sha256") != HA_SHA:
        raise AlphaContractError("OR001 HA001 source mismatch")
    if gf001.get("panel_id") != GF_ID or gf001.get("panel_sha256") != GF_SHA:
        raise AlphaContractError("OR001 GF001 source mismatch")
    if ss002.get("census_id") != SS002_ID or ss002.get("census_sha256") != SS002_SHA:
        raise AlphaContractError("OR001 SS002 source mismatch")

    for payload, label in (
        (ss001, "SS001"),
        (ei001, "EI001"),
        (ha001, "HA001"),
        (gf001, "GF001"),
        (ss002, "SS002"),
    ):
        _require_false(
            payload,
            (
                "return_outcomes_opened",
                "model_fitted",
                "portfolio_eligibility_allowed",
                "live_capital_allowed",
            ),
            label,
        )

    market = _index(ss001.get("rows"), label="SS001")
    earnings = _index(ei001.get("rows"), label="EI001")
    assets = _index(ha001.get("rows"), label="HA001")
    governance = _index(gf001.get("rows"), label="GF001")
    if set(market) != set(earnings) or set(market) != set(assets) or set(market) != set(governance):
        raise AlphaContractError("OR001 full-market identity planes do not match")
    return market, earnings, assets, governance


def _special_index(
    ss002: dict[str, Any],
    current_symbols: set[str],
) -> dict[str, dict[str, Any]]:
    events = ss002.get("events")
    if not isinstance(events, list):
        raise AlphaContractError("OR001 SS002 events unavailable")
    result: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"event_count": 0, "categories": set(), "event_ids": []}
    )
    for event in events:
        if not isinstance(event, dict):
            raise TypeError("OR001 SS002 event rows must be objects")
        if event.get("mapping_state") != "CURRENT_INVESTABLE_IDENTITY":
            continue
        symbol = str(event.get("symbol") or "").upper()
        if symbol not in current_symbols:
            raise AlphaContractError(f"OR001 current special event has unknown symbol: {symbol}")
        event_id = str(event.get("announcement_id") or "")
        categories = event.get("special_situation_categories")
        if not event_id or not isinstance(categories, list):
            raise AlphaContractError("OR001 current special event identity/category unavailable")
        result[symbol]["event_count"] += 1
        result[symbol]["event_ids"].append(event_id)
        result[symbol]["categories"].update(str(value) for value in categories)
    return result


def _governance_context(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    latest = row.get("latest")
    delta = row.get("ownership_delta_pp")
    cautions: list[str] = []

    promoter = public = mf = None
    mf_state = None
    encumbrance = None
    if isinstance(latest, dict):
        promoter = _number(latest.get("promoter_percentage"))
        public = _number(latest.get("public_percentage"))
        mf = _number(latest.get("mutual_fund_percentage"))
        mf_state = latest.get("mutual_fund_state")
        raw_enc = latest.get("promoter_encumbrance")
        if isinstance(raw_enc, dict):
            encumbrance = {
                "pledge": raw_enc.get("pledge"),
                "non_disposal_undertaking": raw_enc.get(
                    "non_disposal_undertaking"
                ),
                "other_encumbrance": raw_enc.get("other_encumbrance"),
            }
            if raw_enc.get("pledge") is True:
                cautions.append("PROMOTER_PLEDGE_TRUE")
            if raw_enc.get("non_disposal_undertaking") is True:
                cautions.append("PROMOTER_NDU_TRUE")
            if raw_enc.get("other_encumbrance") is True:
                cautions.append("PROMOTER_OTHER_ENCUMBRANCE_TRUE")

    promoter_delta = None
    public_delta = None
    mf_delta = None
    if isinstance(delta, dict):
        promoter_delta = _number(delta.get("promoter_percentage_points"))
        public_delta = _number(delta.get("public_percentage_points"))
        mf_delta = _number(delta.get("mutual_fund_percentage_points"))
        if promoter_delta is not None and promoter_delta <= -5.0:
            cautions.append("PROMOTER_OWNERSHIP_DROP_GE_5PP")

    return (
        {
            "governance_state": row.get("governance_state"),
            "promoter_percentage": promoter,
            "public_percentage": public,
            "mutual_fund_state": mf_state,
            "mutual_fund_percentage": mf,
            "promoter_ownership_delta_pp": promoter_delta,
            "public_ownership_delta_pp": public_delta,
            "mutual_fund_ownership_delta_pp": mf_delta,
            "promoter_encumbrance": encumbrance,
        },
        cautions,
    )


def _priority(route_count: int) -> str:
    return {
        3: "P0_TRIPLE_EVIDENCE",
        2: "P1_DUAL_EVIDENCE",
        1: "P2_SINGLE_EVIDENCE",
        0: "P3_NO_CURRENT_ROUTE",
    }[route_count]


def build_opportunity_router(
    *,
    ss001: dict[str, Any],
    ei001: dict[str, Any],
    ha001: dict[str, Any],
    gf001: dict[str, Any],
    ss002: dict[str, Any],
) -> dict[str, Any]:
    market, earnings, assets, governance = _validate_inputs(
        ss001, ei001, ha001, gf001, ss002
    )
    special = _special_index(ss002, set(market))

    rows: list[dict[str, Any]] = []
    priority_counts: Counter[str] = Counter()
    combination_counts: Counter[str] = Counter()
    governance_caution_counts: Counter[str] = Counter()

    for symbol in sorted(market):
        mrow = market[symbol]
        erow = earnings[symbol]
        arow = assets[symbol]
        grow = governance[symbol]

        earnings_flags = [
            str(value) for value in erow.get("opportunity_flags", [])
        ]
        earnings_cautions = [
            str(value) for value in erow.get("caution_flags", [])
        ]
        asset_flags = [str(value) for value in arow.get("opportunity_flags", [])]
        asset_cautions = [str(value) for value in arow.get("caution_flags", [])]

        srow = special.get(symbol)
        special_categories = (
            sorted(srow["categories"]) if srow is not None else []
        )
        special_event_count = int(srow["event_count"]) if srow is not None else 0

        routes: list[str] = []
        if earnings_flags:
            routes.append("EARNINGS_INFLECTION")
        if asset_flags:
            routes.append("ASSET_ANOMALY")
        if special_event_count:
            routes.append("SPECIAL_SITUATION")

        route_count = len(routes)
        priority = _priority(route_count)
        combination = "+".join(routes) if routes else "NONE"
        priority_counts[priority] += 1
        combination_counts[combination] += 1

        governance_context, governance_cautions = _governance_context(grow)
        for caution in governance_cautions:
            governance_caution_counts[caution] += 1

        market_context = mrow.get("market")
        if not isinstance(market_context, dict):
            raise AlphaContractError(f"OR001 {symbol} market context unavailable")
        observed = market_context.get("observed_session_count")
        turnover = _number(market_context.get("median_daily_turnover_inr"))
        band = liquidity_band(
            observed_session_count=observed,
            median_daily_turnover_inr=turnover,
        )

        rows.append(
            {
                "symbol": symbol,
                "isin": mrow.get("isin"),
                "company_name": mrow.get("company_name"),
                "in_existing_u001": bool(mrow.get("in_existing_u001")),
                "opportunity_routes": routes,
                "independent_route_count": route_count,
                "research_priority": priority,
                "earnings_inflection_flags": earnings_flags,
                "earnings_caution_flags": earnings_cautions,
                "asset_anomaly_flags": asset_flags,
                "asset_caution_flags": asset_cautions,
                "special_situation_event_count": special_event_count,
                "special_situation_categories": special_categories,
                "special_situation_event_ids": (
                    sorted(srow["event_ids"]) if srow is not None else []
                ),
                "governance": governance_context,
                "governance_caution_flags": governance_cautions,
                "median_daily_turnover_inr": turnover,
                "observed_session_count": observed,
                "liquidity_band": band,
                "return_outcomes_opened": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    multi_evidence = [row for row in rows if row["independent_route_count"] >= 2]
    multi_evidence.sort(
        key=lambda row: (
            -int(row["independent_route_count"]),
            -(
                float(row["median_daily_turnover_inr"])
                if row["median_daily_turnover_inr"] is not None
                else -1.0
            ),
            str(row["symbol"]),
        )
    )

    output = {
        "schema_version": 1,
        "router_id": ROUTER_ID,
        "classification": "FULL_MARKET_MULTI_EVIDENCE_RESEARCH_ROUTER_NOT_ALPHA",
        "identity_count": IDENTITY_COUNT,
        "source_hashes": {
            "ss001_d001": SS001_SHA,
            "ei001_s001": EI_SHA,
            "ha001_d001": HA_SHA,
            "gf001_d002": GF_SHA,
            "ss002_d001_p2": SS002_SHA,
        },
        "priority_counts": dict(sorted(priority_counts.items())),
        "route_combination_counts": dict(sorted(combination_counts.items())),
        "governance_caution_counts": dict(
            sorted(governance_caution_counts.items())
        ),
        "multi_evidence_count": len(multi_evidence),
        "outside_u001_multi_evidence_count": sum(
            not row["in_existing_u001"] for row in multi_evidence
        ),
        "rows": rows,
        "multi_evidence_queue": multi_evidence,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["router_sha256"] = digest(output)
    return output
