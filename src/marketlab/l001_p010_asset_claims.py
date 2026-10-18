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
