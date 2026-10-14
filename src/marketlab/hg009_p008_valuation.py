"""Source-complete owner-cash valuation math. No default scenario probabilities.

Inputs are incompatible with the current incomplete P008 dossiers by design.
They require independent issuer evidence, actual original market-source bytes,
current diluted equity, documented parent cash attribution and calibration.
Tests use explicitly synthetic fixtures. No execution permissions are produced.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

from marketlab.alpha import AlphaContractError, digest

HORIZON_YEARS = 3
SCENARIOS = ("BEAR", "BASE", "BULL")
SOURCE_KEYS = (
    "owner_cash_source",
    "share_capital_source",
    "cash_and_minority_source",
    "price_and_depth_source",
    "forward_assumptions_source",
    "probability_calibration_source",
)


def _amount(obj: dict, name: str, *, min_value: float = 0) -> float:
    value = obj.get(name)
    if type(value) not in (float, int) or not math.isfinite(value):
        raise AlphaContractError(f"P008 valuation missing finite {name}")
    if value < min_value:
        raise AlphaContractError(f"P008 valuation below required floor: {name}")
    return float(value)


def _source_bindings(
    source_meta: dict[str, dict], original_bytes: dict[str, bytes]
) -> None:
    if set(source_meta) != set(SOURCE_KEYS):
        raise AlphaContractError("P008 valuation incomplete independent primary evidence")
    for key in SOURCE_KEYS:
        item = source_meta[key]
        if (
            item.get("independently_verified_original_source") is not True
            or item.get("original_raw_bytes_archived") is not True
            or not isinstance(item.get("original_document_url"), str)
            or not item["original_document_url"].startswith("https://")
            or not isinstance(item.get("frozen_as_of_date"), str)
            or not isinstance(item.get("sha256"), str)
            or len(item["sha256"]) != 64
        ):
            raise AlphaContractError(f"P008 valuation incomplete source gate: {key}")
        raw = original_bytes.get(key)
        if (
            not isinstance(raw, bytes)
            or not raw
            or hashlib.sha256(raw).hexdigest() != item["sha256"]
        ):
            raise AlphaContractError(f"P008 valuation source hash mismatch: {key}")


def evaluate_issuer_equity_dcf(
    *,
    identity: dict[str, Any],
    owner_cash: dict[str, Any],
    market: dict[str, Any],
    scenarios: list[dict[str, Any]],
    source_meta: dict[str, dict],
    original_bytes: dict[str, bytes],
) -> dict[str, Any]:
    """3-year cash-to-equity DCF, explicitly synthetic until raw proof ready."""
    _source_bindings(source_meta, original_bytes)
    if (
        identity.get("symbol") is None
        or len(str(identity.get("isin") or "")) != 12
        or identity.get("accounting_regime") not in (
            "NONFINANCIAL_CONSOLIDATED_EQUITY_OWNER_CASH",
        )
        or owner_cash.get("period_end") is None
        or owner_cash.get("parent_minorities_reconciled") is not True
        or owner_cash.get("maint_and_growth_capex_separated") is not True
        or owner_cash.get("cash_financing_lease_reconciled") is not True
        or owner_cash.get("working_capital_normalized") is not True
        or owner_cash.get("restricted_investment_cash_excluded") is not True
        or market.get("corporate_action_basis_verified") is not True
        or market.get("order_book_depth_and_impact_verified") is not True
        or market.get("date") is None
    ):
        raise AlphaContractError("P008 valuation shareholder/source reconciliation incomplete")
    cf0 = _amount(owner_cash, "normalized_owner_cash_cr", min_value=1e-9)
    excess = _amount(owner_cash, "separately_verified_excess_cash_cr")
    shares = _amount(market, "current_fully_diluted_shares", min_value=1)
    price = _amount(market, "dated_original_nse_eq_price_inr", min_value=1e-9)
    hurdle = _amount(market, "required_equity_return_fraction")
    impact = _amount(market, "total_round_trip_impact_fees_tax_fraction")
    discount = _amount(market, "shareholder_discount_rate")
    if discount > 0.6 or impact >= 0.5 or hurdle > 0.8:
        raise AlphaContractError("P008 implausible source-backed cost/discount setting")
    if [s.get("name") for s in scenarios] != list(SCENARIOS):
        raise AlphaContractError("P008 3 named bear/base/bull cases required")
    counts = [_amount(s, "historical_base_rate_events") for s in scenarios]
    if sum(counts) < 30 or any(x == 0 for x in counts):
        raise AlphaContractError("P008 probability calibration needs >=30 cases and no empty bins")
    total = sum(counts)
    rows = []
    for s, observations in zip(scenarios, counts, strict=True):
        growth = _amount(s, "annual_owner_cash_growth_plus_one")
        growth -= 1
        multiple = _amount(s, "terminal_cash_to_equity_multiple", min_value=0.01)
        if not (-0.9 < growth <= 0.7) or multiple > 35:
            raise AlphaContractError("P008 unbounded growth or terminal cash multiple")
        cash = [
            cf0 * ((1 + growth) ** yr) for yr in range(1, HORIZON_YEARS + 1)
        ]
        present = sum(
            value / ((1 + discount) ** year)
            for year, value in enumerate(cash, start=1)
        )
        terminal = cash[-1] * multiple / ((1 + discount) ** HORIZON_YEARS)
        equity_cr = excess + present + terminal
        per_share = equity_cr * 10_000_000 / shares
        gross = per_share / price - 1
        net = gross - impact
        rows.append({
            "name": s["name"],
            "base_rate_sample_count": observations,
            "empirical_base_rate_probability": round(observations / total, 8),
            "annual_growth_hypothesis_fraction": round(growth, 8),
            "terminal_owner_cash_multiple": multiple,
            "equity_value_cr": round(equity_cr, 5),
            "per_diluted_share_inr": round(per_share, 5),
            "gross_price_change_fraction": round(gross, 8),
            "net_price_change_fraction_after_cost_proxy": round(net, 8),
            "three_year_net_annualized_return": (
                round((1 + net) ** (1 / 3) - 1, 8) if net > -1 else None
            ),
            "beats_predeclared_return_hurdle": net > hurdle,
        })
    mean_value = sum(
        (r["base_rate_sample_count"] / total) * r["per_diluted_share_inr"]
        for r in rows
    )
    result = {
        "schema_version": 1,
        "model_id": "HG009-P008-EQUITY-OWNER-CASH-3Y-DCF-v1",
        "company_identity": identity,
        "as_of_market_date": market["date"],
        "cash_flow_period_end": owner_cash["period_end"],
        "horizon_years": HORIZON_YEARS,
        "evidence_sha256_by_dimension": {
            key: source_meta[key]["sha256"] for key in SOURCE_KEYS
        },
        "scenarios": rows,
        "weighted_per_share_value_inr": round(mean_value, 5),
        "comparison_share_price_inr": price,
        "weighted_gross_change_fraction": round(mean_value / price - 1, 8),
        "weighted_net_change_after_cost_fraction": round(
            mean_value / price - 1 - impact, 8
        ),
        "this_is_not_realized_future_return": True,
        "not_a_causal_llm_alpha_test": True,
        "uncertainty_not_removed_by_scenario_weights": True,
        "all_capital_execution_disabled": True,
        "live_capital_allowed": False,
    }
    result["model_sha256"] = digest(result)
    return result
