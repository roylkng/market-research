"""Illustrative WWIL/Vibhav funding *capital-structure* bridge, not valuation.

The 7 Oct 2026 listed-company disclosure is available as third-party HTML
transcription, but independent review of the original BSE PDF is pending.
Never label the transfer completed or infer normalized EBITDA/returns.
"""

from __future__ import annotations

import math
from typing import Any

BRIDGE_ID = "HG007-P002-INOXGREEN-WWIL-CONDITIONAL-CAPITAL-STACK-v1"
KNOWN_CASE = "INOXGREEN"
SOURCE = {
    "reported_disclosure_date": "2026-10-07",
    "issuer": "Inox Green Energy Services Limited",
    "nse_symbol": "INOXGREEN",
    "original_bse_pdf_url": (
        "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"
        "d3241df5-32e2-4476-8075-bb5ed130e697.pdf"
    ),
    "original_pdf_independent_review_state": "BSE_403_BLOCKED_NOT_APPROVED",
    "secondary_text_url": (
        "https://bazaarwatch.com/announcement/197190/"
        "inox-green-energy-services-ltd-update-on-the-resolution-plan-"
        "for-wind-world-india-limited-and-invest"
    ),
    "third_party_analyst_url": (
        "https://www.arthneeti.com/announcements/"
        "inox-green-energy-services-ltd-update-on-the-resolution-plan-"
        "for-wind-world-india-limited-and-investment-in-vibhav-energy-"
        "private-limited-a-wholly-own-07-oct-2026"
    ),
    "official_source_pdf_sha256_verified": False,
}

PROVISIONAL_TERMS = {
    "gross_wwil_purchase_consideration_inr_crore": 550.0,
    "inox_green_cash_equity_subscription_inr_crore": 250.0,
    "inox_green_intercompany_deposit_inr_crore": 200.0,
    "authum_external_intercompany_deposit_inr_crore": 100.0,
    "inox_green_deposit_planned_equity_conversion_inr_crore": 50.0,
    "authum_deposit_planned_equity_conversion_inr_crore": 100.0,
    # BSE-filing HTML transcription states paid-up capital AFTER ₹250cr
    # share subscription at face value. Tiny preexisting ₹0.01cr remains.
    "vibhav_paid_up_equity_after_cash_subscription_inr_crore": 250.01,
}


def _number(value: object, name: str) -> float:
    if type(value) not in (float, int) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    if value < 0:
        raise ValueError(f"{name} cannot be negative")
    return float(value)


def build_conditional_funding_bridge(
    terms: dict[str, float],
    *,
    evidence_state: str,
    transfer_conditions_precedent_satisfied: bool,
    original_pdf_reviewed: bool,
) -> dict[str, Any]:
    """Model stated funding *if* all conditional conversions occur.

    There is no probability assigned to conversion or acquisition close.
    """
    if evidence_state != "SECONDARY_TRANSCRIPTION_AWAITING_ORIGINAL_PDF":
        raise ValueError("funding inputs cannot be promoted without original review protocol")
    if transfer_conditions_precedent_satisfied is not False or original_pdf_reviewed is not False:
        raise ValueError("current provisional bridge cannot certify legal close/original source")
    if not isinstance(terms, dict) or set(terms) != set(PROVISIONAL_TERMS):
        raise ValueError("conditional WWIL bridge requires exact declared funding fields")
    numbers = {key: _number(value, key) for key, value in terms.items()}
    purchase = numbers["gross_wwil_purchase_consideration_inr_crore"]
    parent_equity = numbers["inox_green_cash_equity_subscription_inr_crore"]
    parent_deposit = numbers["inox_green_intercompany_deposit_inr_crore"]
    third_party_deposit = numbers["authum_external_intercompany_deposit_inr_crore"]
    parent_convert = numbers["inox_green_deposit_planned_equity_conversion_inr_crore"]
    external_convert = numbers["authum_deposit_planned_equity_conversion_inr_crore"]
    paidup_before = numbers["vibhav_paid_up_equity_after_cash_subscription_inr_crore"]
    if paidup_before <= 0 or paidup_before < parent_equity:
        raise ValueError("subsidiary paid-up equity cannot be below cash subscription")
    if (
        parent_convert > parent_deposit
        or external_convert > third_party_deposit
        or not math.isclose(
            purchase, parent_equity + parent_deposit + third_party_deposit,
            abs_tol=1e-9,
            rel_tol=1e-12,
        )
    ):
        raise ValueError("WWIL stated funding sums/conversions do not reconcile")
    current_equity = paidup_before
    if purchase <= 0:
        raise ValueError("transaction purchase consideration must be positive")
    conditional_total_equity = current_equity + parent_convert + external_convert
    conditional_parent_equity = current_equity + parent_convert
    conditional_outside_equity = external_convert
    if conditional_total_equity <= 0:
        raise ValueError("conditional subsidiary equity denominator must be positive")
    parent_stake = conditional_parent_equity / conditional_total_equity
    outside_stake = conditional_outside_equity / conditional_total_equity

    return {
        "schema_version": 1,
        "bridge_id": BRIDGE_ID,
        "symbol": KNOWN_CASE,
        "classification": "PROVISIONAL_SOURCE_TRANSCRIPTION_FUNDING_BRIDGE_NOT_FAIR_VALUE",
        "source": SOURCE,
        "source_review_state": evidence_state,
        "reported_payment_date": "2026-10-06",
        "reported_transfer_status": "PAYMENT_MADE_BUT_BTA_CONDITIONS_PRECEDENT_PENDING",
        "provisional_reported_terms_inr_crore": numbers,
        "gross_purchase_consideration_inr_crore": purchase,
        "inox_green_total_reported_funding_inr_crore": parent_equity + parent_deposit,
        "authum_external_reported_funding_inr_crore": third_party_deposit,
        "preconversion_issuer_subsidiary_equity_ownership_fraction": 1.0,
        "hypothetical_post_both_conversions_equity_denominator_inr_crore": (
            conditional_total_equity
        ),
        "hypothetical_post_both_conversions_inox_equity_interest_fraction": (
            parent_stake
        ),
        "hypothetical_post_both_conversions_authum_equity_interest_fraction": (
            outside_stake
        ),
        "postconversion_remaining_inox_intercompany_deposit_inr_crore": (
            parent_deposit - parent_convert
        ),
        "postconversion_remaining_authum_deposit_inr_crore": (
            third_party_deposit - external_convert
        ),
        "conversions_completed_verified": False,
        "purchase_transfer_legally_completed_verified": False,
        "original_bse_pdf_audited_verified": False,
        "minority_interest_and_group_consolidation_reviewed": False,
        "future_target_ebitda_verified": False,
        "acquisition_expected_return_calculated": False,
        "market_price_or_fd_share_denominator_refreshed": False,
        "stock_price_target_authorized": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
        "interpretation": (
            "The 550 crore purchase payment is reported as 450 crore provided "
            "by Inox Green (250 equity subscription and 200 intercompany "
            "deposit), plus 100 crore Authum intercompany deposit. "
            "If the stated 50 and 100 crore deposits are eventually converted "
            "to subsidiary equity at the represented capital basis, Inox "
            "Green's illustrative subsidiary equity interest is about 75%, "
            "not a verified currently effective equity percentage. "
            "Intragroup loan interest is not an independent consolidated "
            "enterprise-value gain. Legal closing, target normalized earnings, "
            "liabilities, completion conditions, ownership dilution and "
            "market valuation remain unverified."
        ),
    }
