"""L001 P023: source-pinned four-company value-thesis falsification frontier.

The outputs are independent *necessary-condition* hurdles, deliberately not
comparable stocks/scores, calibrated probabilities, NAVs or fair values.
Everything is retrospective as of October 20, after the original October 15
prospective entry. This code must never change the frozen stock screen.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest

REVIEW_ID = "L001-P023-20261020-CROSS-CASE-CAPITAL-ALLOCATION-FALSIFICATION-v1"
REVIEW_DATE = "2026-10-20"
PINNED = {
    "p017": (
        "research/l001/l001-p017-three-reverse-value-gates-v1.json",
        "24fa660561a11b41ba0052fb69e94817828fd474",
        "report_sha256",
    ),
    "p018": (
        "research/l001/l001-p018-oct19-five-stake-source-repricing-v1.json",
        "1574bd7dd879828dc8ad14ccd24d7cd92e6bb2af",
        "report_sha256",
    ),
    "p020": (
        "research/l001/l001-p020-srl-franchise-profit-and-impairment-hurdle-v1.json",
        "1be878259454939e46e646105fbac4d5764f8feb",
        "report_sha256",
    ),
    "p021": (
        "research/l001/l001-p021-srl-uk-14month-cash-analysis-v1.json",
        "e8106e279a665ed8aad248bbce2b451aa1d34647",
        "report_sha256",
    ),
    "p022_receipt": (
        "research/l001/originals/srl_uk_fy26/attempts/39449015408-1.json",
        "cb5067f83135fc77e416b4cec52f31d777f67046",
        "receipt_sha256",
    ),
}
ORIGINAL_UK_PDF_SHA = (
    "d27366044e48b027153aec379f83807f0ab41e18845f51b1ea990975dba94fe2"
)
COMPANIES = ("GESHIP", "ZUARIIND", "DATAMATICS", "SUNTV")


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _checked_positive(value: object, label: str) -> float:
    if type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
        raise AlphaContractError(f"L001 P023 missing valid {label}")
    return float(value)


def _equal(left: float, right: float, *, tol: float = 0.0001) -> bool:
    return math.isclose(left, right, rel_tol=0, abs_tol=tol)


def load_original_review_sources(
    root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    packets: dict[str, dict[str, Any]] = {}
    receipts: dict[str, dict[str, str]] = {}
    for label, (path, expected_sha, signature_key) in PINNED.items():
        raw = (root / path).read_bytes()
        if _blob(raw) != expected_sha:
            raise AlphaContractError(f"L001 P023 original {label} Git blob changed")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise AlphaContractError(f"L001 P023 {label} source is not JSON object")
        unsigned = copy.deepcopy(payload)
        stored = unsigned.pop(signature_key, None)
        if stored != digest(unsigned):
            raise AlphaContractError(f"L001 P023 {label} original packet SHA mismatch")
        if payload.get("live_capital_allowed") is not False:
            raise AlphaContractError(f"L001 P023 {label} original source permitted trades")
        packets[label] = payload
        receipts[label] = {
            "repo_path": path,
            "git_blob_sha": expected_sha,
            "original_raw_file_sha256": hashlib.sha256(raw).hexdigest(),
            "original_packet_sha256": stored,
        }
    return packets, receipts


def build_cross_company_falsification(
    packets: dict[str, dict[str, Any]],
    receipts: dict[str, dict[str, str]],
) -> dict[str, Any]:
    p017 = packets["p017"]
    p018 = packets["p018"]
    p020 = packets["p020"]
    p021 = packets["p021"]
    uk_receipt = packets["p022_receipt"]
    diag = p017["company_diagnostics"]
    if set(diag) != {"GESHIP", "ZUARIIND", "DATAMATICS"}:
        raise AlphaContractError("L001 P023 three original cases changed")
    if (
        p017.get("source_review_as_of") != "2026-10-19"
        or p018.get("as_of_research_date") != REVIEW_DATE
        or p020.get("research_as_of") != REVIEW_DATE
        or p021.get("research_date") != REVIEW_DATE
        or p017.get("rank_stocks_as_buy") is not False
        or p018.get("actual_parent_lender_waterfall_or_liquidation_tax_verified")
        is not False
        or p020.get("company_paper_investment_eligible") is not False
        or p021.get("portfolio_eligible") is not False
    ):
        raise AlphaContractError("L001 P023 original source/as-of/approval drift")
    if (
        uk_receipt.get("source_state") != "ARCHIVED_FULL_ORIGINAL_UNAUDITED_OCR"
        or uk_receipt.get("original_bytes_archived") is not True
        or uk_receipt.get("original_full_pdf_sha256") != ORIGINAL_UK_PDF_SHA
        or uk_receipt.get("original_source_visual_row_replay_machine_verified")
        is not False
        or uk_receipt.get("parent_owner_cash_verified") is not False
    ):
        raise AlphaContractError("L001 P023 UK PDF custody cannot certify owner cash")
    if (
        p021.get("original_deal_cash_consideration_gbp") != 100500000
        or p021.get("reported_cfo_is_normalized_parent_owner_fcf") is not False
        or p021.get("subsidiary_14month_cash_is_post_control_only") is not False
        or p021.get("parent_control_effective") != "2025-07-28"
    ):
        raise AlphaContractError("L001 P023 UK mixed-owner data is not normalized")

    # Four unique theses. Their denominators, currencies and economic scopes
    # differ; the result must not sort these metrics into one alpha score.
    geship = diag["GESHIP"]
    price_rows = {
        row["symbol"]: row for row in p017["dated_original_close_observations"]
    }
    if set(price_rows) != {"GESHIP", "ZUARIIND", "DATAMATICS"}:
        raise AlphaContractError("L001 P023 dated original NSE EQ marks altered")
    ge_price = _checked_positive(
        price_rows["GESHIP"]["oct19_original_NSE_EQ_close_inr"],
        "GESHIP October19 close",
    )
    stale_nav = _checked_positive(
        geship["issuer_NAV_per_share_inr_stale"], "GESHIP June NAV"
    )
    ge_discount = 100 * (1 - ge_price / stale_nav)
    if (
        price_rows["GESHIP"]["frozen_isin"] != "INE017A01032"
        or not _equal(
            ge_discount, float(geship["dated_Oct19_discount_to_issuer_NAV_percent_not_margin_safety"]),
            tol=0.015,
        )
        or geship.get("current_Oct19_fully_diluted_share_count_verified")
        is not False
    ):
        raise AlphaContractError("L001 P023 GESHIP stale NAV source changed")
    ge_haircut = _checked_positive(
        geship["break_even_haircut_noncash_NAV_Oct19_percent"],
        "GESHIP value-erasing noncash NAV haircut",
    )
    if ge_haircut >= 100:
        raise AlphaContractError("L001 P023 GESHIP NAV haircut infeasible")

    zuari = diag["ZUARIIND"]
    if (
        zuari.get("Oct19_actual_attributable_SOTP_value_cr") is not None
        or zuari.get("Oct19_current_repriced_listed_holdings_cr") is not None
        or zuari.get("Oct19_contemporaneous_debt_and_pledge_covenants_cr") is not None
    ):
        raise AlphaContractError("L001 P023 ZUARI outdated creditor/source bridge promoted")
    quoted_stakes = _checked_positive(
        p018["stake_marks_by_date_cr"]["2026-10-19"], "ZUARI five stakes"
    )
    old_net_debt = _checked_positive(
        p018["net_borrowings_as_of_2026_03_31_cr_not_current"],
        "ZUARI March net debt",
    )
    old_cap = _checked_positive(
        p018["parent_Oct19_cap_from_old_basic_shares_cr_not_current_fd_cap"],
        "ZUARI historical cap",
    )
    remaining_gap = quoted_stakes - old_net_debt - old_cap
    if (
        p018.get("parent_listed_symbol") != "ZUARIIND"
        or p018.get("parent_listed_isin") != "INE217A01012"
        or not _equal(
            remaining_gap, p018["Oct19_gross_hypothetical_residual_to_old_cap_cr"]
        )
        or p018.get("current_oct19_entity_stake_units_verified") is not False
    ):
        raise AlphaContractError("L001 P023 ZUARI source basis or debt bridge drift")
    erase_fraction = remaining_gap / quoted_stakes
    if (
        erase_fraction <= 0
        or not _equal(
            erase_fraction,
            p018["Oct19_further_markdown_erasing_apparent_gap_fraction"],
            tol=1e-8,
        )
    ):
        raise AlphaContractError("L001 P023 ZUARI discount erasure disagrees")

    datamatics = diag["DATAMATICS"]
    fcf_proxy = _checked_positive(
        datamatics["FY26_CFO_less_PPE_CR_not_normalized_owner_cash"],
        "DATAMATICS FY26 cash proxy",
    )
    required = _checked_positive(
        datamatics["annual_owner_cash_needed_for_50pct_gross_at_16x_cr"],
        "DATAMATICS 50pct gross reverse cash hurdle",
    )
    required_growth = 100 * (required / fcf_proxy - 1)
    if (
        price_rows["DATAMATICS"]["frozen_isin"] != "INE365B01017"
        or not _equal(
            required_growth,
            datamatics["cash_proxy_required_growth_for_50pct_gross_at_16x_pct"],
            tol=0.025,
        )
        or datamatics.get("FY26_209_69_cr_acquisition_payable_fully_reconciled")
        is not False
        or datamatics.get("Q1_current_diluted_share_count_verified")
        is not False
    ):
        raise AlphaContractError("L001 P023 DATAMATICS cash/equity scope drift")

    uk_deal = _checked_positive(
        p021["original_deal_cash_consideration_gbp"],
        "SUNTV UK cash deal",
    )
    mixed_cfo = _checked_positive(
        p021["reported_14month_operating_cfo_gbp"],
        "SUNTV mixed 14month CFO",
    )
    uk_yields = []
    for original in p021["illustrative_owner_cash_yield_hurdles_not_forecasts"]:
        y = _checked_positive(original["hypothetical_annual_cash_yield_fraction"], "UK yield")
        cash_need = uk_deal * y
        coverage = cash_need / mixed_cfo
        if (
            not _equal(
                cash_need,
                original["annual_owner_cash_needed_gbp"],
                tol=0.00001,
            )
            or not _equal(
                coverage,
                original["ratio_to_mixed_14month_operating_cash_not_growth_forecast"],
                tol=0.0001,
            )
            or original.get("verified_post_acquisition_recurring_owner_cash")
            is not False
        ):
            raise AlphaContractError("L001 P023 UK owner-cash hurdles drifted")
        uk_yields.append({
            "hypothetical_cash_yield_percent": round(100 * y, 2),
            "annual_owner_cash_necessary_gbp": cash_need,
            "multiple_of_mixed14month_CFO_not_growth_forecast": round(coverage, 4),
            "actual_recurring_postcontrol_cash_verified": False,
        })
    if (
        p020.get("normalized_parent_owner_FCF_cr") is not None
        or p020.get("reported_group_carrying_value_cr_not_liquidation_value")
        != 1248.27
    ):
        raise AlphaContractError("L001 P023 SUNTV group impairment not validated FCF")

    rows = [
        {
            "symbol": "GESHIP",
            "scope": "ISSUER_JUNE30_NAV_VS_OCT19_EQ_PRICE",
            "original_oct19_nse_eq_close_inr": ge_price,
            "historical_issuer_nav_per_old_share_inr_not_marked_current": stale_nav,
            "headline_discount_percent_not_margin_of_safety": round(ge_discount, 2),
            "frozen_reverse_test": {
                "noncash_NAV_haircut_wiping_reference_discount_percent": ge_haircut,
                "fleet_and_offshore_current_sale_value_verified": False,
                "legal_extinction_of_all_reacquired_shares_verified": False,
            },
            "economic_mispricing_confirmed": False,
            "next_decisive_source": "DATED_FLEET_OFFSHORE_CYCLE_NAV_AND_BUYBACK_EXTINCTION",
        },
        {
            "symbol": "ZUARIIND",
            "scope": "FIVE_OCT19_STAKE_MARKS_VS_STALE_MARCH_BORROWINGS",
            "oct19_five_listed_stake_marks_cr": round(quoted_stakes, 4),
            "march_net_borrowings_cr_not_current": round(old_net_debt, 4),
            "oct19_cap_using_old_basic_shares_cr": round(old_cap, 4),
            "hypothetical_undiscounted_stake_gap_cr_not_parent_equity": round(
                remaining_gap, 4
            ),
            "additional_stake_markdown_erasing_gap_percent": round(
                100 * erase_fraction, 3
            ),
            "listed_stake_units_after_June_confirmed": False,
            "current_creditor_pledge_waterfall_reconciled": False,
            "economic_mispricing_confirmed": False,
            "next_decisive_source": "CURRENT_CREDITOR_PLEDGE_STAKE_UNITS_AND_DISTRIBUTIONS",
        },
        {
            "symbol": "DATAMATICS",
            "scope": "FY26_CONSOLIDATED_CFO_MINUS_SELECTED_CAPEX_VS_OCT19_OLD_BASIC_CAP",
            "fy26_cash_proxy_cr_not_owner_cash": fcf_proxy,
            "oct19_historical_basic_share_cap_cr": (
                datamatics["Oct19_price_times_historical_basic_shares_cr"]
            ),
            "hypothetical_cash_required_for_50pct_share_gross_at_16x_cr": required,
            "cash_proxy_growth_required_percent_not_forecast": round(
                required_growth, 2
            ),
            "acquisition_consideration_209_69_cr_reconciled": False,
            "current_parent_diluted_equity_and_owner_cash_verified": False,
            "economic_mispricing_confirmed": False,
            "next_decisive_source": "ACQUISITION_PAYABLE_SCHEDULE_AND_NORMALIZED_OWNER_CASH",
        },
        {
            "symbol": "SUNTV",
            "scope": "MIXED_14_MONTH_UK_FRS102_CASH_VS_FRANCHISE_GBP_PRICE",
            "uk_franchise_deal_gbp": uk_deal,
            "mixed_14_month_uk_operating_CFO_gbp": mixed_cfo,
            "source_period_start": p021["source_period_start"],
            "source_period_end": p021["source_period_end"],
            "parent_control_effective": p021["parent_control_effective"],
            "reverse_owner_cash_yield_hurdles": uk_yields,
            "original_scanned_PDF_sha256_archived": ORIGINAL_UK_PDF_SHA,
            "original_visual_rows_independently_replayed_from_archive": False,
            "post_July28_recurring_owner_cash_reconciled": False,
            "economic_mispricing_confirmed": False,
            "next_decisive_source": "POST_CONTROL_ANNUAL_OWNER_CASH_AND_RIGHTS_RENEWAL_ECONOMICS",
        },
    ]
    result = {
        "schema_version": 1,
        "review_id": REVIEW_ID,
        "analysis_date_ist": REVIEW_DATE,
        "market_session_date_ist": "2026-10-19",
        "analysis_is_after_HG009_frozen_Oct15_entry": True,
        "source_receipts": receipts,
        "issuer_hypotheses_reviewed": list(COMPANIES),
        "four_independent_units_are_not_single_alpha_score": True,
        "economic_value_proven_cases": 0,
        "completed_probability_weighted_equity_valuations": 0,
        "investable_portfolio_candidates_approved": 0,
        "evidence": rows,
        "owner_cash_after_cost_verified_for_all_companies": False,
        "no_source_unavailable_means_company_return_is_zero": True,
        "return_forecasts_created": False,
        "matched_300_HG009_outcome_population_untouched": True,
        "historical_100_issuer_accounting_audit_untouched": True,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result


def materialize_falsification_frontier(root: Path) -> dict[str, Any]:
    packets, receipts = load_original_review_sources(root)
    return build_cross_company_falsification(packets, receipts)


def validate_falsification_frontier(value: dict[str, Any], root: Path) -> None:
    unsigned = copy.deepcopy(value)
    stored = unsigned.pop("report_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("L001 P023 evidence packet SHA mismatch")
    if value != materialize_falsification_frontier(root):
        raise AlphaContractError("L001 P023 original source replay differs")
