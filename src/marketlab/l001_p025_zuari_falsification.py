"""L001 P025 Zuari: reconcile Q1 segment cash-economics warning with stale listed NAV.

This is a *post-entry research falsification*, not a registered trading signal.
The issuer's Q1 FY27 presentation is a publicly viewed original 30-page
document but not part of the input raw byte provenance until separately
archived. The Oct19 share prices and March borrowings are original prior
Git-blob pinned observations, not current transferable shareholder value.
"""

from __future__ import annotations

import copy
import hashlib
import math
from pathlib import Path
from typing import Any

import json

from marketlab.alpha import AlphaContractError, digest

ID = "L001-P025-ZUARI-CROSSDATE-DEBT-SERVICE-VALUE-FALSIFICATION-v1"
REVIEW_DATE = "2026-10-21"
ISSUER = "ZUARIIND"
ISIN = "INE217A01012"
SOURCE = {
    "original_issuer_url": (
        "https://www.zuariindustries.in/storage/uploads/images/1786947593.pdf"
    ),
    "source_publication_date": "2026-08-14",
    "financial_period_end": "2026-06-30",
    "pages": 30,
    "stake_table_pdf_page_zero_based": 19,
    "consolidated_profit_loss_pdf_page_zero_based": 24,
    "consolidated_segments_pdf_page_zero_based": 25,
    "original_pdf_bytes_archived_in_this_packet": False,
    "original_pdf_sha256_in_this_packet": None,
    "issuer_first_observed_original_at_utc": None,
    "source_claim_state": "VISUALLY_REVIEWED_ISSUER_PRESENTATION_NOT_BYTE_REPLAYED",
}
ORIGINAL_REPORTS = {
    "OCT19_LISTED_STAKES": {
        "path": "research/l001/l001-p018-oct19-five-stake-source-repricing-v1.json",
        "blob": "1574bd7dd879828dc8ad14ccd24d7cd92e6bb2af",
        "packet_sha256": "7b07899a164a2a078930cb8cd749f6be093ea7632c71521ca04ad341c5d240d7",
    },
    "REVERSE_VALUE_FALSIFICATION": {
        "path": "research/l001/l001-p023-value-falsification-frontier-v1.json",
        "blob": "dbcf91030ba488ba99d10287f45afead562da6a4",
        "packet_sha256": "847f93a8cb6872a9c7a0a44049504617ea55c387bf3954edb532d3e97c05daef",
    },
}
Q1_PRESENTATION = {
    "investment_value_2026_06_30_cr": 4223.00,
    "investment_value_2026_03_31_cr": 3681.00,
    "consolidated_segment_ebitda_cr": 8.05,
    "consolidated_finance_cost_cr": 61.54,
    "consolidated_net_unallocable_income_cr": 13.74,
    "consolidated_associate_jv_profit_share_cr": 34.37,
    "consolidated_pretax_before_associates_cr": -39.75,
    "consolidated_pretax_before_exceptional_cr": -5.38,
    "consolidated_exceptional_income_cr": 4.81,
    "consolidated_pretax_cr": -0.57,
    "consolidated_pat_cr": 0.05,
    "consolidated_other_comprehensive_income_cr": 519.69,
    "consolidated_segment_ebitda_q1_fy26_cr": 19.87,
    "consolidated_finance_cost_q1_fy26_cr": 63.00,
}
MARKDOWNS = (0, 0.05, 0.10, 0.12586342, 0.15, 0.20)


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_pinned_prior(root: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    reports, receipts = {}, {}
    for name, attrs in ORIGINAL_REPORTS.items():
        raw = (root / attrs["path"]).read_bytes()
        if _git_blob(raw) != attrs["blob"]:
            raise AlphaContractError(f"P025 pinned {name} original Git blob changed")
        candidate = json.loads(raw)
        unsigned = copy.deepcopy(candidate)
        original_hash = unsigned.pop("report_sha256", None)
        if original_hash != attrs["packet_sha256"] or digest(unsigned) != original_hash:
            raise AlphaContractError(f"P025 original {name} packet SHA drift")
        reports[name] = candidate
        receipts[name] = {
            "path": attrs["path"],
            "original_git_blob_sha": attrs["blob"],
            "original_raw_sha256": hashlib.sha256(raw).hexdigest(),
            "original_packet_sha256": original_hash,
        }
    return reports, receipts


def _round(value: float) -> float:
    if not math.isfinite(value):
        raise AlphaContractError("P025 nonfinite derived quantity")
    return round(value, 6)


def build_zuari_falsification(
    reports: dict[str, dict],
    receipts: dict[str, dict],
    *,
    source_facts: dict[str, float] | None = None,
) -> dict[str, Any]:
    old = reports["OCT19_LISTED_STAKES"]
    p023 = reports["REVERSE_VALUE_FALSIFICATION"]
    old_case = next((e for e in p023["evidence"] if e["symbol"] == ISSUER), None)
    if old_case is None:
        raise AlphaContractError("P025 original ZUARI stake falsification missing")
    if (
        old.get("parent_listed_symbol") != ISSUER
        or old.get("parent_listed_isin") != ISIN
        or old.get("source_prices_tradable_at_close_verified") is not False
        or old.get("forecast_next_year_shareholder_return") is not None
        or p023.get("completed_probability_weighted_equity_valuations") != 0
        or old.get("source_rounded_five_stakes_total_cr") != 4224
    ):
        raise AlphaContractError("P025 old source is not same noninvestable ZUARI")
    facts = dict(Q1_PRESENTATION if source_facts is None else source_facts)
    if set(facts) != set(Q1_PRESENTATION):
        raise AlphaContractError("P025 all original presentation figures required")
    if any(
        type(v) not in (int, float) or not math.isfinite(v)
        for v in facts.values()
    ):
        raise AlphaContractError("P025 presentation contains nonfinite original fact")
    # A strong internal numerical identity check, not source-byte authentication.
    pre_assoc = (
        facts["consolidated_segment_ebitda_cr"]
        + facts["consolidated_net_unallocable_income_cr"]
        - facts["consolidated_finance_cost_cr"]
    )
    pre_ex = pre_assoc + facts["consolidated_associate_jv_profit_share_cr"]
    final = pre_ex + facts["consolidated_exceptional_income_cr"]
    if (
        abs(pre_assoc - facts["consolidated_pretax_before_associates_cr"]) > 1e-6
        or abs(pre_ex - facts["consolidated_pretax_before_exceptional_cr"]) > 1e-6
        or abs(final - facts["consolidated_pretax_cr"]) > 1e-6
    ):
        raise AlphaContractError("P025 original Q1 consolidated P&L reconciliation fails")
    stake = float(old["stake_marks_by_date_cr"]["2026-10-19"])
    debt = float(old["net_borrowings_as_of_2026_03_31_cr_not_current"])
    cap = float(old["parent_Oct19_cap_from_old_basic_shares_cr_not_current_fd_cap"])
    gap = stake - debt - cap
    if (
        abs(gap - old["Oct19_gross_hypothetical_residual_to_old_cap_cr"]) > 1e-4
        or abs(stake - old_case["oct19_five_listed_stake_marks_cr"]) > 1e-3
        or abs(gap - old_case["hypothetical_undiscounted_stake_gap_cr_not_parent_equity"]) > 1e-3
    ):
        raise AlphaContractError("P025 original stale stake/debt/share bridge mismatch")
    mark_fraction = gap / stake
    if not 0 < mark_fraction < 1:
        raise AlphaContractError("P025 original NAV gap must be positive to stress")
    scenario = [
        {
            "extra_stake_markdown_pct_not_forecast": _round(h * 100),
            "stressed_listed_stakes_cr_not_current": _round(stake * (1-h)),
            "illustrative_gap_after_stale_March_debt_and_old_cap_cr": (
                _round(stake * (1-h) - debt - cap)
            ),
            "debt_or_parent_cash_flow_updated": False,
        }
        for h in MARKDOWNS
    ]
    result = {
        "schema_version": 1,
        "report_id": ID,
        "analysis_date_ist": REVIEW_DATE,
        "source_page_and_method": SOURCE,
        "original_source_receipts": receipts,
        "source_facts_manually_verified_from_original_issuer_presentation": facts,
        "cross_date_basis": {
            "issuer_June_2026_stakes_cr": facts["investment_value_2026_06_30_cr"],
            "NSE_Oct19_listed_stake_marks_using_June_units_cr": _round(stake),
            "March_2026_net_borrowings_cr_not_current": _round(debt),
            "Oct19_parent_equity_cap_old_basic_shares_cr": _round(cap),
            "Oct19_parent_EQ_close_inr": old["parent_Oct19_official_EQ_close_inr"],
            "historical_basic_shares": old["parent_original_share_count_historical_not_current"],
            "current_stake_units_and_parent_fully_diluted_equity_verified": False,
        },
        "issuer_Q1FY27_reported_segment_ebitda_cr": (
            facts["consolidated_segment_ebitda_cr"]
        ),
        "issuer_Q1FY27_reported_finance_cost_cr": facts["consolidated_finance_cost_cr"],
        "Q1_segment_ebitda_divided_by_finance_cost": _round(
            facts["consolidated_segment_ebitda_cr"] /
            facts["consolidated_finance_cost_cr"]
        ),
        "Q1_segment_ebitda_finance_cost_shortfall_cr": _round(
            facts["consolidated_finance_cost_cr"]
            - facts["consolidated_segment_ebitda_cr"]
        ),
        "Q1_pretax_before_associate_profit_cr": _round(pre_assoc),
        "Q1_associate_JV_earnings_not_distributed_cash_cr": (
            facts["consolidated_associate_jv_profit_share_cr"]
        ),
        "Q1_other_comprehensive_income_not_operating_cash_cr": (
            facts["consolidated_other_comprehensive_income_cr"]
        ),
        "Q1_reported_PBT_cr": _round(final),
        "issuer_June_stakes_to_Oct19_repriced_stakes_change_pct_not_realized": (
            _round(100 * (stake / facts["investment_value_2026_06_30_cr"] - 1))
        ),
        "hypothetical_stale_balance_sheet_stake_gap_cr_not_attributable": _round(gap),
        "additional_stake_markdown_erasing_stale_gap_percent_not_probability": _round(
            100 * mark_fraction
        ),
        "scenarios_without_operating_cashflow_or_new_debt_reconciliation": scenario,
        "operating_ebitda_is_not_cash_available_for_debt_service": True,
        "JV_accounting_share_of_profit_is_not_direct_distributed_parent_cash": True,
        "OCI_is_not_free_cash_or_parent_shareholder_realized_profit": True,
        "issuer_holdings_June_vs_original_NSE_Oct19_mixed_dates": True,
        "March_borrowings_not_contemporaneous_Oct19": True,
        "current_debt_pledges_cash_waterfall_verified": False,
        "company_cashflow_and_lease_adjusted_NAV": None,
        "after_tax_liquidatable_listed_stake_value": None,
        "parent_shareholder_probability_weighted_fair_value": None,
        "expected_1y_3y_net_return": None,
        "dated_tradable_share_fill_or_order_depth_verified": False,
        "valuation_or_buy_recommendation_authorized": False,
        "original_300_company_prospective_return_population_changed": False,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result


def materialize_zuari_falsification(root: Path) -> dict[str, Any]:
    source, receipts = load_pinned_prior(root)
    return build_zuari_falsification(source, receipts)


def validate_zuari_falsification(value: dict[str, Any], *, root: Path) -> None:
    unsigned = copy.deepcopy(value)
    stored = unsigned.pop("report_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("P025 signed ZUARI research report hash changed")
    if value != materialize_zuari_falsification(root):
        raise AlphaContractError("P025 original ZUARI scenario not source reproducible")
