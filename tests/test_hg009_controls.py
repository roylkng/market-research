"""Source-first HG009 control construction is independent of future prices."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_controls import (
    BANDS,
    CONTROL_ID,
    build_hg009_control_manifest,
    load_hg009_inputs,
    verify_hg009_controls,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / (
    "research/hg009/hg009-p001-matched-300-company-controls-v1.json"
)
BAND_QUOTAS = {
    "L1_10CR_PLUS": 51,
    "L2_5_TO_10CR": 12,
    "L3_2_TO_5CR": 17,
    "L4_1_TO_2CR": 7,
    "L5_20L_TO_1CR": 7,
    "L6_BELOW_20L": 4,
    "OBSERVATION_INSUFFICIENT": 2,
}


def _inputs():
    return load_hg009_inputs(ROOT)


def _result() -> dict:
    source, selected = _inputs()
    return build_hg009_control_manifest(source, selected)


def test_300_source_identities_and_liquidity_matched_controls():
    source, selected = _inputs()
    manifest = build_hg009_control_manifest(source, selected)
    verify_hg009_controls(manifest, source=source, selected=selected)
    assert manifest["control_id"] == CONTROL_ID
    assert manifest["method_frozen_date"] == "2026-10-14"
    assert manifest["earliest_future_market_entry_session"] == "2026-10-15"
    assert manifest["source_cohort_sha256"] == selected["cohort_sha256"]
    assert manifest["selected_source_band_quotas"] == BAND_QUOTAS
    assert manifest["selected_company_count"] == 100
    assert manifest["zero_lane_control_company_count"] == 100
    assert manifest["one_lane_control_company_count"] == 100
    assert manifest["total_unique_observation_identities"] == 300
    selected_id = {(row["symbol"], row["isin"]) for row in selected["selected"]}
    all_ids = set(selected_id)
    for kind, number in (("ZERO_LANE", 0), ("ONE_LANE", 1)):
        rows = manifest["controls"][kind]
        counts = Counter(row["source_liquidity_band"] for row in rows)
        assert dict(counts) == BAND_QUOTAS
        assert all(row["control_lane_count"] == number for row in rows)
        assert all(
            len(row["original_hg001_row_sha256"]) == 64 for row in rows
        )
        assert all(row["future_price_labels_opened"] is False for row in rows)
        assert all(row["capital_allowed"] is False for row in rows)
        ids = {(row["symbol"], row["isin"]) for row in rows}
        assert len(ids) == 100
        assert not all_ids & ids
        all_ids |= ids
        for band in BANDS:
            assert manifest["source_eligible_pool_counts_per_band"][kind][
                band
            ] >= BAND_QUOTAS[band]
    assert len(all_ids) == 300


def test_historical_source_pool_availability_pinned_by_band():
    manifest = _result()
    pools = manifest["source_eligible_pool_counts_per_band"]
    assert pools["ZERO_LANE"] == {
        "L1_10CR_PLUS": 99,
        "L2_5_TO_10CR": 32,
        "L3_2_TO_5CR": 29,
        "L4_1_TO_2CR": 19,
        "L5_20L_TO_1CR": 38,
        "L6_BELOW_20L": 65,
        "OBSERVATION_INSUFFICIENT": 12,
    }
    assert pools["ONE_LANE"] == {
        "L1_10CR_PLUS": 160,
        "L2_5_TO_10CR": 45,
        "L3_2_TO_5CR": 74,
        "L4_1_TO_2CR": 40,
        "L5_20L_TO_1CR": 57,
        "L6_BELOW_20L": 91,
        "OBSERVATION_INSUFFICIENT": 5,
    }


def test_deterministic_manifest_and_immutable_source_archive():
    source, selected = _inputs()
    manifest = _result()
    assert json.loads(MANIFEST.read_text(encoding="utf-8")) == manifest
    assert manifest["manifest_sha256"] == digest({
        k: v for k, v in manifest.items() if k != "manifest_sha256"
    })
    verify_hg009_controls(manifest, source=source, selected=selected)
    proc = subprocess.run(
        [
            sys.executable, "scripts/materialize_hg009_controls.py",
            "--repo-root", ".", "--output", str(MANIFEST), "--check",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    result = json.loads(proc.stdout)
    assert result["state"] == "VERIFIED"
    assert result["observation_identities"] == 300
    assert result["manifest_sha256"] == manifest["manifest_sha256"]


def test_no_valuation_or_causal_promotion_from_band_matching():
    manifest = _result()
    assert manifest["matching_is_not_causal_identification"] is True
    assert manifest["hashed_deterministic_control_selection_not_alpha_optimization"]
    assert manifest["not_matched_dimensions"] == [
        "INDUSTRY_OR_SECTOR",
        "COMPANY_SIZE_OR_ENTERPRISE_VALUE",
        "FACTOR_BETAS",
        "SALES_QUALITY_OR_ACCOUNTING_REGIME",
        "ACTUAL_BID_ASK_SPREAD_AND_TICKET_CAPACITY",
    ]
    for key in (
        "baseline_performance_and_returns_opened",
        "future_price_or_excess_return_computed",
        "investment_recommendations_generated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert manifest[key] is False
    assert manifest["stocks_missing_EQ_or_ISIN_at_entry_remain_reported_missing"]
    assert manifest["price_index_benchmark_is_not_total_return"]


def test_attempted_future_outcome_promotion_or_selection_tamper_is_rejected():
    source, selected = _inputs()
    manifest = _result()
    modified = copy.deepcopy(manifest)
    modified["controls"]["ONE_LANE"][0]["symbol"] = "FUTURE_WINNER"
    with pytest.raises(AlphaContractError, match="manifest SHA changed"):
        verify_hg009_controls(modified, source=source, selected=selected)

    modified = copy.deepcopy(manifest)
    modified["controls"]["ONE_LANE"][0]["source_liquidity_band"] = (
        "L1_10CR_PLUS"
    )
    modified["manifest_sha256"] = digest({
        k: v for k, v in modified.items() if k != "manifest_sha256"
    })
    with pytest.raises(AlphaContractError, match="selection not reproducible"):
        verify_hg009_controls(modified, source=source, selected=selected)
    bad_source = copy.deepcopy(source)
    bad_source["rows"][0]["symbol"] = "NOT_AN_ORIGINAL_NSE_SYMBOL"
    with pytest.raises(AlphaContractError, match="original 2319-name source"):
        build_hg009_control_manifest(bad_source, selected)
    bad_selection = copy.deepcopy(selected)
    bad_selection["selected_count"] = 99
    with pytest.raises(AlphaContractError, match="cohort seal SHA"):
        build_hg009_control_manifest(source, bad_selection)
