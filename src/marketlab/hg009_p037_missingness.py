"""HG009 P037: sharp missing-price sensitivity on the *observed* H1 event.

A source-priced-only 99-company mean cannot be silently called the average
return of all 100 original issuers. No imputation or portfolio return is
created. This retrospective falsification is not an alpha test, a signal,
or a source-timing amendment to the October 15 cohort.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest

STUDY_ID = "HG009-P037-20261021-H1-MISSINGNESS-SHARP-BOUNDS-v1"
H1_PATH = Path(
    "research/hg009/price-diagnostics/HG009-P006-H1-20261015-v1.json"
)
H1_SOURCE_GIT_BLOB = "2cca82f5598504ee280320e2d757d7a75c581d7b"
H1_SOURCE_PACKET_SHA = (
    "811fbb1e18481b43ab5b4c6f9bda827b3bb83709c2388b2c7f55038a856ed2b3"
)
ARM_NAMES = ("SELECTED", "ONE_LANE", "ZERO_LANE")
ARBITRARY_STRESS_MAGNITUDE_PP = 20.0


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_original_h1(root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    raw = (root / H1_PATH).read_bytes()
    if _blob(raw) != H1_SOURCE_GIT_BLOB:
        raise AlphaContractError("P037 original NSE H1 Git blob changed")
    packet = json.loads(raw)
    if not isinstance(packet, dict):
        raise AlphaContractError("P037 original H1 document not JSON object")
    original_sha = packet.get("evaluation_sha256")
    unsigned = copy.deepcopy(packet)
    unsigned.pop("evaluation_sha256", None)
    if original_sha != H1_SOURCE_PACKET_SHA or digest(unsigned) != original_sha:
        raise AlphaContractError("P037 original H1 signed report changed")
    receipt = {
        "original_path": str(H1_PATH),
        "original_git_blob_sha": H1_SOURCE_GIT_BLOB,
        "original_raw_file_sha256": hashlib.sha256(raw).hexdigest(),
        "original_signed_evaluation_sha256": original_sha,
    }
    return packet, receipt


def _validated_h1_rows(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if (
        packet.get("horizon_sessions") != 1
        or packet.get("first_entry_date") != "2026-10-15"
        or packet.get("official_exit_date") != "2026-10-15"
        or packet.get("original_universe_size") != 300
        or packet.get("original_denominator_per_arm") != 100
        or packet.get("corporate_action_economic_total_returns_ready") is not False
        or packet.get("actual_fills_recorded") is not False
        or packet.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("P037 input not the original prospective H1 price event")
    rows = packet.get("original_symbol_isin_rows")
    if not isinstance(rows, list) or len(rows) != 300:
        raise AlphaContractError("P037 missing original 300 frozen H1 slots")
    report = packet.get("arm_descriptive_statistics")
    if not isinstance(report, dict) or set(report) != set(ARM_NAMES):
        raise AlphaContractError("P037 original three-arm summary incomplete")
    partitions = {}
    all_identities = set()
    for arm in ARM_NAMES:
        chosen = [row for row in rows if row.get("arm") == arm]
        if len(chosen) != 100:
            raise AlphaContractError("P037 changed original arm count")
        observed = []
        missing = []
        identities = set()
        for row in chosen:
            identity = (row.get("symbol"), row.get("frozen_isin"))
            if identity in identities or identity in all_identities:
                raise AlphaContractError("P037 duplicate H1 issuer or ISIN")
            if not isinstance(identity[0], str) or not isinstance(identity[1], str):
                raise AlphaContractError("P037 original H1 company identity incomplete")
            identities.add(identity)
            all_identities.add(identity)
            fraction = row.get("unadjusted_gross_stock_price_change_fraction")
            if fraction is None:
                if (
                    row.get("state") != "INCOMPLETE_SOURCE_WINDOW_NO_PRICE_CHANGE"
                    or row.get("source_complete_all_intermediate_dates") is not False
                    or not row.get("original_missing_source_receipts")
                ):
                    raise AlphaContractError("P037 missing price silently reclassified")
                missing.append({
                    "symbol": identity[0],
                    "isin": identity[1],
                    "original_missing_source_receipts": row[
                        "original_missing_source_receipts"
                    ],
                })
            else:
                if (
                    type(fraction) not in (int, float)
                    or not math.isfinite(fraction)
                    or row.get("state") != "ORIGINAL_UNADJUSTED_PRICE_CHANGE_ONLY"
                    or row.get("source_complete_all_intermediate_dates") is not True
                ):
                    raise AlphaContractError("P037 priced source row changed")
                observed.append(float(fraction) * 100)
        summary = report[arm]
        if (
            summary.get("original_fixed_denominator") != 100
            or summary.get("priced_observation_count") != len(observed)
            or summary.get("missing_or_changed_source_count") != len(missing)
            or not math.isclose(
                round(math.fsum(observed) / len(observed), 6),
                summary.get("mean_price_change_pct_if_observed"),
                rel_tol=0.0,
                abs_tol=1e-6,
            )
        ):
            raise AlphaContractError("P037 original H1 computed means/counts drifted")
        partitions[arm] = {
            "priced_count": len(observed),
            "missing_count": len(missing),
            "observed_sum_of_percent_returns": math.fsum(observed),
            "observed_mean_percent": summary["mean_price_change_pct_if_observed"],
            "missing_original_issuer_receipts": missing,
        }
    if {arm: partitions[arm]["missing_count"] for arm in ARM_NAMES} != {
        "SELECTED": 1,
        "ONE_LANE": 1,
        "ZERO_LANE": 0,
    }:
        raise AlphaContractError("P037 unexpected H1 source-missing cardinalities")
    if len(all_identities) != 300:
        raise AlphaContractError("P037 original H1 identities not conserved")
    return partitions


def build_hg009_h1_missingness_bounds(
    original_h1: dict[str, Any],
    source_receipt: dict[str, str],
) -> dict[str, Any]:
    arms = _validated_h1_rows(original_h1)
    sums = {
        arm: arms[arm]["observed_sum_of_percent_returns"]
        for arm in ARM_NAMES
    }
    stress = ARBITRARY_STRESS_MAGNITUDE_PP
    # Each original arm contains 100 distinct issuers. Missing values remain
    # unknown; they are varied only for a *counterfactual sensitivity*.
    bounds = {}
    for arm in ARM_NAMES:
        miss = arms[arm]["missing_count"]
        bounds[arm] = {
            "original_fixed_issuer_count": 100,
            "priced_source_count": arms[arm]["priced_count"],
            "missing_source_count": miss,
            "observed_only_mean_percent": arms[arm]["observed_mean_percent"],
            "illustrative_full_cohort_mean_if_missing_at_minus20_percent": round(
                (sums[arm] - stress * miss) / 100, 6
            ),
            "illustrative_full_cohort_mean_if_missing_at_zero_percent": round(
                sums[arm] / 100, 6
            ),
            "illustrative_full_cohort_mean_if_missing_at_plus20_percent": round(
                (sums[arm] + stress * miss) / 100, 6
            ),
            "missing_issuer_identity_and_reason": arms[arm][
                "missing_original_issuer_receipts"
            ],
            "these_are_not_observed_returns_or_exchange_circuit_bands": True,
        }

    # Selected vs one-lane has exactly one unknown return in *each* arm:
    # gap_100 = (sum_selected - sum_one + u_selected - u_one)/100.
    one_threshold = sums["ONE_LANE"] - sums["SELECTED"]
    # The zero-lane group has every source observed:
    # selected > zero iff u_selected > sum_zero - sum_selected.
    zero_threshold = sums["ZERO_LANE"] - sums["SELECTED"]
    gaps = {}
    for name in ("ONE_LANE", "ZERO_LANE"):
        other_missing = arms[name]["missing_count"]
        gap_without_missing = (sums["SELECTED"] - sums[name]) / 100
        min_gap = gap_without_missing - stress * (
            arms["SELECTED"]["missing_count"] + other_missing
        ) / 100
        max_gap = gap_without_missing + stress * (
            arms["SELECTED"]["missing_count"] + other_missing
        ) / 100
        gaps[f"SELECTED_MINUS_{name}"] = {
            "observed_only_mean_gap_pp_not_fixed_100_result": round(
                arms["SELECTED"]["observed_mean_percent"]
                - arms[name]["observed_mean_percent"], 6
            ),
            "illustrative_full_100_gap_with_missing_as_zero_pp": round(
                gap_without_missing, 6
            ),
            "lower_gap_if_each_unknown_between_minus20_plus20_pp": round(
                min_gap, 6
            ),
            "upper_gap_if_each_unknown_between_minus20_plus20_pp": round(
                max_gap, 6
            ),
            "gap_sign_robust_to_hypothetical_20pct_interval": (
                (min_gap > 0 and max_gap > 0)
                or (min_gap < 0 and max_gap < 0)
            ),
            "significance_test_or_investable_alpha_eligible": False,
        }
    report = {
        "schema_version": 1,
        "review_id": STUDY_ID,
        "analysis_date_ist": "2026-10-21",
        "original_predeclared_entry_session": "2026-10-15",
        "source_price_basis": (
            "NSE_EQ_UNADJUSTED_OPEN_TO_CLOSE_ONE_TRADING_DAY_NOT_TOTAL_RETURN"
        ),
        "analysis_developed_after_H1_was_observed": True,
        "study_does_not_amend_original_HG009_cohort_or_first_entry": True,
        "original_input_receipt": source_receipt,
        "original_fixed_company_count_per_arm": 100,
        "distinct_market_entry_event_count": 1,
        "arm_source_missingness_sensitivity": bounds,
        "comparison_bounds": gaps,
        "observed_missingness_break_even": {
            "selected_missing_stock": arms["SELECTED"][
                "missing_original_issuer_receipts"
            ][0]["symbol"],
            "one_lane_missing_stock": arms["ONE_LANE"][
                "missing_original_issuer_receipts"
            ][0]["symbol"],
            "selected_unknown_return_minus_one_lane_unknown_return_exceeds_pp": (
                round(one_threshold, 6)
            ),
            "selected_unknown_return_exceeds_to_overtake_zero_lane_pct": (
                round(zero_threshold, 6)
            ),
            "zero_lane_has_no_missing_H1_quotes": True,
            "these_are_algebraic_reversal_hurdles_not_forecasts": True,
        },
        "arbitrary_missing_stock_stress_interval_pct": {
            "lower": -stress,
            "upper": stress,
            "not_a_guaranteed_price_band_or_probabilistic_confidence_interval": True,
        },
        "H1_result_is_one_common_trading_day_not_300_independent_trials": True,
        "unknown_stock_returns_never_imputed_in_original_report": True,
        "negative_observed_H1_evidence_is_not_repeatable_negative_alpha_proof": True,
        "H5_includes_first_H1_source_and_is_not_independent_replication": True,
        "H5_will_be_measurable_only_after_2026_10_22_close_and_source": True,
        "corporate_action_and_dividend_economic_returns_reconciled": False,
        "sector_size_beta_and_industry_confounders_sufficiently_balanced": False,
        "forward_profit_or_price_targets_calculated": False,
        "investment_recommendations_generated": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report


def materialize_hg009_h1_missingness(root: Path) -> dict[str, Any]:
    data, receipt = load_original_h1(root)
    return build_hg009_h1_missingness_bounds(data, receipt)


def verify_hg009_h1_missingness(
    output: dict[str, Any], *, root: Path
) -> None:
    unsigned = copy.deepcopy(output)
    sha = unsigned.pop("report_sha256", None)
    if sha != digest(unsigned):
        raise AlphaContractError("P037 missingness report SHA changed")
    if output != materialize_hg009_h1_missingness(root):
        raise AlphaContractError("P037 missingness report not original-source reproducible")
