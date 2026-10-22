"""Post-hoc H5 missing-source sensitivity, not alpha or economic return.

The original independently source-replayed HG009-P006 H5 result is immutable.
This study leaves the missing RETAIL and MOREPENLAB returns unknown and
examines their algebraic influence on fixed 100-name arm comparisons.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest

AUDIT_ID = "HG009-P038-20261022-H5-100-SLOT-MISSINGNESS-v1"
ORIGINAL_PATH = Path("research/hg009/price-diagnostics/HG009-P006-H5-20261015-v1.json")
ORIGINAL_GIT_BLOB_SHA = "158fd143a0c13675cfdcd8cc716e576cd515fdab"
ORIGINAL_SIGNED_SHA256 = "7ee99e2b9a9a356b89850ac1acd30c4e7f367da5c306793e5cf874ab0098d0aa"
STRESS_LIMIT = 20.0
ARMS = ("SELECTED", "ONE_LANE", "ZERO_LANE")
ENTRY = "2026-10-15"
EXIT = "2026-10-22"
EXACT_SESSIONS = (
    "2026-10-15", "2026-10-16", "2026-10-19",
    "2026-10-21", "2026-10-22",
)


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_original_h5(root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    path = root / ORIGINAL_PATH
    raw = path.read_bytes()
    if _blob(raw) != ORIGINAL_GIT_BLOB_SHA:
        raise AlphaContractError("P038 original H5 Git blob changed")
    packet = json.loads(raw)
    if not isinstance(packet, dict):
        raise TypeError("original H5 official NSE diagnostic must be an object")
    unsigned = {k: v for k, v in packet.items() if k != "evaluation_sha256"}
    if (
        packet.get("evaluation_sha256") != ORIGINAL_SIGNED_SHA256
        or digest(unsigned) != ORIGINAL_SIGNED_SHA256
    ):
        raise AlphaContractError("P038 original H5 packet SHA changed")
    return packet, {
        "source_path": str(ORIGINAL_PATH),
        "source_git_blob_sha": ORIGINAL_GIT_BLOB_SHA,
        "source_raw_sha256": hashlib.sha256(raw).hexdigest(),
        "original_signed_evaluation_sha256": ORIGINAL_SIGNED_SHA256,
    }


def _validate_prices(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if (
        packet.get("evaluation_id") != "HG009-P006-CAUSAL-ORIGINAL-PRICE-DIAGNOSTIC-v1"
        or packet.get("horizon_sessions") != 5
        or packet.get("first_entry_date") != ENTRY
        or packet.get("official_exit_date") != EXIT
        or packet.get("exact_frozen_holding_sessions") != list(EXACT_SESSIONS)
        or packet.get("original_universe_size") != 300
        or packet.get("original_denominator_per_arm") != 100
        or packet.get("corporate_action_economic_total_returns_ready") is not False
        or packet.get("actual_fills_recorded") is not False
        or packet.get("one_cross_section_demonstrates_replicable_alpha") is not False
        or packet.get("portfolio_eligibility_allowed") is not False
        or packet.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("H5 official original source/outcome research-only boundary changed")
    sources = packet.get("official_source_evidence")
    if (
        not isinstance(sources, list)
        or [x.get("date_ist") for x in sources] != list(EXACT_SESSIONS)
        or any(
            not isinstance(x.get("NSE_cash_udiff_SHA256"), str)
            or len(x["NSE_cash_udiff_SHA256"]) != 64
            or not isinstance(x.get("NSE_Nifty500_index_SHA256"), str)
            or len(x["NSE_Nifty500_index_SHA256"]) != 64
            for x in sources
        )
    ):
        raise AlphaContractError("H5 requires all five exact source-hashed NSE trading sessions")
    rows = packet.get("original_symbol_isin_rows")
    if not isinstance(rows, list) or len(rows) != 300:
        raise AlphaContractError("H5 must retain exactly 300 frozen identities")
    result: dict[str, dict[str, Any]] = {}
    all_keys = set()
    for arm in ARMS:
        members = [x for x in rows if x.get("arm") == arm]
        if len(members) != 100:
            raise AlphaContractError(f"H5 {arm} lost fixed original 100-name denominator")
        observed = []
        missing = []
        for row in members:
            key = (row.get("symbol"), row.get("frozen_isin"))
            if (
                not isinstance(key[0], str) or not key[0]
                or not isinstance(key[1], str) or len(key[1]) != 12
                or key in all_keys
            ):
                raise AlphaContractError("H5 company/ISIN duplicated or invalid")
            all_keys.add(key)
            ratio = row.get("unadjusted_gross_stock_price_change_fraction")
            if ratio is None:
                if (
                    row.get("state") != "INCOMPLETE_SOURCE_WINDOW_NO_PRICE_CHANGE"
                    or row.get("source_complete_all_intermediate_dates") is not False
                    or not isinstance(row.get("original_missing_source_receipts"), list)
                    or not row["original_missing_source_receipts"]
                ):
                    raise AlphaContractError("H5 missing price was silently interpreted")
                missing.append({
                    "symbol": key[0],
                    "isin": key[1],
                    "missing_sources": row["original_missing_source_receipts"],
                })
                continue
            if (
                type(ratio) not in (float, int)
                or not math.isfinite(float(ratio))
                or ratio <= -1
                or row.get("state") != "ORIGINAL_UNADJUSTED_PRICE_CHANGE_ONLY"
                or row.get("source_complete_all_intermediate_dates") is not True
                or row.get("original_missing_source_receipts") != []
            ):
                raise AlphaContractError("H5 observed price ratio not source-valid")
            observed.append(float(ratio))
        stats = packet.get("arm_descriptive_statistics", {}).get(arm)
        if not isinstance(stats, dict):
            raise TypeError("H5 arm summary missing")
        if (
            stats.get("original_fixed_denominator") != 100
            or stats.get("priced_observation_count") != len(observed)
            or stats.get("missing_or_changed_source_count") != len(missing)
        ):
            raise AlphaContractError("H5 observed/missing arm count changed")
        if observed:
            mean = 100 * statistics.fmean(observed)
            median = 100 * statistics.median(observed)
            if not math.isclose(
                mean, float(stats.get("mean_price_change_pct_if_observed")),
                rel_tol=0, abs_tol=0.000002,
            ) or not math.isclose(
                median, float(stats.get("median_price_change_pct_if_observed")),
                rel_tol=0, abs_tol=0.000002,
            ):
                raise AlphaContractError("H5 individual issuer observations disagree with summary")
        else:
            mean = median = None
        result[arm] = {
            "observed_price_fractions": observed,
            "priced_count": len(observed),
            "missing": missing,
            "observed_only_mean_pct": round(mean, 6) if mean is not None else None,
            "observed_only_median_pct": round(median, 6) if median is not None else None,
        }
    if len(all_keys) != 300:
        raise AlphaContractError("H5 original 300 universe lost members")
    return result


def build_hg009_h5_missingness(
    packet: dict[str, Any], *,
    provenance: dict[str, str],
) -> dict[str, Any]:
    data = _validate_prices(packet)
    if (
        [data[arm]["priced_count"] for arm in ARMS] != [99, 99, 100]
        or [[x["symbol"] for x in data[arm]["missing"]] for arm in ARMS]
        != [["RETAIL"], ["MOREPENLAB"], []]
    ):
        raise AlphaContractError("H5 source completeness differs from original actual observations")
    arms = {}
    for arm, record in data.items():
        total_100_pct = sum(record["observed_price_fractions"]) * 100 / 100
        missing_count = len(record["missing"])
        lower = total_100_pct - STRESS_LIMIT * missing_count / 100
        upper = total_100_pct + STRESS_LIMIT * missing_count / 100
        arms[arm] = {
            "original_fixed_identity_denominator": 100,
            "source_priced_company_count": record["priced_count"],
            "source_missing_company_count": missing_count,
            "missing_issuers": record["missing"],
            "observed_only_mean_price_change_pct": record["observed_only_mean_pct"],
            "observed_only_median_price_change_pct": record["observed_only_median_pct"],
            "hypothetical_full_100_mean_with_missing_zero_pct": round(total_100_pct, 6),
            "illustrative_lower_mean_if_each_missing_minus20_pct": round(lower, 6),
            "illustrative_upper_mean_if_each_missing_plus20_pct": round(upper, 6),
            "missing_source_price_never_replaced_with_zero": True,
        }
    sel = arms["SELECTED"]
    gaps = {}
    for comparator in ("ONE_LANE", "ZERO_LANE"):
        other = arms[comparator]
        observed = (
            sel["observed_only_mean_price_change_pct"]
            - other["observed_only_mean_price_change_pct"]
        )
        lower = (
            sel["illustrative_lower_mean_if_each_missing_minus20_pct"]
            - other["illustrative_upper_mean_if_each_missing_plus20_pct"]
        )
        upper = (
            sel["illustrative_upper_mean_if_each_missing_plus20_pct"]
            - other["illustrative_lower_mean_if_each_missing_minus20_pct"]
        )
        gaps[f"SELECTED_MINUS_{comparator}"] = {
            "observed_only_mean_gap_pp_not_full_fixed100": round(observed, 6),
            "illustrative_fixed100_missing_at_zero_gap_pp": round(
                sel["hypothetical_full_100_mean_with_missing_zero_pct"]
                - other["hypothetical_full_100_mean_with_missing_zero_pct"], 6
            ),
            "lower_gap_if_each_unknown_between_minus20_plus20_pp": round(lower, 6),
            "upper_gap_if_each_unknown_between_minus20_plus20_pp": round(upper, 6),
            "negative_gap_robust_within_arbitrary_20pct_stress": upper < 0,
            "causal_or_investable_alpha_eligible": False,
        }

    s_observed_sum = sum(data["SELECTED"]["observed_price_fractions"]) * 100
    o_observed_sum = sum(data["ONE_LANE"]["observed_price_fractions"]) * 100
    z_observed_sum = sum(data["ZERO_LANE"]["observed_price_fractions"]) * 100
    # At fixed N=100, equality of selected/zero requires missing
    # selected percent return = 100*zero mean - sum of 99 priced returns.
    threshold_vs_zero = z_observed_sum - s_observed_sum
    # Equality of selected/one with one unknown each requires:
    # SELECTED_unknown - ONE_LANE_unknown = observed_one_sum - observed_selected_sum.
    differential_vs_one = o_observed_sum - s_observed_sum
    result: dict[str, Any] = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "POST_H5_SOURCE_MISSINGNESS_SENSITIVITY_NOT_ALPHA_OR_TOTAL_RETURN",
        "developed_after_H5_outcomes_observed": True,
        "analysis_as_of_date_ist": "2026-10-22",
        "original_precommitted_first_entry": ENTRY,
        "original_frozen_five_trading_sessions": list(EXACT_SESSIONS),
        "original_h5_price_evidence": provenance,
        "three_arm_original_size_each": 100,
        "sector_size_beta_profitability_and_cost_balance_not_certified": True,
        "missing_price_stress": {
            "lower_hypothetical_stock_return_pct": -STRESS_LIMIT,
            "upper_hypothetical_stock_return_pct": STRESS_LIMIT,
            "not_exchange_price_limits_or_probabilistic_bounds": True,
        },
        "arm_data": arms,
        "comparison_bounds": gaps,
        "missing_source_algebraic_reversal_hurdles": {
            "selected_missing_issuer": "RETAIL",
            "one_lane_missing_issuer": "MOREPENLAB",
            "selected_missing_stock_return_exceeds_to_overtake_zero_arm_pct": round(
                threshold_vs_zero, 6
            ),
            "selected_missing_return_minus_one_lane_missing_return_exceeds_pp": round(
                differential_vs_one, 6
            ),
            "these_are_algebraic_thresholds_not_forecasts_or_actual_returns": True,
        },
        "nifty500_unadjusted_price_only_change_pct": packet["Nifty500_price_only_change_pct"],
        "observed_market_entry_event_count": 1,
        "H1_and_H5_share_the_same_initial_market_entry_event": True,
        "five_day_interval_is_not_five_independent_randomized_trials": True,
        "issuer_dividend_corporate_action_and_share_entitlement_basis_verified": False,
        "market_execution_slippage_transaction_costs_verified": False,
        "original_hg009_cohort_or_price_diagnostic_changed": False,
        "recommendations_or_fair_values_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result


def materialize_hg009_h5_missingness(root: Path) -> dict[str, Any]:
    original, provenance = load_original_h5(root)
    return build_hg009_h5_missingness(original, provenance=provenance)


def verify_hg009_h5_missingness(
    candidate: dict[str, Any], *, repo_root: Path
) -> None:
    unsigned = {k: v for k, v in candidate.items() if k != "report_sha256"}
    if candidate.get("report_sha256") != digest(unsigned):
        raise AlphaContractError("H5 P038 report SHA changed")
    if candidate != materialize_hg009_h5_missingness(repo_root):
        raise AlphaContractError("H5 P038 report differs from the original signed NSE result")
