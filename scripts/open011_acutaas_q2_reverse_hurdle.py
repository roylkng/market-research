"""OPEN011: reverse-underwrite post-release Acutaas Q2 earnings, never signals.

This study fixes the last COMPLETE prior NSE market-session reference at
Oct 26 and observes the company's Q2 announcement on Oct 27. The old
price is NOT a post-announcement executable trade. All financial filing
amounts are secondary transcriptions of an issuer BSE attachment which
was HTTP-403 on original-byte acquisition. No raw original custody
or point-in-time alpha has been established.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

DEFAULT_INPUT = (
    Path(__file__).resolve().parents[1]
    / "research/broad-discovery/OPEN011_ACUTAAS_FY27Q2_REVERSE_HURDLE_INPUT_20261027.json"
)


def num(v: object, field: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{field} must have a numeric source")
    result = float(v)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{field} must be finite and positive")
    return result


def evaluate(p: dict) -> dict:
    if p["schema"] != "OPEN011-20261027-ACUTAAS-REVERSE-UNDERWRITING-V1":
        raise ValueError("protocol changed")
    if p["status"] != "POST_HOC_EARNINGS_SURPRISE_NOT_A_PROSPECTIVE_ALPHA_SIGNAL":
        raise ValueError("retrospective filing cannot generate a past alpha signal")
    if p["research_date"] != "2026-10-27":
        raise ValueError("research date altered")
    if p["identity"] != {"symbol": "ACUTAAS", "isin": "INE00FF01025"}:
        raise ValueError("issuer symbol/ISIN mismatch")
    evidence = p["observation_basis"]
    if (
        evidence["market_price_date"] != "2026-10-26"
        or evidence["publication_date"] != "2026-10-27"
        or evidence["original_issuer_quarterly_source_state"]
        != "SECONDARY_TRANSCRIPT_OF_COMPANY_EXCHANGE_ISSUER_FILING"
    ):
        raise ValueError("market/report chronology or evidence level altered")
    if (
        evidence["signed_original_PDF_access_status"]
        != "ORIGINAL_BSE_ATTACHMENT_HTTP_403_NOT_BYTE_VERIFIED"
        or evidence["raw_original_bytes_archived"] is not False
        or evidence["original_sha256"] is not None
        or evidence["first_original_retrieved_utc"] is not None
    ):
        raise ValueError("cannot claim original custody without retrieved bytes")
    if (
        not evidence["signed_BSE_original_attachment_url"].startswith(
            "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"
        )
        or not evidence["source_transcription_financial_url"].startswith(
            "https://www.investywise.com/"
        )
        or not evidence["source_transcription_issuer_press_url"].startswith(
            "https://www.investywise.com/"
        )
    ):
        raise ValueError("issuer filing/source pointer changed")
    approvals = p["approval"]
    if approvals != {
        "source_verified_original_bytes": False,
        "normalized_parent_owner_cash": False,
        "fully_diluted_oct27_shares": False,
        "intrinsic_value_approved": False,
        "stock_trade_approved": False,
        "no_frozen_alpha_changes": True,
    }:
        raise ValueError("unsupported buy, original source, or alpha approval")

    cap = num(evidence["approximate_market_cap_crore"], "dated cap")
    price = num(evidence["market_close_inr"], "dated quote")
    if price != 3348.80 or cap != 27409.0:
        raise ValueError("source price/capitalisation inputs modified")
    q = p["reported_Q2_FY27"]
    half = p["reported_H1_FY27"]
    if q["ended"] != "2026-09-30" or half["ended"] != "2026-09-30":
        raise ValueError("FY27 fiscal observation period changed")
    revenue_q = num(q["consolidated_revenue_from_operations_crore"], "Q2 group revenue")
    old_q = num(q["consolidated_revenue_prior_crore"], "old group revenue")
    ebitda = num(q["company_press_consolidated_EBITDA_crore"], "Q2 EBITDA")
    ebitda_old = num(q["company_press_consolidated_EBITDA_prior_crore"], "old EBITDA")
    group_pat = num(q["company_press_consolidated_PAT_crore"], "Q2 group PAT")
    group_pat_old = num(q["company_press_consolidated_PAT_prior_crore"], "old PAT")
    parent_pat = num(
        q["financial_transcription_profit_attributable_to_parent_crore"],
        "Q2 parent PAT"
    )
    standalone_pat = num(
        q["financial_transcription_standalone_PAT_crore"], "standalone PAT"
    )
    standalone_pbt = num(
        q["financial_transcription_standalone_PBT_crore"], "standalone PBT"
    )
    standalone_tax = num(
        q["financial_transcription_standalone_tax_crore"], "standalone tax"
    )
    if abs(standalone_pbt - standalone_tax - standalone_pat) > 0.001:
        raise ValueError("standalone profit/tax bridge invalid")
    if q["source_group_ownership_of_subsidiary_and_NCI_cash_unknown"] is not True:
        raise ValueError("group cash attributed without minority rights")
    if parent_pat <= group_pat:
        # Source-specific distinction: the subsidiary's non-controlling
        # shareholders have a LOSS this quarter, not positive PAT.
        raise ValueError("mixed or relabelled Q2 parent/group earnings")
    h1_revenue = num(
        half["consolidated_revenue_from_operations_crore"], "H1 revenue"
    )
    h1_ebitda = num(
        half["company_press_consolidated_EBITDA_crore"], "H1 EBITDA"
    )
    h1_group_pat = num(
        half["consolidated_total_PAT_crore"], "H1 group PAT"
    )
    h1_standalone_cfo = num(
        half["standalone_after_tax_CFO_crore"], "H1 standalone CFO"
    )
    if any(
        half[key] is not None
        for key in (
            "consolidated_after_tax_CFO_crore",
            "maintenance_vs_growth_capex_crore",
            "group_FCFE_crore",
        )
    ):
        raise ValueError("source-unknown group CFO/capex/owner cash must stay null")
    if h1_revenue < revenue_q or h1_group_pat < group_pat:
        raise ValueError("quarter exceeds six-month year-to-date balance")

    guidance = p["company_revised_guidance"]
    if (
        guidance["FY27_revenue_growth_low_pct"],
        guidance["FY27_revenue_growth_high_pct"],
        guidance["FY27_EBITDA_margin_low_pct"],
        guidance["FY27_EBITDA_margin_high_pct"],
    ) != (25, 30, 38, 40):
        raise ValueError("issuer guidance claims altered")
    if not guidance["source"].startswith("ISSUER_MANAGEMENT_GUIDANCE_TRANSCRIBED"):
        raise ValueError("management guidance cannot become independent forecast")
    contract = p["conditional_valuation_contract"]
    if contract != {
        "horizons_years": 3,
        "demanded_hypothetical_annual_equity_return_pct": 12,
        "hypothetical_terminal_PE_multiples": [20, 25, 30, 40],
        "base_PAT_procedure":
            "TWO_TIMES_PAST_HALF_YEAR_PAT_IS_MECHANICAL_STARTING_REFERENCE_NOT_NEXT_FY27_FORECAST",
        "taxes_dividends_buybacks_dilution_merger_and_execution_costs_modeled": False,
        "annualized_shareholder_return_has_not_been_calibrated": True,
    }:
        raise ValueError("reverse-hurdle scenario spec mutated")

    proxy_annual_pat = h1_group_pat * 2
    target_cap = cap * (1.12**3)
    cases = []
    for terminal_pe in contract["hypothetical_terminal_PE_multiples"]:
        target_profit = target_cap / terminal_pe
        needed_compound_profit_growth = (target_profit / proxy_annual_pat)**(1/3) - 1
        cases.append({
            "terminal_multiple_hypothesis_x": terminal_pe,
            "required_year_3_group_PAT_crore": round(target_profit, 2),
            "required_3_year_PAT_CAGR_vs_doubled_H1_pct": round(
                needed_compound_profit_growth * 100, 2
            ),
            "probability_calibrated": None,
            "trade_signal": False,
            "is_price_target": False,
        })
    return {
        "research_date": p["research_date"],
        "issuer": "ACUTAAS",
        "source_state": "SECONDARY_ISSUER_TRANSCRIPTION_NO_RAW_CUSTODY",
        "pre_publication_market_cap_crore": cap,
        "pre_publication_share_price_inr": price,
        "Q2_FY27_group_revenue_crore": round(revenue_q, 4),
        "Q2_revenue_YoY_pct_recomputed_from_rounded_source": round(
            (revenue_q / old_q - 1)*100, 2
        ),
        "Q2_company_operating_EBITDA_crore": ebitda,
        "Q2_group_EBITDA_YoY_pct_from_rounded_source": round(
            (ebitda / ebitda_old - 1) * 100, 2
        ),
        "Q2_company_EBITDA_margin_pct": round(
            ebitda / revenue_q * 100, 2
        ),
        "Q2_company_group_PAT_crore": group_pat,
        "Q2_group_PAT_YoY_pct_from_rounded_source": round(
            (group_pat / group_pat_old - 1)*100, 2
        ),
        "Q2_profit_attributable_to_parent_crore": parent_pat,
        "Q2_standalone_PAT_crore": standalone_pat,
        "Q2_group_noncontrolling_profit_or_loss_crore_approx": round(
            group_pat - parent_pat, 4
        ),
        "H1_group_reported_PAT_crore": h1_group_pat,
        "H1_group_EBITDA_margin_pct": round(
            h1_ebitda / h1_revenue * 100, 2
        ),
        "H1_standalone_after_tax_CFO_crore": h1_standalone_cfo,
        "H1_group_after_tax_CFO": None,
        "H1_group_CFO_to_PAT_conversion": None,
        "doubled_H1_group_PAT_only_mechanical_reference_crore": round(
            proxy_annual_pat, 4
        ),
        "pre_release_market_cap_over_doubled_H1_group_PAT_x": round(
            cap/proxy_annual_pat, 2
        ),
        "conditional_three_year_terminal_equity_cap_for_12pct_return_crore": round(
            target_cap, 2
        ),
        "reverse_hurdle_cases": cases,
        "owner_cash_verified": False,
        "probability_validated": False,
        "capital_authorized": False,
        "decision": "GROWTH_CONFIRMED_VALUATION_MARGIN_OF_SAFETY_NOT_ESTABLISHED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.input.read_text(encoding="utf-8"))),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
