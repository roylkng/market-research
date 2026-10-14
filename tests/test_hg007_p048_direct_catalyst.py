"""Adversarial controls for seven historical source-catalyst research cases."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.hg007_p048_direct_catalyst import (
    AUDIT_ID,
    LANES,
    SOURCE_FILES,
    build_direct_catalyst_triage,
    load_frozen_sources,
    materialize_direct_catalyst_triage,
    validate_direct_catalyst_triage,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "research/hg007/hg007-p048-direct-catalyst-triage-v1.json"


def _inputs():
    sources, receipts = load_frozen_sources(ROOT)
    return sources, receipts


def _build_from(sources, receipts):
    return build_direct_catalyst_triage(
        sources["P043_20_SESSION_LIQUIDITY"],
        sources["P046_LATEST_CATALYST_STAGE"],
        sources["P047_OFFICIAL_OCT13_MARKET"],
        source_receipts=receipts,
    )


def test_exact_seven_active_cases_are_reviewed_without_altering_28_universe():
    result = materialize_direct_catalyst_triage(ROOT)
    assert result["audit_id"] == AUDIT_ID
    assert result["original_frozen_cohort_count"] == 28
    assert result["active_direct_catalyst_count"] == 7
    assert [case["symbol"] for case in result["cases"]] == [
        "ANANTRAJ", "AXITA", "DATAMATICS", "INOXGREEN",
        "SAMBHV", "SANDESH", "SUVIDHAA",
    ]
    assert result["review_lanes"][LANES[0]] == [
        "ANANTRAJ", "SAMBHV", "INOXGREEN"
    ]
    assert result["review_lanes"][LANES[1]] == ["DATAMATICS"]
    assert result["review_lanes"][LANES[2]] == [
        "AXITA", "SANDESH", "SUVIDHAA"
    ]
    assert result["review_lane_counts"] == {
        LANES[0]: 3, LANES[1]: 1, LANES[2]: 3,
    }
    validate_direct_catalyst_triage(result)


def test_original_official_prices_liquidity_and_time_basis_reconciled():
    result = materialize_direct_catalyst_triage(ROOT)
    cases = {row["symbol"]: row for row in result["cases"]}
    assert result["latest_official_price_session_ist"] == "2026-10-13"
    assert cases["ANANTRAJ"]["official_equity_close_inr_not_current"] == 562.65
    assert cases["INOXGREEN"]["official_equity_close_inr_not_current"] == 123.2
    assert cases["SAMBHV"]["official_equity_close_inr_not_current"] == 164.06
    assert cases["DATAMATICS"]["official_equity_close_inr_not_current"] == 777.9
    assert cases["ANANTRAJ"][
        "original_prior20_EQ_median_turnover_inr_crore"
    ] == pytest.approx(88.72696000750001)
    assert cases["SAMBHV"][
        "original_prior20_EQ_median_turnover_inr_crore"
    ] == pytest.approx(47.8594882545)
    assert cases["INOXGREEN"][
        "original_prior20_EQ_median_turnover_inr_crore"
    ] == pytest.approx(26.6312475355)
    assert cases["DATAMATICS"][
        "original_prior20_EQ_median_turnover_inr_crore"
    ] == pytest.approx(5.0118065425)
    assert result["turnover_below_one_crore_symbols"] == [
        "AXITA", "SANDESH", "SUVIDHAA",
    ]
    assert result["very_thin_prior20_turnover_below_0_1_crore_symbols"] == [
        "SANDESH", "SUVIDHAA",
    ]
    assert result["latest_oct13_price_is_current_oct14_quote"] is False


def test_no_hidden_gem_buy_recommendation_or_implied_return():
    result = materialize_direct_catalyst_triage(ROOT)
    assert result["eligible_for_investment_count"] == 0
    assert result["individual_probability_estimate_count"] == 0
    assert result["company_fair_value_estimate_count"] == 0
    assert result["future_price_or_market_relative_return_calculated"] is False
    assert result["investment_recommendations_generated"] is False
    assert result["live_capital_allowed"] is False
    assert result["portfolio_eligibility_allowed"] is False
    for row in result["cases"]:
        assert row["capital_deployment_eligible"] is False
        assert row["current_fully_diluted_shares_verified"] is False
        assert row["expected_return"] is None
        assert row["company_specific_completion_probability"] is None
        assert row["risk_adjusted_fair_value_inr"] is None
        assert row["historical_turnover_is_executable_capacity"] is False
        assert row["missing_original_document_gate_count"] >= 3
        assert row["needs_actual_bid_ask_depth_and_execution_evidence"] is True


def test_mutating_source_identity_or_historical_band_is_detected():
    sources, receipts = _inputs()
    mutated = copy.deepcopy(sources)
    target = next(
        c for c in mutated["P043_20_SESSION_LIQUIDITY"]["company_cases"]
        if c["symbol"] == "INOXGREEN"
    )
    target["historical_eq_source_readiness"][
        "median_daily_cash_market_value_traded_inr_crore"
    ] *= 5
    with pytest.raises(ValueError, match="liquidity mismatch"):
        _build_from(mutated, receipts)

    mutated = copy.deepcopy(sources)
    target = next(
        c for c in mutated["P046_LATEST_CATALYST_STAGE"][
            "casework_with_current_vepl_milestone"
        ]
        if c["symbol"] == "SAMBHV"
    )
    target["hg003_thread_state"] = "COMPLETED_DIRECT_EVENT_ONLY"
    with pytest.raises(ValueError, match="source drift"):
        _build_from(mutated, receipts)


def test_tampered_original_blob_or_packet_hash_rejected(tmp_path: Path):
    for path, _ in SOURCE_FILES.values():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / path).read_bytes())
    sources, receipts = load_frozen_sources(tmp_path)
    assert len(sources) == 3
    assert len(receipts) == 3
    path = tmp_path / SOURCE_FILES["P047_OFFICIAL_OCT13_MARKET"][0]
    path.write_bytes(path.read_bytes().replace(b"ANANTRAJ", b"CHANGED_", 1))
    with pytest.raises(ValueError, match="original frozen Git blob changed"):
        load_frozen_sources(tmp_path)

    result = materialize_direct_catalyst_triage(ROOT)
    result["cases"][0]["official_equity_close_inr_not_current"] = 100_000
    with pytest.raises(ValueError, match="packet SHA changed"):
        validate_direct_catalyst_triage(result)


def test_derived_output_is_bit_identical_and_cli_check_is_read_only():
    result = materialize_direct_catalyst_triage(ROOT)
    assert result == json.loads(ARTIFACT.read_text(encoding="utf-8"))
    output = subprocess.run(
        [
            sys.executable, "scripts/materialize_hg007_p048.py",
            "--repo-root", ".", "--output", str(ARTIFACT),
            "--check",
        ],
        check=True, capture_output=True, text=True,
    )
    summary = json.loads(output.stdout)
    assert summary["state"] == "VALIDATED"
    assert summary["packet_sha256"] == result["packet_sha256"]
