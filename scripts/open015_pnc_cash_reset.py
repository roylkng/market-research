"""OPEN015 PNC: reproduce the signed 28-Oct-2026 H1 cash waterfall.

Output is an issuer accounting alert, not a prospective alpha signal or owner
cash valuation. No original PDF bytes were archived; visual inspection verified
PDF pages 6, 11-15.
"""
from __future__ import annotations

import argparse
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "research/broad-discovery/OPEN015_PNC_Q2_H1_ISSUER_CASH_INPUT_20261029.json"
RUPEE_CRORE_IN_LAKH = Decimal(100)


def dec(obj: dict, name: str) -> Decimal:
    val = obj[name]
    if isinstance(val, bool) or not isinstance(val, (int, float, Decimal)):
        raise TypeError(f"Source value {name} must be a number")
    d = Decimal(str(val))
    if not d.is_finite():
        raise ValueError(f"Source value {name} must be finite")
    return d


def crore(v: Decimal) -> str:
    return str((v / RUPEE_CRORE_IN_LAKH).quantize(Decimal("0.0001")))


def rd(v: Decimal, precision: str = "0.01") -> str:
    return str(v.quantize(Decimal(precision), rounding=ROUND_HALF_UP))


def verify(data: dict) -> dict:
    if (data["schema"], data["symbol"], data["isin"]) != (
        "OPEN015-PNC-Q2-H1-ISSUER-CASH-V1", "PNCINFRA", "INE195J01029"
    ):
        raise ValueError("Wrong schema/company")
    if (data["issuer_original_signed_date"], data["financial_period_end"],
        data["research_observation_date"]) != ("2026-10-28", "2026-09-30", "2026-10-29"):
        raise ValueError("Original disclosure/observation chronology invalid")
    if data["primary_url"] != (
        "https://www.pncinfratech.com/pdfs/unaudited-financial-results-30-09-2026.pdf"
    ):
        raise ValueError("Issuer signed original URL changed")
    if data["issuer_pdf_visually_inspected_pages_zero_index"] != [6,11,12,13,14,15]:
        raise ValueError("Original visual page custody must be preserved")
    if data["original_pdf_bytes_archived"] or data["original_pdf_sha256"] is not None:
        raise ValueError("Do not invent a raw-source SHA")
    if data["issuer_statement_scope"] != (
        "LIMITED_REVIEW_UNAUDITED_H1_CONSOLIDATED_AND_STANDALONE_INR_LAKH"
    ):
        raise ValueError("Issuer unit, period, limited review or scope changed")

    g = data["consolidated_cash_flow_H1_lakh"]
    p = data["standalone_cash_flow_H1_lakh"]
    inc = data["consolidated_income_lakh"]
    b = data["consolidated_balance_20260930_lakh"]
    q = data["as_of_quote"]
    gov = data["governance"]
    controls = data["controls"]
    wc_fields = (
        "inventory_change", "trade_receivables_change",
        "other_assets_change", "other_financial_assets_change",
        "trade_payables_change", "other_liabilities_and_provisions_change",
        "other_financial_liabilities_change",
    )
    expected_wc = (
        "-21998.19","-27723.67","-14478.29","-4095.77",
        "-25826.87","-6841.01","-4148.82"
    )
    for k, expected in zip(wc_fields,expected_wc):
        if dec(g,k) != Decimal(expected):
            raise ValueError(f"Source H1 working-capital component mutated: {k}")
    expected_g = {
        "before_working_capital":"81078.91",
        "cash_from_operations_pre_tax":"-24033.71",
        "direct_tax_paid":"-13743.06",
        "net_after_tax_CFO":"-37776.77",
        "prior_H1_after_tax_CFO":"418905.58",
        "current_H1_cash_PPE_CWIP_intangibles":"15588.52",
        "H1_dividends_paid":"1539.23",
        "H1_interest_paid":"25725.77",
        "ending_cash_equivalents":"55927.44",
    }
    for k,expected in expected_g.items():
        if dec(g,k) != Decimal(expected):
            raise ValueError(f"Signed consolidated statement value changed: {k}")
    wc = sum((dec(g,k) for k in wc_fields),Decimal(0))
    if (dec(g,"before_working_capital") + wc
          != dec(g,"cash_from_operations_pre_tax")):
        raise ValueError("Issuer H1 cash after working capital not reconciled")
    if (dec(g,"cash_from_operations_pre_tax") + dec(g,"direct_tax_paid")
          != dec(g,"net_after_tax_CFO")):
        raise ValueError("Issuer after-tax operating cash cannot be reproduced")
    expected_parent = {
        "net_after_tax_CFO":"-12760.28",
        "prior_H1_after_tax_CFO":"-40430.93",
        "before_working_capital":"52546.55",
        "cash_PPE_CWIP":"15686.24",
    }
    for k,expected in expected_parent.items():
        if dec(p,k) != Decimal(expected):
            raise ValueError(f"Signed parent statement value changed: {k}")
    expected_profit = {
        "Q2_reported_revenue":"132246.99",
        "Q2_previous_revenue":"112763.99",
        "Q2_reported_PAT":"11467.83",
        "Q2_previous_PAT":"21569.91",
        "Q1_reported_PAT":"33193.29",
        "H1_revenue":"301092.95",
        "H1_one_time_Agra_Bypass_Vivad_se_Vishwas_III_settlement_revenue":"21765.54",
        "H1_prior_settlement_revenue":"0",
        "Q2_road_segment_profit":"8783.14",
        "Q1_road_segment_profit":"32381.76",
    }
    for k,expected in expected_profit.items():
        if dec(inc,k) != Decimal(expected):
            raise ValueError(f"Signed consolidated income / note changed: {k}")
    if dec(inc,"Q2_reported_PAT") + dec(inc,"Q1_reported_PAT") != Decimal("44661.12"):
        raise ValueError("Consolidated Q1+Q2 PAT does not match H1")
    expected_balance = {
        "noncurrent_trade_receivables":"570238.61",
        "current_trade_receivables":"142998.77",
        "cash_equivalents":"55927.44",
        "other_bank_balances":"141884.33",
        "current_investments":"111459.91",
        "noncurrent_borrowings":"488529.65",
        "current_borrowings":"102652.87",
        "equity_attributable_parent":"724840.19",
        "paidup_equity_capital":"5130.78",
        "face_value_per_share_inr":"2",
    }
    for k,expected in expected_balance.items():
        if dec(b,k) != Decimal(expected):
            raise ValueError(f"Signed Sept consolidated balance value changed: {k}")
    if dec(b,"cash_equivalents") != dec(g,"ending_cash_equivalents"):
        raise ValueError("Consolidated cashflow ending cash not equal balance cash")
    if (
        b["other_book_liabilities_not_net_cash_verified"] is not True
        or b["bank_balances_fully_unrestricted_verified"] is not False
        or b["investments_all_cash_available_to_parent_verified"] is not False
    ):
        raise ValueError("Unproven liquidity is not unrestricted parent cash")

    if (q["observation_date"], q["source_url"],
        q["exact_NSE_close_source_verified"]) != (
        "2026-10-29",
        "https://www.valueresearchonline.com/stocks/92059/pnc-infratech-ltd/news/",
        False
    ):
        raise ValueError("Price evidence exact-close status was tampered with")
    if dec(q,"quote_inr") != Decimal("133.98"):
        raise ValueError("Quote-time price changed without new source")
    if gov != {
        "NHAI_SPV_debarment_date":"2026-09-03",
        "NHAI_promoter_extension_date":"2026-09-11",
        "Delhi_HC_interim_stay_receipt":"2026-10-13",
        "definitive_court_clearance":False,
        "relevant_pdf_note":"Consolidated results PDF 0-index page 15, Note 6",
    }:
        raise ValueError("Interim stay cannot become a final court clearance")
    if controls != {
        "research_only":True,
        "no_new_buy":True,
        "no_owner_cash_proxy_from_CFO_less_PPE":True,
        "prior_H1_after_tax_cash_is_repeated_asset_recycling_not_operating_baseline_verified":False,
        "settlement_not_periodized_to_Q2":True,
        "never_double_count_concession_receivables_as_unrestricted_bank_cash":True,
        "no_retroactive_H002_H003_HG009_changes":True,
        "no_fabricated_raw_sha":True,
        "no_trading_or_capital_authorization":True,
    }:
        raise ValueError("Original experiment and research control invalid")

    shares = (dec(b,"paidup_equity_capital") * Decimal(100000)
              / dec(b,"face_value_per_share_inr"))
    if shares != shares.to_integral_value():
        raise ValueError("Issued shares cannot be fractional")
    price = dec(q,"quote_inr")
    market_cap_crore = shares * price / Decimal(10000000)
    debt = dec(b,"noncurrent_borrowings") + dec(b,"current_borrowings")
    cash_bank = dec(b,"cash_equivalents") + dec(b,"other_bank_balances")
    receivables = (dec(b,"noncurrent_trade_receivables")
                   + dec(b,"current_trade_receivables"))
    stress_5pct_crore = receivables * Decimal("0.05") / RUPEE_CRORE_IN_LAKH
    annual_cfo_yield = None

    return {
        "research_only":True,
        "share_count_from_face_capital":int(shares),
        "quote_time_equity_cap_crore":rd(market_cap_crore,"0.0001"),
        "Q2_consolidated_PAT_YoY_pct":rd(
            (dec(inc,"Q2_reported_PAT")/dec(inc,"Q2_previous_PAT")-1)*100),
        "H1_after_tax_consolidated_CFO_crore":crore(dec(g,"net_after_tax_CFO")),
        "H1_prior_consolidated_CFO_crore":crore(dec(g,"prior_H1_after_tax_CFO")),
        "H1_after_tax_parent_CFO_crore":crore(dec(p,"net_after_tax_CFO")),
        "H1_prior_parent_CFO_crore":crore(dec(p,"prior_H1_after_tax_CFO")),
        "H1_consolidated_before_WC_crore":crore(dec(g,"before_working_capital")),
        "H1_consolidated_working_cap_drain_crore":crore(wc),
        "H1_consolidated_cash_from_ops_before_tax_crore":crore(
            dec(g,"cash_from_operations_pre_tax")),
        "H1_one_time_settlement_revenue_crore":crore(
            dec(inc,"H1_one_time_Agra_Bypass_Vivad_se_Vishwas_III_settlement_revenue")),
        "one_time_settlement_pct_of_H1_revenue":rd(
            dec(inc,"H1_one_time_Agra_Bypass_Vivad_se_Vishwas_III_settlement_revenue")
            / dec(inc,"H1_revenue")*100),
        "borrowings_crore":crore(debt),
        "cash_plus_other_banks_crore_restrictions_unverified":crore(cash_bank),
        "borrowings_less_cash_and_bank_crore_not_true_net_debt":crore(debt-cash_bank),
        "current_investments_crore":crore(dec(b,"current_investments")),
        "noncurrent_plus_current_trade_receivables_crore":crore(receivables),
        "hypothetical_5pct_receivables_impairment_before_tax_crore":rd(
            stress_5pct_crore),
        "hypothetical_5pct_impairment_as_pct_equity_cap":rd(
            stress_5pct_crore/market_cap_crore*100),
        "next_price_is_a_quoted_observation_not_exchange_close":True,
        "normalized_annual_parent_owner_cash_crore":annual_cfo_yield,
        "HC_order_is_interim_stay_only":True,
        "investment_status":"INVESTIGATED_RISK_ONLY_NOT_BUY",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=DEFAULT)
    args = p.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"),
                      parse_float=Decimal,parse_int=Decimal)
    print(json.dumps(verify(data),indent=2,sort_keys=True))


if __name__ == "__main__":
    main()
