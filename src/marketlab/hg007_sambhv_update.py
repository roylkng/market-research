"""Overlay real Sambhv Oct Q2 volume and conditional warrant cash onto five-case readiness.

Preserve original P030 five-company hypothesis/readiness immutably.
Source SHA for July15 P032, October P031 and P030 original is mandatory.
No stock ranking, alpha, capital, or realized EBITDA is inferred.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

AUDIT_ID = "HG007-P033-FIVE-CASE-UNDERWRITING-LATEST-SAMBHV-v1"
SOURCES = {
    "p030": (
        "research/hg007/hg007-p030-five-case-underwriting-readiness-v1.json",
        "41bea93418f0dbaf8ac024375f99d8c5d1cf0f79",
    ),
    "p031": (
        "research/hg007/sambhv-oct2026-sources/sambhv-october-case-v1.json",
        "4f6c9df119250e9a29efa432570bb00f386d1614",
    ),
    "p032": (
        "research/hg007/sambhv-july2026-warrant/warrant-board-cash-timing-v1.json",
        "08bdd7f2d19103e6112ded8766d70595e083301a",
    ),
    "july_board_receipt": (
        "research/hg007/sambhv-july2026-warrant/original-source-receipt-v1.json",
        "dd0f8a4e6ef6cab7bccb90abf7669c2c0fbb5499",
    ),
}
FROZEN_FIVE = ("ANANTRAJ", "DEVX", "INOXGREEN", "NPST", "SAMBHV")
ORIGINAL_JULY_BOARD_SHA = (
    "9e421b2e6de480acfc7db7fb1f3b6aa1b4b125513c1cf2360ca34b8f0c3e1a6f"
)
ORIGINAL_JULY_BOARD = (
    "research/hg007/sambhv-july2026-warrant/original-raw/sha256/"
    + ORIGINAL_JULY_BOARD_SHA + ".pdf"
)


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_pinned_latest(root: Path) -> tuple[dict[str, dict], dict]:
    source: dict[str, dict] = {}
    hashes: dict[str, dict] = {}
    for key, (filename, expected) in SOURCES.items():
        raw = (root / filename).read_bytes()
        if _git_blob(raw) != expected:
            raise ValueError(f"original source Git blob drifted: {key}")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise TypeError("original company research must be JSON object")
        source[key] = value
        hashes[key] = {
            "path": filename,
            "git_blob_sha": expected,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
        }
    original = (root / ORIGINAL_JULY_BOARD).read_bytes()
    if (
        hashlib.sha256(original).hexdigest() != ORIGINAL_JULY_BOARD_SHA
        or len(original) != 346834
    ):
        raise ValueError("original five-page warrant board PDF source SHA changed")
    hashes["july_board_original_pdf"] = {
        "path": ORIGINAL_JULY_BOARD,
        "sha256": ORIGINAL_JULY_BOARD_SHA,
        "byte_count": len(original),
    }
    return source, hashes


def _check_float(value: object, expected: float, label: str) -> None:
    if (
        type(value) not in (int, float)
        or not math.isfinite(float(value))
        or not math.isclose(float(value), expected, abs_tol=1e-8, rel_tol=1e-12)
    ):
        raise ValueError(f"original {label} violates frozen numeric source")


def build_latest_underwriting(
    source: dict[str, dict], hashes: dict[str, dict],
) -> dict[str, Any]:
    if set(source) != set(SOURCES) or set(hashes) != {*SOURCES, "july_board_original_pdf"}:
        raise ValueError("only original four dated issuer sources may enter five-case update")
    board = source["p030"]
    oct = source["p031"]
    cash = source["p032"]
    original = source["july_board_receipt"]
    if (
        board.get("readiness_id")
        != "HG007-P030-2026-10-11-FIVE-CASE-UNDERWRITING-READINESS-v1"
        or board.get("original_five_hg005_company_count") != 5
        or board.get("separate_valuation_or_return_ready_company_count") != 0
        or board.get("case_completion_probabilities_published") != 0
        or board.get("live_capital_allowed") is not False
    ):
        raise ValueError("original five-company underwriting gate changed")
    rows = board.get("casework")
    if not isinstance(rows, list) or tuple(row["symbol"] for row in rows) != FROZEN_FIVE:
        raise ValueError("original P030 five-company source/order changed")
    if (
        oct.get("readout_id")
        != "HG007-P031-SAMBHV-OCT2026-VOLUME-WARRANT-PRIMARY-SOURCE-v1"
        or oct.get("q2_2026_27_volume_report_date") != "2026-10-02"
        or oct.get("warrant_monitoring_appointment_date") != "2026-10-06"
        or oct.get("shareholder_prior_approval_date") != "2026-08-10"
        or oct.get("warrant_exercise_and_dilution_verified") is not False
        or oct.get("warrant_proceeds_are_verified_current_cash") is not False
        or oct.get("live_capital_allowed") is not False
    ):
        raise ValueError("October source cannot be treated as realized warrant cash")
    q2 = oct.get("q2_vs_q1_vs_prior_year_sales_tonnes", {}).get(
        "all_product_sales_tonnes"
    )
    if not isinstance(q2, dict):
        raise TypeError("original Q2 sales-volume source missing")
    if (
        q2.get("q2_fy27_tonnes") != 122662
        or q2.get("q2_fy26_tonnes") != 98768
        or q2.get("q1_fy27_tonnes") != 107771
        or oct.get("sales_yoy_growth_proves_incremental_ebitda") is not False
    ):
        raise ValueError("issuer Q2 sales tonnes must remain volume, not EBITDA")
    expected_growth = 100 * (122662 / 98768 - 1)
    _check_float(q2.get("yoy_pct"), expected_growth, "Q2 sales YoY tonnes")
    _check_float(
        oct.get("warrant_proceeds_issuer_disclosed_inr_crore"),
        99.9971, "headline monitoring-agency proceeds",
    )
    if (
        cash.get("readout_id") != "HG007-P032-SAMBHV-BOARD-WARRANT-CASH-TRANCHES-v1"
        or cash.get("original_source_provenance", {}).get("original_pdf_sha256")
        != ORIGINAL_JULY_BOARD_SHA
        or cash.get("proposed_maximum_warrants") != 8695400
        or cash.get("cash_issue_price_per_warrant_inr") != 115
        or cash.get("exercise_time_limit_months_after_actual_allotment") != 18
        or cash.get("actual_allotment_date_verified") is not False
        or cash.get("all_8_6954m_warrants_issued_verified") is not False
        or cash.get("first_25pct_subscription_cash_received_verified") is not False
        or cash.get("last_75pct_conversion_cash_received_verified") is not False
        or cash.get("live_capital_allowed") is not False
    ):
        raise ValueError("board cash schedule cannot be promoted as received funds")
    if (
        original.get("state") != "ORIGINAL_BOARD_PDF_CAPTURED_AND_TERMS_BOUND"
        or original.get("original_pdf_sha256") != ORIGINAL_JULY_BOARD_SHA
        or original.get("original_pdf_bytes") != 346834
        or original.get("source_text_verified", {}).get(
            "percent_due_only_at_actual_warrant_allotment"
        ) != 25
        or original.get("source_text_verified", {}).get(
            "percent_due_only_at_equity_conversion"
        ) != 75
        or original.get("actual_warrant_conversion_verified") is not False
    ):
        raise ValueError("fixed original five-page issuer cash terms changed")
    first = cash.get("scenario_only_upfront_cash_at_100pct_allotment_cr")
    later = cash.get("scenario_only_later_cash_at_100pct_conversion_cr")
    total = cash.get("fully_exercised_maximum_gross_issue_consideration_cr")
    capex = cash.get("frozen_source_steel_plus_power_project_capex_cr")
    _check_float(first, 24.999275, "25% hypothetical upfront cash")
    _check_float(later, 74.997825, "75% hypothetical conversion cash")
    _check_float(total, 99.9971, "full warrant cash only upon exercise")
    _check_float(capex, 935, "older steel plus power budget")
    if not math.isclose(first + later, total, abs_tol=1e-10):
        raise ValueError("proposed 25/75 company warrant payments do not reconcile")
    concentration = cash.get("promoter_group_anjaneya_proportion_of_proposal_pct")
    _check_float(concentration, 100 * 6_608_600 / 8_695_400, "original promoter concentration")

    result_cases = []
    for row in rows:
        case = deepcopy(row)
        if case["symbol"] == "SAMBHV":
            old_stage = case.get("source_evidence_case", {})
            if (
                old_stage.get("combined_steel_plus_power_capex_if_both_required_inr_crore")
                != 935
                or old_stage.get("steel_only_issuer_capex_inr_crore") != 810
                or case.get("probability_weighted_equity_expected_return") is not None
            ):
                raise ValueError("original Sambhv P030 capex or return gate changed")
            case["newer_original_sambhv_cash_and_volume_evidence"] = {
                "source_July15_proposed_issue_total_cr": total,
                "if_100pct_allotted_25pct_advance_cr_not_bank_cash": first,
                "if_100pct_exercised_75pct_later_cr_not_bank_cash": later,
                "actual_allotment_or_cash_receipt_verified": False,
                "first_cash_tranche_received_by_oct11_verified": False,
                "actual_exercise_or_new_shares_verified": False,
                "proposed_18_month_window_starts_on_actual_allotment_date": True,
                "actual_allotment_date_unknown": True,
                "proposed_anjaneya_76pct_concentration": concentration,
                "q2_fy27_sales_volume_tonnes": 122662,
                "q2_fy27_sales_tonnes_yoy_pct": expected_growth,
                "q2_sales_growth_proves_new_plant_or_ebitda": False,
                "steel_plus_power_gross_capex_cr": capex,
                "hypothetical_full_gross_warrants_over_combined_capex": total / capex,
                "hypothetical_25pct_advance_over_combined_capex": first / capex,
                "actual_funding_gap_verifiable": False,
                "historical_hg005_or_p030_repriced": False,
                "valuation_ready": False,
            }
        else:
            case["newer_original_sambhv_cash_and_volume_evidence"] = None
        if (
            case.get("current_price_target") is not None
            or case.get("portfolio_eligibility_allowed") is not False
            or case.get("live_capital_allowed") is not False
        ):
            raise ValueError("five-company readiness cannot be promoted by Sambhv-only update")
        result_cases.append(case)
    return {
        "schema_version": 1,
        "overlay_id": AUDIT_ID,
        "classification": "DATED_COMPANY_SOURCE_UPDATE_NOT_ALPHARANK_OR_STOCK_TARGET",
        "as_of_ist": "2026-10-11",
        "original_five_case_count": 5,
        "original_five_case_names_and_order_unchanged": True,
        "source_provenance": hashes,
        "source_case_count_with_new_sambhv_data": 1,
        "casework": result_cases,
        "latest_sambhv_warrant_cash_received_independently_verified": False,
        "latest_sambhv_q2_incremental_ebitda_verified": False,
        "current_five_company_FD_and_EV_verified": False,
        "source_probabilities_or_expected_returns_published": 0,
        "stock_selection_or_investment_rankings_changed": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
