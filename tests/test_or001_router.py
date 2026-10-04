from __future__ import annotations

from marketlab.or001_router import build_opportunity_router


def _market_row(index: int) -> dict:
    return {
        "symbol": f"S{index:04d}",
        "isin": f"INE{index:09d}",
        "company_name": f"Company {index}",
        "in_existing_u001": index == 0,
        "market": {
            "observed_session_count": 20,
            "median_daily_turnover_inr": 50_000_000.0 + index,
        },
    }


def _base_panel(kind: str) -> dict:
    rows = []
    for index in range(2319):
        symbol = f"S{index:04d}"
        if kind == "ei":
            rows.append(
                {
                    "symbol": symbol,
                    "opportunity_flags": ["STRONG_GROWTH"] if index in {0, 1} else [],
                    "caution_flags": [],
                }
            )
        elif kind == "ha":
            rows.append(
                {
                    "symbol": symbol,
                    "opportunity_flags": ["LIQUID_ASSET_HEAVY"] if index in {0, 2} else [],
                    "caution_flags": [],
                }
            )
        elif kind == "gf":
            rows.append(
                {
                    "symbol": symbol,
                    "governance_state": "CORE_READY",
                    "latest": {
                        "promoter_percentage": 60.0,
                        "public_percentage": 40.0,
                        "mutual_fund_state": "READY",
                        "mutual_fund_percentage": 5.0,
                        "promoter_encumbrance": {
                            "pledge": index == 0,
                            "non_disposal_undertaking": False,
                            "other_encumbrance": False,
                        },
                    },
                    "ownership_delta_pp": {
                        "promoter_percentage_points": -6.0 if index == 2 else 0.0,
                        "public_percentage_points": 0.0,
                        "mutual_fund_percentage_points": 0.0,
                    },
                }
            )
    if kind == "ei":
        return {
            "router_id": "EI001-S001-v1",
            "router_sha256": (
                "fa1e0df536402088f5c3d822c77295f576f77beba1908155cdfed10f83ca716b"
            ),
            "rows": rows,
            "return_outcomes_opened": False,
            "model_fitted": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        }
    if kind == "ha":
        return {
            "panel_id": "HA001-D001-v1",
            "panel_sha256": (
                "81651ebbac5a3102bb2dda9f2931dc10157583bfe2753cc610585811204f5bb3"
            ),
            "rows": rows,
            "return_outcomes_opened": False,
            "model_fitted": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        }
    return {
        "panel_id": "GF001-D002-v1",
        "panel_sha256": (
            "dd338cd91f44396278300e27e8cdac1506dae11b63dd31ce827505fe62e8abe7"
        ),
        "rows": rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _ss001() -> dict:
    return {
        "census_id": "SS001-D001-v1",
        "census_sha256": (
            "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"
        ),
        "rows": [_market_row(i) for i in range(2319)],
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _ss002() -> dict:
    return {
        "census_id": "SS002-D001-P2-v1",
        "census_sha256": (
            "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071"
        ),
        "events": [
            {
                "symbol": "S0000",
                "announcement_id": "event0",
                "mapping_state": "CURRENT_INVESTABLE_IDENTITY",
                "special_situation_categories": ["BUYBACK"],
            },
            {
                "symbol": "S0003",
                "announcement_id": "event3",
                "mapping_state": "CURRENT_INVESTABLE_IDENTITY",
                "special_situation_categories": ["RIGHTS_ISSUE"],
            },
        ],
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_router_prioritizes_independent_evidence_without_weighting() -> None:
    output = build_opportunity_router(
        ss001=_ss001(),
        ei001=_base_panel("ei"),
        ha001=_base_panel("ha"),
        gf001=_base_panel("gf"),
        ss002=_ss002(),
    )
    rows = {row["symbol"]: row for row in output["rows"]}
    assert rows["S0000"]["research_priority"] == "P0_TRIPLE_EVIDENCE"
    assert rows["S0000"]["independent_route_count"] == 3
    assert rows["S0001"]["research_priority"] == "P2_SINGLE_EVIDENCE"
    assert rows["S0002"]["research_priority"] == "P2_SINGLE_EVIDENCE"
    assert rows["S0003"]["research_priority"] == "P2_SINGLE_EVIDENCE"
    assert output["multi_evidence_count"] == 1


def test_governance_is_caution_context_not_route() -> None:
    output = build_opportunity_router(
        ss001=_ss001(),
        ei001=_base_panel("ei"),
        ha001=_base_panel("ha"),
        gf001=_base_panel("gf"),
        ss002=_ss002(),
    )
    rows = {row["symbol"]: row for row in output["rows"]}
    assert "PROMOTER_PLEDGE_TRUE" in rows["S0000"]["governance_caution_flags"]
    assert "PROMOTER_OWNERSHIP_DROP_GE_5PP" in rows["S0002"][
        "governance_caution_flags"
    ]
    assert rows["S0002"]["independent_route_count"] == 1


def test_liquidity_is_context_not_exclusion() -> None:
    ss001 = _ss001()
    ss001["rows"][4]["market"]["observed_session_count"] = 5
    output = build_opportunity_router(
        ss001=ss001,
        ei001=_base_panel("ei"),
        ha001=_base_panel("ha"),
        gf001=_base_panel("gf"),
        ss002=_ss002(),
    )
    row = output["rows"][4]
    assert row["liquidity_band"] == "OBSERVATION_INSUFFICIENT"
    assert row["research_priority"] == "P3_NO_CURRENT_ROUTE"
    assert output["identity_count"] == 2319
