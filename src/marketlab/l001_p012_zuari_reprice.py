"""L001 P012: synchronize five Zuari listed-stake marks to October 15 NSE closes.

The source is original hash-checked full-market NSE UDiFF bytes captured
AFTER the October 15 AE001 18:30 IST decision cutoff. Post-hoc research only.
June investment holdings can change before October and the March debt is
unreconciled to October. No liquidation value or alpha is established.
"""

from __future__ import annotations

import hashlib
import io
import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_market import parse_udiff_eq_panel

UDIFF_ORIGINAL_SHA = "3d1c7039e2c70868cc44b51d1f9e4b0f942afc0575fe8c4a524aed9e01eac3e8"
ISSUER_JUNE_DECK_SHA = "6ebec1ef99aba350000aab28b1e9f1b6c6a39471458df488ece9c7f8ea4fb25b"
P004_REPORT_SHA = "97cd3432e3c779f48ad09c75d42b5c18b431e2f6e297cf10421a31055c92e82d"
H021_DATE = "2026-10-15"
OCT_PRICE_CAPTURED_AT_UTC = "2026-10-15T17:21:34.130436Z"
JUNE_REPORTED_TOTAL_CR = 4223.0
MARCH_GROSS_BORROWINGS_CR = 2581.29
MARCH_CASH_CR = 61.8655

# Exact ISINs from issuer/NSE historical source records. Quoted June values
# are issuer rounded presentation values, *not exact holdings or future values*.
@dataclass(frozen=True)
class OriginalHolding:
    symbol: str
    isin: str
    issuer_reported_name: str
    june_mark_cr: float
    june_reference_price_inr: float


ORIGINAL_JUNE_HOLDINGS = (
    OriginalHolding(
        "CHAMBLFERT", "INE085A01013", "Chambal Fertilizers & Chemicals Ltd.", 2783, 468
    ),
    OriginalHolding(
        "ZUARI", "INE840M01016", "Zuari Agro Chemicals Ltd.", 310, 230
    ),
    OriginalHolding(
        "PARADEEP", "INE088F01024", "Paradeep Phosphates Ltd.", 8, 136
    ),
    OriginalHolding(
        "TEXRAIL", "INE621L01012", "Texmaco Rail & Engineering Ltd.", 695, 108
    ),
    OriginalHolding(
        "TEXINFRA", "INE435C01024", "Texmaco Infrastructure and Holdings Ltd.", 428, 109
    ),
)


def repriced_listed_portfolio(
    prices_by_identity: dict[tuple[str, str], float],
    *,
    zuari_historical_basic_shares: int,
    zuari_oct15_close: float,
    haircuts: tuple[float, ...] = (0, 0.1, 0.2, 0.25, 0.3),
) -> dict:
    """Value the *unchanged June holdings assumption* at Oct 15 original closes."""
    if (
        type(zuari_historical_basic_shares) is not int
        or zuari_historical_basic_shares <= 0
        or not isinstance(zuari_oct15_close, (int, float))
        or not math.isfinite(zuari_oct15_close) or zuari_oct15_close <= 0
        or len(prices_by_identity) != len(ORIGINAL_JUNE_HOLDINGS)
        or not haircuts
        or any(type(h) not in (int, float) or not math.isfinite(h) or not 0 <= h <= 1 for h in haircuts)
    ):
        raise AlphaContractError("P012 invalid fully comparable historical inputs")
    keys = {(x.symbol, x.isin) for x in ORIGINAL_JUNE_HOLDINGS}
    if set(prices_by_identity) != keys:
        raise AlphaContractError("P012 all five original exchange symbol + ISIN prices required")
    june_rounded_sum = sum(r.june_mark_cr for r in ORIGINAL_JUNE_HOLDINGS)
    if june_rounded_sum != 4224:
        raise AlphaContractError("issuer rounded holding values changed")
    scale = JUNE_REPORTED_TOTAL_CR / june_rounded_sum
    portfolio = []
    for holding in ORIGINAL_JUNE_HOLDINGS:
        close = prices_by_identity[(holding.symbol, holding.isin)]
        if (
            type(close) not in (float, int)
            or not math.isfinite(close)
            or close <= 0
        ):
            raise AlphaContractError("P012 official market price missing or invalid")
        implied_value = holding.june_mark_cr * close / holding.june_reference_price_inr
        portfolio.append({
            "symbol": holding.symbol, "isin": holding.isin,
            "june_2026_issuer_rounded_mark_cr": holding.june_mark_cr,
            "june_2026_issuer_reference_close_inr": holding.june_reference_price_inr,
            "oct_15_2026_original_nse_close_inr": float(close),
            "individual_mark_change_fraction": round(
                close / holding.june_reference_price_inr - 1, 8
            ),
            "oct_15_pro_forma_unchanged_holdings_mark_cr": round(implied_value * scale, 6),
        })
    june_scaled_sum = sum(r["oct_15_pro_forma_unchanged_holdings_mark_cr"] for r in portfolio)
    # Round source legs at six decimals, so use raw exact ratios for totals.
    oct_mark = sum(
        h.june_mark_cr * prices_by_identity[(h.symbol, h.isin)] / h.june_reference_price_inr
        for h in ORIGINAL_JUNE_HOLDINGS
    ) * scale
    basic_cap = zuari_historical_basic_shares * zuari_oct15_close / 1e7
    net_borrowing = MARCH_GROSS_BORROWINGS_CR - MARCH_CASH_CR
    residual = oct_mark - net_borrowing
    if abs(june_scaled_sum - oct_mark) > 0.00001:
        raise AlphaContractError("P012 numerical portfolio sum inconsistent")
    scenarios = [
        {
            "post_oct15_asset_stress_haircut_not_a_forecast": float(h),
            "remaining_rounded_portfolio_cr": round(oct_mark * (1 - h), 6),
            "old_march_net_debt_subtracted_once_cr": round(net_borrowing, 6),
            "residual_excluding_all_other_assets_and_claims_cr": round(
                oct_mark * (1 - h) - net_borrowing, 6
            ),
            "residual_minus_basic_cap_cr_not_margin_of_safety": round(
                oct_mark * (1 - h) - net_borrowing - basic_cap, 6
            ),
        }
        for h in sorted(set(haircuts))
    ]
    return {
        "status": "POSTHOC_OCT15_UNCHANGED_JUNE_HOLDINGS_PRICE_REMARK_ONLY",
        "issuer": "ZUARIIND",
        "source_june_reported_aggregate_cr": JUNE_REPORTED_TOTAL_CR,
        "source_june_rounded_components_sum_cr": june_rounded_sum,
        "june_component_rounding_scale_not_share_count": round(scale, 10),
        "oct15_pro_forma_portfolio_mark_cr": round(oct_mark, 6),
        "oct15_pro_forma_portfolio_change_from_june_reported_fraction": round(
            oct_mark / JUNE_REPORTED_TOTAL_CR - 1, 8
        ),
        "old_march_net_debt_cr": round(net_borrowing, 6),
        "oct15_historical_issued_share_market_cap_cr": round(basic_cap, 6),
        "oct15_pro_forma_portfolio_less_old_march_net_debt_cr": round(residual, 6),
        "additional_markdown_asset_haircut_needed_to_match_basic_cap": round(
            (residual - basic_cap) / oct_mark, 8
        ),
        "investments_holdings_confirmed_unchanged_after_june": False,
        "debt_and_cash_rolled_forward_to_october_15": False,
        "share_denominator_fully_diluted_asof_october_15": False,
        "pledge_release_and_parent_claims_verified": False,
        "after_oct15_price_source_capture_is_not_oct15_eod_signal": True,
        "reference_nse_original_sha256": UDIFF_ORIGINAL_SHA,
        "reference_issuer_deck_sha256": ISSUER_JUNE_DECK_SHA,
        "reference_p004_original_source_sha256": P004_REPORT_SHA,
        "source_close_captured_at_utc": OCT_PRICE_CAPTURED_AT_UTC,
        "portfolio": portfolio,
        "asset_stress_scenarios": scenarios,
        "expected_return": None, "investment_authorized": False,
    }


