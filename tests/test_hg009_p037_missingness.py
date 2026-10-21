"""P037: one-day missing-source sensitivity is not an alpha result."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p037_missingness import (
    _validated_h1_rows,
    build_hg009_h1_missingness_bounds,
    load_original_h1,
    materialize_hg009_h1_missingness,
    verify_hg009_h1_missingness,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/hg009/hg009-p037-h1-missingness-bounds-v1.json"


def test_genuinely_source_missing_one_company_in_each_first_two_arms():
    original, receipt = load_original_h1(ROOT)
    counts = _validated_h1_rows(original)
    assert [counts[arm]["priced_count"] for arm in (
        "SELECTED", "ONE_LANE", "ZERO_LANE"
    )] == [99, 99, 100]
    assert [counts[arm]["missing_count"] for arm in (
        "SELECTED", "ONE_LANE", "ZERO_LANE"
    )] == [1, 1, 0]
    assert counts["SELECTED"]["missing_original_issuer_receipts"][0][
        "symbol"
    ] == "RETAIL"
    assert counts["ONE_LANE"]["missing_original_issuer_receipts"][0][
        "symbol"
    ] == "MOREPENLAB"
    assert receipt["original_git_blob_sha"].startswith("2cca82f55985")
    result = build_hg009_h1_missingness_bounds(original, receipt)
    assert result["distinct_market_entry_event_count"] == 1
    assert result["unknown_stock_returns_never_imputed_in_original_report"]


def test_observed_h1_shortfall_vs_both_control_arms_and_reversal_math():
    report = materialize_hg009_h1_missingness(ROOT)
    gaps = report["comparison_bounds"]
    one = gaps["SELECTED_MINUS_ONE_LANE"]
    zero = gaps["SELECTED_MINUS_ZERO_LANE"]
    assert one["observed_only_mean_gap_pp_not_fixed_100_result"] == pytest.approx(
        -0.141339, abs=1e-6
    )
    assert zero["observed_only_mean_gap_pp_not_fixed_100_result"] == pytest.approx(
        -0.334037, abs=1e-6
    )
    reversed_if = report["observed_missingness_break_even"]
    assert reversed_if[
        "selected_unknown_return_minus_one_lane_unknown_return_exceeds_pp"
    ] == pytest.approx(13.992561, abs=0.002)
    assert reversed_if[
        "selected_unknown_return_exceeds_to_overtake_zero_lane_pct"
    ] == pytest.approx(31.99336, abs=0.002)
    assert one["gap_sign_robust_to_hypothetical_20pct_interval"] is False
    assert zero["gap_sign_robust_to_hypothetical_20pct_interval"] is True
    assert zero["upper_gap_if_each_unknown_between_minus20_plus20_pp"] < 0
    assert one["upper_gap_if_each_unknown_between_minus20_plus20_pp"] > 0
    assert one["lower_gap_if_each_unknown_between_minus20_plus20_pp"] < 0


def test_counterfactual_missing_hypotheses_not_issuer_observations():
    report = materialize_hg009_h1_missingness(ROOT)
    bounds = report["arm_source_missingness_sensitivity"]
    assert bounds["SELECTED"][
        "illustrative_full_cohort_mean_if_missing_at_minus20_percent"
    ] < bounds["SELECTED"][
        "illustrative_full_cohort_mean_if_missing_at_plus20_percent"
    ]
    zero = bounds["ZERO_LANE"]
    assert zero["missing_source_count"] == 0
    assert zero["illustrative_full_cohort_mean_if_missing_at_minus20_percent"] == (
        zero["illustrative_full_cohort_mean_if_missing_at_plus20_percent"]
    )
    assert all(
        item["these_are_not_observed_returns_or_exchange_circuit_bands"]
        for item in bounds.values()
    )
    assert report["arbitrary_missing_stock_stress_interval_pct"] == {
        "lower": -20,
        "upper": 20,
        "not_a_guaranteed_price_band_or_probabilistic_confidence_interval": True,
    }
    assert report["H1_result_is_one_common_trading_day_not_300_independent_trials"]
    assert report["H5_includes_first_H1_source_and_is_not_independent_replication"]
    assert report["negative_observed_H1_evidence_is_not_repeatable_negative_alpha_proof"]
    assert report["corporate_action_and_dividend_economic_returns_reconciled"] is False
    assert report["live_capital_allowed"] is False


def test_source_price_tampering_and_missing_price_imputation_rejected():
    original, receipt = load_original_h1(ROOT)
    changed = copy.deepcopy(original)
    idx = next(
        i for i, row in enumerate(changed["original_symbol_isin_rows"])
        if row["symbol"] == "RETAIL"
    )
    changed["original_symbol_isin_rows"][idx][
        "unadjusted_gross_stock_price_change_fraction"
    ] = 0.2
    with pytest.raises(AlphaContractError, match="priced source row changed"):
        build_hg009_h1_missingness_bounds(changed, receipt)
    changed = copy.deepcopy(original)
    changed["original_symbol_isin_rows"][idx]["original_missing_source_receipts"] = []
    with pytest.raises(AlphaContractError, match="missing price silently"):
        build_hg009_h1_missingness_bounds(changed, receipt)
    tampered = materialize_hg009_h1_missingness(ROOT)
    tampered["comparison_bounds"]["SELECTED_MINUS_ZERO_LANE"][
        "upper_gap_if_each_unknown_between_minus20_plus20_pp"
    ] = 5
    with pytest.raises(AlphaContractError, match="report SHA changed"):
        verify_hg009_h1_missingness(tampered, root=ROOT)


def test_materializer_matches_immutable_report_and_is_read_only_in_check():
    artifact = materialize_hg009_h1_missingness(ROOT)
    assert artifact["report_sha256"] == digest({
        key: val for key, val in artifact.items() if key != "report_sha256"
    })
    assert artifact == json.loads(OUTPUT.read_text(encoding="utf-8"))
    run = subprocess.run(
        [sys.executable, "scripts/materialize_hg009_p037.py", "--check"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    result = json.loads(run.stdout)
    assert result["state"] == "VERIFIED"
    assert result["sha256"] == artifact["report_sha256"]
    assert result["live_capital_allowed"] is False
