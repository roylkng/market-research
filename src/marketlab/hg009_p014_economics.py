"""HG009 P014: original-source economic falsification, not stock ranking.

The ten company names were frozen before October 15 prices. This October 16
review follows the first market outcome, hence cannot count as preregistered
alpha, tune HG009 selections, or create a future-return recommendation.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_daily import validate_hg009_daily_snapshot

REVIEW_ID = "HG009-P014-20261016-SYMMETRIC-OWNER-CASH-REVIEW-v1"
SOURCE_MAP = {
    "underwriting": (
        "research/hg009/hg009-p008-ten-underwriting-evidence-v1.json",
        "6b26dcf1cc00858c7745bf552f6626af389dcfef",
        "packet_sha256",
    ),
    "mayur": (
        "research/hg009/hg009-p010-mayur-investing-cash-bridge-v1.json",
        "e6b4d2e710d65f2577ef94fabe599550756d890f",
        "report_sha256",
    ),
    "pix": (
        "research/hg009/hg009-p011-pix-symmetric-quarter-profit-v1.json",
        "3158dbdddebec91296ab5c706e04750a1fa25928",
        "packet_sha256",
    ),
    "datamatics": (
        "research/hg009/hg009-p012-datamatics-fy26-cash-bridge-v1.json",
        "b3eff26c8fdd674d24c9ae2f50bde49de6a9d9e1",
        "report_sha256",
    ),
    "three": (
        "research/hg009/hg009-p013-fy26-cash-use-bridge-v1.json",
        "2b2891b1d5c38a570bd492b4eb822fabf9fd9f36",
        "report_sha256",
    ),
    "market": (
        "research/hg009/daily/2026-10-15-v1.json",
        "187fa19e8c2e8384dfc82b1fc3814e4768f0644e",
        "packet_sha256",
    ),
}
PREDECLARED = (
    "ANANTRAJ", "SAMBHV", "INOXGREEN", "DATAMATICS",
    "ACUTAAS", "ACE", "TRAVELFOOD", "POKARNA",
    "MAYURUNIQ", "PIXTRANS",
)
QUESTION = {
    "ANANTRAJ": "EFFECTIVE_CLOUD_DEMERGER_WITH_NO_DOUBLE_COUNTED_DEBT_EQUITY_FCF",
    "SAMBHV": "COMMISSIONED_0_36_MMTPA_CAPACITY_NET_OF_POWER_CAPEX_DEBT_WARRANTS",
    "INOXGREEN": "CLOSED_WWIL_ASSETS_PARENT_SHARE_POST_MINORITIES_AND_FINANCING",
    "DATAMATICS": "OPERATING_OWNER_CASH_VERSUS_INVESTMENT_AND_ACQUISITION_PLACEMENTS",
    "ACUTAAS": "INCREMENTAL_ROIC_FROM_FY26_REINVESTMENT_AND_WC_RELEASE",
    "ACE": "REPEATABLE_EQUIPMENT_CASH_WITH_FINANCIAL_INVESTMENTS_NOT_DOUBLE_COUNTED",
    "TRAVELFOOD": "PARENT_CONCESSION_CASH_AFTER_LEASE_RENEWALS_INTEREST_MINORITIES",
    "POKARNA": "SOURCE_COMPLETE_QUARTZ_CAPACITY_CASH_AND_DILUTION",
    "MAYURUNIQ": "LONG_TERM_ASSET_PLACEMENTS_REALIZABILITY_AND_MULTIYEAR_CASH",
    "PIXTRANS": "SYMMETRIC_STANDALONE_VS_CONSOLIDATED_RECURRING_PROFIT",
}


def _git_blob(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data,
        usedforsecurity=False,
    ).hexdigest()


def _money(value: object, *, label: str) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise AlphaContractError(f"P014 missing finite source value: {label}")
    return float(value)


def _close(a: float, b: float, label: str, *, abs_tol: float = 0.00011) -> None:
    if not math.isclose(a, b, rel_tol=0, abs_tol=abs_tol):
        raise AlphaContractError(f"P014 source reconciliation conflict: {label}")


def _source_proof(root: Path, report: dict[str, Any], symbol: str) -> None:
    path = report.get("original_source_path") or report.get("pinned_original_byte_path")
    sha = report.get("original_nse_full_html_sha256") or report.get(
        "pinned_original_byte_sha256"
    )
    if not isinstance(path, str) or not isinstance(sha, str) or len(sha) != 64:
        raise AlphaContractError(f"P014 {symbol} missing archived original filing")
    target = root / path
    if not target.is_file():
        raise AlphaContractError(f"P014 {symbol} archived original missing")
    saved = target.read_bytes()
    raw = gzip.decompress(saved) if target.suffix == ".gz" else saved
    if hashlib.sha256(raw).hexdigest() != sha:
        raise AlphaContractError(f"P014 {symbol} original archive hash differs")


def load_inputs(root: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    packets, receipts = {}, {}
    for key, (relpath, blob, sha_key) in SOURCE_MAP.items():
        raw = (root / relpath).read_bytes()
        if _git_blob(raw) != blob:
            raise AlphaContractError(f"P014 pinned source Git blob changed: {key}")
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise AlphaContractError(f"P014 {key} must be JSON object")
        unsigned = copy.deepcopy(obj)
        stored = unsigned.pop(sha_key, None)
        if stored != digest(unsigned):
            raise AlphaContractError(f"P014 historical source seal mismatch: {key}")
        packets[key] = obj
        receipts[key] = {
            "original_path": relpath,
            "original_git_blob_sha": blob,
            "raw_bytes_sha256": hashlib.sha256(raw).hexdigest(),
        }
    validate_hg009_daily_snapshot(packets["market"])
    if packets["market"]["date_ist"] != "2026-10-15":
        raise AlphaContractError("P014 original market-source date changed")
    for entry in packets["three"]["symbol_records"]:
        _source_proof(root, entry, entry["symbol"])
    _source_proof(root, packets["mayur"], "MAYURUNIQ")
    _source_proof(root, packets["datamatics"], "DATAMATICS")
    return packets, receipts


def _cash_basis(packets: dict[str, dict], symbol: str) -> dict[str, Any] | None:
    industrials = {
        x["symbol"]: x for x in packets["three"]["symbol_records"]
    }
    if symbol in industrials:
        row = industrials[symbol]
        money = row["original_values_in_inr_crore"]
        cfo = _money(money["cfo"], label="CFO")
        ppe = _money(money["ppe_purchase"], label="PPE")
        net_investing = _money(money["net_investing"], label="net investing")
        financing = _money(money["net_financing"], label="net financing")
        change = _money(money["cash_change"], label="cash change")
        _close(cfo - ppe, row["source_CFO_less_PPE_cash_proxy_cr_not_owner_fcf"],
               f"{symbol} CFO/PPE")
        _close(cfo + net_investing, row["cashflow_after_all_investing_cr_not_owner_fcf"],
               f"{symbol} after investing")
        _close(cfo + net_investing + financing, change, f"{symbol} cash change")
        if row["cash_begin_to_end_reconciles_to_CFO_investing_financing"] is not True:
            raise AlphaContractError(f"P014 original {symbol} cash not reconciled")
        return {
            "basis": "FY26_CONSOLIDATED_ORIGINAL_SOURCE_REPLAY",
            "CFO_cr": round(cfo, 4),
            "PPE_cash_spend_cr": round(ppe, 4),
            "CFO_less_PPE_proxy_cr_not_owner_FCF": round(cfo - ppe, 4),
            "net_investing_cash_cr": round(net_investing, 4),
            "CFO_after_all_investing_cr_not_owner_FCF": round(
                cfo + net_investing, 4
            ),
            "net_financing_cash_cr": round(financing, 4),
            "net_reported_cash_change_cr": round(change, 4),
            "working_capital_selected_components_not_total_cr": row[
                "selected_inventory_receivables_payables_cash_movement_cr_not_total_WC"
            ],
            "financial_investments_treated_as_expense": False,
            "financing_cash_is_owner_cash": False,
        }
    if symbol == "MAYURUNIQ":
        m = packets["mayur"]
        cfo, ppe = m["fy26_cfo_cr"], m["fy26_ppe_cash_purchase_cr"]
        _close(cfo - ppe, m["fy26_cfo_less_ppe_cr_not_fcf"], "Mayur cash proxy")
        # Long-term placements have balance-sheet claims and must not be
        # reclassified as permanent consumption merely because cash moved.
        _close(
            m["other_long_term_assets_purchase_cr"]
            - m["other_long_term_assets_proceeds_cr"],
            m["other_long_term_assets_net_cash_placement_cr"],
            "Mayur long-term placement",
        )
        return {
            "basis": "FY26_CONSOLIDATED_ORIGINAL_SOURCE_REPLAY",
            "CFO_cr": cfo,
            "PPE_cash_spend_cr": ppe,
            "CFO_less_PPE_proxy_cr_not_owner_FCF": m["fy26_cfo_less_ppe_cr_not_fcf"],
            "net_asset_placement_cr_not_expense": m[
                "other_long_term_assets_net_cash_placement_cr"
            ],
            "CFO_after_all_investing_cr_not_owner_FCF": m[
                "fy26_cash_after_all_investing_cr"
            ],
            "original_source_filed_investments_and_deposits": m[
                "original_balance_sheet_investments_and_deposits_cr"
            ],
            "restricted_vs_unrestricted_investments_verified": False,
            "multi_year_reversal_verified": False,
        }
    if symbol == "DATAMATICS":
        d = packets["datamatics"]
        cfo, ppe = d["fy26_operating_cash_cr"], d[
            "original_cashflow_rows_in_cr"
        ]["fy26_cash_capex"]
        if ppe < 0:
            ppe = -ppe
        _close(
            cfo - ppe,
            d["fy26_cfo_less_fixed_asset_cash_cr_not_owner_fcf"],
            "Datamatics cash proxy",
        )
        return {
            "basis": "FY26_CONSOLIDATED_ORIGINAL_SOURCE_REPLAY",
            "CFO_cr": cfo,
            "PPE_cash_spend_cr": ppe,
            "CFO_less_PPE_proxy_cr_not_owner_FCF": cfo - ppe,
            "CFO_after_all_investing_cr_not_owner_FCF": d[
                "fy26_cfo_after_all_investing_cr_not_owner_fcf"
            ],
            "net_investment_purchase_cr_not_expense": d[
                "fy26_investment_purchase_net_cr_not_expense"
            ],
            "acquisition_cash_outflow_cr_not_automatically_FCF": d[
                "fy26_acquisition_cash_outflow_cr"
            ],
            "financial_investments_distributable_verified": False,
        }
    if symbol == "PIXTRANS":
        p = packets["pix"]
        current = p["quarter_numbers_recalculated_to_inr_crore"]["Q1FY27_STANDALONE"]
        prior = p["quarter_numbers_recalculated_to_inr_crore"]["Q1FY26_STANDALONE"]
        if not current or not prior:
            raise AlphaContractError("P014 PIX missing symmetric original quarters")
        current_core = current["pbt"] - current["other_income"]
        prior_core = prior["pbt"] - prior["other_income"]
        _close(current_core, p["current_pbt_excluding_all_other_income_cr"],
               "PIX current symmetric income")
        _close(prior_core, p["prior_pbt_excluding_all_other_income_cr"],
               "PIX prior symmetric income")
        if prior_core <= 0:
            raise AlphaContractError("P014 PIX symmetric previous base not positive")
        yoy = 100 * (current_core / prior_core - 1)
        _close(yoy, p["symmetric_pbt_excluding_all_other_income_yoy_pct"],
               "PIX symmetric yoy", abs_tol=0.011)
        if p["asymmetric_comparison_is_normalized_operating_growth"] is not False:
            raise AlphaContractError("P014 PIX misleading asymmetric growth promoted")
        return {
            "basis": "Q1FY27_VS_Q1FY26_STANDALONE_UNAUDITED",
            "current_reported_PBT_cr": current["pbt"],
            "current_FVTPL_in_other_income_cr": current["fvtpl"],
            "current_other_income_cr": current["other_income"],
            "prior_other_income_cr": prior["other_income"],
            "asymmetric_only_current_FVTPL_excluded_growth_pct_not_comparable": p[
                "asymmetric_current_less_fvtpl_vs_prior_reported_pbt_growth_pct"
            ],
            "symmetric_both_periods_PBT_ex_other_income_growth_pct_not_owner_FCF": (
                round(yoy, 2)
            ),
            "consolidated_profit_and_cash_flow_verified": False,
        }
    return None


def build_review(packets: dict[str, dict], receipts: dict[str, dict]) -> dict:
    base = packets["underwriting"]
    if base["company_count"] != 10 or base["fully_underwritten_equity_valuations_count"] != 0:
        raise AlphaContractError("P014 original ten company research scope changed")
    if packets["three"]["archived_full_original_fy26_cashflow_source_count"] != 3:
        raise AlphaContractError("P014 three original audited FY26 documents absent")
    if packets["pix"]["reporting_basis"] != "STANDALONE_UNAUDITED_QUARTER_COMPARISON":
        raise AlphaContractError("P014 PIX standalone compared to wrong basis")
    by_market = {
        (x["symbol"], x["frozen_isin"]): x
        for x in packets["market"]["source_identity_rows"]
    }
    base_names = [x["symbol"] for x in base["cases"]]
    if tuple(base_names) != PREDECLARED or len(by_market) != 300:
        raise AlphaContractError("P014 ten frozen identities or market evidence drift")
    rows = []
    for case in base["cases"]:
        symbol, isin = case["symbol"], case["frozen_isin"]
        quote = by_market.get((symbol, isin))
        if quote is None or quote.get("state") != "ORIGINAL_NSE_EQ_OHLC_OBSERVED_NOT_FILL":
            raise AlphaContractError(f"P014 {symbol} no same-ISIN original Oct15 quote")
        observed = _money(quote["ohlcv"]["close_inr"], label=f"{symbol} EQ close")
        if observed <= 0:
            raise AlphaContractError("P014 invalid original EQ close")
        evidence = _cash_basis(packets, symbol)
        lane = (
            "CASH_FLOW_REPLAY_NEEDS_ATTRIBUTION"
            if evidence and evidence["basis"].startswith("FY26_CONSOLIDATED")
            else "QUARTER_OTHER_INCOME_SYMMETRY_NEEDS_CONSOLIDATION"
            if evidence else "ORIGINAL_OPERATING_CASH_OR_LEGAL_SOURCE_MISSING"
        )
        # These lanes order verification work, not expected share performance.
        rows.append({
            "symbol": symbol,
            "original_isin": isin,
            "research_lane_not_investment_rank": lane,
            "critical_falsification": QUESTION[symbol],
            "source_reported_economics_not_owner_fcf": evidence,
            "original_oct15_official_EQ_close_inr_not_current_quote": observed,
            "price_date": "2026-10-15",
            "old_reference_historical_turnover_cr_not_order_capacity": case[
                "source_prior_20_session_EQ_median_traded_value_inr_crore_not_capacity"
            ],
            "original_underwriting_missing_document_keys": case[
                "missing_verified_source_requirements"
            ],
            "corresponding_owner_cash_3year_scenario_source_complete": False,
            "source_current_parent_diluted_shares_verified": False,
            "source_corporate_actions_and_dividends_cleared": False,
            "independent_execution_spread_market_impact_verified": False,
            "investable_risk_adjusted_value_per_share": None,
            "predicted_1year_or_3year_after_cost_return": None,
            "capital_eligible": False,
        })
    by_lane = {
        lane: sorted(row["symbol"] for row in rows
                     if row["research_lane_not_investment_rank"] == lane)
        for lane in (
            "CASH_FLOW_REPLAY_NEEDS_ATTRIBUTION",
            "QUARTER_OTHER_INCOME_SYMMETRY_NEEDS_CONSOLIDATION",
            "ORIGINAL_OPERATING_CASH_OR_LEGAL_SOURCE_MISSING",
        )
    }
    if [len(x) for x in by_lane.values()] != [5, 1, 4]:
        raise AlphaContractError("P014 source evidence readiness pattern unexpectedly drifted")
    result = {
        "schema_version": 1,
        "review_id": REVIEW_ID,
        "analysis_date": "2026-10-16",
        "first_price_observation_date": "2026-10-15",
        "outcome_data_seen_before_posthoc_review": True,
        "this_is_not_preregistered_first_day_alpha": True,
        "source_receipts": receipts,
        "original_10_research_dossiers_preserved": True,
        "diligence_source_lanes_not_expected_return_rankings": by_lane,
        "cash_flow_and_other_income_diagnostics": rows,
        "case_count": 10,
        "price_source_EQ_coverage_count": 10,
        "verified_owner_cash_source_complete_count": 0,
        "scenario_calibration_complete_count": 0,
        "investment_value_ready_count": 0,
        "shareholder_total_returns_computed": False,
        "all_historical_investing_asset_placements_are_permanent_expense": False,
        "single_adjustment_pix_is_valid_symmetric_growth_claim": False,
        "reinvestment_returns_verified_for_ACE_ACUTAAS_TRAVELFOOD": False,
        "stock_selection_fitted_to_oct15_prices": False,
        "investment_recommendations_created": False,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result


def materialize(root: Path) -> dict:
    packets, receipts = load_inputs(root)
    return build_review(packets, receipts)


def validate_review(review: dict, root: Path) -> None:
    unsigned = copy.deepcopy(review)
    actual = unsigned.pop("report_sha256", None)
    if actual != digest(unsigned):
        raise AlphaContractError("P014 signed review hash mismatch")
    if review != materialize(root):
        raise AlphaContractError("P014 historical source replay differs")