def from_original_documents(
    original_udiff_zip: bytes,
    issuer_june_deck_pdf: bytes,
    p004_report: dict,
) -> dict:
    """Strictly replay raw original listed-price and basic-cap sources."""
    if hashlib.sha256(original_udiff_zip).hexdigest() != UDIFF_ORIGINAL_SHA:
        raise AlphaContractError("Oct15 original UDiFF source SHA mismatch")
    if hashlib.sha256(issuer_june_deck_pdf).hexdigest() != ISSUER_JUNE_DECK_SHA:
        raise AlphaContractError("original issuer June price/portfolio deck changed")
    if not isinstance(p004_report, dict) or p004_report.get("report_sha256") != P004_REPORT_SHA:
        raise AlphaContractError("original P004 issuer share-cap panel not verified")
    if digest({k: v for k, v in p004_report.items() if k != "report_sha256"}) != P004_REPORT_SHA:
        raise AlphaContractError("P004 source ledger content hash mismatch")
    members = p004_report.get("source_results")
    if not isinstance(members, list) or len(members) != 100:
        raise AlphaContractError("P004 original 100-company source missing")
    matches = [r for r in members if r.get("symbol") == "ZUARIIND" and r.get("isin") == "INE217A01012"]
    if len(matches) != 1 or matches[0].get("reported_issued_shares_not_fully_diluted") != 29781184:
        raise AlphaContractError("Zuari original basic share number is not source-consistent")

    try:
        from pypdf import PdfReader
        page = PdfReader(io.BytesIO(issuer_june_deck_pdf), strict=True).pages[19]
        table = re.sub(r"\s+", " ", page.extract_text() or "").casefold()
    except Exception as exc:
        raise AlphaContractError("issuer 30 June original investment deck unreadable") from exc
    for holding in ORIGINAL_JUNE_HOLDINGS:
        if holding.issuer_reported_name.casefold() not in table:
            raise AlphaContractError("issuer original June holding description absent")
    if "4,223" not in table or "3,681" not in table:
        raise AlphaContractError("issuer original listed asset aggregate unverified")

    observed = parse_udiff_eq_panel(original_udiff_zip, session_date=date(2026, 10, 15))
    by_symbol: dict[str, list] = {}
    for row in observed:
        by_symbol.setdefault(row.symbol, []).append(row)
    prices: dict[tuple[str, str], float] = {}
    for holding in ORIGINAL_JUNE_HOLDINGS:
        records = by_symbol.get(holding.symbol, [])
        matching = [row for row in records if row.isin == holding.isin]
        if len(records) != 1 or len(matching) != 1:
            raise AlphaContractError("original issuer stake NSE EQ identity missing/ambiguous")
        prices[(holding.symbol, holding.isin)] = matching[0].close_price
    issuer = by_symbol.get("ZUARIIND", [])
    correct_issuer = [row for row in issuer if row.isin == "INE217A01012"]
    if len(issuer) != 1 or len(correct_issuer) != 1:
        raise AlphaContractError("parent issuer October 15 NSE source identity not unique")
    result = repriced_listed_portfolio(
        prices,
        zuari_historical_basic_shares=matches[0]["reported_issued_shares_not_fully_diluted"],
        zuari_oct15_close=correct_issuer[0].close_price,
    )
    result["report_sha256"] = digest(result)
    return result
