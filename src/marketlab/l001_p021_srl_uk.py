"""Reconcile original scanned UK SunRisers Leeds statutory financial tables.

Source figures are whole GBP in the issuer's 14-month FRS102 accounts. The
original manual page readings are preserved. This model CANNOT convert mixed-
ownership period cash flow into an annualized post-acquisition investor return.
"""

from __future__ import annotations

import copy
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest

REGISTRY = Path("registry/l001_p021_srl_uk_filing_facts.json")
P020 = Path("research/l001/l001-p020-srl-franchise-profit-and-impairment-hurdle-v1.json")
P020_BLOB_SHA = "1be878259454939e46e646105fbac4d5764f8feb"
P020_SIGNATURE = "7c6bb12c2e63eb4873e19401e525165f4b7eefc9714df8e452352c0e1b1a6311"
ID = "L001-P021-UK-SRL-14MONTH-SOURCE-CASH-v1"
SOURCE_URL = "https://www.suntv.in/pdf/AGM/2025/SunRisers_Leeds_Limited_Financials_25-26.pdf"
FROZEN_REVIEW = "2026-10-20"


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_original_sources(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict]:
    raw_facts = (root / REGISTRY).read_bytes()
    facts = json.loads(raw_facts)
    raw_parent = (root / P020).read_bytes()
    if _blob(raw_parent) != P020_BLOB_SHA:
        raise AlphaContractError("P021 parent original P020 signed source drift")
    parent = json.loads(raw_parent)
    unsigned = copy.deepcopy(parent)
    expected = unsigned.pop("report_sha256", None)
    if expected != P020_SIGNATURE or digest(unsigned) != expected:
        raise AlphaContractError("P021 parent P020 signature mismatch")
    if facts.get("original_issuer_url") != SOURCE_URL:
        raise AlphaContractError("P021 original UK subsidiary URL differs")
    receipt = {
        "original_registry_path": str(REGISTRY),
        "original_registry_raw_sha256": hashlib.sha256(raw_facts).hexdigest(),
        "pinned_parent_P020_git_blob_sha1": P020_BLOB_SHA,
        "pinned_parent_P020_packet_sha256": P020_SIGNATURE,
    }
    return facts, parent, receipt


def _pounds(facts: dict, key: str) -> Decimal:
    value = facts.get(key)
    if type(value) is not int or value < 0:
        raise AlphaContractError(f"P021 invalid original whole-pound amount: {key}")
    return Decimal(value)


