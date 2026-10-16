"""HG009 P019: expectation-gap arithmetic and source-gated scenario analysis.

This module deliberately does not forecast cash flows or estimate probabilities.
Only supplied, verified scenarios can produce expected values. Historical basic
capitalizations are not substitutes for fully diluted equity value.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


class EvidenceError(ValueError):
    """Missing or invalid provenance or economic inputs."""


@dataclass(frozen=True)
class Scenario:
    name: str
    probability: float
    annual_parent_owner_cash_cr: float
    terminal_multiple: float
    net_claims_cr: float = 0.0


@dataclass(frozen=True)
class Case:
    symbol: str
    price_inr: float
    fully_diluted_shares_cr: float | None
    shares_source: str | None
    price_source: str
    owner_cash_source: str | None
    scenarios: tuple[Scenario, ...]
    as_of: str
    terminal_years: int
    execution_cost_fraction: float
    annual_discount_rate: float
    independent_probability_basis: str | None = None
    dividend_present_value_cr: float = 0.0


def _finite(x: float, field: str) -> None:
    if not isfinite(x):
        raise EvidenceError(f"{field}_not_finite")


def reverse_hurdles(basic_equity_cap_cr: float, multiples: tuple[float, ...] = (12, 16, 20),
                    upside: float = 0.5) -> dict[str, float]:
    """Historical illustrative equity cash hurdle, not an investable valuation."""
    _finite(basic_equity_cap_cr, "cap")
    _finite(upside, "upside")
    if basic_equity_cap_cr <= 0 or upside <= -1:
        raise EvidenceError("invalid_cap_or_upside")
    values = {}
    for multiple in multiples:
        _finite(multiple, "multiple")
        if multiple <= 0:
            raise EvidenceError("nonpositive_multiple")
        values[str(multiple)] = basic_equity_cap_cr * (1 + upside) / multiple
    return values


def evaluate(case: Case) -> dict:
    """Evaluate externally specified scenarios, or explicitly abstain.

    The terminal owner-cash multiple is an equity-value proxy. Claims and
    dilution must be accounted for by the analyst, not inferred from CFO-PPE.
    """
    reasons = []
    if not case.shares_source or case.fully_diluted_shares_cr is None:
        reasons.append("current_fully_diluted_shares_unverified")
    if not case.owner_cash_source:
        reasons.append("parent_owner_cash_unverified")
    if not case.price_source:
        reasons.append("dated_price_source_missing")
    if not case.independent_probability_basis:
        reasons.append("scenario_probabilities_unsubstantiated")
    if not case.scenarios:
        reasons.append("no_source_backed_scenarios")
    if reasons:
        return {"status": "ABSTAIN", "symbol": case.symbol, "reasons": reasons,
                "investment_authorized": False}
    assert case.fully_diluted_shares_cr is not None
    for field, value in (("price", case.price_inr), ("shares", case.fully_diluted_shares_cr),
                         ("cost", case.execution_cost_fraction), ("discount", case.annual_discount_rate),
                         ("dividends", case.dividend_present_value_cr)):
        _finite(value, field)
    if case.price_inr <= 0 or case.fully_diluted_shares_cr <= 0:
        raise EvidenceError("nonpositive_price_or_shares")
    if not 0 <= case.execution_cost_fraction < 1 or case.annual_discount_rate < 0:
        raise EvidenceError("invalid_cost_or_discount")
    if case.terminal_years < 1 or case.dividend_present_value_cr < 0:
        raise EvidenceError("invalid_horizon_or_dividends")
    total_probability = 0.0
    values = []
    for s in case.scenarios:
        for field, v in (("probability", s.probability), ("cash", s.annual_parent_owner_cash_cr),
                         ("multiple", s.terminal_multiple), ("claims", s.net_claims_cr)):
            _finite(v, field)
        if not 0 <= s.probability <= 1 or s.terminal_multiple <= 0 or s.net_claims_cr < 0:
            raise EvidenceError("invalid_scenario")
        total_probability += s.probability
        # Negative owner cash is allowed as evidence of weakness but never
        # multiplied into negative operating value. Outstanding claims remain.
        terminal_equity_cr = max(0.0, max(0.0, s.annual_parent_owner_cash_cr) *
                                  s.terminal_multiple - s.net_claims_cr)
        pv_equity_cr = terminal_equity_cr / (1 + case.annual_discount_rate) ** case.terminal_years
        values.append((s.name, s.probability, pv_equity_cr))
    if abs(total_probability - 1.0) > 1e-9:
        raise EvidenceError("probabilities_do_not_sum_to_one")
    expected_pv_cr = sum(p * v for _, p, v in values) + case.dividend_present_value_cr
    price_cap_cr = case.price_inr * case.fully_diluted_shares_cr
    after_cost_edge = expected_pv_cr * (1 - case.execution_cost_fraction) / price_cap_cr - 1
    return {
        "status": "SCENARIO_MATH_ONLY",
        "symbol": case.symbol,
        "expected_pv_equity_cr": round(expected_pv_cr, 6),
        "after_cost_expected_value_gap_fraction": round(after_cost_edge, 8),
        "downside_terminal_pv_cr": round(min(v for _, _, v in values), 6),
        "source_price_cap_cr": round(price_cap_cr, 6),
        "investment_authorized": False,
        "note": "Scenario assumptions are external, not calibrated or validated by this calculation.",
    }
