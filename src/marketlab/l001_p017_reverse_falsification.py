"""L001 P017: reverse-value falsification at independently sourced Oct19 NSE prices.

Original 2026-10-15/19 prices are source-stamped, but legacy issuer NAV,
holdings, cashflow and shares are *older* observations. No owner intrinsic
value, expected return, trading signal or real-time market quote follows.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_daily import validate_hg009_daily_snapshot

ID = "L001-P017-20261019-CROSS-DATE-REVERSE-VALUATION-REDTEAM-v1"
SOURCE_PATHS = {
    "oct15": (
        "research/hg009/daily/2026-10-15-v1.json",
        "187fa19e8c2e8384dfc82b1fc3814e4768f0644e",
    ),
    "oct19": (
        "research/hg009/daily/2026-10-19-v1.json",
        "7f321de65ace44d76380060e7b18b0b8d5bfbd1d",
    ),
    "geship": (
        "research/l001/l001-p009-geship-buyback-nav-downside-20261018.md",
        "70d455d849d831928bab60ab2880681dc872d925",
    ),
    "zuari": (
        "research/l001/l001-p012-reprice-listed-strategic-stakes-20261018.md",
        "ad0552f1b2c0a35bf173c36b869a833449a92370",
    ),
    "datamatics": (
        "research/hg007/hg007-p049-datamatics-cash-hurdle-v1.json",
        "706c2dd100a49859b5054323baeddc345531fb59",
    ),
    "owner": (
        "research/l001/l001-p016-owner-cash-evidence-gates-100-v1.json",
        "00241232ca88aa8f1217407be0929e686335f928",
    ),
}
IDENTITIES = {
    "GESHIP": "INE017A01032",
    "ZUARIIND": "INE217A01012",
    "DATAMATICS": "INE365B01017",
}
# These values are the original *dated* manual issuer-source analyses in
# SHA-pinned memos. They are not new market-source observations.
GESHIP_Q1_NAV_INR = 1886.0
GESHIP_Q1_NET_CASH_CR = 8056.0
GESHIP_OLD_BASIC_SHARES_CR_ROUNDED = 14.2767
GESHIP_CUM_BUYBACK_PURCHASED_THROUGH_OCT16 = 2901660
GESHIP_LEGALLY_EXTINGUISHED_SEP_LOT = 1858941
ZUARI_OCT15_LISTED_MARK_CR = 3820.124826
ZUARI_MARCH_NET_BORROWINGS_CR = 2519.4245
ZUARI_STALE_BASIC_SHARES = 29781184
DATAMATICS_MARCH_BASIC_SHARES = 59106389
REVERSE_CASH_MULTIPLE = 16.0
REVERSE_GROSS_UPSIDE_HURDLE = 0.50


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_source_packets(root: Path) -> tuple[dict[str, Any], dict[str, dict]]:
    source: dict[str, Any] = {}
    receipts: dict[str, dict] = {}
    for key, (path, sha) in SOURCE_PATHS.items():
        raw = (root / path).read_bytes()
        if _git_blob(raw) != sha:
            raise AlphaContractError(f"P017 source {key} changed after original freeze")
        source[key] = json.loads(raw) if path.endswith(".json") else raw.decode("utf-8")
        receipts[key] = {
            "original_repository_path": path,
            "original_git_blob": sha,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    return source, receipts


def _dated_company_price(packet: dict, *, date: str, symbol: str) -> float:
    validate_hg009_daily_snapshot(packet)
    if packet.get("date_ist") != date:
        raise AlphaContractError("P017 NSE original price session drift")
    stocks = [x for x in packet["source_identity_rows"] if x["symbol"] == symbol]
    if (
        len(stocks) != 1
        or stocks[0].get("frozen_isin") != IDENTITIES[symbol]
        or stocks[0].get("state") != "ORIGINAL_NSE_EQ_OHLC_OBSERVED_NOT_FILL"
        or stocks[0].get("actual_trade_fill") is not False
    ):
        raise AlphaContractError(f"P017 official price/ISIN unverified: {symbol}")
    val = stocks[0]["ohlcv"]["close_inr"]
    if type(val) not in (int, float) or not (0 < val < 1_000_000):
        raise AlphaContractError("P017 original NSE company close is missing")
    return float(val)


def _r(value: float, decimals: int = 4) -> float:
    return round(value, decimals)


def build_l001_p017(
    sources: dict[str, Any],
    receipts: dict[str, dict],
) -> dict[str, Any]:
    first = {sym: _dated_company_price(sources["oct15"],date="2026-10-15",symbol=sym)
             for sym in IDENTITIES}
    final = {sym: _dated_company_price(sources["oct19"],date="2026-10-19",symbol=sym)
             for sym in IDENTITIES}
    owner = sources["owner"]
    owner_rows = {row["symbol"]: row for row in owner["company_cashflow_classification_rows"]}
    if (
        owner["issuer_count"] != 100
        or owner["issuer_sustainable_owner_cash_estimated_count"] != 0
        or owner["company_expected_return_estimated_count"] != 0
        or any(
            owner_rows[sym]["normalized_attributable_owner_cash_cr"] is not None
            for sym in IDENTITIES
        )
        or sources["datamatics"]["packet_sha256"]
        != "1b72056878c56f12f5c13b8f7d557d1fa8fa0e67c34fddd60621ffd890cfb278"
    ):
        raise AlphaContractError("P017 original owner-cash and basic fact gates drift")
    if "21.31%" not in sources["geship"] or "13.19%" not in sources["zuari"]:
        raise AlphaContractError("P017 original issuer audit baseline memo mismatch")

    price_rows = [
        {
            "symbol": sym,
            "frozen_isin": IDENTITIES[sym],
            "oct15_original_NSE_EQ_close_inr": first[sym],
            "oct19_original_NSE_EQ_close_inr": final[sym],
            "between_close_price_change_percent_not_pnl": _r(
                (final[sym] / first[sym] - 1) * 100, 4
            ),
            "economic_dividend_and_share_adjusted_return": None,
            "actual_fill_price": None,
            "prospective_strategy_signal": False,
        }
        for sym in IDENTITIES
    ]

    geship_cash_per_old_share = (
        GESHIP_Q1_NET_CASH_CR / GESHIP_OLD_BASIC_SHARES_CR_ROUNDED
    )
    residual = GESHIP_Q1_NAV_INR - geship_cash_per_old_share
    geship_haircut_15 = (GESHIP_Q1_NAV_INR - first["GESHIP"]) / residual
    geship_haircut_19 = (GESHIP_Q1_NAV_INR - final["GESHIP"]) / residual
    if not residual > 0:
        raise AlphaContractError("P017 source NAV/cash residual invalid")

    zuari_old_oct15_cap = first["ZUARIIND"] * ZUARI_STALE_BASIC_SHARES / 1e7
    zuari_old_oct19_cap = final["ZUARIIND"] * ZUARI_STALE_BASIC_SHARES / 1e7
    zuari_residual_15 = (
        ZUARI_OCT15_LISTED_MARK_CR - ZUARI_MARCH_NET_BORROWINGS_CR
    )
    zuari_additional_haircut_15 = (
        zuari_residual_15 - zuari_old_oct15_cap
    ) / ZUARI_OCT15_LISTED_MARK_CR

    p049 = sources["datamatics"]
    proxy = p049["fy26_cfo_less_fixed_asset_cash_spending_inr_crore_not_normalized_fcf"]
    if proxy != 284.42 or p049[
        "estimated_basic_shares_using_mar31_paidup_not_oct13_current"
    ] != DATAMATICS_MARCH_BASIC_SHARES:
        raise AlphaContractError("P017 original cash proxy or basic shares changed")
    datamatics_old_oct19_cap = (
        final["DATAMATICS"] * DATAMATICS_MARCH_BASIC_SHARES / 1e7
    )
    parity_cash = datamatics_old_oct19_cap / REVERSE_CASH_MULTIPLE
    fifty_upside_cash = parity_cash * (1 + REVERSE_GROSS_UPSIDE_HURDLE)

    result: dict[str, Any] = {
        "schema_version": 1,
        "research_id": ID,
        "source_review_as_of": "2026-10-19",
        "date_basis": "ORIGINAL_NSE_OCT15_AND_OCT19_POST_ENTRY_MARKET_CLOSES",
        "original_source_receipts": receipts,
        "dated_original_close_observations": price_rows,
        "company_diagnostics": {
            "GESHIP": {
                "historical_issuer_NAV_report_date": "2026-06-30",
                "issuer_NAV_per_share_inr_stale": GESHIP_Q1_NAV_INR,
                "issuer_reported_net_cash_cr_stale": GESHIP_Q1_NET_CASH_CR,
                "historical_basic_shares_crore_rounded_not_current": (
                    GESHIP_OLD_BASIC_SHARES_CR_ROUNDED
                ),
                "cash_per_old_share_estimate_inr": _r(geship_cash_per_old_share,2),
                "noncash_residual_NAV_per_old_share_estimate_inr": _r(residual,2),
                "dated_Oct15_discount_to_issuer_NAV_percent_not_margin_safety": _r(
                    (1 - first["GESHIP"] / GESHIP_Q1_NAV_INR) * 100,2
                ),
                "dated_Oct19_discount_to_issuer_NAV_percent_not_margin_safety": _r(
                    (1 - final["GESHIP"] / GESHIP_Q1_NAV_INR) * 100,2
                ),
                "break_even_haircut_noncash_NAV_Oct15_percent": _r(
                    geship_haircut_15 * 100,2
                ),
                "break_even_haircut_noncash_NAV_Oct19_percent": _r(
                    geship_haircut_19 * 100,2
                ),
                "issuer_buyback_cumulative_purchased_as_of_2026_10_16": (
                    GESHIP_CUM_BUYBACK_PURCHASED_THROUGH_OCT16
                ),
                "issuer_buyback_September_legally_extinguished_lot": (
                    GESHIP_LEGALLY_EXTINGUISHED_SEP_LOT
                ),
                "current_Oct19_fully_diluted_share_count_verified": False,
                "issuer_NAV_2026_10_19_repriced_with_fleet_values": False,
                "shipping_fleet_cycle_normalized_NAV": None,
                "current_shareholder_economic_return_estimate": None,
                "most_material_falsification": (
                    "APPRAISE_FLEET_OFFSHORE_TROUGH_VALUES_AND_RECONCILE_BUYBACK_SHARE_EXTINCTION"
                ),
            },
            "ZUARIIND": {
                "original_listed_holdings_mark_at_Oct15_cr": ZUARI_OCT15_LISTED_MARK_CR,
                "borrowing_net_of_cash_as_of_2026_03_31_cr_not_current": (
                    ZUARI_MARCH_NET_BORROWINGS_CR
                ),
                "historical_basic_shares_not_current": ZUARI_STALE_BASIC_SHARES,
                "Oct15_old_share_cap_cr": _r(zuari_old_oct15_cap,4),
                "Oct19_old_share_cap_cr_not_full_valuation": _r(
                    zuari_old_oct19_cap,4
                ),
                "Oct15_repriced_stakes_less_stale_March_debt_cr": _r(
                    zuari_residual_15,4
                ),
                "further_listed_holding_discount_erasing_Oct15_apparent_gap_pct": _r(
                    zuari_additional_haircut_15 * 100,2
                ),
                "Oct19_current_repriced_listed_holdings_cr": None,
                "Oct19_contemporaneous_debt_and_pledge_covenants_cr": None,
                "Oct19_actual_attributable_SOTP_value_cr": None,
                "Oct19_debt_pledged_value_double_counted": False,
                "cash_collections_and_Dubai_repatriation_after_August_confirmed": False,
                "Oct19_cheapness_inferred_from_price_drop": False,
                "most_material_falsification": (
                    "SAME_DAY_FIVE_LISTED_ASSETS_CURRENT_SHARE_UNITS_LENDER_WATERFALL_DUBAI_CASH"
                ),
            },
            "DATAMATICS": {
                "historical_basic_share_count_as_of_2026_03_31": (
                    DATAMATICS_MARCH_BASIC_SHARES
                ),
                "Oct19_price_times_historical_basic_shares_cr": _r(
                    datamatics_old_oct19_cap,4
                ),
                "FY26_CFO_less_PPE_CR_not_normalized_owner_cash": proxy,
                "arbitrary_cross_date_proxy_multiple": REVERSE_CASH_MULTIPLE,
                "Oct19_basic_cap_to_FY26_cash_proxy_multiple": _r(
                    datamatics_old_oct19_cap/proxy,2
                ),
                "annual_owner_cash_needed_for_16x_Oct19_basic_share_parity_cr": _r(
                    parity_cash,2
                ),
                "annual_owner_cash_needed_for_50pct_gross_at_16x_cr": _r(
                    fifty_upside_cash,2
                ),
                "cash_proxy_required_growth_for_50pct_gross_at_16x_pct": _r(
                    (fifty_upside_cash/proxy - 1)*100,2
                ),
                "FY26_209_69_cr_acquisition_payable_fully_reconciled": False,
                "Q1_current_diluted_share_count_verified": False,
                "current_attributable_owner_cash_cr": None,
                "verified_equity_fair_value": None,
                "most_material_falsification": (
                    "RECONCILE_AUDITED_ACQUISITION_CONSIDERATION_AND_REPEATABLE_OWNER_CASH"
                ),
            },
        },
        "price_date_change_is_posthoc_not_oct15_preregistered_alpha": True,
        "zuari_asset_value_cannot_be_rolled_forward_without_issuer_share_units": True,
        "different_timing_of_NAV_listed_assets_and_debt_explicit": True,
        "share_buyback_purchases_not_equal_to_legal_cancellations": True,
        "uncalibrated_multiples_and_NAV_are_not_fair_values": True,
        "risk_adjusted_expected_return_for_any_company": None,
        "rank_stocks_as_buy": False,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result


def materialize_l001_p017(root: Path) -> dict[str, Any]:
    source, receipts = load_source_packets(root)
    return build_l001_p017(source, receipts)


def validate_l001_p017(value: dict[str, Any], *, root: Path) -> None:
    unsigned = copy.deepcopy(value)
    stored = unsigned.pop("report_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("P017 risk report source signature changed")
    if value != materialize_l001_p017(root):
        raise AlphaContractError("P017 cannot replay original source dates and costs")
