"""P030: original-source-pinned five-stock underwriting READINESS, not forecasts.

Reconcile immutable historical payoff hurdles with newer primary-source
accounting, cash-flow, dilution and timing evidence. Never re-rank HG002,
infer case-specific completion probabilities or authorize a share purchase.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BOARD_ID = "HG007-P030-2026-10-11-FIVE-CASE-UNDERWRITING-READINESS-v1"
FROZEN_FIVE = ("ANANTRAJ", "DEVX", "INOXGREEN", "NPST", "SAMBHV")
SOURCE_BLOBS = {
    "historical_market": (
        "research/hg005-d001-result-v1.json",
        "2dbbc3055d1aacec8a37dd510a1a75a3c7868006",
    ),
    "original_payoff": (
        "research/hg005-d003-result-v1.json",
        "b235bd9168bc658f7511f9cec1913f20f82cf311",
    ),
    "current_company_context": (
        "research/hg007/hg007-p013-28-case-sept29-fd-pledge-overlay-v1.json",
        "c5b542e56ec79c0a47afb4359e57c1638d3c0086",
    ),
    "anantraj_scheme": (
        "research/hg007/anantraj-full-scheme/p026-clause-review-v1.json",
        "d1c18d07eaa6a756e0b83ac8e0f477dd33ac99f0",
    ),
    "anantraj_qip": (
        "research/hg007/anantraj-qip-monitor-june2026/p029-source-object-cash-ledger-v1.json",
        "ca0b26afd49a792c42710967e63f7342fb288939",
    ),
    "devx_cash_credit": (
        "research/hg007/devx-originals/lease-cash-credit-gate-v1.json",
        "a149de9e355e561719227b47b0f05b3f610a497b",
    ),
    "npst_funding": (
        "research/hg007/npst-aug2026-originals/june-2026-financial-and-funding-ledger-v1.json",
        "73809c3d731468b4ef9e43438cd25454a9a6cf0d",
    ),
    "npst_visual": (
        "research/hg007/npst-aug2026-originals/june-visual-financial-review-v1.json",
        "6fcb4c40b7e700a7b3e35c1fb361481c5ede6b63",
    ),
    "sambhv_plant": (
        "research/hg007/sambhv-aug2026-investor/phase1-steel-power-capex-v1.json",
        "1dbb0ddaa6243b6afe79746906f214c4cc422461",
    ),
    "inoxgreen_wwil_funding": (
        "research/hg007/wwil-bse-original/reconciled-issuer-terms-v1.json",
        "c40af0367686c0602653576f072755f776ff8cec",
    ),
    "inoxgreen_synergy": (
        "research/hg007/wwil-oct7-press/source-bound-post-synergy-hurdle-v1.json",
        "60ebddda7ec4b5cec08f79f2dca48ca1503d0dbd",
    ),
}

NECESSARY_GATES = {
    "ANANTRAJ": (
        "OFFICIAL_EFFECTIVE_SCHEME_AND_CLOUD_RECORD_DATE",
        "CLOUD_NEWCO_TRANSFERRED_ASSET_CASH_LIABILITIES_AND_DEBT_SCHEDULE",
        "QIP_FDR_0_02_CRORE_VARIANCE_ORIGINAL_BANK_RECONCILIATION",
        "AUDITED_SEPARATED_CLOUD_FREE_CASH_FLOW_AND_REVENUE_BACKLOG",
        "NEWCO_PARENT_DOUBLE_OWNERSHIP_AND_QIP_CASH_NONADDITIVITY_REVIEW",
    ),
    "DEVX": (
        "WINSTON_PROJECT_LEASES_OCCUPANCY_AND_POST_RENT_CASH_EBIT",
        "FY26_INDAS_116_TO_CASH_FLOW_AND_DEBT_EV_SCOPE",
        "ACTUAL_NCD_CASH_AND_INTEREST_SERVICE_AFTER_OCT8_RATING",
        "LATEST_FULLY_DILUTED_SHARES_FUNDING_AND_CURRENT_EV",
    ),
    "INOXGREEN": (
        "LEGAL_WWIL_TRANSFER_CONDITIONS_PRECEDENT_AND_EFFECTIVE_DATE",
        "ACTUAL_WWIL_O_AND_M_NORMALIZED_EBITDA_MAINTENANCE_CAPEX_AND_FCF",
        "AUTHUM_THIRD_PARTY_INTERCORPORATE_LOAN_SECURITY_AND_CONVERSION",
        "VIBHAV_SUBORDINATED_LOAN_ELIMINATION_AND_POST_CONVERSION_MINORITIES",
        "CURRENT_INOXGREEN_FULLY_DILUTED_SHARES_NET_DEBT_AND_PLEDGE_UPDATE",
    ),
    "NPST": (
        "AUDITED_RECURRENT_OPERATING_EBITDA_EXCLUDING_NONCORE_OTHER_INCOME",
        "JUNE_REG32_UNSPENT_ALLOCATIONS_TO_CURRENT_BANK_CASH_RECONCILIATION",
        "INDAS_CASH_FLOW_RECEIVABLES_AND_PRODUCT_EARNINGS_CONVERSION",
        "LATEST_FULLY_DILUTED_SHARES_NET_CASH_AND_POST_JUNE_DEPLOYMENT",
    ),
    "SAMBHV": (
        "ACTUAL_0_36_MMTPA_PHASE_I_CAPACITY_COMMISSIONING_AND_RAMP",
        "STEEL_810_CRORE_AND_POWER_125_CRORE_FUNDING_SPEND_AND_DEBT",
        "POWER_PROJECT_COST_SAVINGS_AND_STEEL_EBITDA_NONADDITIVITY",
        "CURRENT_WARRANTS_FULLY_DILUTED_SHARES_AND_FREE_CASH_FLOW",
    ),
}


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_pinned_underwriting_sources(root: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    inputs: dict[str, dict] = {}
    receipts: dict[str, dict] = {}
    for family, (relative, sha) in SOURCE_BLOBS.items():
        original = (root / relative).read_bytes()
        if _git_blob(original) != sha:
            raise ValueError(f"{family}: original research Git blob changed")
        payload = json.loads(original)
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise TypeError(f"{family}: source contract is not original schema-v1 object")
        if payload.get("live_capital_allowed") is not False:
            raise ValueError(f"{family}: capital authorization in historical source")
        if payload.get("portfolio_eligibility_allowed", False) is not False:
            raise ValueError(f"{family}: historical source portfolio authorization")
        if payload.get("expected_returns_calculated") is True:
            raise ValueError(f"{family}: cannot add outcome-opened expected return")
        inputs[family] = payload
        receipts[family] = {
            "path": relative,
            "git_blob_sha": sha,
            "raw_sha256": hashlib.sha256(original).hexdigest(),
        }
    return inputs, receipts


def _num(raw: object, field: str) -> float:
    if type(raw) not in (float, int) or not math.isfinite(raw):
        raise ValueError(f"invalid numeric source fact: {field}")
    return float(raw)


def _check(original: float, expected: float, label: str, tolerance: float = 1e-8) -> None:
    if not math.isclose(original, expected, rel_tol=1e-10, abs_tol=tolerance):
        raise ValueError(f"source historical fact changed: {label}")


def _blocked_case(symbol: str, *, old: dict, stage: dict) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "original_hg005_oct1_close_inr_not_current": _num(old["close_price_inr"], "price"),
        "original_hg005_oct1_fd_cap_inr_crore_not_current": _num(
            old["reported_fd_market_cap_inr_crore"], "FD cap"
        ),
        "original_hg005_hurdle_unmodified": stage,
        "source_evidence_case": None,
        "necessary_original_document_and_underwriting_gates": list(NECESSARY_GATES[symbol]),
        "missing_core_underwriting_gate_count": len(NECESSARY_GATES[symbol]),
        "primary_source_economic_cashflow_sufficient": False,
        "current_fully_diluted_capital_and_ev_sufficient": False,
        "corporate_action_and_dividend_basis_verified": False,
        "company_specific_completion_probability_published": False,
        "probability_weighted_equity_expected_return": None,
        "current_price_target": None,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def build_p030_case_readiness(
    sources: dict[str, dict], receipts: dict[str, dict]
) -> dict[str, Any]:
    if set(sources) != set(SOURCE_BLOBS) or set(receipts) != set(SOURCE_BLOBS):
        raise ValueError("source set must contain exactly eleven pinned originals")
    old = sources["historical_market"]
    hurdles = sources["original_payoff"]
    context = sources["current_company_context"]
    if (
        old.get("price_session") != "2026-10-01"
        or old.get("context_id") != "HG005-D001-v1"
        or set(old.get("key_mechanical_context", {})) != set(FROZEN_FIVE)
        or hurdles.get("context_id") != "HG005-D003-v1"
        or set(hurdles.get("key_hurdles", {})) != set(FROZEN_FIVE)
        or hurdles.get("completion_probabilities_assigned") is not False
        or context.get("audit_id") != "HG007-P013-SEPT29-FD-PLEDGE-PUBLICATION-OVERLAY-v1"
        or context.get("original_28_case_count") != 28
        or context.get("revised_case_count") != 1
        or context.get("case_specific_completion_probabilities_published") != 0
        or context.get("verified_current_oct11_fully_diluted_share_counts") != 0
    ):
        raise ValueError("HG005 or P013 frozen membership/capital/probability contract changed")
    rows = context.get("company_cases")
    if not isinstance(rows, list) or len(rows) != 28:
        raise ValueError("original 28-case source cohort incomplete")
    indexed = {x.get("symbol"): x for x in rows if isinstance(x, dict)}
    if len(indexed) != 28 or not set(FROZEN_FIVE).issubset(indexed):
        raise ValueError("original 28-case selected identity drifted")
    for symbol in FROZEN_FIVE:
        case = indexed[symbol]
        if (
            case.get("frozen_hg005_mechanical_hurdle") != hurdles["key_hurdles"][symbol]
            or case.get("price_reference_session") != old["price_session"]
            or case.get("case_specific_probability_published") is not False
        ):
            raise ValueError(f"{symbol}: old frozen payout or company case drifted")

    cases = {
        symbol: _blocked_case(
            symbol,
            old=old["key_mechanical_context"][symbol],
            stage=hurdles["key_hurdles"][symbol],
        )
        for symbol in FROZEN_FIVE
    }

    # ANANTRAJ: QIP receipts/assets are not legally transferred newco cash.
    scheme = sources["anantraj_scheme"]
    qip = sources["anantraj_qip"]
    if (
        scheme.get("reviewed_specific_legal_clause_count") != 22
        or scheme.get("scheme_legal_approval_and_effective_date_verified") is not False
        or scheme.get("actual_cloud_equity_fair_value_calculated") is not False
        or qip.get("original_pdf_page_count") != 21
        or qip.get("data_cutoff_date") != "2026-06-30"
        or qip.get("original_exchange_publication_date") != "2026-08-08"
        or qip.get("cloud_qip_unused_is_newco_free_cash") is not False
        or qip.get("newco_net_cash_or_equity_value_calculated") is not False
        or qip.get("fdr_total_discrepancy_explained_by_original_source") is not False
    ):
        raise ValueError("ANANTRAJ legal effectiveness or QIP source state changed")
    _check(_num(qip["reported_QIP_gross_proceeds_inr_crore"], "QIP gross"), 1100, "ANANTRAJ gross")
    _check(_num(qip["reported_QIP_net_proceeds_inr_crore"], "QIP net"), 1072.2, "ANANTRAJ net")
    _check(_num(qip["reported_cumulative_used_by_june30_inr_crore"], "used"), 410.01, "ANANTRAJ used")
    _check(_num(qip["reported_unused_by_june30_inr_crore"], "unused"), 689.99, "ANANTRAJ unused")
    _check(_num(qip["historical_cloud_qip_unused_allocation_inr_crore"], "cloud"), 358.74, "ANANTRAJ cloud")
    _check(_num(qip["monitoring_report_same_date_fdr_total_inr_crore"], "FDR"), 690.01, "ANANTRAJ FDR")
    _check(
        _num(qip["fdr_less_unutilized_report_discrepancy_inr_crore"], "variance"),
        0.02, "ANANTRAJ FDR variance"
    )
    _check(
        qip["monitoring_report_same_date_fdr_total_inr_crore"]
        - qip["reported_unused_by_june30_inr_crore"],
        qip["fdr_less_unutilized_report_discrepancy_inr_crore"],
        "ANANTRAJ original FDR-vs-unused",
    )
    cases["ANANTRAJ"]["source_evidence_case"] = {
        "source_publication_date": qip["original_exchange_publication_date"],
        "monitoring_cutoff": qip["data_cutoff_date"],
        "gross_qip_inr_crore": qip["reported_QIP_gross_proceeds_inr_crore"],
        "net_qip_inr_crore": qip["reported_QIP_net_proceeds_inr_crore"],
        "unused_qip_earmarked_object_amount_inr_crore_not_newco_cash": (
            qip["historical_cloud_qip_unused_allocation_inr_crore"]
        ),
        "unreconciled_fdr_minus_qip_unused_inr_crore": (
            qip["fdr_less_unutilized_report_discrepancy_inr_crore"]
        ),
        "scheme_effective_date_confirmed": False,
        "newco_net_cash_or_equity_value_verified": False,
        "source_warning": "Historical earmarked QIP object is not a newco cash balance.",
    }

    # DEVX: IndAS EBITDA is NOT post-rent cash EBIT.
    devx = sources["devx_cash_credit"]
    financial = devx.get("fy26_standalone_issuer_reported")
    credit = devx.get("oct8_independent_credit_report")
    if not isinstance(financial, dict) or not isinstance(credit, dict):
        raise TypeError("DEVX original financial and credit report incomplete")
    if (
        devx.get("winston_realized_income_verified") is not False
        or devx.get("cash_flow_earnings_to_current_valuation_reconciled") is not False
        or credit.get("credit_date") != "2026-10-08"
        or credit.get("additional_ncd_proposed_not_issued_cr") != 50
        or credit.get("rated_ncd_outstanding_cr") != 100
    ):
        raise ValueError("DEVX credit, rent or Winston source state changed")
    eb = _num(financial.get("fy26_indas_ebitda"), "DEVX IndAS EBITDA")
    rent = _num(financial.get("fy26_rent_outflow"), "DEVX rent")
    cash_ebit = _num(financial.get("fy26_cash_ebit"), "DEVX cash EBIT")
    _check(eb, 103.46, "DEVX EBITDA")
    _check(rent, 66.92, "DEVX cash rent")
    _check(cash_ebit, 36.55, "DEVX cash EBIT")
    _check(eb - rent, cash_ebit, "DEVX rent bridge", tolerance=0.02)
    _check(_num(credit["ncd_coupon_pct"], "NCD rate"), 11.75, "DEVX NCD")
    cases["DEVX"]["source_evidence_case"] = {
        "fy26_standalone_reported_indas_ebitda_inr_crore": eb,
        "fy26_standalone_cash_rent_outflow_inr_crore": rent,
        "fy26_standalone_cash_ebit_after_rent_inr_crore": cash_ebit,
        "oct8_credit_outstanding_rated_ncd_inr_crore": 100,
        "existing_ncd_coupon_pct": 11.75,
        "additional_50cr_ncd_not_confirmed_issued": True,
        "winston_incremental_cash_ebit_verified": False,
        "source_warning": "11.85cr illustrative HG005 EBITDA hurdle is not evidence of incremental post-rent Winston FCF.",
    }

    # NPST: displayed EBITDA includes income not yet demonstrated recurring.
    npst = sources["npst_funding"]
    visual = sources["npst_visual"]
    financ = npst.get("financials_q1fy27_consolidated_issuer_presentation")
    fundraising = npst.get("fundraising")
    if not isinstance(financ, dict) or not isinstance(fundraising, dict):
        raise TypeError("NPST Q1 source or Regulation 32 funds ledger absent")
    if (
        npst.get("normalized_recurrent_earnings_proven") is not False
        or npst.get("current_cash_from_unspent_proceeds_proven") is not False
        or visual.get("original_earnings_independent_cashflow_audit_complete") is not False
        or visual.get("current_fully_diluted_market_cap_verified") is not False
        or financ.get("ebitda_calculation_includes_other_income_in_total_income") is not True
    ):
        raise ValueError("NPST source has changed EBITDA quality/funding gate")
    npst_ebitda = _num(financ.get("ebitda_financial_tables_inr_crore"), "NPST EBITDA")
    other_income = _num(financ.get("other_income_inr_crore"), "NPST other income")
    unspent = _num(fundraising.get("derived_remaining_allocation_not_bank_balance_inr_crore"), "NPST unspent")
    _check(npst_ebitda, 18.79, "NPST EBITDA")
    _check(other_income, 4.94, "NPST other")
    _check(unspent, 264.3632, "NPST unused")
    _check(_num(visual["confirmed_q1fy27_two_table_ebitda_inr_crore"], "NPST visual EBITDA"), npst_ebitda, "NPST visual/table")
    cases["NPST"]["source_evidence_case"] = {
        "q1fy27_presentation_ebitda_inr_crore": npst_ebitda,
        "q1fy27_other_income_in_total_income_inr_crore": other_income,
        "other_income_fraction_of_reported_ebitda_pct": 100 * other_income / npst_ebitda,
        "reg32_unused_allocation_inr_crore_not_verified_cash": unspent,
        "recurrent_core_ebitda_independently_verified": False,
        "source_warning": "Unused stated objects are not bank cash; EBITDA includes other income of unverified recurrence.",
    }

    # SAMBHV: old steel-only upside omitted independent 125cr power capex.
    sambhv = sources["sambhv_plant"]
    steel = _num(sambhv.get("source_verified_steel_only_capex_inr_crore"), "steel capex")
    power = _num(sambhv.get("source_verified_additional_power_capex_inr_crore"), "power capex")
    if (
        sambhv.get("symbol") != "SAMBHV"
        or sambhv.get("source_target_steel_and_power_commissioning") != "Q4FY27"
        or sambhv.get("new_plant_operational_ebitda_verified") is not False
        or sambhv.get("future_steel_power_synergy_ebitda_verified") is not False
        or sambhv.get("source_verified_separate_captive_power_mw") != 25
    ):
        raise ValueError("SAMBHV power/capex or earnings proof state changed")
    _check(steel, 810, "SAMBHV steel capex")
    _check(power, 125, "SAMBHV power capex")
    _check(
        _num(sambhv["source_verified_steel_coils_capacity_add_mmtpa"], "SAMBHV capacity"),
        0.36, "SAMBHV new capacity"
    )
    scenario = sambhv.get("two_alternative_assumptions_not_additive_payoff_estimates")
    if not isinstance(scenario, list) or len(scenario) != 2:
        raise ValueError("SAMBHV steel+power scenario evidence missing")
    strong = next(
        (x for x in scenario if x.get("original_cell") == "ILLUSTRATIVE_STRONG"),
        None,
    )
    if strong is None:
        raise ValueError("SAMBHV original strong scenario absent")
    _check(strong["steel_plus_power_conditional_capex_inr_crore"], steel + power, "SAMBHV both capex")
    _check(
        strong["conditional_steel_plus_power_net_increment_to_frozen_cap"],
        0.4981218777654825, "SAMBHV scenario"
    )
    cases["SAMBHV"]["source_evidence_case"] = {
        "steel_only_issuer_capex_inr_crore": steel,
        "separate_25mw_power_capex_inr_crore": power,
        "combined_steel_plus_power_capex_if_both_required_inr_crore": steel + power,
        "capacity_addition_mmtpa": 0.36,
        "issuer_commissioning_target_not_actual": "Q4FY27",
        "strong_illustrative_steel_plus_power_net_increment_to_stale_oct1_cap_fraction": (
            strong["conditional_steel_plus_power_net_increment_to_frozen_cap"]
        ),
        "this_is_prospective_operational_earnings": False,
        "source_warning": "Do not use steel-only 810cr capex in a model that assumes unverified power-project savings.",
    }

    # INOXGREEN: Sep29 special XBRL was FIRST PUBLIC Oct8, not available Oct1.
    inox = indexed["INOXGREEN"].get("asof_29sep_exchange_source_update")
    terms = sources["inoxgreen_wwil_funding"]
    synergy = sources["inoxgreen_synergy"]
    if not isinstance(inox, dict):
        raise TypeError("INOXGREEN original NSE September special ownership absent")
    public_time = datetime.fromisoformat(
        inox.get("original_first_public_broadcast_utc")
    ).astimezone(UTC)
    if (
        public_time != datetime(2026, 10, 8, 13, 24, 47, tzinfo=UTC)
        or inox.get("fully_diluted_shares_as_of_sep29") != 422070138
        or inox.get("issued_basic_shares_as_of_sep29") != 419602518
        or inox.get("pledged_shares_at_sep29") != 4_900_000
        or inox.get("oct11_current_issued_and_fd_verified") is not False
        or inox.get("oct1_use_as_publicly_visible_fd_denominator_allowed") is not False
        or terms.get("wwil_transfer_legally_completed_verified") is not False
        or terms.get("loan_conversion_completed_verified") is not False
        or terms.get("wwil_ebitda_cashflow_verified") is not False
        or synergy.get("acquired_business_historical_normalized_ebitda_verified") is not False
        or synergy.get("post_synergy_ebitda_achieved") is not False
    ):
        raise ValueError("INOXGREEN corporate-action/event/cashflow evidence changed")
    claims = terms["disclosed_terms"]
    def term(field: str) -> Any:
        return claims[field]["reported_value"]
    _check(_num(term("wwil_cash_consideration_paid_inr_crore"), "INOX cash"), 550, "INOX amount")
    _check(_num(term("parent_total_funding_inr_crore"), "INOX funding"), 450, "INOX funds")
    _check(_num(term("parent_loan_annual_coupon_pct"), "INOX coupon"), 12, "INOX coupon")
    _check(_num(term("parent_loan_up_to_50_crore_principal_may_convert"), "INOX conversion"), 50, "INOX optional conversion")
    _check(_num(synergy["reverse_implied_future_annual_ebitda_inr_crore_if_quote_basis_comparable"], "INOX EBITDA"), 275, "INOX management-synergy hurdle")
    reported_share_price = _num(inox["reference_oct9_source_price_inr"], "INOX reference price")
    reported_equity_cap = _num(inox["sept29_fd_shares_at_oct9_price_inr_crore"], "INOX dated FD cap")
    _check(reported_share_price, 128.92, "INOX Oct9")
    _check(reported_equity_cap, 422070138 * 128.92 / 10_000_000, "INOX SepFD Oct9 price")
    cases["INOXGREEN"]["source_evidence_case"] = {
        "official_shares_asof_date": context["original_nse_xbrl_asof_date"],
        "first_public_broadcast_utc": inox["original_first_public_broadcast_utc"],
        "official_fd_shares_asof_sep29": inox["fully_diluted_shares_as_of_sep29"],
        "promoter_pledged_shares_asof_sep29": inox["pledged_shares_at_sep29"],
        "dated_sep29_fd_shares_times_oct9_price_cap_inr_crore_not_oct11_current": reported_equity_cap,
        "old_oct1_share_basis_may_not_use_oct8_publication_retroactively": True,
        "issuer_wwil_cash_consideration_paid_inr_crore": term("wwil_cash_consideration_paid_inr_crore"),
        "parent_subsidiary_funding_inr_crore": term("parent_total_funding_inr_crore"),
        "wwil_transfer_legally_completed_verified": False,
        "parent_subordinated_intercompany_loan_coupon_pct": term("parent_loan_annual_coupon_pct"),
        "parent_loan_up_to_50cr_conversion_optional": True,
        "management_implied_post_synergy_ebitda_inr_crore_unverified": (
            synergy["reverse_implied_future_annual_ebitda_inr_crore_if_quote_basis_comparable"]
        ),
        "source_warning": "Management post-synergy EBITDA is not acquired historical earnings; funding and minority interests block equity valuation.",
    }

    if set(cases) != set(FROZEN_FIVE) or any(
        v["source_evidence_case"] is None
        or v["primary_source_economic_cashflow_sufficient"] is not False
        or v["probability_weighted_equity_expected_return"] is not None
        for v in cases.values()
    ):
        raise ValueError("original five-company source reconciliation incomplete")

    return {
        "schema_version": 1,
        "readiness_id": BOARD_ID,
        "classification": "FIVE_SOURCE_PINNED_CASE_EVIDENCE_GATES_NOT_ALPHA_OR_RANKING",
        "assembled_as_of_ist": "2026-10-11",
        "evidence_source_git_blob_receipts": receipts,
        "original_hg005_price_session": "2026-10-01",
        "original_hg002_and_hg005_frozen_selection_unchanged": True,
        "original_five_hg005_company_count": len(cases),
        "separate_valuation_or_return_ready_company_count": 0,
        "unverified_current_oct11_fully_diluted_company_count": len(cases),
        "case_completion_probabilities_published": 0,
        "economically_validated_50pct_upside_cases": 0,
        "casework": [cases[symbol] for symbol in FROZEN_FIVE],
        "corporate_action_and_dividend_basis_verified": False,
        "expected_equity_returns_calculated": False,
        "investment_recommendations_authorized": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
