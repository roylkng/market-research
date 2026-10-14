"""HG009-P003: outcome-blind accounting red-team for 100 frozen NSE cases.

All 100 get *review flags* from the frozen October 5 HG001 numeric source.
Two case-specific exceptions were subsequently checked in original NSE
issuer iXBRL pages and are explicitly labeled October 14 manual source
review, NOT already-known October 5 financial signals.

This is a documentation acquisition priority queue, NOT valuation, fraud
detection, stock ranking, prediction, or live execution.
"""

from __future__ import annotations

import copy
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_100 import load_hg001_router, validate_hg009_100

REVIEW_ID = "HG009-P003-2026-10-14-ACCOUNTING-QUALITY-RED-TEAM-v1"
SNAPSHOT_DATE = "2026-10-05"
REVIEW_DATE = "2026-10-14"
COHORT_SHA = "e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5"
EPS_GAP_THRESHOLD_PP = 40.0
MIN_EPS_FOR_GAP_PERCENT = 50.0
PBT_MARGIN_JUMP_PP = 8.0
EXTREME_EPS_PERCENT = 100.0
MAX_REV_FOR_EXTREME_PERCENT = 40.0
FINANCE_COST_SPIKE_PERCENT = 100.0
SOURCE = Path("research/hg009/original-hg001-d001-router-20261005.json.gz")
COHORT = Path("research/hg009/hg009-d001-100-experimental-companies-v1.json")

# These are manually transcribed public issuer/source disclosures. Original HTML
# bytes and first-seen retrieval metadata are NOT archived in this workstream.
# Publication is earlier than the October 14 method review, and income/cash
# units are explicit. No claim of audited cash-flow for PIX Q1 is made.
ORIGINAL_FILING_CASES: dict[str, dict[str, Any]] = {
    "MAYURUNIQ": {
        "source_url": (
            "https://nsearchives.nseindia.com/corporate/ixbrl/"
            "INTEGRATED_FILING_INDAS_159322_20052026182510_iXBRL_WEB.html"
        ),
        "source_reporting": "FY26_CONSOLIDATED_AUDITED",
        "source_period_end": "2026-03-31",
        "source_publication_or_filing_date": "2026-05-20",
        "source_unit": "INR_LAKH",
        "original_html_bytes_archived": False,
        "fy26_consolidated_pbt_lakh": 25898.23,
        "fy26_consolidated_cfo_lakh": 13315.27,
        "fy26_consolidated_ppe_cash_purchase_lakh": 2420.71,
        "fy26_inventory_working_capital_outflow_lakh": 4750.15,
        "fy26_receivables_working_capital_outflow_lakh": 2264.22,
        "fy26_other_current_assets_working_capital_outflow_lakh": 1776.33,
        "fy26_payables_working_capital_inflow_lakh": 2597.16,
    },
    "PIXTRANS": {
        "current_source_url": (
            "https://nsearchives.nseindia.com/corporate/ixbrl/"
            "INTEGRATED_FILING_INDAS_183737_07082026172912_iXBRL_WEB.html"
        ),
        "prior_source_url": (
            "https://nsearchives.nseindia.com/corporate/ixbrl/"
            "INTEGRATED_FILING_INDAS_109641_08082025184215_iXBRL_WEB.html"
        ),
        "source_reporting": "Q1FY27_VS_Q1FY26_STANDALONE_UNAUDITED",
        "source_period_end": "2026-06-30",
        "source_publication_or_filing_date": "2026-08-07",
        "source_unit": "INR_LAKH",
        "original_html_bytes_archived": False,
        "q1fy27_standalone_pbt_lakh": 6081.68,
        "q1fy26_standalone_pbt_lakh": 3096.66,
        "q1fy27_fvtpl_included_in_other_income_lakh": 2529.49,
        "q4fy26_other_expenses_fvtpl_loss_lakh": 2252.29,
    },
}