def build_uk_cash_case(facts: dict, parent: dict, receipt: dict) -> dict:
    if (
        facts.get("review_date") != FROZEN_REVIEW
        or facts.get("reported_period_start") != "2025-02-01"
        or facts.get("source_reported_ownership_start") != "2025-07-28"
        or facts.get("reported_period_end") != "2026-03-31"
        or facts.get("statement_reporting_span_months") != 14
        or facts.get("financial_accounting_standard") != "UK_FRS_102"
        or facts.get("currency") != "GBP"
        or facts.get("raw_original_pdf_archived") is not False
        or facts.get("raw_original_pdf_sha256") is not None
        or facts.get("live_capital_allowed") is not False
        or parent.get("source_aoc1_period", {}).get("after_tax_profit_cr") != "16.33"
        or parent.get("source_impairment_note", {}).get(
            "management_dcf_discount_rate_percent"
        ) != "9"
    ):
        raise AlphaContractError("P021 UK period, parent control or FRS102 basis drift")
    money = facts.get("monetary_facts_gbp")
    if not isinstance(money, dict):
        raise AlphaContractError("P021 GBP financial statement missing")
    v = lambda key: _pounds(money, key)
    if (
        v("revenue") != sum((v("broadcast_income"), v("sponsorship_income"),
                              v("ticket_income"), v("other_income")))
        or v("revenue") - v("cost_of_sales") != v("gross_profit")
        or v("gross_profit") - v("administrative_expenses")
        != v("operating_profit")
        or v("operating_profit") - v("interest_expense")
        != v("profit_before_tax")
        or v("profit_before_tax") - v("tax_expense")
        != v("profit_after_tax")
        or v("cash_generated_operations") + v("tax_cash_refund")
        != v("net_operating_cash_inflow")
        or v("cash_interest_paid") + v("cash_dividends_paid")
        != v("net_cash_financing_outflow")
        or v("net_operating_cash_inflow") - v("net_cash_financing_outflow")
        != v("net_cash_increase")
        or v("cash_beginning") + v("net_cash_increase")
        != v("cash_end")
        or v("interest_expense") != v("cash_interest_paid")
    ):
        raise AlphaContractError("P021 subsidiary statement equations differ")
    purchase = _pounds(
        {"purchase": facts.get("parent_disclosed_acquisition_consideration_gbp")},
        "purchase",
    )
    if purchase != Decimal(100_500_000):
        raise AlphaContractError("P021 parent original GBP purchase consideration changed")
    operating = v("net_operating_cash_inflow")
    owner_coupon = operating - v("cash_interest_paid")
    hurdles = []
    for fraction in (Decimal("0.05"), Decimal("0.09"), Decimal("0.12")):
        target = fraction * purchase
        hurdles.append({
            "hypothetical_annual_cash_yield_fraction": float(fraction),
            "annual_owner_cash_needed_gbp": int(target),
            "ratio_to_mixed_14month_operating_cash_not_growth_forecast": round(
                float(target / operating), 4
            ),
            "verified_post_acquisition_recurring_owner_cash": False,
        })

    out = {
        "schema_version": 1,
        "report_id": ID,
        "research_date": FROZEN_REVIEW,
        "source_issuer": "SUNRISERS_LEEDS_LIMITED",
        "parent_issuer": "SUNTV",
        "source_facts_sha_receipts": receipt,
        "original_subsidiary_pdf_url": SOURCE_URL,
        "source_pages_original_zero_based": facts["source_pages_zero_based"],
        "original_document_scanned_visual_source": True,
        "original_full_pdf_archived_in_this_source_packet": False,
        "original_full_pdf_sha256": None,
        "original_first_retrieval_at_utc": None,
        "subsequent_pdf_capture_receipt_is_a_distinct_record": True,
        "reporting_basis": "UK_FRS_102_14_MONTH_MIXED_OWNERSHIP",
        "source_period_start": facts["reported_period_start"],
        "source_period_end": facts["reported_period_end"],
        "parent_control_effective": facts["source_reported_ownership_start"],
        "historical_original_gbp_tables": money,
        "statement_arithmetic_reconciled": True,
        "reported_14month_operating_cfo_gbp": int(operating),
        "reported_14month_cfo_less_financing_interest_gbp": int(owner_coupon),
        "reported_14month_cash_close_gbp_not_parent_distribution": int(v("cash_end")),
        "reported_dividends_paid_prior_owner_gbp": int(v("cash_dividends_paid")),
        "broadcast_revenue_fraction": round(
            float(v("broadcast_income") / v("revenue")), 6
        ),
        "original_deal_cash_consideration_gbp": int(purchase),
        "reported_mixed_period_cfo_to_deal_price_pct_not_roic": round(
            float(100 * operating / purchase), 4
        ),
        "reported_mixed_period_cfo_less_interest_to_deal_price_pct_not_roic": round(
            float(100 * owner_coupon / purchase), 4
        ),
        "illustrative_owner_cash_yield_hurdles_not_forecasts": hurdles,
        "future_rights_economic_life_and_renewal_cost_verified": False,
        "uk_cash_source_reconciled_to_parent_indas_consolidation": False,
        "subsidiary_14month_cash_is_post_control_only": False,
        "reported_dividends_were_post_suntv_control": False,
        "reported_cfo_is_normalized_parent_owner_fcf": False,
        "cross_currency_fx_adjusted_cash_return_calculated": False,
        "investor_required_cash_yield_calibrated": False,
        "actual_investor_rate_of_return_calculated": False,
        "current_suntv_fair_value_calculated": False,
        "expected_stock_return_estimated": False,
        "portfolio_eligible": False,
        "live_capital_allowed": False,
    }
    out["report_sha256"] = digest(out)
    return out


def materialize(root: Path) -> dict:
    facts, parent, receipt = load_original_sources(root)
    return build_uk_cash_case(facts, parent, receipt)


def verify(result: dict, root: Path) -> None:
    unsigned = copy.deepcopy(result)
    original_hash = unsigned.pop("report_sha256", None)
    if digest(unsigned) != original_hash:
        raise AlphaContractError("P021 source-derived report altered")
    if result != materialize(root):
        raise AlphaContractError("P021 signed financial sources do not replay")
