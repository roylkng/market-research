from __future__ import annotations

import hashlib
import math
from datetime import date
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_market import DailyEquityObservation, parse_udiff_eq_panel

PANEL_ID = "SS002-P007-v1"
P006_SHA = "e4ff14a24c204471ad6fee037fe93afbddce66e9f46119707f4d9f4fdb8603e7"
PRICE_SESSION = "2026-10-09"
ACCEPTANCE_GRID = (0.0, 0.25, 0.50, 0.75, 1.0)
RESIDUAL_MULTIPLIERS = (0.70, 0.85, 1.00)


def _positive(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AlphaContractError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise AlphaContractError(f"{label} must be finite and positive")
    return number


def _claim(row: dict[str, Any], path: str, unit: str) -> float:
    matches = [
        claim
        for claim in row.get("claims", [])
        if claim.get("field_path") == path
    ]
    if len(matches) != 1:
        raise AlphaContractError(f"{row['symbol']}: missing/duplicate term {path}")
    claim = matches[0]
    if (
        claim.get("extracted_unit") != unit
        or claim.get("citation_integrity_verified") is not True
        or claim.get("independent_semantic_verification") != "PENDING"
    ):
        raise AlphaContractError(f"{row['symbol']}: term provenance is invalid {path}")
    return _positive(claim.get("extracted_value"), path)


def _breakeven_acceptance(price: float, buyback: float, residual: float) -> dict[str, Any]:
    if buyback <= residual:
        return {"state": "NO_MONOTONIC_TENDER_ACCEPTANCE_ADVANTAGE", "minimum_fraction": None}
    threshold = (price - residual) / (buyback - residual)
    if threshold <= 0:
        return {"state": "NONE_REQUIRED", "minimum_fraction": 0.0}
    if threshold > 1:
        return {"state": "IMPOSSIBLE_WITHIN_UNIT_INTERVAL", "minimum_fraction": None}
    return {"state": "WITHIN_UNIT_INTERVAL", "minimum_fraction": threshold}


def tender_payoff_surface(*, purchase_price: float, buyback_price: float) -> dict[str, Any]:
    p = _positive(purchase_price, "purchase_price")
    b = _positive(buyback_price, "buyback_price")
    scenarios = []
    for mult in RESIDUAL_MULTIPLIERS:
        residual = p * mult
        threshold = _breakeven_acceptance(p, b, residual)
        for accepted in ACCEPTANCE_GRID:
            proceeds = accepted * b + (1.0 - accepted) * residual
            scenarios.append(
                {
                    "acceptance_fraction_hypothetical": accepted,
                    "residual_price_multiple_hypothetical": mult,
                    "residual_price_inr_hypothetical": residual,
                    "gross_cash_proceeds_per_initial_share_inr": proceeds,
                    "conditional_gross_price_change_pct_before_all_costs": (
                        proceeds / p - 1.0
                    ) * 100.0,
                    "breakeven_acceptance": threshold,
                }
            )
    return {
        "status": "CONDITIONAL_GROSS_SENSITIVITY_ONLY",
        "official_close_inr": p,
        "source_extracted_buyback_price_inr_unverified_semantics": b,
        "fully_accepted_gross_tender_premium_pct_before_all_costs": (b / p - 1.0) * 100.0,
        "acceptance_grid": list(ACCEPTANCE_GRID),
        "residual_price_multiple_grid": list(RESIDUAL_MULTIPLIERS),
        "hypothetical_scenarios": scenarios,
        "acceptance_distribution_estimated": False,
        "residual_exit_price_forecasted": False,
        "taxes_fees_slippage_included": False,
        "annualized": False,
    }


def rights_theoretical_surface(
    *,
    cum_rights_price: float,
    fully_paid_issue_price: float,
    rights_shares: int,
    existing_shares: int,
) -> dict[str, Any]:
    p = _positive(cum_rights_price, "cum_rights_price")
    issue = _positive(fully_paid_issue_price, "fully_paid_issue_price")
    if (
        isinstance(rights_shares, bool)
        or not isinstance(rights_shares, int)
        or rights_shares <= 0
        or isinstance(existing_shares, bool)
        or not isinstance(existing_shares, int)
        or existing_shares <= 0
    ):
        raise AlphaContractError("rights entitlement numerator/denominator must be positive integers")
    if issue >= p:
        return {
            "state": "NO_POSITIVE_THEORETICAL_IN_THE_MONEY_EXERCISE_VALUE",
            "cum_rights_price_inr": p,
            "fully_paid_issue_price_inr": issue,
            "rights_per_existing": rights_shares / existing_shares,
            "theoretical_ex_rights_price_inr": None,
            "existing_share_entitlement_value_inr": 0.0,
            "fully_paid_rights_share_value_net_of_subscription_inr": 0.0,
            "partly_paid_cash_calls_verified": False,
            "investment_return_estimated": False,
        }
    terp = (existing_shares * p + rights_shares * issue) / (
        existing_shares + rights_shares
    )
    return {
        "state": "THEORETICAL_FULLY_PAID_DILUTION_MECHANICS_ONLY",
        "cum_rights_price_inr": p,
        "fully_paid_issue_price_inr": issue,
        "rights_shares": rights_shares,
        "existing_shares": existing_shares,
        "rights_per_existing": rights_shares / existing_shares,
        "theoretical_ex_rights_price_inr": terp,
        "existing_share_entitlement_value_inr": p - terp,
        "fully_paid_rights_share_value_net_of_subscription_inr": terp - issue,
        "theoretical_new_share_fraction_after_full_subscription": (
            rights_shares / (existing_shares + rights_shares)
        ),
        "partly_paid_cash_calls_verified": False,
        "investment_return_estimated": False,
    }


def _validate_packet(packet: dict[str, Any]) -> list[dict[str, Any]]:
    if packet.get("pack_id") != "SS002-P006-v1" or packet.get("pack_sha256") != P006_SHA:
        raise AlphaContractError("P007 requires frozen P006 packet")
    if packet.get("case_count") != 8 or packet.get("explicit_fact_count") != 52:
        raise AlphaContractError("P007 requires complete original P006 case accounting")
    for field in (
        "independent_semantic_audit_complete",
        "current_entry_prices_verified",
        "share_action_clearance_proven",
        "expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if packet.get(field) is not False:
            raise AlphaContractError(f"P007 requires P006 {field}=false")
    rows = packet.get("cases")
    if not isinstance(rows, list) or len(rows) != 8:
        raise AlphaContractError("P007 P006 cases unavailable")
    symbols = [row.get("symbol") for row in rows]
    if len(set(symbols)) != 8:
        raise AlphaContractError("P007 P006 case symbols are not unique")
    return rows


def build_p007_price_scenarios(packet: dict[str, Any], *, udiff_raw: bytes) -> dict[str, Any]:
    rows = _validate_packet(packet)
    observations = parse_udiff_eq_panel(udiff_raw, session_date=date.fromisoformat(PRICE_SESSION))
    by_identity: dict[tuple[str, str], DailyEquityObservation] = {
        (row.symbol, row.isin): row for row in observations
    }
    outputs = []
    matched = 0
    for row in sorted(rows, key=lambda x: x["symbol"]):
        symbol = row["symbol"]
        isin = row["isin"]
        observation = by_identity.get((symbol, isin))
        price = observation.close_price if observation is not None else None
        if price is not None:
            matched += 1
        scenario: dict[str, Any] = {
            "symbol": symbol,
            "isin": isin,
            "research_lane": row.get("research_lane"),
            "price_session": PRICE_SESSION,
            "price_state": (
                "EXACT_EQ_ISIN_MATCH" if observation is not None else "SOURCE_IDENTITY_UNAVAILABLE"
            ),
            "official_close_inr": price,
            "official_turnover_inr": observation.turnover_inr if observation else None,
            "scenario_family": "NONE_SOURCE_INCOMPLETE_OR_NOT_APPLICABLE",
            "conditional_mechanics": None,
            "source_terms_semantically_independently_verified": False,
            "dated_entry_price_current_at_future_execution": False,
            "underwriting_ready": False,
            "expected_return_estimated": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        }
        if price is not None and symbol == "VRLLOG":
            b = _claim(row, "security_economics.offer_price_per_share", "INR_PER_SHARE")
            n = _claim(row, "security_economics.maximum_securities", "EQUITY_SHARES")
            amount = _claim(row, "consideration.total_consideration", "INR_LAKH")
            if not math.isclose(b * n, amount * 100_000.0, rel_tol=1e-10):
                raise AlphaContractError("VRLLOG extracted buyback terms contradict mechanically")
            scenario["scenario_family"] = "TENDER_BUYBACK"
            scenario["conditional_mechanics"] = tender_payoff_surface(
                purchase_price=price, buyback_price=b
            )
        if price is not None and symbol == "OLAELEC":
            issue = _claim(row, "security_economics.issue_price_per_share", "INR_PER_RIGHTS_SHARE")
            numerator = _claim(row, "ratios_entitlement.rights_entitlement_numerator", "RIGHTS_SHARES")
            denominator = _claim(row, "ratios_entitlement.rights_entitlement_denominator", "EXISTING_SHARES")
            n = _claim(row, "security_economics.number_of_securities", "PARTLY_PAID_RIGHTS_SHARES")
            amount = _claim(row, "consideration.total_consideration", "INR_ASSUMING_FULL_SUBSCRIPTION_AND_CALL")
            if not math.isclose(issue * n, amount, rel_tol=1e-10):
                raise AlphaContractError("OLAELEC extracted capital amount contradicts share/price math")
            if not numerator.is_integer() or not denominator.is_integer():
                raise AlphaContractError("OLAELEC entitlement ratio must be integer")
            scenario["scenario_family"] = "PARTLY_PAID_RIGHTS_ISSUE"
            scenario["conditional_mechanics"] = rights_theoretical_surface(
                cum_rights_price=price,
                fully_paid_issue_price=issue,
                rights_shares=int(numerator),
                existing_shares=int(denominator),
            )
        outputs.append(scenario)

    mechanical = sum(row["conditional_mechanics"] is not None for row in outputs)
    checks = {
        "all_eight_identities_accounted": len(outputs) == 8,
        "at_least_six_exact_official_eq_prices": matched >= 6,
        "both_tender_and_rights_mechanics_present": mechanical == 2,
        "no_independent_semantic_approval_created": all(
            row["source_terms_semantically_independently_verified"] is False
            for row in outputs
        ),
        "no_portfolio_or_live_capital": all(
            row["portfolio_eligibility_allowed"] is False
            and row["live_capital_allowed"] is False for row in outputs
        ),
    }
    result = {
        "schema_version": 1,
        "panel_id": PANEL_ID,
        "classification": "POST_EVENT_PRICE_AND_CONDITIONAL_GROSS_MECHANICS_NOT_EXPECTED_RETURN",
        "source_p006_sha256": P006_SHA,
        "price_session": PRICE_SESSION,
        "official_bhavcopy_sha256": hashlib.sha256(udiff_raw).hexdigest(),
        "identity_count": len(outputs),
        "matched_price_count": matched,
        "mechanical_scenario_count": mechanical,
        "threshold_passes": checks,
        "feasibility_pass": all(checks.values()),
        "rows": outputs,
        "post_announcement_price_observed": True,
        "future_holding_period_return_outcomes_opened": False,
        "model_fitted": False,
        "independent_semantic_audit_complete": False,
        "share_action_clearance_proven": False,
        "underwriting_ready": False,
        "expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["panel_sha256"] = digest(result)
    return result
