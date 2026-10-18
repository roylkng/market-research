"""Arithmetic and safety constraints for post-hoc cash-residual NAV sensitivity."""

from __future__ import annotations

from dataclasses import replace

from marketlab.l001_p009_asset_nav import AssetNavCase, stress_non_cash_nav


def case(**changes):
    data = {
        "symbol": "GESHIP", "price_inr": 1484.1,
        "price_observation_date": "2026-10-15",
        "issuer_nav_per_share_inr": 1886.0, "nav_as_of_date": "2026-06-30",
        "issuer_net_cash_cr": 8056.0, "historical_basic_shares_cr": 14.2767161,
        "nav_source": "issuer Q1FY27 original presentation",
        "net_cash_source": "issuer Q1FY27 original presentation",
        "original_price_source": "HG009 original NSE Oct15 packet",
        "source_original_bytes_verified": False,
        "fully_diluted_shares_verified_at_price_date": False,
    }
    data.update(changes)
    return AssetNavCase(**data)


def test_crossdated_issuer_nav_is_arithmetic_not_return_prediction():
    value = stress_non_cash_nav(case(), (0.0, 0.15, 0.25, 0.30, 0.35))
    assert value["status"] == "POSTHOC_ASSET_NAV_MATH_ONLY"
    assert abs(value["cross_dated_price_discount_to_issuer_nav"] - 0.2130965) < 1e-6
    assert value["scenarios"][0]["illustrative_nav_per_share_inr"] == 1886
    assert value["scenarios"][3]["nav_to_historical_price_gap_fraction"] < .01
    assert value["scenarios"][4]["nav_to_historical_price_gap_fraction"] < 0
    assert value["source_original_bytes_verified"] is False
    assert value["issuer_nav_stale_or_unverified_not_investable"] is True
    assert value["investment_authorized"] is False
    assert value["expected_return"] is None


def test_future_nav_cannot_be_backdated():
    value = stress_non_cash_nav(case(nav_as_of_date="2026-11-15"), (0.1,))
    assert value["status"] == "ABSTAIN"
    assert "future_nav_used_with_past_price" in value["reasons"]


def test_invalid_and_nonfinite_haircuts_rejected():
    for h in ((-0.1,), (1.2,), (float("nan"),), (float("inf"),), ()):
        assert stress_non_cash_nav(case(), h)["status"] == "ABSTAIN"


def test_invalid_price_and_cash_rejected():
    assert stress_non_cash_nav(case(price_inr=0), (0.1,))["status"] == "ABSTAIN"
    assert stress_non_cash_nav(
        replace(case(), issuer_net_cash_cr=float("nan")), (0.1,)
    )["status"] == "ABSTAIN"


def test_cash_exceeding_nav_fails_closed():
    assert stress_non_cash_nav(case(issuer_net_cash_cr=30000), (0.1,))["status"] == "ABSTAIN"
