from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest

ROUTER_ID = "HG001-D001-v1"
EXPECTED_IDENTITY_COUNT = 2319
EXPECTED_EI_ID = "EI001-S001-v1"
EXPECTED_HA_ID = "HA001-D001-v1"
EXPECTED_HA_SHA = "81651ebbac5a3102bb2dda9f2931dc10157583bfe2753cc610585811204f5bb3"
EXPECTED_GF_ID = "GF001-D002-v1"
EXPECTED_GF_SHA = "dd338cd91f44396278300e27e8cdac1506dae11b63dd31ce827505fe62e8abe7"
EXPECTED_I_ID = "SS001-I001-v1"
EXPECTED_I_SHA = "5f7cda9e8eb41954d5cb944b2fd06da9c888fe3513bd7d3acd294a33c93293d4"
EXPECTED_SS_ID = "SS002-D001-P2-v1"
EXPECTED_SS_SHA = "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071"


def _index(rows: object, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        raise TypeError(f"{label} rows must be a list")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError(f"{label} rows must be objects")
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol or symbol in result:
            raise AlphaContractError(f"{label} symbols must be unique")
        result[symbol] = row
    return result


def _validate_research_only(payload: dict[str, Any], label: str) -> None:
    for field in ("return_outcomes_opened", "portfolio_eligibility_allowed", "live_capital_allowed"):
        if payload.get(field) is not False:
            raise AlphaContractError(f"{label} requires {field}=false")


def build_hidden_gem_router(
    *,
    ei: dict[str, Any],
    ha: dict[str, Any],
    gf: dict[str, Any],
    investability: dict[str, Any],
    special: dict[str, Any],
) -> dict[str, Any]:
    if ei.get("router_id") != EXPECTED_EI_ID:
        raise AlphaContractError("HG001 requires EI001-S001")
    if ha.get("panel_id") != EXPECTED_HA_ID or ha.get("panel_sha256") != EXPECTED_HA_SHA:
        raise AlphaContractError("HG001 HA001 source mismatch")
    if gf.get("panel_id") != EXPECTED_GF_ID or gf.get("panel_sha256") != EXPECTED_GF_SHA:
        raise AlphaContractError("HG001 GF001 source mismatch")
    if investability.get("context_id") != EXPECTED_I_ID or investability.get("context_sha256") != EXPECTED_I_SHA:
        raise AlphaContractError("HG001 I001 source mismatch")
    if special.get("census_id") != EXPECTED_SS_ID or special.get("census_sha256") != EXPECTED_SS_SHA:
        raise AlphaContractError("HG001 SS002 source mismatch")

    for label, payload in (
        ("EI001", ei), ("HA001", ha), ("GF001", gf),
        ("SS001-I001", investability), ("SS002", special),
    ):
        _validate_research_only(payload, label)

    ei_idx = _index(ei.get("rows"), "EI001")
    ha_idx = _index(ha.get("rows"), "HA001")
    gf_idx = _index(gf.get("rows"), "GF001")
    inv_idx = _index(investability.get("rows"), "I001")

    if not (
        len(ei_idx) == len(ha_idx) == len(gf_idx) == len(inv_idx) == EXPECTED_IDENTITY_COUNT
        and set(ei_idx) == set(ha_idx) == set(gf_idx) == set(inv_idx)
    ):
        raise AlphaContractError("HG001 cross-plane identity mismatch")

    event_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    events = special.get("events")
    if not isinstance(events, list):
        raise AlphaContractError("HG001 SS002 events unavailable")
    for event in events:
        if not isinstance(event, dict):
            raise TypeError("HG001 SS002 event must be object")
        if event.get("mapping_state") != "CURRENT_INVESTABLE_IDENTITY":
            continue
        symbol = str(event.get("symbol") or "").strip().upper()
        if symbol in ei_idx:
            event_by_symbol[symbol].append(event)

    rows = []
    route_counts: Counter[str] = Counter()
    lane_count_distribution: Counter[int] = Counter()
    governance_flag_counts: Counter[str] = Counter()
    convergent_outside_u001 = 0

    for symbol in sorted(ei_idx):
        ei_row = ei_idx[symbol]
        ha_row = ha_idx[symbol]
        gf_row = gf_idx[symbol]
        inv_row = inv_idx[symbol]
        symbol_events = event_by_symbol.get(symbol, [])

        earnings_lane = ei_row.get("inflection_state") in {
            "STRONG_INFLECTION", "SUPPORTED_INFLECTION"
        }
        ha_flags = ha_row.get("opportunity_flags")
        if not isinstance(ha_flags, list):
            raise AlphaContractError(f"{symbol}: HA opportunity flags unavailable")
        asset_lane = bool(ha_flags)
        special_lane = bool(symbol_events)
        lanes = []
        if earnings_lane:
            lanes.append("EARNINGS_INFLECTION")
        if asset_lane:
            lanes.append("ASSET_OR_CAPACITY_ANOMALY")
        if special_lane:
            lanes.append("CURRENT_SPECIAL_SITUATION")

        governance_cautions: list[str] = []
        latest = gf_row.get("latest")
        if gf_row.get("governance_state") != "CORE_READY" or not isinstance(latest, dict):
            governance_cautions.append("GOVERNANCE_SOURCE_INCOMPLETE")
        else:
            enc = latest.get("promoter_encumbrance")
            if isinstance(enc, dict):
                if enc.get("pledge") is True:
                    governance_cautions.append("PROMOTER_PLEDGE_PRESENT")
                if enc.get("non_disposal_undertaking") is True:
                    governance_cautions.append("PROMOTER_NDU_PRESENT")
                if enc.get("other_encumbrance") is True:
                    governance_cautions.append("PROMOTER_OTHER_ENCUMBRANCE_PRESENT")
            delta = gf_row.get("ownership_delta_pp")
            if isinstance(delta, dict):
                promoter_delta = delta.get("promoter_percentage_points")
                if (
                    isinstance(promoter_delta, (int, float))
                    and not isinstance(promoter_delta, bool)
                    and float(promoter_delta) <= -2.0
                ):
                    governance_cautions.append("PROMOTER_REDUCTION_2PP")

        asset_cautions = ha_row.get("caution_flags")
        if not isinstance(asset_cautions, list):
            raise AlphaContractError(f"{symbol}: HA caution flags unavailable")

        if len(lanes) >= 2:
            route = "CONVERGENT_DEEP_DIVE"
        elif special_lane:
            route = "SPECIAL_SITUATION_UNDERWRITE"
        elif earnings_lane:
            route = "EARNINGS_INFLECTION_DEEP_DIVE"
        elif asset_lane:
            route = "ASSET_ANOMALY_DEEP_DIVE"
        else:
            route = "BACKLOG_NO_ACTIVE_LANE"

        in_u001 = bool(inv_row.get("in_existing_u001"))
        if route == "CONVERGENT_DEEP_DIVE" and not in_u001:
            convergent_outside_u001 += 1

        event_categories = sorted({
            category
            for event in symbol_events
            for category in (
                event.get("special_situation_categories")
                if isinstance(event.get("special_situation_categories"), list)
                else []
            )
        })

        route_counts[route] += 1
        lane_count_distribution[len(lanes)] += 1
        governance_flag_counts.update(governance_cautions)

        rows.append({
            "symbol": symbol,
            "isin": inv_row.get("isin"),
            "in_existing_u001": in_u001,
            "research_route": route,
            "active_opportunity_lanes": lanes,
            "active_opportunity_lane_count": len(lanes),
            "earnings_inflection_state": ei_row.get("inflection_state"),
            "earnings_positive_flags": ei_row.get("positive_flags"),
            "earnings_negative_flags": ei_row.get("negative_flags"),
            "earnings_metrics": ei_row.get("metrics"),
            "asset_opportunity_flags": sorted(ha_flags),
            "asset_caution_flags": sorted(asset_cautions),
            "governance_caution_flags": sorted(set(governance_cautions)),
            "governance_caution_count": len(set(governance_cautions)),
            "promoter_percentage": latest.get("promoter_percentage") if isinstance(latest, dict) else None,
            "promoter_delta_pp": (
                gf_row.get("ownership_delta_pp", {}).get("promoter_percentage_points")
                if isinstance(gf_row.get("ownership_delta_pp"), dict)
                else None
            ),
            "liquidity_band": inv_row.get("liquidity_band"),
            "median_daily_turnover_inr": inv_row.get("median_daily_turnover_inr"),
            "research_capacity_state": inv_row.get("research_capacity_state"),
            "special_situation_event_count": len(symbol_events),
            "special_situation_categories": event_categories,
            "return_outcomes_opened": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        })

    rows.sort(key=lambda row: (
        -row["active_opportunity_lane_count"],
        row["governance_caution_count"],
        len(row["asset_caution_flags"]),
        row["symbol"],
    ))
    active = [row for row in rows if row["active_opportunity_lane_count"] > 0]
    output = {
        "schema_version": 1,
        "router_id": ROUTER_ID,
        "classification": "FULL_MARKET_CROSS_PLANE_RESEARCH_ROUTER_NOT_ALPHA",
        "identity_count": EXPECTED_IDENTITY_COUNT,
        "active_research_candidate_count": len(active),
        "convergent_outside_u001_count": convergent_outside_u001,
        "research_route_counts": dict(sorted(route_counts.items())),
        "lane_count_distribution": {
            str(key): value for key, value in sorted(lane_count_distribution.items())
        },
        "governance_caution_flag_counts": dict(sorted(governance_flag_counts.items())),
        "rows": rows,
        "research_queue": active,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["router_sha256"] = digest(output)
    return output
