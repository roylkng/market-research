"""100 company full-market cohort is a frozen coverage population, not winners."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg009_100 import (
    COHORT_ID,
    DOUBLE_MIN_MEDIAN_VALUE_INR,
    FROZEN_SOURCE_SHA,
    PAIRS,
    build_hg009_100,
    load_hg001_router,
    validate_hg009_100,
)

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "research/hg009/original-hg001-d001-router-20261005.json.gz"
COHORT = ROOT / "research/hg009/hg009-d001-100-experimental-companies-v1.json"


def _build():
    source = load_hg001_router(ORIGINAL)
    return source, build_hg009_100(source)


def test_frozen_router_is_original_two_thousand_three_hundred_nineteen() -> None:
    source = load_hg001_router(ORIGINAL)
    assert source["identity_count"] == 2319
    assert source["router_sha256"] == FROZEN_SOURCE_SHA
    assert source["lane_count_distribution"] == {
        "0": 896, "1": 949, "2": 395, "3": 79
    }
    assert source["return_outcomes_opened"] is False
    assert source["model_fitted"] is False
    assert source["live_capital_allowed"] is False


def test_exact_100_with_28_original_triples_and_stratified_72_doubles() -> None:
    source, packet = _build()
    validate_hg009_100(packet, source=source)
    assert packet["cohort_id"] == COHORT_ID
    assert packet["selected_count"] == 100
    assert packet["selected_3lane_count"] == 28
    assert packet["selected_2lane_count"] == 72
    assert set(packet["source_double_eligible_counts_by_pair"]) == set(PAIRS)
    assert packet["source_double_eligible_counts_by_pair"] == {
        "ASSET_OR_CAPACITY_ANOMALY+CURRENT_SPECIAL_SITUATION": 26,
        "EARNINGS_INFLECTION+ASSET_OR_CAPACITY_ANOMALY": 55,
        "EARNINGS_INFLECTION+CURRENT_SPECIAL_SITUATION": 49,
    }
    categories = Counter(row["research_class"] for row in packet["selected"])
    assert categories["ORIGINAL_THREE_LANES"] == 28
    for pair in PAIRS:
        assert categories[pair] == 24
    assert len(set(packet["selected_symbols_sorted"])) == 100
    assert packet["selected_symbols_sorted"] == sorted(packet["selected_symbols_sorted"])
    assert all(row["in_existing_u001"] is False for row in packet["selected"])
    assert all(row["governance_flags"] == [] for row in packet["selected"])
    assert all(row["asset_cautions"] == [] for row in packet["selected"])
    assert all(row["investable_decision"] is False for row in packet["selected"])
    for row in packet["selected"]:
        if row["lane_count"] == 2:
            assert (
                row["median_daily_turnover_inr_source_not_capacity"]
                >= DOUBLE_MIN_MEDIAN_VALUE_INR
            )
            assert len(row["deterministic_sample_hash"]) == 64
        else:
            assert row["lane_count"] == 3
            assert row["deterministic_sample_hash"] is None


def test_selected_preserves_original_hg002_cohort_exactly() -> None:
    source, cohort = _build()
    original = {
        row["symbol"] for row in source["rows"]
        if row["active_opportunity_lane_count"] == 3
        and not row["in_existing_u001"]
        and row["governance_caution_flags"] == []
        and row["asset_caution_flags"] == []
        and row["governance_caution_count"] == 0
    }
    assert len(original) == 28
    selected = {
        row["symbol"] for row in cohort["selected"]
        if row["research_class"] == "ORIGINAL_THREE_LANES"
    }
    assert original == selected


def test_historical_market_liquidity_not_conflated_with_trades_or_alpha() -> None:
    source, cohort = _build()
    for field in (
        "source_selection_uses_future_returns",
        "selection_method_optimized_on_historical_returns",
        "selection_method_optimized_for_expected_alpha",
        "price_or_market_cap_used_for_selection",
        "liquidity_is_executable_order_capacity",
        "scientifically_confirmed_return_alpha",
        "expected_return_or_price_target_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert cohort[field] is False
    assert cohort["original_HG002_28_members_preserved"] is True
    assert cohort["original_router_sha256"] == FROZEN_SOURCE_SHA
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()
    assert source["return_outcomes_opened"] is False


def test_router_and_cohort_edits_fail_closed() -> None:
    source, packet = _build()
    corrupted = copy.deepcopy(source)
    corrupted["rows"][0]["symbol"] = "ALTERED"
    with pytest.raises(AlphaContractError, match="original 2319-name source"):
        build_hg009_100(corrupted)
    altered = copy.deepcopy(packet)
    altered["selected"][0]["symbol"] = "NOT_AS_SELECTED"
    with pytest.raises(AlphaContractError, match="cohort seal SHA mismatch"):
        validate_hg009_100(altered, source=source)
    altered = copy.deepcopy(packet)
    altered.pop("cohort_sha256")
    from marketlab.alpha import digest

    altered["selected"][0]["research_class"] = "FAKE_FUTURE_WINNER"
    altered["cohort_sha256"] = digest(altered)
    with pytest.raises(AlphaContractError, match="not reproducible"):
        validate_hg009_100(altered, source=source)


def test_100_cohort_can_be_regenerated_byte_for_byte_from_archived_source() -> None:
    _source, expected = _build()
    assert expected == json.loads(COHORT.read_text(encoding="utf-8"))
    run = subprocess.run(
        [
            sys.executable, "scripts/materialize_hg009_100.py",
            "--source", str(ORIGINAL),
            "--archived-original", str(ORIGINAL),
            "--output", str(COHORT),
            "--check",
        ],
        capture_output=True, text=True, check=True,
    )
    summary = json.loads(run.stdout)
    assert summary["selected"] == 100
    assert summary["cohort_sha256"] == expected["cohort_sha256"]
    assert summary["state"] == "VERIFIED"
    assert summary["live_capital_allowed"] is False
