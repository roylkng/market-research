"""OPEN004: source-labeled cash accounting, not a model or a trading strategy.

Reconstructs BLS FY26 consolidated and parent standalone cash flows without
double-counting intra-group dividends. Reconstructs Mastek FY27 H1 cash and
Q2 exceptional accounting against the original prior-year comparatives.

Original source first-retrieval clocks and raw bytes are not archived here.
Do not use this study for a prospective decision, owner-FCFE or capital.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

DEFAULT = (
    Path(__file__).resolve().parents[1]
    / "research/broad-discovery/OPEN004_BLS_MASTEK_CASH_SOURCES_20261025.json"
)


def amount(obj: dict, key: str) -> float:
    raw = obj[key]
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise TypeError(f"{key}: amount must be numeric")
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{key}: invalid nonnegative amount")
    return value


def r4(v: float) -> float:
    return round(v, 4)


def evaluate(data: dict) -> dict:
    if data["schema"] != "OPEN004-20261025-PARENT-CASH-CHALLENGE-v1":
        raise ValueError("different or changed protocol")
    if data["type"] != "POST_HOC_UNDERWRITING_FALSIFICATION":
        raise ValueError("cannot represent prospective alpha")
    if data["analyzed_at_date"] != "2026-10-25" or data["prices_observed_at"] != "2026-10-23":
        raise ValueError("source chronology mismatch")
    if data["no_original_h002_h003_hg009_modifications"] is not True:
        raise ValueError("frozen research would be changed")
    evidence = data["evidence_custody"]
    if evidence != {
        "original_bytes_archived_in_research_repo": False,
        "first_retrieved_utc": None,
        "raw_sha256": None,
    }:
        raise ValueError("unverified raw source custody asserted")
    if data["approval"] != {
        "parent_owner_fcfe_verified": False,
        "conservative_intrinsic_value_verified": False,
        "capital_authorized": False,
        "portfolio_entries": 0,
    }:
        raise ValueError("research-only decision cannot be promoted")

    bls = data["BLS"]
    mastek = data["MASTEK"]
    if bls["nse_symbol"] != "BLS" or bls["isin"] != "INE153T01027":
        raise ValueError("BLS identity mismatch")
    if mastek["nse_symbol"] != "MASTEK" or mastek["isin"] != "INE759A01021":
        raise ValueError("MASTEK identity mismatch")
    if bls["fy_end"] != "2026-03-31" or mastek["fy27_H1_end"] != "2026-09-30":
        raise ValueError("cashflow observation period changed")
    if (
        not bls["consolidated_original_nse"].startswith(
            "https://nsearchives.nseindia.com/corporate/ixbrl/"
        )
        or not bls["standalone_original_nse"].startswith(
            "https://nsearchives.nseindia.com/corporate/ixbrl/"
        )
        or not mastek["original_nse_press_and_presentation"].startswith(
            "https://nsearchives.nseindia.com/corporate/"
        )
    ):
        raise ValueError("original NSE source identity missing")

    b = bls["consolidated"]
    p = bls["standalone_parent"]
    cfo = amount(b, "after_tax_cfo_crore")
    ppe = amount(b, "ppe_cash_crore")
    lease = amount(b, "lease_principal_cash_crore")
    interest = amount(b, "finance_interest_paid_crore")
    core_but_unverified = cfo - ppe - lease - interest
    selected_other_uses = sum(
        amount(b, key)
        for key in (
            "cash_used_to_obtain_control_of_business_crore",
            "cash_paid_to_invest_partnership_crore",
            "cash_paid_change_ownership_subsidiaries_crore",
        )
    )
    after_selected_uses = core_but_unverified - selected_other_uses
    shares = amount(bls, "basic_share_count_crore_from_FY26_paid_up_capital")
    price = amount(bls, "price_inr")
    mcap = shares * price
    if min(cfo, shares, price, mcap) <= 0:
        raise ValueError("BLS denominator/cash invalid")
    if r4(
        amount(b, "parent_attributable_profit_crore")
        + amount(b, "noncontrolling_profit_crore")
    ) != 723.8002:
        raise ValueError("profit-attribution mismatch")

    parent_cfo = amount(p, "after_tax_cfo_crore")
    parent_dividend = amount(p, "subsidiary_dividends_investing_inflow_crore")
    parent_after_selected = (
        parent_cfo + parent_dividend
        - amount(p, "ppe_cash_crore")
        - amount(p, "lease_principal_cash_crore")
    )
    parent_after_common_dividend = (
        parent_after_selected - amount(p, "common_dividends_paid_crore")
    )
    cash_like = sum(
        amount(b, key)
        for key in ("current_investments_crore", "cash_equivalents_crore",
                    "other_bank_balances_crore")
    )
    gross_financing = sum(
        amount(b, key)
        for key in ("gross_current_and_noncurrent_borrowings_crore",
                    "gross_current_and_noncurrent_lease_liabilities_crore")
    )

    curr = mastek["H1_FY27"]
    prev = mastek["H1_FY26"]
    def mastek_h1(x: dict) -> dict:
        operating = amount(x, "after_tax_cfo_crore")
        asset_purchase = amount(x, "selected_ppe_and_intangible_cash_crore")
        lease_payment = amount(x, "lease_principal_cash_crore")
        borrowing_interest = amount(x, "interest_paid_on_loan_crore")
        lease_interest = amount(x, "interest_paid_on_finance_lease_crore")
        return {
            "operating_cash": operating,
            "after_ppe_lease_principal": operating - asset_purchase - lease_payment,
            "after_ppe_lease_all_finance_interest": (
                operating - asset_purchase - lease_payment - borrowing_interest
                - lease_interest
            ),
        }

    current = mastek_h1(curr)
    previous = mastek_h1(prev)
    if previous["operating_cash"] <= 0 or previous["after_ppe_lease_principal"] <= 0:
        raise ValueError("invalid Mastek period comparison")
    quarter = mastek["Q2_FY27"]
    older_q2 = mastek["Q2_FY26"]
    operating_pbt = (
        amount(quarter, "reported_pbt_crore")
        - amount(quarter, "reported_net_exceptional_items_gain_crore")
    )
    previous_pbt = amount(older_q2, "reported_pbt_crore")
    if previous_pbt <= 0 or operating_pbt < 0:
        raise ValueError("invalid normalized group PBT")
    q2property = amount(quarter, "standalone_property_sale_gain_recorded_crore")
    if q2property < amount(quarter, "reported_net_exceptional_items_gain_crore"):
        raise ValueError("exceptional PBT bridge misassigned")

    return {
        "schema": data["schema"],
        "as_of": data["analyzed_at_date"],
        "research_only": True,
        "capital_authorized": False,
        "verified_parent_owner_fcfe": None,
        "price_targets": None,
        "BLS": {
            "group_cash_after_ppe_lease_interest_crore": r4(core_but_unverified),
            "group_cash_after_selected_acquisition_uses_crore": r4(after_selected_uses),
            "naive_cash_ratio_after_ppe_lease_interest_pct": r4(
                core_but_unverified / mcap * 100
            ),
            "naive_cash_ratio_after_selected_acquisition_uses_pct": r4(
                after_selected_uses / mcap * 100
            ),
            "parent_cfo_crore": r4(parent_cfo),
            "parent_actual_dividends_received_from_subs_crore": r4(parent_dividend),
            "parent_cash_after_ppe_lease_including_sub_dividends_crore": r4(
                parent_after_selected
            ),
            "parent_cash_after_including_ordinary_dividend_paid_crore": r4(
                parent_after_common_dividend
            ),
            "double_counting_parent_receipts_in_group_cash_forbidden": True,
            "group_cashlike_before_restrictions_crore": r4(cash_like),
            "group_cashlike_less_borrowings_and_lease_liabilities_crore": r4(
                cash_like - gross_financing
            ),
            "cash_legally_available_to_parent_crore": None,
            "fy26_shares_are_not_new_verified_diluted_shares": True,
        },
        "MASTEK": {
            "h1_current_after_tax_cfo_crore": r4(current["operating_cash"]),
            "h1_prior_after_tax_cfo_crore": r4(previous["operating_cash"]),
            "cfo_yoy_change_pct": r4(
                (current["operating_cash"] / previous["operating_cash"] - 1) * 100
            ),
            "h1_current_after_ppe_and_lease_crore": r4(
                current["after_ppe_lease_principal"]
            ),
            "h1_prior_after_ppe_and_lease_crore": r4(
                previous["after_ppe_lease_principal"]
            ),
            "cash_proxy_yoy_change_pct": r4(
                (current["after_ppe_lease_principal"] /
                 previous["after_ppe_lease_principal"] - 1) * 100
            ),
            "h1_current_after_selected_finance_interest_crore": r4(
                current["after_ppe_lease_all_finance_interest"]
            ),
            "h1_prior_after_selected_finance_interest_crore": r4(
                previous["after_ppe_lease_all_finance_interest"]
            ),
            "Q2_current_pbt_ex_exceptional_crore": r4(operating_pbt),
            "Q2_reported_pbt_prior_crore": r4(previous_pbt),
            "Q2_underlying_pbt_yoy_change_pct": r4(
                (operating_pbt / previous_pbt - 1) * 100
            ),
            "h1_bad_debts_written_off_crore": r4(
                amount(curr, "bad_debts_written_off_crore")
            ),
            "Q2_property_sale_gain_standalone_crore": r4(q2property),
            "h1_property_sale_investing_cash_net_tax_crore": r4(
                amount(curr, "sale_of_property_gross_proceeds_net_disposal_cost_crore")
                - amount(curr, "tax_on_property_sale_cash_crore")
            ),
            "backlog_sequential_change_pct": r4(
                (amount(curr, "outstanding_backlog_crore") /
                 amount(mastek["Q1_FY27"], "order_backlog_crore") - 1) * 100
            ),
            "cash_after_selected_claims_not_owner_fcfe": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT)
    args = parser.parse_args()
    report = evaluate(json.loads(args.input.read_text(encoding="utf-8")))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
