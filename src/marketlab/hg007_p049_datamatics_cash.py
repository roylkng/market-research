"""P049: Datamatics FY26 audited-cashflow reverse-hurdle development lens.

Original NSE FY26 results and August 2026 company quarterly release supply
page-attributed, manually verified numbers. The original financial PDF bytes
are NOT stored here. This is a provisional research sensitivity, not a price
target, an investment grade valuation, or a return model.

Market price comes only from frozen P047 original October 13 NSE UDiFF packet.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from marketlab.alpha import digest
from marketlab.hg007_oct13_28_snapshot import validate_oct13_market_snapshot

AUDIT_ID = "HG007-P049-DATAMATICS-FY26-CASH-FLOW-REVERSE-HURDLE-v1"
PRICE_PACKET_PATH = Path(
    "research/hg007/hg007-p047-oct13-28-official-nse-source-v1.json"
)
PRICE_PACKET_GIT_BLOB = "5e495c980985e0c42c112868cb04bfffb27807dd"

# FIRST-PARTY documentation, page-numbered. Links have been visually checked
# but source PDF bytes have not been retained/hashed in this repository.
FINANCIAL_SOURCE = {
    "url": (
        "https://nsearchives.nseindia.com/corporate/"
        "DGSL_21052026190445_SEOutcomeUploaded.pdf"
    ),
    "document_date": "2026-05-21",
    "audit_period_end": "2026-03-31",
    "board_announcement_page_zero_based": 0,
    "merger_no_new_share_consideration_page_zero_based": 2,
    "share_capital_balance_sheet_page_zero_based": 6,
    "consolidated_cashflow_page_zero_based": 7,
    "raw_pdf_bytes_archived": False,
}
QUARTER_SOURCE = {
    "url": (
        "https://www.datamatics.com/press-release-list/"
        "datamatics-q1fy27-revenue-up-9.9-yoy-to-513.9-crore-pat-at-"
        "72.3-crore-up-by-43.5-yoy?hs_amp=true"
    ),
    "document_date": "2026-08-05",
    "source_type": "COMPANY_PRESS_RELEASE_NOT_AUDITED_STANDALONE_Q1_SOURCE",
}
FY26_SOURCE = {
    "url": (
        "https://www.datamatics.com/press-release-list/"
        "datamatics-fy26-revenue-up-15.3-yoy-to-1987.2-crore-ebitda-at-"
        "371.6-crore-up-by-62.1-yoy"
    ),
    "document_date": "2026-05-21",
    "source_type": "MANAGEMENT_PRESS_RELEASE_CONSOLIDATED_EBITDA",
}

# FY25/FY26 cashflow statement consolidated columns from the first-party NSE
# filing, 0-based PDF page 7; all monetary values below are INR crores.
AUDITED_CASH_FACTS = {
    "fy26_cfo_inr_crore": 323.99,
    "fy26_fixed_assets_capital_work_advances_cash_inr_crore": 39.57,
    "fy25_cfo_inr_crore": 223.72,
    "fy25_fixed_assets_capital_work_advances_cash_inr_crore": 35.91,
    "fy26_consolidated_cash_and_equivalents_inr_crore": 141.42,
    "fy26_consolidated_current_borrowing_inr_crore": 54.74,
    "fy26_consolidated_noncurrent_borrowing_inr_crore": 86.62,
    "fy26_current_lease_liability_inr_crore": 32.80,
    "fy26_noncurrent_lease_liability_inr_crore": 45.77,
    "fy26_current_investments_inr_crore": 410.13,
    "fy26_noncurrent_investments_inr_crore": 228.77,
    "fy26_goodwill_inr_crore": 611.12,
    "fy26_paid_up_equity_share_capital_inr_crore": 29.5531945,
    "equity_share_face_value_inr": 5.0,
    "fy26_paid_up_equity_share_capital_exact_inr": 295531945,
    "fy26_consolidated_ebitda_management_reported_inr_crore": 371.6,
}
Q1_MANAGEMENT_FACTS = {
    "q1fy27_revenue_inr_crore": 513.9,
    "q1fy26_revenue_inr_crore": 467.6,
    "q4fy26_revenue_inr_crore": 519.3,
    "q1fy27_ebitda_inr_crore": 101.1,
    "q1fy26_ebitda_inr_crore": 75.9,
    "q4fy26_ebitda_inr_crore": 110.6,
    "q1fy27_pat_after_nci_inr_crore": 72.3,
    "q1fy26_pat_after_nci_inr_crore": 50.4,
}
EXPLORATORY_FCF_MULTIPLES = (12, 16, 20)


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _nonnegative_finite(value: object, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label}: amount must be nonnegative and finite")
    return float(value)


def _price_from_frozen_oct13(root: Path) -> tuple[float, str, str]:
    raw = (root / PRICE_PACKET_PATH).read_bytes()
    if _git_blob(raw) != PRICE_PACKET_GIT_BLOB:
        raise ValueError("P049 frozen October 13 NSE source blob changed")
    packet = json.loads(raw)
    validate_oct13_market_snapshot(packet)
    rows = [
        row for row in packet["company_source_observations"]
        if row["symbol"] == "DATAMATICS"
    ]
    if len(rows) != 1:
        raise ValueError("P049 requires exactly one original DATAMATICS NSE EQ row")
    row = rows[0]
    if (
        row.get("source_series_state")
        != "OFFICIAL_EQ_PRICE_VOLUME_OBSERVED_NOT_FILL"
        or row.get("frozen_isin") != "INE365B01017"
        or packet.get("market_session_ist") != "2026-10-13"
        or row.get("actual_trade_execution_confirmed") is not False
    ):
        raise ValueError("P049 NSE DATAMATICS identity or source-date drift")
    price = _nonnegative_finite(row.get("reported_EQ_close_inr"), "Oct13 close")
    if price <= 0:
        raise ValueError("P049 original closing price must be positive")
    return price, packet["packet_sha256"], hashlib.sha256(raw).hexdigest()


def build_datamatics_reverse_hurdle(
    *,
    oct13_close_inr: float,
    frozen_source_packet_sha256: str,
    frozen_source_raw_sha256: str,
    cash_facts: dict[str, float | int] | None = None,
    q1_facts: dict[str, float] | None = None,
) -> dict[str, Any]:
    cash = AUDITED_CASH_FACTS if cash_facts is None else cash_facts
    quarter = Q1_MANAGEMENT_FACTS if q1_facts is None else q1_facts
    if set(cash) != set(AUDITED_CASH_FACTS) or set(quarter) != set(Q1_MANAGEMENT_FACTS):
        raise ValueError("P049 all explicitly sourced cash and quarter facts required")
    facts = {
        k: _nonnegative_finite(v, k) for k, v in cash.items()
    }
    q1 = {
        k: _nonnegative_finite(v, k) for k, v in quarter.items()
    }
    share_capital = facts["fy26_paid_up_equity_share_capital_exact_inr"]
    face = facts["equity_share_face_value_inr"]
    if face <= 0 or share_capital <= 0 or share_capital % face != 0:
        raise ValueError("P049 reported basic share-count cannot be reconstructed")
    if not math.isclose(
        facts["fy26_paid_up_equity_share_capital_inr_crore"] * 10_000_000,
        share_capital,
        abs_tol=0.01,
    ):
        raise ValueError("P049 equity paid-up face-value source conflict")

    basic_shares = int(share_capital / face)
    price = _nonnegative_finite(oct13_close_inr, "observed NSE price")
    if price <= 0 or not all(
        isinstance(s, str) and len(s) == 64
        for s in (frozen_source_packet_sha256, frozen_source_raw_sha256)
    ):
        raise ValueError("P049 frozen market quote or price source SHA missing")
    mcap = basic_shares * price / 10_000_000
    fy26_cash_proxy = (
        facts["fy26_cfo_inr_crore"]
        - facts["fy26_fixed_assets_capital_work_advances_cash_inr_crore"]
    )
    fy25_cash_proxy = (
        facts["fy25_cfo_inr_crore"]
        - facts["fy25_fixed_assets_capital_work_advances_cash_inr_crore"]
    )
    if fy26_cash_proxy <= 0 or fy25_cash_proxy <= 0:
        raise ValueError("P049 source-year operating-cash-less-capex invalid")

    # No net cash (especially investment assets), minority, lease-adjusted EV
    # or debt correction. This is NOT a professional DCF/fair value.
    scenarios = [
        {
            "exploratory_multiple_on_fy26_cash_proxy": multiple,
            "illustrative_equity_value_inr_crore_not_fair_value": round(
                fy26_cash_proxy * multiple, 3
            ),
            "price_equivalent_inr_not_target": round(
                fy26_cash_proxy * multiple * 10_000_000 / basic_shares, 2
            ),
            "percent_difference_vs_oct13_close_not_return_forecast": round(
                100 * (fy26_cash_proxy * multiple / mcap - 1), 2
            ),
            "probability": None,
        }
        for multiple in EXPLORATORY_FCF_MULTIPLES
    ]
    required_for_50pct_at_16 = 1.5 * mcap / 16
    result: dict[str, Any] = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": (
            "FY26_OBSERVED_CASH_PROXY_CROSS_DATE_REVERSE_HURDLE_ONLY"
        ),
        "market_source": {
            "date": "2026-10-13",
            "symbol": "DATAMATICS",
            "isin": "INE365B01017",
            "official_EQ_close_inr_not_current_quote": price,
            "frozen_original_28_case_packet_sha256": frozen_source_packet_sha256,
            "frozen_original_28_case_file_sha256": frozen_source_raw_sha256,
        },
        "source_page_refs": {
            "audited_exchange_fy26": FINANCIAL_SOURCE,
            "issuer_fy26_ebitda": FY26_SOURCE,
            "issuer_q1fy27": QUARTER_SOURCE,
        },
        "source_financial_pdf_raw_archived_and_replayable": False,
        "fy26_historical_cash_and_balance_sheet_facts": cash,
        "q1fy27_historical_issuer_reported_facts": quarter,
        "estimated_basic_shares_using_mar31_paidup_not_oct13_current": basic_shares,
        "estimated_oct13_cross_date_basic_market_cap_inr_crore": round(mcap, 3),
        "fy26_cfo_less_fixed_asset_cash_spending_inr_crore_not_normalized_fcf": (
            round(fy26_cash_proxy, 3)
        ),
        "fy25_comparable_cashflow_proxy_inr_crore": round(fy25_cash_proxy, 3),
        "historical_cashflow_proxy_growth_percent_not_next_year_forecast": round(
            100 * (fy26_cash_proxy / fy25_cash_proxy - 1), 2
        ),
        "basic_reference_market_cap_to_fy26_cashflow_proxy_multiple": round(
            mcap / fy26_cash_proxy, 3
        ),
        "observed_cashflow_proxy_yield_percent": round(
            100 * fy26_cash_proxy / mcap, 2
        ),
        "fy26_financial_borrowings_less_cash_inr_crore_excluding_lease": round(
            facts["fy26_consolidated_noncurrent_borrowing_inr_crore"]
            + facts["fy26_consolidated_current_borrowing_inr_crore"]
            - facts["fy26_consolidated_cash_and_equivalents_inr_crore"],
            3,
        ),
        "fy26_consolidated_total_lease_liabilities_inr_crore": round(
            facts["fy26_current_lease_liability_inr_crore"]
            + facts["fy26_noncurrent_lease_liability_inr_crore"],
            3,
        ),
        "q1fy27_yoy_revenue_growth_percent_source_only": round(
            100 * (
                q1["q1fy27_revenue_inr_crore"] / q1["q1fy26_revenue_inr_crore"] - 1
            ),
            2,
        ),
        "q1fy27_yoy_ebitda_growth_percent_source_only": round(
            100 * (
                q1["q1fy27_ebitda_inr_crore"] / q1["q1fy26_ebitda_inr_crore"] - 1
            ),
            2,
        ),
        "q1fy27_sequential_revenue_growth_percent_source_only": round(
            100 * (
                q1["q1fy27_revenue_inr_crore"] / q1["q4fy26_revenue_inr_crore"] - 1
            ),
            2,
        ),
        "exploratory_multiples_are_not_calibrated": True,
        "no_net_cash_or_investment_adjustment_applied": True,
        "no_share_dilution_model_applied": True,
        "cashflow_proxy_excludes_acquisition_investment_and_financing_outflows": True,
        "scenarios_are_price_equivalents_not_targets": scenarios,
        "cash_proxy_required_for_50pct_gross_share_value_at_16x_inr_crore": round(
            required_for_50pct_at_16, 3
        ),
        "cash_proxy_increase_required_for_50pct_at_16x_percent_not_forecast": round(
            100 * (required_for_50pct_at_16 / fy26_cash_proxy - 1), 2
        ),
        "current_oct13_fully_diluted_shares_verified": False,
        "normalized_sustainable_fcf_verified": False,
        "shareholder_cost_of_capital_estimated": False,
        "corporate_action_adjusted_total_return_estimated": False,
        "probability_weighted_fair_value_inr": None,
        "expected_future_total_return": None,
        "live_capital_allowed": False,
        "portfolio_eligibility_allowed": False,
        "investment_recommendation_generated": False,
    }
    result["packet_sha256"] = digest(result)
    return result


def materialize_datamatics_cash_hurdle(root: Path) -> dict[str, Any]:
    price, packet_sha, source_sha = _price_from_frozen_oct13(root)
    return build_datamatics_reverse_hurdle(
        oct13_close_inr=price,
        frozen_source_packet_sha256=packet_sha,
        frozen_source_raw_sha256=source_sha,
    )