def _valid_metric(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if type(value) not in (float, int) or not math.isfinite(value):
        raise AlphaContractError(f"HG009-P003 invalid numeric source metric {name}")
    return float(value)


def _flags(row: dict[str, Any]) -> list[str]:
    metrics = row.get("earnings_metrics")
    if not isinstance(metrics, dict):
        raise AlphaContractError("HG009-P003 original HG001 numeric metrics absent")
    eps = _valid_metric(metrics.get("basic_eps_yoy_pct"), "EPS YoY")
    rev = _valid_metric(metrics.get("revenue_yoy_pct"), "revenue YoY")
    margin = _valid_metric(metrics.get("pbt_margin_delta_pp"), "margin change")
    current = _valid_metric(metrics.get("current_pbt_margin_pct"), "current margin")
    fin = _valid_metric(metrics.get("finance_cost_yoy_pct"), "finance YoY")
    flags = []
    if (
        eps is not None and rev is not None
        and eps >= MIN_EPS_FOR_GAP_PERCENT
        and eps - rev >= EPS_GAP_THRESHOLD_PP
    ):
        flags.append("EPS_REVENUE_DIVERGENCE_REVIEW")
    if margin is not None and margin >= PBT_MARGIN_JUMP_PP:
        flags.append("PBT_MARGIN_JUMP_REVIEW")
    if (
        eps is not None and rev is not None
        and eps >= EXTREME_EPS_PERCENT
        and rev <= MAX_REV_FOR_EXTREME_PERCENT
    ):
        flags.append("TRIPLE_DIGIT_EPS_MODERATE_TOPLINE_REVIEW")
    if current is not None and current < 0:
        flags.append("NEGATIVE_PRETAX_MARGIN_NOT_CHEAP_EARNINGS")
    if fin is not None and fin >= FINANCE_COST_SPIKE_PERCENT:
        flags.append("FINANCE_COST_SPIKE_REVIEW")
    if "INVESTMENT_HOLDING_HEAVY" in row.get("asset_opportunity_flags", []):
        flags.append("INVESTMENT_ASSET_VS_OPERATING_EARNINGS_RECONCILE")
    if eps is None and "EARNINGS_INFLECTION" in row.get(
        "active_opportunity_lanes", []
    ):
        flags.append("GROWTH_DENOMINATOR_EPS_UNDEFINED")
    return flags


def _positive_fact(case: dict, key: str) -> float:
    value = _valid_metric(case.get(key), key)
    if value is None or value <= 0:
        raise AlphaContractError(f"HG009-P003 original issuer fact {key} missing")
    return value


def build_two_filing_pilots() -> dict[str, dict[str, Any]]:
    mayur = ORIGINAL_FILING_CASES["MAYURUNIQ"]
    pix = ORIGINAL_FILING_CASES["PIXTRANS"]
    cfo = _positive_fact(mayur, "fy26_consolidated_cfo_lakh")
    capex = _positive_fact(mayur, "fy26_consolidated_ppe_cash_purchase_lakh")
    pretax = _positive_fact(mayur, "fy26_consolidated_pbt_lakh")
    fcf = cfo - capex
    if fcf <= 0 or cfo >= pretax:
        raise AlphaContractError("HG009-P003 Mayur original cashflow check drift")
    # Exchange statement is in INR lakh with two decimals. Conversion into
    # crore is rounded to four decimals to avoid machine-float display drift.
    working_capital_components = {
        "inventory": round(-_positive_fact(
            mayur, "fy26_inventory_working_capital_outflow_lakh"
        ) / 100, 4),
        "trade_receivables": round(-_positive_fact(
            mayur, "fy26_receivables_working_capital_outflow_lakh"
        ) / 100, 4),
        "other_current_assets": round(-_positive_fact(
            mayur, "fy26_other_current_assets_working_capital_outflow_lakh"
        ) / 100, 4),
        "trade_payables": round(_positive_fact(
            mayur, "fy26_payables_working_capital_inflow_lakh"
        ) / 100, 4),
    }
    pbt = _positive_fact(pix, "q1fy27_standalone_pbt_lakh")
    prior_pbt = _positive_fact(pix, "q1fy26_standalone_pbt_lakh")
    fvtpl = _positive_fact(
        pix, "q1fy27_fvtpl_included_in_other_income_lakh"
    )
    corrected = pbt - fvtpl
    if corrected <= 0 or fvtpl >= pbt:
        raise AlphaContractError("HG009-P003 PIX original FVTPL constraint drift")

    return {
        "MAYURUNIQ": {
            "company": "MAYURUNIQ",
            "source": mayur,
            "manual_extraction_as_of_ist": REVIEW_DATE,
            "audited_cashflow_reported": True,
            "all_values_in_inr_crore": True,
            "fy26_pbt_inr_crore": round(pretax / 100, 4),
            "fy26_cfo_inr_crore": round(cfo / 100, 4),
            "fy26_ppe_cash_purchase_inr_crore": round(capex / 100, 4),
            "fy26_cfo_less_ppe_purchase_proxy_inr_crore_not_normalized_fcf": (
                round(fcf / 100, 4)
            ),
            "fy26_cfo_over_pretax_profit_ratio_not_pat_conversion": round(
                cfo / pretax, 4
            ),
            "fy26_cfo_less_ppe_proxy_over_pbt_ratio": round(
                fcf / pretax, 4
            ),
            "selected_working_capital_component_movements_inr_crore": (
                working_capital_components
            ),
            "partial_wc_component_sum_is_not_total_wc_change": True,
            "root_cause_proven": False,
            "issuer_cfo_quality_reconciled_for_multiyear_cycle": False,
            "company_fair_value_available": False,
            "necessary_followup": [
                "MULTIYEAR_CASH_CONVERSION_TAX_AND_WORKING_CAPITAL_CYCLE",
                "MAINTENANCE_VS_GROWTH_PPE_AND_PLANT_UTILIZATION",
                "INVESTMENT_BALANCES_RESTRICTED_CASH_AND_SHARE_COUNT",
            ],
        },
        "PIXTRANS": {
            "company": "PIXTRANS",
            "source": pix,
            "manual_extraction_as_of_ist": REVIEW_DATE,
            "q1_reporting_basis": "STANDALONE_NOT_CONSOLIDATED",
            "all_values_in_inr_crore": True,
            "q1fy27_standalone_reported_pbt_inr_crore": round(pbt / 100, 4),
            "q1fy26_standalone_reported_pbt_inr_crore": round(prior_pbt / 100, 4),
            "q1fy27_fvtpl_nonoperating_included_in_income_inr_crore": round(
                fvtpl / 100, 4
            ),
            "q1fy27_pbt_excluding_only_investment_fvtpl_inr_crore": (
                round(corrected / 100, 4)
            ),
            "fvtpl_share_of_reported_pbt_percent": round(
                100 * fvtpl / pbt, 2
            ),
            "unadjusted_pbt_yoy_percent": round(
                100 * (pbt / prior_pbt - 1), 2
            ),
            "single_item_excluded_pbt_yoy_percent_not_normalized_earnings": round(
                100 * (corrected / prior_pbt - 1), 2
            ),
            "financial_assets_fair_value_gain_is_not_operating_profit": True,
            "tax_effect_of_reclassification_applied": False,
            "prior_period_other_income_normalized": False,
            "q1_cashflow_coverage_confirmed": False,
            "company_fair_value_available": False,
            "necessary_followup": [
                "CONSOLIDATED_OPERATING_EARNINGS_VS_STANDALONE_SEPARATE",
                "Q1_2025_OTHER_NONOPERATING_INCOME_AND_OTHER_Q1_BASE_EFFECTS",
                "FVTPL_INVESTMENT_ASSET_REALIZABILITY_AND_CASHFLOW",
            ],
        },
    }


def build_hg009_accounting_review(
    *,
    router: dict[str, Any],
    cohort: dict[str, Any],
) -> dict[str, Any]:
    validate_hg009_100(cohort, source=router)
    if cohort.get("cohort_sha256") != COHORT_SHA:
        raise AlphaContractError("HG009-P003 source cohort SHA changed")
    names = {
        (row["symbol"], row["isin"]): row for row in router["rows"]
    }
    rows: list[dict[str, Any]] = []
    for selected in cohort["selected"]:
        original = names.get((selected["symbol"], selected["isin"]))
        if original is None or digest(original) != selected[
            "full_frozen_router_row_sha256"
        ]:
            raise AlphaContractError("HG009-P003 original numeric signal row drift")
        flags = _flags(original)
        metrics = original["earnings_metrics"]
        rows.append({
            "symbol": selected["symbol"],
            "isin": selected["isin"],
            "research_class": selected["research_class"],
            "source_snapshot_date_not_review_date": SNAPSHOT_DATE,
            "source_earnings_metrics": metrics,
            "document_acquisition_flags": flags,
            "issuer_regime_and_accounting_basis_verified": False,
            "quarterly_cfo_capex_cash_conversion_verified": False,
            "source_filing_manual_review_case": (
                selected["symbol"] in ORIGINAL_FILING_CASES
            ),
            "company_expected_return": None,
            "company_normalized_fcf": None,
            "company_fair_value": None,
            "selection_is_not_investment_eligibility": True,
        })
    rows.sort(key=lambda row: row["symbol"])
    pilots = build_two_filing_pilots()
    if not set(pilots).issubset({row["symbol"] for row in rows}):
        raise AlphaContractError("HG009-P003 manual audits not frozen in HG009 cohort")
    counts = Counter(flag for row in rows for flag in row["document_acquisition_flags"])
    result: dict[str, Any] = {
        "schema_version": 1,
        "review_id": REVIEW_ID,
        "classification": "ORIGINAL_SOURCE_ACCOUNTING_DOCUMENT_REDTEAM_NOT_ALPHA",
        "method_review_date": REVIEW_DATE,
        "original_screen_snapshot_date": SNAPSHOT_DATE,
        "original_screen_had_no_future_return_labels": True,
        "original_hg009_cohort_sha256": COHORT_SHA,
        "selected_case_count": 100,
        "cashflow_primary_source_manual_pilot_case_count": len(pilots),
        "thresholds_are_diagnostic_not_statistically_calibrated": {
            "eps_revenue_divergence_min_eps_yoy_percent": MIN_EPS_FOR_GAP_PERCENT,
            "eps_revenue_gap_min_percentage_points": EPS_GAP_THRESHOLD_PP,
            "pbt_margin_jump_min_percentage_points": PBT_MARGIN_JUMP_PP,
            "extreme_eps_yoy_percent": EXTREME_EPS_PERCENT,
            "max_revenue_yoy_for_extreme_eps_percent": MAX_REV_FOR_EXTREME_PERCENT,
            "finance_cost_growth_spike_percent": FINANCE_COST_SPIKE_PERCENT,
        },
        "screen_flags_count": dict(sorted(counts.items())),
        "source_outcome_agnostic_company_rows": rows,
        "original_nse_iXBRL_manual_filing_pilots": pilots,
        "two_pilot_original_html_bytes_retained_and_hashed": False,
        "all_100_filing_cashflow_quality_verified": False,
        "finance_company_industry_specific_accounting_model_required": True,
        "eps_growth_is_not_sustainable_cash_earnings": True,
        "investment_assets_are_not_free_distributable_cash": True,
        "screens_are_not_misconduct_allegations": True,
        "latest_oct14_price_used": False,
        "future_returns_opened": False,
        "expected_returns_calculated": False,
        "equity_value_or_current_fully_diluted_share_count_calculated": False,
        "investable_stocks_recommended": False,
        "live_capital_allowed": False,
    }
    result["packet_sha256"] = digest(result)
    return result


def materialize_hg009_accounting_review(root: Path) -> dict[str, Any]:
    router = load_hg001_router(root / SOURCE)
    cohort = json.loads((root / COHORT).read_text(encoding="utf-8"))
    return build_hg009_accounting_review(router=router, cohort=cohort)


def validate_hg009_accounting_review(
    result: dict[str, Any], *, router: dict[str, Any], cohort: dict[str, Any]
) -> None:
    unsigned = copy.deepcopy(result)
    sha = unsigned.pop("packet_sha256", None)
    if sha != digest(unsigned):
        raise AlphaContractError("HG009-P003 accounting review SHA mismatch")
    expected = build_hg009_accounting_review(router=router, cohort=cohort)
    if result != expected:
        raise AlphaContractError("HG009-P003 numerical source review not reproducible")
