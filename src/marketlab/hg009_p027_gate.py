"""HG009 P027: reproduce the negative first observation and block unsupported alpha.

Scientific review dated 2026-10-21, conducted AFTER the 2026-10-15
outcome. Does not amend the original research cohorts, fit models or
pretend that H5 on 2026-10-22 is an independent confirmation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest

REVIEW_ID = "HG009-P027-20261021-INDEPENDENT-COHORT-GATE-v1"
SOURCES = {
    "h1": (
        "research/hg009/price-diagnostics/HG009-P006-H1-20261015-v1.json",
        "2cca82f5598504ee280320e2d757d7a75c581d7b",
    ),
    "growth": (
        "research/hg009/hg009-p025-h1-growth-balanced-20261021.json",
        "cbc0c3bbffc746aba5ec4444edeb22b535e39e31",
    ),
    "industry": (
        "research/hg009/hg009-p026-postentry-sector-coverage-v1.json",
        "75bd288b96c30886111d969ab78cea3ecea5fc9f",
    ),
    "underwriting": (
        "research/hg009/hg009-p008-ten-underwriting-evidence-v1.json",
        "6b26dcf1cc00858c7745bf552f6626af389dcfef",
    ),
    "action": (
        "research/hg009/hg009-p007-action-hazard-p1-v1.json",
        "ce03231de08809877531bdb746a1c33b90ef4911",
    ),
    "calendar_amendment": (
        "research/hg009/hg009-p004-a1-nov08-calendar-v1.json",
        "ff2bc35970ed73d219bb4b26a9160a37b4947415",
    ),
    "four_value_cases": (
        "research/l001/l001-p023-value-falsification-frontier-v1.json",
        "dbcf91030ba488ba99d10287f45afead562da6a4",
    ),
}
ARM_NAMES = ("SELECTED", "ONE_LANE", "ZERO_LANE")
SOURCE_INDUSTRY_COVERAGE_GATE = 0.95
SOURCE_INDUSTRY_EACH_ARM_GATE = 0.90


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _money(value: object, *, label: str) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise AlphaContractError(f"HG009 P027 nonfinite original metric: {label}")
    return float(value)


def load_p027_sources(root: Path) -> tuple[dict[str, dict[str, Any]], dict]:
    sources = {}
    receipts = {}
    for name, (path, expected_blob) in SOURCES.items():
        raw = (root / path).read_bytes()
        if _git_blob_sha(raw) != expected_blob:
            raise AlphaContractError(f"P027 original historical packet moved: {name}")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise AlphaContractError("P027 original research artifact not a JSON object")
        sources[name] = data
        receipts[name] = {
            "original_repo_path": path,
            "frozen_git_blob_sha": expected_blob,
            "original_raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
    return sources, receipts


def build_decision_gate(
    original: dict[str, dict[str, Any]],
    original_receipts: dict,
) -> dict:
    h1 = original["h1"]
    growth = original["growth"]
    industry = original["industry"]
    underwriting = original["underwriting"]
    actions = original["action"]
    calendar = original["calendar_amendment"]
    value = original["four_value_cases"]

    if (
        h1.get("evaluation_id") != "HG009-P006-CAUSAL-ORIGINAL-PRICE-DIAGNOSTIC-v1"
        or h1.get("horizon_sessions") != 1
        or h1.get("first_entry_date") != "2026-10-15"
        or h1.get("official_exit_date") != "2026-10-15"
        or h1.get("original_universe_size") != 300
        or h1.get("original_denominator_per_arm") != 100
        or h1.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("P027 wrong H1 prospective source or capital gate")
    if (
        growth.get("original_price_report_sha256") != h1["evaluation_sha256"]
        or growth.get("method_selected_after_h1_price_observed") is not True
        or growth.get("posthoc_one_event_not_prospective_multi_date_alpha") is not True
    ):
        raise AlphaContractError("P027 H1 posthoc source chronology invalid")

    counts = {}
    for arm in ARM_NAMES:
        s = h1["arm_descriptive_statistics"].get(arm)
        g = growth["diagnostics"].get(arm)
        i = industry["arm_observations"].get(arm)
        if (
            not all(isinstance(x, dict) for x in (s, g, i))
            or s["original_fixed_denominator"] != 100
            or g["fixed_population"] != 100
            or i["frozen_members"] != 100
            or s["priced_observation_count"] != g["priced"]
            or g["missing"] != s["missing_or_changed_source_count"]
            or not math.isclose(
                _money(s["mean_price_change_pct_if_observed"], label=f"{arm} H1"),
                _money(g["conditional_observed"]["mean"], label=f"{arm} reanalysis"),
                abs_tol=0.000001, rel_tol=0,
            )
        ):
            raise AlphaContractError(f"P027 incompatible H1 cohort evidence: {arm}")
        counts[arm] = {
            "frozen_company_count": 100,
            "source_priced_h1": s["priced_observation_count"],
            "h1_missing_source": s["missing_or_changed_source_count"],
            "observed_only_H1_mean_unadjusted_price_pct": _money(
                s["mean_price_change_pct_if_observed"], label=f"{arm} H1 mean"
            ),
            "h1_growth_bucket_balanced_mean_pct_POSTHOC": _money(
                g["growth_standardized_conditional_mean_pct"],
                label=f"{arm} posthoc",
            ),
            "later_Oct16_index_subset_industry_matches": i["exact_source_matches"],
            "industry_subset_missing_count": i["not_covered_by_original_index_subset"],
            "sector_source_coverage_ratio": round(
                i["exact_source_matches"] / 100, 6
            ),
            "sector_source_pre_Oct15_observed": False,
        }
    raw_control_gaps = {}
    for name in ("ONE_LANE", "ZERO_LANE"):
        target = f"SELECTED_MINUS_{name}"
        g = growth["gaps"][target]
        observed = (
            counts["SELECTED"]["observed_only_H1_mean_unadjusted_price_pct"]
            - counts[name]["observed_only_H1_mean_unadjusted_price_pct"]
        )
        if (
            not math.isclose(
                observed, g["raw_observed_mean_gap_pp"], abs_tol=0.0000015, rel_tol=0
            )
            or g["causal_or_after_cost_alpha_proven"] is not False
            or g.get("two_sided_p_value") is not None
            or _money(g["growth_standardized_mean_gap_pp"], label=target) >= 0
        ):
            raise AlphaContractError(f"P027 missing or positive-only H1 record: {target}")
        raw_control_gaps[target] = {
            "observed_only_H1_mean_gap_pp": round(observed, 6),
            "POSTHOC_growth_bucket_balanced_gap_pp": g[
                "growth_standardized_mean_gap_pp"
            ],
            "source_prices_are_economic_total_returns": False,
            "causal_or_after_cost_alpha_established": False,
            "posthoc_significance_test_eligible": False,
        }

    exact = sum(row["later_Oct16_index_subset_industry_matches"] for row in counts.values())
    if (
        exact != industry.get("source_exact_match_count")
        or exact != 142
        or industry.get("source_report_session_is_after_original_entry") is not True
        or industry.get("sector_matched_three_arm_causal_inference_available") is not False
        or industry.get("source_95pct_total_coverage_gate") is not False
        or industry.get("source_90pct_each_arm_coverage_gate") is not False
    ):
        raise AlphaContractError("P027 retrospective sector evidence misrepresented")
    if (
        actions.get("original_declared_identity_count") != 300
        or actions.get("exhaustive_action_coverage_certified") is not False
        or actions.get("fully_action_adjusted_investable_equity_returns_count") != 0
        or underwriting.get("company_count") != 10
        or underwriting.get("fully_underwritten_equity_valuations_count") != 0
        or underwriting.get("paper_investment_eligibility_count") != 0
        or value.get("completed_probability_weighted_equity_valuations") != 0
        or value.get("investable_portfolio_candidates_approved") != 0
    ):
        raise AlphaContractError("P027 cannot declare capital-approved results")
    if (
        calendar.get("amended_H20_last_session") != "2026-11-12"
        or calendar.get("h5_existing_original_dates_unchanged") != [
            "2026-10-15", "2026-10-16", "2026-10-19",
            "2026-10-21", "2026-10-22",
        ]
        or calendar.get("H60_still_requires_official_2027_calendar") is not True
        or calendar.get("original_oct15_100_plus_200_company_identity_set_unchanged") is not True
    ):
        raise AlphaContractError("P027 official NSE forward amendment missing")
    total_coverage = exact / 300
    ready = (
        total_coverage >= SOURCE_INDUSTRY_COVERAGE_GATE
        and all(
            counts[arm]["sector_source_coverage_ratio"] >= SOURCE_INDUSTRY_EACH_ARM_GATE
            for arm in ARM_NAMES
        )
    )
    if ready:
        raise AlphaContractError("P027 source is post-entry, not permissible next cohort")
    result: dict[str, Any] = {
        "schema_version": 1,
        "review_id": REVIEW_ID,
        "review_date_ist": "2026-10-21",
        "classification": "POST_ENTRY_FALSIFICATION_AND_NEXT_INDEPENDENT_COHORT_GATE",
        "original_source_git_sha_receipts": original_receipts,
        "source_companies_frozen": 300,
        "H1_original_market_event": "2026-10-15",
        "H1_was_one_trade_date_not_100_independent_trials": True,
        "H1_selected_lags_both_source_controls": all(
            g["observed_only_H1_mean_gap_pp"] < 0 for g in raw_control_gaps.values()
        ),
        "H1_arm_diagnostics": counts,
        "H1_selected_minus_controls": raw_control_gaps,
        "H1_not_proof_of_structurally_negative_future_alpha": True,
        "H1_not_positive_alpha_evidence": True,
        "H1_growth_balancing_chosen_after_observing_H1": True,
        "H5_original_close_session": "2026-10-22",
        "H5_holding_period_contains_already_examined_H1": True,
        "H5_cannot_be_called_new_independent_validation": True,
        "H20_new_original_muhurat_session_2026_11_08_confirmed": True,
        "H20_source_safely_amended_exit": "2026-11-12",
        "H60_official_2027_calendar_missing": True,
        "original_2026_10_16_index_subset_sector_matches": exact,
        "original_2026_10_16_index_subset_coverage_fraction": round(total_coverage, 6),
        "original_index_subset_is_not_entire_2319_nse_universe": True,
        "industry_date_is_after_first_cohort_entry": True,
        "pre_entry_retroactive_sector_source_admissible": False,
        "minimum_next_trial_industry_coverage_total": SOURCE_INDUSTRY_COVERAGE_GATE,
        "minimum_next_trial_industry_coverage_per_arm": SOURCE_INDUSTRY_EACH_ARM_GATE,
        "sector_coverage_complete_for_next_eligible_cohort": False,
        "size_free_float_and_beta_exposures_source_verified": False,
        "lending_insurance_cashflow_industrial_normalization_interchangeable": False,
        "corporate_actions_and_dividends_adjusted": False,
        "issuer_original_ten_three_scenario_attributable_valuations_complete": 0,
        "four_independent_deep_value_cases_approved": 0,
        "result_state": "NO_SUPPORTED_INVESTABLE_ALPHA_NOT_ALPHA_DISPROVEN",
        "live_capital_allowed": False,
        "investment_recommendations_generated": False,
        "next_experiment_protocol": {
            "name": "HG009-NEXT-INDEPENDENT-COHORT-REGISTRATION-GATE",
            "eligible_entered_after_method_and_source_freeze": True,
            "source_sector_size_regime_and_share_count_asof_entry_verified": True,
            "original_separate_financial_vs_industrial_earnings_models": True,
            "minimum_sector_source_coverage_total": SOURCE_INDUSTRY_COVERAGE_GATE,
            "minimum_sector_source_coverage_each_arm": SOURCE_INDUSTRY_EACH_ARM_GATE,
            "independent_new_cohort_selected_without_market_return_labels": True,
            "frozen_controls_sector_size_liquidity_beta_and_quality_balanced": True,
            "balance_required_before_any_new_entry": True,
            "frozen_horizons_trading_sessions": [60, 120, 252],
            "corporate_actions_dividends_and_dilution_economically_reconciled": True,
            "original_nse_close_is_not_executable_market_fill": True,
            "actual_cost_impact_and_position_capacity_benchmarks_required": True,
            "multiple_independent_future_entry_dates_required": True,
            "no_retraining_on_first_cohort_H1_or_H5_results": True,
            "not_activated_until_all_evidence_gates_pass": True,
            "next_experiment_active": False,
        },
    }
    result["report_sha256"] = digest(result)
    return result


def materialize(root: Path) -> dict:
    inputs, receipts = load_p027_sources(root)
    return build_decision_gate(inputs, receipts)


def verify_packet(packet: dict, root: Path) -> None:
    unsigned = copy.deepcopy(packet)
    actual = unsigned.pop("report_sha256", None)
    if actual != digest(unsigned):
        raise AlphaContractError("P027 audit report tampered")
    if materialize(root) != packet:
        raise AlphaContractError("P027 source result no longer reproducible")
