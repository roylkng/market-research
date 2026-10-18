"""L001 P010: falsifiable cross-dated holding-value and buyback sensitivities.

These functions do NOT authenticate issuer documents or predict security prices.
Inputs are sourced research assertions. All outputs reject investment permission.
Do not treat pledged shares as an additional debt haircut if the borrowing
secured by them is already deducted, or subtract a purchased share until its
legal extinguishment is independently established.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite


@dataclass(frozen=True)
class HoldingCompanyObservation:
    symbol: str
    price_date: str
    financial_position_date: str
    investments_date: str
    price_inr: float
    reported_basic_shares: int
    listed_stake_mtm_cr: float
    financial_borrowings_cr: float
    cash_equivalents_cr: float
    pledged_largest_stake_shares: int
    total_largest_stake_shares: int
    largest_stake_reference_quote_inr: float
    financing_interest_paid_cr: float
    operating_cashflow_cr: float
    ppe_cash_purchase_cr: float
    lease_cash_paid_cr: float
    issuer_original_presentation_bytes_authenticated: bool = False
    full_parent_attribution_verified: bool = False
    current_diluted_equity_verified: bool = False


@dataclass(frozen=True)
class BuybackObservation:
    symbol: str
    price_date: str
    issuer_nav_date: str
    cancellation_date: str
    old_shares: int
    legally_extinguished_shares: int
    purchased_after_cancellation_not_yet_extinguished: int
    quoted_price_inr: float
    issuer_nav_low_inr: float
    issuer_nav_mid_inr: float
    issuer_nav_high_inr: float
    cash_spent_on_cancelled_lot_cr: float
    original_nav_pdf_bytes_authenticated: bool = False
    extinguishment_certificate_authenticated: bool = False
    diluted_sharecount_verified: bool = False


def _valid(x: object, *, zero: bool = False) -> bool:
    return (
        isinstance(x, (int, float)) and not isinstance(x, bool)
        and isfinite(x) and (x >= 0 if zero else x > 0)
    )


def _dates(price: str, *historical: str) -> bool:
    try:
        today = date.fromisoformat(price)
        return all(date.fromisoformat(old) <= today for old in historical)
    except (ValueError, TypeError):
        return False


def _rejected(symbol: str, reason: str) -> dict:
    return {
        "symbol": symbol, "status": "ABSTAIN", "reasons": [reason],
        "investment_authorized": False, "expected_return": None,
    }


def holding_company_sensitivity(
    observation: HoldingCompanyObservation,
    *,
    investment_haircuts: tuple[float, ...] = (0, 0.1, 0.2, 0.25, 0.3),
) -> dict:
    """Listed-mark-to-market less *one* recognized debt net of cash, not SOTP.

    Subsidiary claims can overlap with pledged share collateral. Any other
    operating assets, minority interests, restricted investments and taxes
    are deliberately excluded. This simplistic residual is NOT a floor.
    """
    v = observation
    if not v.symbol or not _dates(
        v.price_date, v.financial_position_date, v.investments_date
    ):
        return _rejected(v.symbol, "identity_or_cross_date_invalid")
    scalars = (
        v.price_inr, v.reported_basic_shares, v.listed_stake_mtm_cr,
        v.financial_borrowings_cr, v.cash_equivalents_cr,
        v.total_largest_stake_shares, v.largest_stake_reference_quote_inr,
    )
    if any(not _valid(x) for x in scalars) or any(
        not _valid(x, zero=True) for x in (
            v.pledged_largest_stake_shares, v.financing_interest_paid_cr,
            v.operating_cashflow_cr, v.ppe_cash_purchase_cr, v.lease_cash_paid_cr,
        )
    ):
        return _rejected(v.symbol, "invalid_financial_quantity")
    if (
        type(v.reported_basic_shares) is not int
        or type(v.pledged_largest_stake_shares) is not int
        or type(v.total_largest_stake_shares) is not int
        or v.pledged_largest_stake_shares > v.total_largest_stake_shares
    ):
        return _rejected(v.symbol, "pledge_share_denominator_invalid")
    if not investment_haircuts or any(
        not _valid(h, zero=True) or h > 1 for h in investment_haircuts
    ):
        return _rejected(v.symbol, "invalid_investment_haircut")
    basic_equity_cr = v.reported_basic_shares * v.price_inr / 1e7
    net_borrowings = v.financial_borrowings_cr - v.cash_equivalents_cr
    pledged_stake_value_cr = (
        v.pledged_largest_stake_shares * v.largest_stake_reference_quote_inr / 1e7
    )
    base_residual_cr = v.listed_stake_mtm_cr - net_borrowings
    scenarios = tuple({
        "listed_asset_mark_to_market_haircut": float(h),
        "gross_listed_stake_mtm_cr": round(v.listed_stake_mtm_cr * (1 - h), 6),
        "simplified_residual_cr_not_shareholder_value": round(
            v.listed_stake_mtm_cr * (1 - h) - net_borrowings, 6
        ),
        "residual_relative_to_historical_basic_equity_fraction_not_expected_return": round(
            (v.listed_stake_mtm_cr * (1 - h) - net_borrowings) / basic_equity_cr - 1,
            8,
        ),
    } for h in sorted(set(investment_haircuts)))
    return {
        "symbol": v.symbol,
        "status": "POSTHOC_SUM_OF_PARTS_FALSIFICATION_ONLY",
        "price_date": v.price_date,
        "listed_stake_value_date": v.investments_date,
        "borrowing_and_cash_date": v.financial_position_date,
        "historical_basic_equity_cap_cr": round(basic_equity_cr, 6),
        "historical_net_borrowings_less_cash_cr": round(net_borrowings, 6),
        "illustrative_listed_assets_minus_net_borrowings_cr": round(
            base_residual_cr, 6
        ),
        "issuer_pledged_shares_of_largest_stake": v.pledged_largest_stake_shares,
        "pledged_fraction_largest_stake": round(
            v.pledged_largest_stake_shares / v.total_largest_stake_shares, 8
        ),
        "pledged_stake_gross_mtm_cr_not_extra_liability": round(
            pledged_stake_value_cr, 6
        ),
        "listed_asset_haircut_that_matches_price_no_other_assets": round(
            (base_residual_cr - basic_equity_cr) / v.listed_stake_mtm_cr, 8
        ),
        "historic_cfo_minus_ppe_cr_not_owner_cash": round(
            v.operating_cashflow_cr - v.ppe_cash_purchase_cr, 6
        ),
        "historic_cfo_less_ppe_interest_and_leases_cr_not_owner_cash": round(
            v.operating_cashflow_cr - v.ppe_cash_purchase_cr
            - v.financing_interest_paid_cr - v.lease_cash_paid_cr, 6
        ),
        "pledge_is_collateral_not_additional_debt": True,
        "issuer_presentation_original_bytes_authenticated": (
            v.issuer_original_presentation_bytes_authenticated
        ),
        "full_parent_attribution_verified": v.full_parent_attribution_verified,
        "current_diluted_equity_verified": v.current_diluted_equity_verified,
        "excess_return_probability": None,
        "expected_return": None,
        "investment_authorized": False,
        "scenarios": list(scenarios),
    }


def buyback_nav_sensitivity(observation: BuybackObservation) -> dict:
    """Respect *legally cancelled* shares and reduce NAV by cash actually spent.

    This models pro-forma NAV assuming zero changes in the other asset values
    between the old NAV date, cancellation date and historical price date.
    No observed current NAV, trading return or capital permission is inferred.
    """
    b = observation
    if not b.symbol or not _dates(
        b.price_date, b.issuer_nav_date, b.cancellation_date
    ):
        return _rejected(b.symbol, "observation_dates_invalid")
    if any(not _valid(x) for x in (
        b.old_shares, b.legally_extinguished_shares, b.quoted_price_inr,
        b.issuer_nav_low_inr, b.issuer_nav_mid_inr, b.issuer_nav_high_inr,
    )) or any(not _valid(x, zero=True) for x in (
        b.purchased_after_cancellation_not_yet_extinguished,
        b.cash_spent_on_cancelled_lot_cr,
    )):
        return _rejected(b.symbol, "invalid_share_or_nav_input")
    if any(type(x) is not int for x in (
        b.old_shares, b.legally_extinguished_shares,
        b.purchased_after_cancellation_not_yet_extinguished,
    )) or (
        b.legally_extinguished_shares >= b.old_shares
        or not b.issuer_nav_low_inr <= b.issuer_nav_mid_inr <= b.issuer_nav_high_inr
    ):
        return _rejected(b.symbol, "invalid_legal_shares_or_issuer_range")
    legal = b.old_shares - b.legally_extinguished_shares
    spent_rupees = b.cash_spent_on_cancelled_lot_cr * 1e7
    def proforma(nav: float) -> float:
        return (b.old_shares * nav - spent_rupees) / legal
    return {
        "status": "POSTHOC_CROSS_DATE_BUYBACK_NAV_MATH_ONLY",
        "symbol": b.symbol,
        "price_date": b.price_date,
        "issuer_nav_date": b.issuer_nav_date,
        "legal_cancellation_date": b.cancellation_date,
        "pre_buyback_issued_shares": b.old_shares,
        "shares_legally_extinguished": b.legally_extinguished_shares,
        "issued_shares_after_extinguishment": legal,
        "subsequent_purchased_not_yet_canceled_in_legal_denominator": (
            b.purchased_after_cancellation_not_yet_extinguished
        ),
        "historical_basic_equity_cap_cr_at_oct_price": round(
            b.quoted_price_inr * legal / 1e7, 6
        ),
        "historical_close_price_inr_not_executable_fill": b.quoted_price_inr,
        "original_issuer_nav_range_per_share_inr": [
            b.issuer_nav_low_inr, b.issuer_nav_high_inr
        ],
        "stale_nav_per_share_midpoint": b.issuer_nav_mid_inr,
        "post_cancellation_nav_per_share_as_if_no_other_changes": round(
            proforma(b.issuer_nav_mid_inr), 6
        ),
        "midpoint_nav_accretion_from_september_lot_only_inr": round(
            proforma(b.issuer_nav_mid_inr) - b.issuer_nav_mid_inr, 6
        ),
        "post_cancellation_nav_range_as_if_no_other_changes": [
            round(proforma(b.issuer_nav_low_inr), 6),
            round(proforma(b.issuer_nav_high_inr), 6),
        ],
        "issuer_nav_original_bytes_authenticated": (
            b.original_nav_pdf_bytes_authenticated
        ),
        "extinguishment_certificate_authenticated": (
            b.extinguishment_certificate_authenticated
        ),
        "diluted_sharecount_verified_at_price_date": (
            b.diluted_sharecount_verified
        ),
        "repurchased_uncanceled_shares_not_silently_retired": True,
        "issuer_nav_is_not_fair_value_certified": True,
        "expected_return": None,
        "investment_authorized": False,
    }


@dataclass(frozen=True)
class ReceivableSettlement:
    debtor: str
    creditor: str
    outstanding_before_cr: float
    first_payment_cr: float
    first_payment_date: str
    final_payment_cr: float
    final_payment_date: str
    source_first: str
    source_final: str
    audited_bank_credit_verified: bool = False


def creditor_recovery_reconciliation(
    settlement: ReceivableSettlement,
    *,
    research_cutoff_date: str,
    reference_basic_equity_cap_cr: float,
) -> dict:
    """Counterparty exchange confirmations of receivable conversion to cash.

    A completed repayment extinguishes an existing receivable. It is NOT
    incremental group wealth or proof the creditor repaid outside lenders.
    """
    p = settlement
    if (
        not p.debtor or not p.creditor
        or not p.source_first.startswith("https://www.zuari.in/")
        or not p.source_final.startswith("https://www.zuari.in/")
        or not _dates(
            research_cutoff_date, p.first_payment_date, p.final_payment_date
        )
        or p.first_payment_date > p.final_payment_date
    ):
        return _rejected(p.creditor, "original_repayment_identity_or_time_missing")
    if any(not _valid(v) for v in (
        p.outstanding_before_cr, p.first_payment_cr, p.final_payment_cr,
        reference_basic_equity_cap_cr,
    )):
        return _rejected(p.creditor, "repayment_amount_or_cap_invalid")
    amount = p.first_payment_cr + p.final_payment_cr
    if abs(amount - p.outstanding_before_cr) > 1e-6:
        return _rejected(p.creditor, "repayment_does_not_reconcile_to_prior_debt")
    return {
        "status": "ISSUER_COUNTERPARTY_DISCLOSED_FULL_RECEIVABLE_RECOVERY",
        "debtor": p.debtor,
        "creditor": p.creditor,
        "first_payment_date": p.first_payment_date,
        "final_payment_date": p.final_payment_date,
        "recovered_receivable_cr": round(amount, 6),
        "remaining_reported_receivable_cr": 0.0,
        "payment_as_fraction_of_old_basic_equity_cap": round(
            amount / reference_basic_equity_cap_cr, 8
        ),
        "bank_credit_independently_verified": p.audited_bank_credit_verified,
        "new_shareholder_wealth_from_debt_to_cash_reclassification_cr": 0,
        "creditor_external_debt_repayment_independently_verified": False,
        "cash_now_held_by_parent_or_subsidiary_unverified": True,
        "receipt_does_not_mean_free_cashflow": True,
        "investment_authorized": False,
        "expected_return": None,
    }


@dataclass(frozen=True)
class InternalGroupTransfer:
    parent: str
    wholly_owned_seller: str
    listed_issuer: str
    transaction_date: str
    acquired_target_shares: int
    parent_shares_before: int
    subsidiary_shares_before: int
    purchase_cost_cr: float
    source_uri: str


def internal_group_asset_transfer(
    transfer: InternalGroupTransfer, *, research_cutoff_date: str,
) -> dict:
    """Same-group transfer changes direct ownership, not consolidated units."""
    t = transfer
    if (
        not t.parent or not t.wholly_owned_seller or not t.listed_issuer
        or not t.source_uri.startswith("https://")
        or not _dates(research_cutoff_date, t.transaction_date)
        or any(type(v) is not int or v < 0 for v in (
            t.acquired_target_shares, t.parent_shares_before,
            t.subsidiary_shares_before,
        ))
        or t.acquired_target_shares == 0
        or t.acquired_target_shares > t.subsidiary_shares_before
        or not _valid(t.purchase_cost_cr)
    ):
        return _rejected(t.parent, "internal_transfer_source_or_identity_invalid")
    group_before = t.parent_shares_before + t.subsidiary_shares_before
    new_parent = t.parent_shares_before + t.acquired_target_shares
    new_sub = t.subsidiary_shares_before - t.acquired_target_shares
    return {
        "status": "INTRAGROUP_TRANSFER_NOT_NEW_GROUP_EQUITY_UNITS",
        "issuer": t.listed_issuer,
        "parent": t.parent,
        "wholly_owned_seller_asserted_not_corporate_tree_verified": (
            t.wholly_owned_seller
        ),
        "date": t.transaction_date,
        "parent_direct_shares_before": t.parent_shares_before,
        "parent_direct_shares_after": new_parent,
        "subsidiary_shares_before": t.subsidiary_shares_before,
        "subsidiary_shares_after": new_sub,
        "consolidated_shares_before": group_before,
        "consolidated_shares_after": new_parent + new_sub,
        "net_new_group_shares": 0,
        "reported_transaction_cost_cr_not_extra_consolidated_asset": (
            t.purchase_cost_cr
        ),
        "transaction_taxes_and_external_cash_leakage_not_reconciled": True,
        "historical_group_holding_must_not_be_double_counted": True,
        "expected_return": None,
        "investment_authorized": False,
    }
