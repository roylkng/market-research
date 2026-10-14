"""HG009 P005: source-only diagnostic differences, never future alpha."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_controls import load_hg009_inputs
from marketlab.hg009_p005_baseline import (
    ARMS,
    METRICS,
    SOURCE_CONTROL,
    build_hg009_source_baseline,
    validate_hg009_source_baseline,
)

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "research/hg009/hg009-p005-source-baseline-300-v1.json"


def _data() -> tuple[dict, dict, dict]:
    source, selected = load_hg009_inputs(ROOT)
    controls = json.loads((ROOT / SOURCE_CONTROL).read_text(encoding="utf-8"))
    return source, selected, controls


def _build() -> dict:
    source, selected, controls = _data()
    return build_hg009_source_baseline(
        source=source, selected=selected, controls=controls
    )


def test_300_locked_original_source_identities_and_no_outcomes():
    report = _build()
    assert report["unique_frozen_identity_count"] == 300
    assert set(report["arms"]) == set(ARMS)
    assert len(report["source_identity_metric_rows"]) == 300
    assert len({
        (r["symbol"], r["isin"]) for r in report["source_identity_metric_rows"]
    }) == 300
    for name in ARMS:
        arm = report["arms"][name]
        assert arm["original_source_count"] == 100
        assert sum(arm["liquidity_band_counts"].values()) == 100
        assert sum(arm["opportunity_lane_count_distribution"].values()) == 100
        assert set(arm["earnings_metrics"]) == set(METRICS)
        for metric in arm["earnings_metrics"].values():
            assert metric["observed_count"] + metric["missing_count"] == 100
    assert (
        report["arms"]["SELECTED"]["liquidity_band_counts"]
        == report["arms"]["ONE_LANE"]["liquidity_band_counts"]
        == report["arms"]["ZERO_LANE"]["liquidity_band_counts"]
    )
    for row in report["source_identity_metric_rows"]:
        assert row["original_promotion_or_index_membership"] is False
        assert row["price_return_opened"] is False
        assert row["trading_capacity_verified"] is False
        assert len(row["original_hg001_row_sha256"]) == 64
    for field in (
        "industry_matching_complete",
        "financial_vs_industrial_comparable_normalization_complete",
        "size_enterprise_value_matching_complete",
        "future_market_returns_observed",
        "causal_alpha_demonstrated",
        "investment_recommendations_generated",
        "live_capital_allowed",
    ):
        assert report[field] is False
    assert report["liquidity_band_only_matching"] is True
    assert report["source_diagnostics_are_not_return_predictors"] is True


def test_original_opportunity_lanes_not_retrospectively_reclassified():
    report = _build()
    assert report["arms"]["SELECTED"][
        "opportunity_lane_count_distribution"
    ] == {"2": 72, "3": 28}
    assert report["arms"]["ONE_LANE"][
        "opportunity_lane_count_distribution"
    ] == {"1": 100}
    assert report["arms"]["ZERO_LANE"][
        "opportunity_lane_count_distribution"
    ] == {"0": 100}
    for key in METRICS:
        values = report["arms"]["SELECTED"]["earnings_metrics"][key]
        assert values["observed_count"] >= 0
        assert values["missing_count"] >= 0
        if values["median_if_observed"] is not None:
            assert values["minimum_if_observed"] <= values[
                "median_if_observed"
            ] <= values["maximum_if_observed"]


def test_original_byte_and_member_tampering_is_detected():
    source, selected, controls = _data()
    clean = build_hg009_source_baseline(
        source=source, selected=selected, controls=controls
    )
    altered = copy.deepcopy(clean)
    altered["arms"]["SELECTED"]["earnings_metrics"]["revenue_yoy_pct"][
        "median_if_observed"
    ] = 10_000
    with pytest.raises(AlphaContractError, match="tampered"):
        validate_hg009_source_baseline(
            altered, source=source, selected=selected, controls=controls
        )
    altered["packet_sha256"] = digest({
        k: v for k, v in altered.items() if k != "packet_sha256"
    })
    with pytest.raises(AlphaContractError, match="unreproducible"):
        validate_hg009_source_baseline(
            altered, source=source, selected=selected, controls=controls
        )
    changed = copy.deepcopy(controls)
    changed["controls"]["ONE_LANE"][0]["symbol"] = "AFTER_THE_FACT_WINNER"
    with pytest.raises(AlphaContractError, match="manifest SHA changed"):
        build_hg009_source_baseline(
            source=source, selected=selected, controls=changed
        )


def test_report_exact_original_and_standalone_script():
    report = _build()
    assert json.loads(PACKET.read_text(encoding="utf-8")) == report
    p = subprocess.run(
        [
            sys.executable, "scripts/materialize_hg009_p005.py",
            "--repo-root", ".", "--output", str(PACKET), "--check",
        ],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    info = json.loads(p.stdout)
    assert info["state"] == "VERIFIED"
    assert info["selected_count"] == 100
    assert info["one_lane_count"] == 100
    assert info["zero_lane_count"] == 100
    assert info["packet_sha256"] == report["packet_sha256"]
