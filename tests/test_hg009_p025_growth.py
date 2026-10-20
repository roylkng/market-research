"""P025 source-first H1 posthoc diagnostics, not tested investment alpha."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p025_growth import (
    BINS,
    _bucket,
    build_report,
    load_sources,
    validate_report,
)

ROOT = Path(__file__).resolve().parents[1]
H1 = ROOT / "research/hg009/hg009-p025-h1-growth-balanced-20261021.json"


def _sources() -> tuple[dict, dict]:
    return load_sources(ROOT, 1)


def test_original_source_matches_frozen_oct05_and_oct15_digests():
    base, h1 = _sources()
    result = build_report(base, h1, horizon=1)
    assert result["original_prior_sha256"] == (
        "09b31afc59b2b2b5cd3278ee4c73a5cff4c12dc835486fd9a0726ad45202b25e"
    )
    assert result["original_price_report_sha256"] == (
        "811fbb1e18481b43ab5b4c6f9bda827b3bb83709c2388b2c7f55038a856ed2b3"
    )
    assert result["exit_date"] == "2026-10-15"
    assert result["method_selected_after_h1_price_observed"] is True
    assert result["posthoc_one_event_not_prospective_multi_date_alpha"] is True
    assert result["live_capital_allowed"] is False
    validate_report(result, baseline=base, market=h1)


def test_300_stock_membership_missing_and_trimmed_mean_preserved():
    base, h1 = _sources()
    r = build_report(base, h1, horizon=1)
    s = r["diagnostics"]
    assert [s[k]["fixed_population"] for k in (
        "SELECTED", "ONE_LANE", "ZERO_LANE"
    )] == [100, 100, 100]
    assert [s[k]["priced"] for k in (
        "SELECTED", "ONE_LANE", "ZERO_LANE"
    )] == [99, 99, 100]
    assert s["SELECTED"]["conditional_observed"]["mean"] == pytest.approx(-1.410336)
    assert s["SELECTED"]["conditional_observed"]["median"] == pytest.approx(-1.462724)
    assert s["SELECTED"]["conditional_observed"]["trimmed10"] == pytest.approx(
        -1.2798, abs=.001
    )
    assert s["SELECTED"]["conditional_observed"]["positive"] == 24
    assert s["ONE_LANE"]["conditional_observed"]["positive"] == 27
    assert s["ZERO_LANE"]["conditional_observed"]["positive"] == 26
    assert r["missing_prices_not_zero_imputed"] is True
    assert r["corporate_actions_dividends_not_reconciled"] is True


def test_growth_strata_weights_and_posthoc_comparison_are_not_alpha():
    base, h1 = _sources()
    r = build_report(base, h1, horizon=1)
    assert tuple(r["selected_source_growth_bucket_weights"]) == BINS
    assert r["selected_source_growth_bucket_weights"] == {
        "NEGATIVE": 0.14,
        "ZERO_TO_15": 0.26,
        "ABOVE_15": 0.57,
        "UNAVAILABLE": 0.03,
    }
    assert r["diagnostics"]["SELECTED"][
        "growth_standardized_conditional_mean_pct"
    ] == pytest.approx(-1.4131, abs=.0001)
    assert r["diagnostics"]["ONE_LANE"][
        "growth_standardized_conditional_mean_pct"
    ] == pytest.approx(-1.1927, abs=.0001)
    assert r["diagnostics"]["ZERO_LANE"][
        "growth_standardized_conditional_mean_pct"
    ] == pytest.approx(-1.2241, abs=.0001)
    assert r["gaps"]["SELECTED_MINUS_ONE_LANE"][
        "growth_standardized_mean_gap_pp"
    ] == pytest.approx(-.2204, abs=.0001)
    assert r["gaps"]["SELECTED_MINUS_ZERO_LANE"][
        "growth_standardized_mean_gap_pp"
    ] == pytest.approx(-.189, abs=.0001)
    assert r["gaps"]["SELECTED_MINUS_ZERO_LANE"][
        "raw_observed_mean_gap_pp"
    ] == pytest.approx(-.334037)
    for comparison in r["gaps"].values():
        assert comparison["two_sided_p_value"] is None
        assert comparison["causal_or_after_cost_alpha_proven"] is False
    assert r["sector_size_beta_profitability_not_balanced"] is True


def test_tampered_original_price_or_forged_date_is_rejected():
    base, h1 = _sources()
    forged = copy.deepcopy(h1)
    forged["original_symbol_isin_rows"][0][
        "unadjusted_gross_stock_price_change_fraction"
    ] = 2.0
    with pytest.raises(AlphaContractError, match="signature"):
        build_report(base, forged, horizon=1)
    forged = copy.deepcopy(h1)
    forged["official_source_evidence"][0]["date_ist"] = "2026-10-16"
    forged.pop("evaluation_sha256")
    forged["evaluation_sha256"] = digest(forged)
    with pytest.raises(AlphaContractError, match="trading-date"):
        build_report(base, forged, horizon=1)
    forged = copy.deepcopy(h1)
    forged["original_symbol_isin_rows"][0]["frozen_isin"] = "INE000000000"
    forged.pop("evaluation_sha256")
    forged["evaluation_sha256"] = digest(forged)
    with pytest.raises(AlphaContractError, match="membership"):
        build_report(base, forged, horizon=1)


def test_zero_imputation_and_growth_bin_manipulation_blocked():
    base, h1 = _sources()
    forged = copy.deepcopy(h1)
    missing = next(x for x in forged["original_symbol_isin_rows"]
                   if x["unadjusted_gross_stock_price_change_fraction"] is None)
    missing["unadjusted_gross_stock_price_change_fraction"] = 0.0
    forged.pop("evaluation_sha256")
    forged["evaluation_sha256"] = digest(forged)
    with pytest.raises(AlphaContractError, match="invalid original"):
        build_report(base, forged, horizon=1)
    corrupted = copy.deepcopy(base)
    corrupted["source_identity_metric_rows"][0][
        "original_earnings_metrics"
    ]["revenue_yoy_pct"] = 999999
    with pytest.raises(AlphaContractError, match="signature"):
        build_report(corrupted, h1, horizon=1)
    assert _bucket(None) == "UNAVAILABLE"
    assert _bucket(-0.1) == "NEGATIVE"
    assert _bucket(0) == "ZERO_TO_15"
    assert _bucket(15) == "ZERO_TO_15"
    assert _bucket(15.001) == "ABOVE_15"


def test_h5_cannot_be_materialized_from_missing_real_future_source():
    source = ROOT / "research/hg009/price-diagnostics/HG009-P006-H5-20261015-v1.json"
    if not source.exists():
        with pytest.raises(FileNotFoundError, match="not yet published"):
            load_sources(ROOT, 5)
    process = subprocess.run(
        [
            sys.executable, "scripts/materialize_hg009_p025_growth.py",
            "--horizon", "5", "--check",
        ], cwd=ROOT, text=True, capture_output=True, check=True,
    )
    response = json.loads(process.stdout)
    assert response["proven_alpha"] is False
    assert response["live_capital_allowed"] is False


def test_signed_report_and_direct_cli_reproduce_without_modifying_market():
    base, h1 = _sources()
    report = build_report(base, h1, horizon=1)
    assert report == json.loads(H1.read_text(encoding="utf-8"))
    done = subprocess.run(
        [sys.executable, "scripts/materialize_hg009_p025_growth.py", "--check"],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    response = json.loads(done.stdout)
    assert response["state"] == "VERIFIED"
    assert response["report_sha256"] == report["report_sha256"]
    assert response["proven_alpha"] is False
