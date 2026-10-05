from __future__ import annotations

import math
from typing import Any

from marketlab.alpha import AlphaContractError, digest

FRAMEWORK_ID = "HG005-D003-v1"
EXPECTED_D001_ID = "HG005-D001-v1"
EXPECTED_D001_SHA = "f8cb5079e266f451013d964b67b38dd833c7212bdffa4ffe23bd4fcef28fa48b"
EXPECTED_D002B_ID = "HG005-D002B-SYNTHESIS-v1"
EXPECTED_D002B_SHA = "beee365eb088e22b52e1827e0c1d6e2b68e842d36015c8ac988b8f5380f07287"

UPLIFT_TARGETS = (0.25, 0.50, 1.00)
ANANTRAJ_EV_REVENUE = (5.0, 10.0, 15.0)
ANANTRAJ_EV_PER_MW = (25.0, 50.0, 75.0)
DEVX_MULTIPLES = (10.0, 15.0, 20.0)
NPST_MULTIPLES = (20.0, 30.0, 40.0)
SAMBHV_UTILIZATION = (0.70, 0.85, 1.00)
SAMBHV_EBITDA_PER_TONNE = (5000.0, 7000.0, 9000.0)
SAMBHV_MULTIPLES = (8.0, 10.0, 12.0)


def _finite_positive(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AlphaContractError(f"{field} must be numeric")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise AlphaContractError(f"{field} must be finite and positive")
    return parsed


def _validate_market_context(context: dict[str, Any]) -> dict[str, Any]:
    if context.get("context_id") != EXPECTED_D001_ID:
        raise AlphaContractError("HG005 D003 market context identity mismatch")
    if context.get("context_sha256") != EXPECTED_D001_SHA:
        raise AlphaContractError("HG005 D003 market context SHA mismatch")
    if context.get("price_session") != "2026-10-01":
        raise AlphaContractError("HG005 D003 price session mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if context.get(field) is not False:
            raise AlphaContractError(f"HG005 D003 requires market {field}=false")
    rows = context.get("key_mechanical_context")
    if not isinstance(rows, dict):
        raise AlphaContractError("HG005 D003 market rows unavailable")
    return rows


def _validate_synthesis(synthesis: dict[str, Any]) -> None:
    if synthesis.get("synthesis_id") != EXPECTED_D002B_ID:
        raise AlphaContractError("HG005 D003 synthesis identity mismatch")
    if synthesis.get("synthesis_sha256") != EXPECTED_D002B_SHA:
        raise AlphaContractError("HG005 D003 synthesis SHA mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if synthesis.get(field) is not False:
            raise AlphaContractError(f"HG005 D003 requires synthesis {field}=false")


def _fact_index(synthesis: dict[str, Any]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    result: dict[str, dict[str, list[dict[str, Any]]]] = {}
    rows = synthesis.get("extractions")
    if not isinstance(rows, list):
        raise AlphaContractError("HG005 D003 extraction rows unavailable")
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG005 D003 extraction row must be object")
        symbol = str(row.get("symbol") or "")
        if not symbol:
            raise AlphaContractError("HG005 D003 extraction symbol missing")
        symbol_index = result.setdefault(symbol, {})
        facts = row.get("facts")
        if not isinstance(facts, list):
            raise TypeError("HG005 D003 extraction facts must be list")
        for fact in facts:
            if not isinstance(fact, dict) or fact.get("status") != "EXPLICIT":
                continue
            name = str(fact.get("fact_name") or "")
            if not name:
                raise AlphaContractError("HG005 D003 explicit fact name missing")
            symbol_index.setdefault(name, []).append(fact)
    return result


def _fact_values(
    index: dict[str, dict[str, list[dict[str, Any]]]],
    symbol: str,
    name: str,
) -> list[dict[str, Any]]:
    return index.get(symbol, {}).get(name, [])


def _latest_fact(
    index: dict[str, dict[str, list[dict[str, Any]]]],
    symbol: str,
    name: str,
) -> dict[str, Any]:
    values = _fact_values(index, symbol, name)
    if not values:
        raise AlphaContractError(f"{symbol}: required fact missing: {name}")

    def key(row: dict[str, Any]) -> str:
        value = row.get("effective_or_reporting_date")
        return value if isinstance(value, str) else ""

    latest_date = max(key(row) for row in values)
    latest = [row for row in values if key(row) == latest_date]
    canonical = {
        (str(row.get("value")), str(row.get("unit")))
        for row in latest
    }
    if len(canonical) != 1:
        raise AlphaContractError(f"{symbol}: latest fact conflict: {name}")
    return latest[0]


def _number(
    index: dict[str, dict[str, list[dict[str, Any]]]],
    symbol: str,
    name: str,
) -> float:
    row = _latest_fact(index, symbol, name)
    return _finite_positive(row.get("value"), f"{symbol}.{name}")


def _lane_state(synthesis: dict[str, Any], symbol: str, lane: str) -> str:
    companies = synthesis.get("companies")
    if not isinstance(companies, dict):
        raise AlphaContractError("HG005 D003 synthesis companies unavailable")
    company = companies.get(symbol)
    if not isinstance(company, dict):
        raise AlphaContractError(f"HG005 D003 missing company synthesis: {symbol}")
    lanes = company.get("lanes")
    if not isinstance(lanes, list):
        raise AlphaContractError(f"HG005 D003 lanes unavailable: {symbol}")
    matches = [row for row in lanes if row.get("lane") == lane]
    if len(matches) != 1:
        raise AlphaContractError(f"{symbol}: expected one {lane} lane")
    return str(matches[0].get("source_state") or "")


def _anant_raj(
    market: dict[str, Any],
    facts: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    cap = _finite_positive(
        market["ANANTRAJ"]["reported_fd_market_cap_inr_crore"],
        "ANANTRAJ.market_cap",
    )
    revenue = _number(facts, "ANANTRAJ", "demerged_business_fy26_revenue_inr_crore")
    mw = _number(facts, "ANANTRAJ", "operating_data_center_capacity_mw")
    revenue_rows = [
        {
            "ev_revenue_multiple": multiple,
            "gross_separated_business_ev_inr_crore": revenue * multiple,
            "gross_ev_to_current_market_cap": revenue * multiple / cap,
        }
        for multiple in ANANTRAJ_EV_REVENUE
    ]
    mw_rows = [
        {
            "ev_per_operating_mw_inr_crore": multiple,
            "gross_separated_business_ev_inr_crore": mw * multiple,
            "gross_ev_to_current_market_cap": mw * multiple / cap,
        }
        for multiple in ANANTRAJ_EV_PER_MW
    ]
    return {
        "lane": "DEMERGER_ENTITLEMENT",
        "state": "SENSITIVITY_READY_GROSS_EV_ONLY",
        "current_market_cap_inr_crore": cap,
        "demerged_business_fy26_revenue_inr_crore": revenue,
        "operating_data_center_capacity_mw": mw,
        "revenue_multiple_surface": revenue_rows,
        "operating_mw_surface": mw_rows,
        "equity_bridge_state": "BLOCKED_TRANSFERRED_NET_DEBT_AND_LIABILITIES_UNQUANTIFIED",
    }


def _reverse_ebitda_hurdles(
    *,
    cap: float,
    multiples: tuple[float, ...],
    area_sqft: float | None = None,
    observed_quarter_ebitda: float | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for uplift in UPLIFT_TARGETS:
        value_required = cap * uplift
        for multiple in multiples:
            annual = value_required / multiple
            row: dict[str, Any] = {
                "target_equity_uplift_pct": uplift * 100.0,
                "ev_ebitda_multiple": multiple,
                "required_incremental_annual_ebitda_inr_crore": annual,
            }
            if area_sqft is not None:
                row["required_annual_ebitda_per_sqft_inr"] = (
                    annual * 10_000_000.0 / area_sqft
                )
            if observed_quarter_ebitda is not None:
                quarterly = annual / 4.0
                row["quarterly_equivalent_ebitda_inr_crore"] = quarterly
                row["quarterly_equivalent_vs_observed_q1_ebitda"] = (
                    quarterly / observed_quarter_ebitda
                )
            rows.append(row)
    return rows


def _devx(
    market: dict[str, Any],
    facts: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    cap = _finite_positive(
        market["DEVX"]["reported_fd_market_cap_inr_crore"],
        "DEVX.market_cap",
    )
    area = _number(facts, "DEVX", "winston_area_sqft")
    deposit = _number(facts, "DEVX", "security_deposit_required_inr_crore")
    deployed = _number(facts, "DEVX", "security_deposit_utilized_inr_crore")
    return {
        "lane": "CAPITAL_DEPLOYMENT_AND_DILUTION",
        "state": "REVERSE_HURDLE_READY",
        "current_market_cap_inr_crore": cap,
        "winston_area_sqft": area,
        "security_deposit_required_inr_crore": deposit,
        "security_deposit_utilized_inr_crore": deployed,
        "deposit_required_to_market_cap": deposit / cap,
        "deposit_utilized_to_market_cap": deployed / cap,
        "hurdles": _reverse_ebitda_hurdles(
            cap=cap,
            multiples=DEVX_MULTIPLES,
            area_sqft=area,
        ),
        "explicit_winston_guidance_state": "NO_EXPLICIT_REVENUE_OR_EBITDA_GUIDANCE",
    }


def _npst(
    market: dict[str, Any],
    facts: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    cap = _finite_positive(
        market["NPST"]["reported_fd_market_cap_inr_crore"],
        "NPST.market_cap",
    )
    revenue = _number(facts, "NPST", "q1fy27_revenue_inr_crore")
    ebitda = _number(facts, "NPST", "q1fy27_ebitda_inr_crore")
    raise_amount = _number(facts, "NPST", "raise_amount_inr_crore")
    deployed = _number(facts, "NPST", "cumulative_deployed_inr_crore")
    unutilized = _number(facts, "NPST", "unutilized_proceeds_inr_crore")
    return {
        "lane": "CAPITAL_DEPLOYMENT_MONITOR",
        "state": "REVERSE_HURDLE_READY",
        "current_market_cap_inr_crore": cap,
        "q1fy27_revenue_inr_crore": revenue,
        "q1fy27_ebitda_inr_crore": ebitda,
        "raise_amount_inr_crore": raise_amount,
        "cumulative_deployed_inr_crore": deployed,
        "unutilized_proceeds_inr_crore": unutilized,
        "raise_to_market_cap": raise_amount / cap,
        "deployed_to_market_cap": deployed / cap,
        "unutilized_to_market_cap": unutilized / cap,
        "hurdles": _reverse_ebitda_hurdles(
            cap=cap,
            multiples=NPST_MULTIPLES,
            observed_quarter_ebitda=ebitda,
        ),
    }


def _sambhv(
    market: dict[str, Any],
    facts: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    cap = _finite_positive(
        market["SAMBHV"]["reported_fd_market_cap_inr_crore"],
        "SAMBHV.market_cap",
    )
    shares = _finite_positive(
        market["SAMBHV"]["lanes"]["DILUTION_FINANCING"]["event_adjusted_fd_shares"],
        "SAMBHV.event_adjusted_fd_shares",
    )
    capacity = _number(facts, "SAMBHV", "phase1_stainless_capacity_addition_mmtpa")
    capex_million = _number(facts, "SAMBHV", "phase1_capex_inr_million")
    capex_cr = capex_million / 10.0
    rows = []
    tonnes = capacity * 1_000_000.0
    for utilization in SAMBHV_UTILIZATION:
        for ebitda_per_tonne in SAMBHV_EBITDA_PER_TONNE:
            incremental_ebitda_cr = (
                tonnes * utilization * ebitda_per_tonne / 10_000_000.0
            )
            for multiple in SAMBHV_MULTIPLES:
                gross_ev = incremental_ebitda_cr * multiple
                net_equity = gross_ev - capex_cr
                rows.append(
                    {
                        "utilization_pct": utilization * 100.0,
                        "ebitda_per_tonne_inr": ebitda_per_tonne,
                        "ev_ebitda_multiple": multiple,
                        "incremental_ebitda_inr_crore": incremental_ebitda_cr,
                        "gross_incremental_ev_inr_crore": gross_ev,
                        "gross_incremental_ev_to_market_cap": gross_ev / cap,
                        "conservative_net_incremental_equity_value_inr_crore": net_equity,
                        "conservative_net_equity_value_to_market_cap": net_equity / cap,
                        "conservative_net_incremental_value_per_share_inr": (
                            net_equity * 10_000_000.0 / shares
                        ),
                    }
                )
    return {
        "lane": "DILUTION_FINANCING_AND_PHASE1_CAPACITY",
        "state": "SENSITIVITY_READY",
        "current_market_cap_inr_crore": cap,
        "event_adjusted_fd_shares": shares,
        "phase1_capacity_addition_mmtpa": capacity,
        "phase1_capex_inr_million": capex_million,
        "phase1_capex_inr_crore_deterministic_conversion": capex_cr,
        "surface": rows,
        "latest_financing_stage": _latest_fact(
            facts, "SAMBHV", "financing_stage_text"
        )["value"],
    }


def build_payoff_frameworks(
    *,
    market_context: dict[str, Any],
    d002b_synthesis: dict[str, Any],
) -> dict[str, Any]:
    market = _validate_market_context(market_context)
    _validate_synthesis(d002b_synthesis)

    for symbol, lane in (
        ("ANANTRAJ", "DEMERGER_ENTITLEMENT"),
        ("DEVX", "DILUTION_FINANCING"),
        ("DEVX", "CAPITAL_DEPLOYMENT_MONITOR"),
        ("NPST", "CAPITAL_DEPLOYMENT_MONITOR"),
        ("SAMBHV", "DILUTION_FINANCING"),
    ):
        if _lane_state(d002b_synthesis, symbol, lane) != "SOURCE_READY":
            raise AlphaContractError(f"{symbol}/{lane}: D003 source-ready gate closed")

    if _lane_state(d002b_synthesis, "INOXGREEN", "ACQUISITION_ECONOMICS") != "SOURCE_PARTIAL":
        raise AlphaContractError("INOXGREEN acquisition must remain source-partial")
    if _lane_state(d002b_synthesis, "INOXGREEN", "DEMERGER_ENTITLEMENT") != "SOURCE_PARTIAL":
        raise AlphaContractError("INOXGREEN demerger must remain source-partial")

    facts = _fact_index(d002b_synthesis)
    companies = {
        "ANANTRAJ": _anant_raj(market, facts),
        "DEVX": _devx(market, facts),
        "NPST": _npst(market, facts),
        "SAMBHV": _sambhv(market, facts),
        "INOXGREEN": {
            "state": "PAYOFF_FRAMEWORK_BLOCKED_SOURCE_PARTIAL",
            "blocked_lanes": [
                "ACQUISITION_ECONOMICS",
                "DEMERGER_ENTITLEMENT",
            ],
        },
    }

    output = {
        "schema_version": 1,
        "framework_id": FRAMEWORK_ID,
        "classification": "FAMILY_SPECIFIC_BREAK_EVEN_AND_PAYOFF_SENSITIVITY_NOT_EXPECTED_RETURN",
        "source_market_context_sha256": EXPECTED_D001_SHA,
        "source_d002b_synthesis_sha256": EXPECTED_D002B_SHA,
        "uplift_hurdles_pct": [value * 100.0 for value in UPLIFT_TARGETS],
        "companies": companies,
        "completion_probabilities_assigned": False,
        "expected_returns_calculated": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["framework_sha256"] = digest(output)
    return output
