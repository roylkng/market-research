"""L001 P012 original-market repricing tests, not investment prediction."""

from __future__ import annotations

import math

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.l001_p012_zuari_reprice import (
    JUNE_REPORTED_TOTAL_CR,
    ORIGINAL_JUNE_HOLDINGS,
    repriced_listed_portfolio,
)


def prices_at_june():
    return {
        (row.symbol, row.isin): row.june_reference_price_inr
        for row in ORIGINAL_JUNE_HOLDINGS
    }


def test_june_prices_reproduce_original_issuer_aggregate_despite_rounding():
    result = repriced_listed_portfolio(
        prices_at_june(), zuari_historical_basic_shares=29781184,
        zuari_oct15_close=267.55,
    )
    assert result["oct15_pro_forma_portfolio_mark_cr"] == JUNE_REPORTED_TOTAL_CR
    assert result["source_june_rounded_components_sum_cr"] == 4224
    assert result["june_component_rounding_scale_not_share_count"] < 1
    assert result["old_march_net_debt_cr"] == 2519.4245
    assert result["oct15_historical_issued_share_market_cap_cr"] == 796.795578
    assert result["investments_holdings_confirmed_unchanged_after_june"] is False
    assert result["after_oct15_price_source_capture_is_not_oct15_eod_signal"] is True
    assert result["investment_authorized"] is False
    assert result["expected_return"] is None


def test_lower_chambal_quote_can_erase_apparent_discount():
    prices = prices_at_june()
    prices[("CHAMBLFERT", "INE085A01013")] = 350
    out = repriced_listed_portfolio(
        prices, zuari_historical_basic_shares=29781184,
        zuari_oct15_close=267.55,
    )
    assert out["oct15_pro_forma_portfolio_mark_cr"] < 4223
    assert out["additional_markdown_asset_haircut_needed_to_match_basic_cap"] < .21472411
    assert out["portfolio"][0]["individual_mark_change_fraction"] < 0


def test_missing_or_changed_isin_rejects_source_instead_of_guessing():
    prices = prices_at_june()
    del prices[("TEXINFRA", "INE435C01024")]
    with pytest.raises(AlphaContractError, match="all five original"):
        repriced_listed_portfolio(
            prices, zuari_historical_basic_shares=29781184,
            zuari_oct15_close=267.55,
        )
    prices[("TEXINFRA", "INE000000000")] = 109
    with pytest.raises(AlphaContractError, match="all five original"):
        repriced_listed_portfolio(
            prices, zuari_historical_basic_shares=29781184,
            zuari_oct15_close=267.55,
        )


def test_nonfinite_negative_and_unrealistic_haircuts_reject():
    for value in (float("nan"), -1, 0, float("inf")):
        prices = prices_at_june()
        prices[("CHAMBLFERT", "INE085A01013")] = value
        with pytest.raises(AlphaContractError):
            repriced_listed_portfolio(
                prices, zuari_historical_basic_shares=29781184,
                zuari_oct15_close=267.55,
            )
    for h in ((-0.1,), (1.2,), (float("nan"),), ()):
        with pytest.raises(AlphaContractError):
            repriced_listed_portfolio(
                prices_at_june(), zuari_historical_basic_shares=29781184,
                zuari_oct15_close=267.55, haircuts=h,
            )


def test_invalid_historical_issued_shares_not_silently_imputed():
    with pytest.raises(AlphaContractError):
        repriced_listed_portfolio(
            prices_at_june(), zuari_historical_basic_shares=0,
            zuari_oct15_close=267.55,
        )


def test_june_asset_repricing_is_monotone_in_holding_quotes():
    prices = prices_at_june()
    first = repriced_listed_portfolio(
        prices, zuari_historical_basic_shares=29781184,
        zuari_oct15_close=267.55,
    )
    raised = dict(prices)
    raised[("ZUARI", "INE840M01016")] = 230 * 1.15
    second = repriced_listed_portfolio(
        raised, zuari_historical_basic_shares=29781184,
        zuari_oct15_close=267.55,
    )
    assert second["oct15_pro_forma_portfolio_mark_cr"] > first[
        "oct15_pro_forma_portfolio_mark_cr"
    ]
