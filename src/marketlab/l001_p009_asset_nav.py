"""L001 P009: asset-heavy NAV-discount downside arithmetic, never alpha.

Cross-dated issuer NAV and historical basic price cannot establish a margin of
safety. Haircut only the non-cash residual NAV, not net cash twice. A company's
reported cash and NAV are caller-provided assertions, not verified by this code.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class AssetNavCase:
    symbol: str
    price_inr: float
    price_observation_date: str
    issuer_nav_per_share_inr: float
    nav_as_of_date: str
    issuer_net_cash_cr: float
    historical_basic_shares_cr: float
    nav_source: str
    net_cash_source: str
    original_price_source: str
    source_original_bytes_verified: bool
    fully_diluted_shares_verified_at_price_date: bool


def _valid_positive(value: float) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(value) and value > 0


def stress_non_cash_nav(case: AssetNavCase, haircuts: tuple[float, ...]) -> dict:
    """Stress non-cash residual NAV with asset haircuts.

    A time-lagged asset statement can show arithmetic, not current fair value.
    No share buyback or dividends are netted here because dates are unequal.
    """
    reasons = []
    if not case.symbol or not case.nav_source or not case.net_cash_source or not case.original_price_source:
        reasons.append("source_identification_incomplete")
    if any(not _valid_positive(v) for v in (
        case.price_inr, case.issuer_nav_per_share_inr, case.historical_basic_shares_cr,
    )) or not isinstance(case.issuer_net_cash_cr, (int, float)) or not isfinite(case.issuer_net_cash_cr):
        reasons.append("invalid_nav_cash_or_basic_equity")
    from datetime import date

    try:
        price_date = date.fromisoformat(case.price_observation_date)
        nav_date = date.fromisoformat(case.nav_as_of_date)
        if nav_date > price_date:
            reasons.append("future_nav_used_with_past_price")
    except (TypeError, ValueError):
        reasons.append("invalid_observation_dates")
    if not haircuts or any(
        not isinstance(h, (int, float)) or isinstance(h, bool)
        or not isfinite(h) or not 0 <= h <= 1 for h in haircuts
    ):
        reasons.append("haircut_values_invalid")
    if reasons:
        return {
            "symbol": case.symbol, "status": "ABSTAIN", "reasons": sorted(set(reasons)),
            "investment_authorized": False,
        }
    net_cash_per_share = case.issuer_net_cash_cr / case.historical_basic_shares_cr
    non_cash_nav = case.issuer_nav_per_share_inr - net_cash_per_share
    if non_cash_nav < 0:
        return {
            "symbol": case.symbol, "status": "ABSTAIN",
            "reasons": ["net_cash_exceeds_issuer_nav"], "investment_authorized": False,
        }
    scenarios = [
        {
            "non_cash_residual_haircut_fraction": float(haircut),
            "illustrative_nav_per_share_inr": round(net_cash_per_share + non_cash_nav * (1 - haircut), 4),
            "nav_to_historical_price_gap_fraction": round(
                (net_cash_per_share + non_cash_nav * (1 - haircut)) / case.price_inr - 1, 8
            ),
        }
        for haircut in sorted(set(haircuts))
    ]
    return {
        "symbol": case.symbol, "status": "POSTHOC_ASSET_NAV_MATH_ONLY",
        "historical_price_date": case.price_observation_date,
        "issuer_nav_date": case.nav_as_of_date,
        "issuer_nav_per_share_inr": case.issuer_nav_per_share_inr,
        "historical_basic_price_inr": case.price_inr,
        "cross_dated_price_discount_to_issuer_nav": round(
            1 - case.price_inr / case.issuer_nav_per_share_inr, 8
        ),
        "issuer_cash_per_historical_basic_share_inr": round(net_cash_per_share, 4),
        "residual_non_cash_nav_per_share_inr": round(non_cash_nav, 4),
        "source_original_bytes_verified": case.source_original_bytes_verified,
        "fully_diluted_sharecount_verified_at_price_date": case.fully_diluted_shares_verified_at_price_date,
        "nav_is_current_on_price_date": case.nav_as_of_date == case.price_observation_date,
        "issuer_nav_stale_or_unverified_not_investable": True,
        "cash_buyback_vessel_repricing_ownership_unadjusted": True,
        "scenario_return_probability": None,
        "expected_return": None,
        "investment_authorized": False,
        "scenarios": scenarios,
    }
