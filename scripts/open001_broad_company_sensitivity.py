"""OPEN001 source-bounded Indian company screening, not a buy-signal generator.

Annual FY2026 audited figures and the 2026-10-23 close are different dates.
All scenario multiples/growth inputs are deliberately hypothetical, not probabilities.
No frozen H-series experimental cohort is changed or backfilled.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT = (
    REPO / "research/broad-discovery/open001-bls-transrail-oct2026-source-input.json"
)


def number(data: object, name: str) -> float:
    if isinstance(data, bool) or not isinstance(data, (int, float)):
        raise TypeError(f"{name} requires numeric value")
    n = float(data)
    if not math.isfinite(n):
        raise ValueError(f"{name} must be finite")
    return n


def evaluate(data: dict) -> dict:
    if data["status"] != "POSTHOC_DISCOVERY_RESEARCH_ONLY":
        raise ValueError("forbidden research status")
    if data["overall_decision"] != "BLS_RELATIVE_PRIORITY_ABOVE_GESHIP_NON_INVESTABLE":
        raise ValueError("investment permission cannot be inferred")
    if {x["symbol"] for x in data["candidates"]} != {"BLS", "TRANSRAILL"}:
        raise ValueError("expected two independently identified candidates")
    results = []
    for issuer in data["candidates"]:
        p = number(issuer["price_inr"], "price")
        eps = number(issuer["fy26_diluted_eps_inr"], "EPS")
        cfo = number(issuer["fy26_consolidated_after_tax_cfo_crore"], "CFO")
        capex = number(issuer["fy26_cash_purchase_ppe_crore"], "PPE cash")
        if min(p, eps, cfo) <= 0 or capex < 0:
            raise ValueError("invalid price/EPS/cash inputs")
        if issuer["price_date"] != "2026-10-23":
            raise ValueError("dated price source invalid")
        if issuer["reference_financial_year_end"] != "2026-03-31":
            raise ValueError("FY source period altered")
        if issuer["conservative_or_parent_distributable_owner_cash_crore"] is not None:
            raise ValueError("uncertified parent-owner cash cannot be populated")

        if issuer["symbol"] == "BLS":
            shares = number(issuer["fy26_original_basic_shares_crore"], "shares")
            if shares <= 0:
                raise ValueError("invalid share denominator")
            market_cap = shares * p
            parent_pat = number(issuer["fy26_parent_attributable_pat_crore"], "parent PAT")
            minority_pat = number(issuer["fy26_nci_pat_crore"], "minority PAT")
            consolidated_pat = number(issuer["fy26_consolidated_pat_crore"], "group PAT")
            if abs(parent_pat + minority_pat - consolidated_pat) > 0.0001:
                raise ValueError("cannot attribute NCI profit to parent shareholders")
            visa_result = number(issuer["fy26_visas_segment_pre_finance_result_crore"], "visa")
            digital_result = number(issuer["fy26_digital_segment_pre_finance_result_crore"], "digital")
            if visa_result <= 0 or digital_result <= 0:
                raise ValueError("cannot establish segment result contribution")
            visa_result_share = visa_result / (visa_result + digital_result)
        else:
            market_cap = number(issuer["fy26_market_cap_crore_observed"], "market cap")
            visa_result_share = None

        if market_cap <= 0:
            raise ValueError("invalid market capitalization")
        scenarios = []
        names: set[str] = set()
        for case in issuer["hypothetical_two_year_scenarios"]:
            label = case["case"]
            if label in names:
                raise ValueError("duplicate stress scenario")
            names.add(label)
            shock = number(case["one_time_eps_shock_fraction"], "shock")
            growth = number(case["annual_eps_growth_fraction"], "growth")
            multiple = number(case["terminal_pe_multiple"], "P/E")
            if not (-1 < shock <= 1 and -1 < growth <= 2 and 1 <= multiple <= 40):
                raise ValueError("stress assumptions out of range")
            terminal = eps * (1 + shock) * (1 + growth) ** 2 * multiple
            scenarios.append({
                "case": label,
                "conditional_two_year_value_inr": round(terminal, 2),
                "conditional_price_change_pct": round((terminal / p - 1) * 100, 2),
                "probability": None,
                "is_price_target": False,
            })
        if names != {"bear", "flat_no_rerating", "conditional_base", "optimistic"}:
            raise ValueError("missing expected comparative sensitivity case")
        results.append({
            "symbol": issuer["symbol"],
            "price_at_2026_10_23": p,
            "FY26_diluted_eps": eps,
            "FY26_after_tax_consolidated_CFO_crore": cfo,
            "FY26_CFO_less_selected_PPE_crore": round(cfo - capex, 4),
            "FY26_naive_CFO_less_PPE_to_observed_mcap_pct": round(
                (cfo - capex) / market_cap * 100, 2
            ),
            "visa_share_of_reported_segment_results_pct": (
                round(visa_result_share * 100, 2)
                if visa_result_share is not None else None
            ),
            "two_year_conditional_sensitivities": scenarios,
            "verified_parent_owner_cash_crore": None,
            "recommendation": "NO_BUY_RESEARCH_ONLY",
        })
    return {
        "study": data["schema"],
        "as_of": data["research_date"],
        "used_known_historical_results_to_modify_original_HG009": False,
        "approved_live_capital": False,
        "investment_readiness": "NOT_ESTABLISHED",
        "candidates": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.input.read_text())), indent=2))


if __name__ == "__main__":
    main()
