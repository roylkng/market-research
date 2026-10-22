"""H5 missing price sharp bounds are retrospective and not investment alpha."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p038_h5_missingness import (
    ORIGINAL_GIT_BLOB_SHA,
    ORIGINAL_SIGNED_SHA256,
    _validate_prices,
    build_hg009_h5_missingness,
    load_original_h5,
    materialize_hg009_h5_missingness,
    verify_hg009_h5_missingness,
)

ROOT = Path(__file__).resolve().parents[1]


def test_source_bound_h5_original_horizon_and_exact_300_slots() -> None:
    source, receipt = load_original_h5(ROOT)
    assert receipt["source_git_blob_sha"] == ORIGINAL_GIT_BLOB_SHA
    assert receipt["original_signed_evaluation_sha256"] == ORIGINAL_SIGNED_SHA256
    observations = _validate_prices(source)
    assert [observations[x]["priced_count"] for x in (
        "SELECTED", "ONE_LANE", "ZERO_LANE",
    )] == [99, 99, 100]
    assert [[m["symbol"] for m in observations[x]["missing"]] for x in (
        "SELECTED", "ONE_LANE", "ZERO_LANE",
    )] == [["RETAIL"], ["MOREPENLAB"], []]
    assert source["official_exit_date"] == "2026-10-22"
    assert len(source["official_source_evidence"]) == 5
    assert source["official_source_evidence"][3]["date_ist"] == "2026-10-21"
    assert source["original_universe_size"] == 300


def test_selected_versus_controls_h5_stress_and_reversal_thresholds() -> None:
    data = materialize_hg009_h5_missingness(ROOT)
    s = data["arm_data"]["SELECTED"]
    one = data["arm_data"]["ONE_LANE"]
    zero = data["arm_data"]["ZERO_LANE"]
    assert s["observed_only_mean_price_change_pct"] == pytest.approx(-6.286652)
    assert one["observed_only_mean_price_change_pct"] == pytest.approx(-6.083574)
    assert zero["observed_only_mean_price_change_pct"] == pytest.approx(-5.421358)
    bounds = data["comparison_bounds"]
    assert bounds["SELECTED_MINUS_ONE_LANE"][
        "observed_only_mean_gap_pp_not_full_fixed100"
    ] == pytest.approx(-0.203078)
    assert bounds["SELECTED_MINUS_ZERO_LANE"][
        "observed_only_mean_gap_pp_not_full_fixed100"
    ] == pytest.approx(-0.865294)
    assert bounds["SELECTED_MINUS_ONE_LANE"][
        "lower_gap_if_each_unknown_between_minus20_plus20_pp"
    ] == pytest.approx(-0.601048, abs=1e-6)
    assert bounds["SELECTED_MINUS_ONE_LANE"][
        "upper_gap_if_each_unknown_between_minus20_plus20_pp"
    ] == pytest.approx(0.198952, abs=1e-6)
    assert bounds["SELECTED_MINUS_ONE_LANE"][
        "negative_gap_robust_within_arbitrary_20pct_stress"
    ] is False
    assert bounds["SELECTED_MINUS_ZERO_LANE"][
        "upper_gap_if_each_unknown_between_minus20_plus20_pp"
    ] == pytest.approx(-0.602428, abs=1e-6)
    assert bounds["SELECTED_MINUS_ZERO_LANE"][
        "negative_gap_robust_within_arbitrary_20pct_stress"
    ] is True
    threshold = data["missing_source_algebraic_reversal_hurdles"]
    assert threshold[
        "selected_missing_stock_return_exceeds_to_overtake_zero_arm_pct"
    ] == pytest.approx(80.242815, abs=1e-6)
    assert threshold[
        "selected_missing_return_minus_one_lane_missing_return_exceeds_pp"
    ] == pytest.approx(20.104777, abs=1e-6)
    assert data["H1_and_H5_share_the_same_initial_market_entry_event"] is True
    assert data["sector_size_beta_profitability_and_cost_balance_not_certified"] is True
    assert data["observed_market_entry_event_count"] == 1
    assert data["live_capital_allowed"] is False


def test_no_missing_return_imputation_or_distorted_holding_calendar() -> None:
    report, receipt = load_original_h5(ROOT)
    mutated = copy.deepcopy(report)
    missing = next(
        row for row in mutated["original_symbol_isin_rows"]
        if row["symbol"] == "RETAIL" and row["arm"] == "SELECTED"
    )
    missing["unadjusted_gross_stock_price_change_fraction"] = 0.0
    with pytest.raises(AlphaContractError, match="observed price ratio"):
        build_hg009_h5_missingness(mutated, provenance=receipt)
    mutated = copy.deepcopy(report)
    mutated["exact_frozen_holding_sessions"][3] = "2026-10-20"
    with pytest.raises(AlphaContractError, match="original source/outcome"):
        build_hg009_h5_missingness(mutated, provenance=receipt)


def test_original_price_summary_and_ordered_sources_immutable() -> None:
    packet, receipt = load_original_h5(ROOT)
    bogus = copy.deepcopy(packet)
    record = next(
        row for row in bogus["original_symbol_isin_rows"]
        if row["arm"] == "SELECTED" and row["unadjusted_gross_stock_price_change_fraction"] is not None
    )
    record["unadjusted_gross_stock_price_change_fraction"] = 50.0
    with pytest.raises(AlphaContractError, match="individual issuer observations"):
        build_hg009_h5_missingness(bogus, provenance=receipt)
    bogus = copy.deepcopy(packet)
    bogus["official_source_evidence"] = bogus["official_source_evidence"][:4]
    with pytest.raises(AlphaContractError, match="five exact"):
        build_hg009_h5_missingness(bogus, provenance=receipt)


def test_source_audit_digest_no_return_or_alpha_promotion() -> None:
    packet = materialize_hg009_h5_missingness(ROOT)
    unsigned = {k: v for k, v in packet.items() if k != "report_sha256"}
    assert digest(unsigned) == packet["report_sha256"]
    verify_hg009_h5_missingness(packet, repo_root=ROOT)
    assert packet["developed_after_H5_outcomes_observed"] is True
    assert packet["issuer_dividend_corporate_action_and_share_entitlement_basis_verified"] is False
    assert packet["market_execution_slippage_transaction_costs_verified"] is False
    assert packet["recommendations_or_fair_values_calculated"] is False
    assert packet["portfolio_eligibility_allowed"] is False
    assert packet["live_capital_allowed"] is False
    tampered = copy.deepcopy(packet)
    tampered["comparison_bounds"]["SELECTED_MINUS_ZERO_LANE"][
        "upper_gap_if_each_unknown_between_minus20_plus20_pp"
    ] = 10.0
    with pytest.raises(AlphaContractError, match="report SHA changed"):
        verify_hg009_h5_missingness(tampered, repo_root=ROOT)


def test_materializer_cli_idempotence_and_append_only(tmp_path: Path) -> None:
    target = tmp_path / "report.json"
    cmd = [
        sys.executable, "scripts/materialize_hg009_p038.py",
        "--out", str(target),
    ]
    initial = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=ROOT)
    assert json.loads(initial.stdout)["selected_observed"] == 99
    assert json.loads(target.read_text(encoding="utf-8")) == materialize_hg009_h5_missingness(ROOT)
    checked = subprocess.run(
        cmd + ["--check"], check=True, capture_output=True, text=True, cwd=ROOT
    )
    assert json.loads(checked.stdout)["state"] == "VERIFIED"
    target.write_text(target.read_text(encoding="utf-8") + "extra")
    bad = subprocess.run(
        cmd + ["--check"], check=False, capture_output=True, text=True, cwd=ROOT
    )
    assert bad.returncode != 0
    assert "does not match" in bad.stderr
