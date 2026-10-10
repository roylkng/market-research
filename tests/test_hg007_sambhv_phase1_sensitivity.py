from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_sambhv_phase1_sensitivity import (
    MODEL_ID,
    PDF_PATH,
    SOURCES,
    build_steel_power_sensitivity,
    load_sambhv_pinned_sources,
)


@pytest.fixture(scope="module")
def originals() -> tuple[dict, dict, dict, dict]:
    return load_sambhv_pinned_sources(Path("."))


@pytest.fixture(scope="module")
def audit(originals: tuple[dict, dict, dict, dict]) -> dict:
    return build_steel_power_sensitivity(*originals[:3], provenance=originals[3])


def test_original_sambhv_capex_and_payoff_source_pins(audit: dict) -> None:
    assert audit["sensitivity_id"] == MODEL_ID
    assert audit["source_verified_steel_coils_capacity_add_mmtpa"] == 0.36
    assert audit["source_verified_steel_only_capex_inr_crore"] == 810
    assert audit["source_verified_separate_captive_power_mw"] == 25
    assert audit["source_verified_additional_power_capex_inr_crore"] == 125
    assert audit["source_target_steel_and_power_commissioning"] == "Q4FY27"
    assert audit["historical_reported_fd_market_cap_inr_crore"] == pytest.approx(
        4757.470221205
    )
    assert audit["historical_unchanged_market_price_inr"] == 161.45
    assert audit["source_provenance"]["original_issuer_pdf"][
        "roadmap_page_number_one_based"
    ] == 9
    assert audit["source_provenance"]["original_issuer_pdf"]["byte_count"] == 5654565


def test_steel_only_and_captive_power_scenarios_are_mutually_exclusive(audit: dict) -> None:
    strong, mid = audit["two_alternative_assumptions_not_additive_payoff_estimates"]
    assert strong["illustrative_annual_operating_ebitda_inr_crore"] == pytest.approx(275.4)
    assert strong["hypothetical_gross_incremental_ev_inr_crore"] == pytest.approx(3304.8)
    assert strong["steel_only_original_capex_inr_crore"] == 810
    assert strong["steel_plus_power_conditional_capex_inr_crore"] == 935
    assert strong["original_steel_only_net_increment_inr_crore"] == pytest.approx(2494.8)
    assert strong["conditional_steel_plus_power_net_increment_inr_crore"] == pytest.approx(2369.8)
    assert strong["original_steel_only_net_increment_to_frozen_cap"] == pytest.approx(
        0.5243963459571802
    )
    assert strong["conditional_steel_plus_power_net_increment_to_frozen_cap"] == (
        pytest.approx(0.4981218777654825)
    )
    assert strong["independent_power_only_ebitda_required_to_offset_capex_at_same_multiple_cr"] == (
        pytest.approx(125 / 12)
    )
    assert mid["illustrative_annual_operating_ebitda_inr_crore"] == 252
    assert mid["original_steel_only_net_increment_to_frozen_cap"] == pytest.approx(
        0.35943472486242517
    )
    assert mid["conditional_steel_plus_power_net_increment_to_frozen_cap"] == (
        pytest.approx(0.3331602566707274)
    )
    assert mid["independent_power_only_ebitda_required_to_offset_capex_at_same_multiple_cr"] == 12.5
    assert strong["change_due_only_to_extra_power_capex_fraction_of_frozen_cap"] == (
        pytest.approx(-125 / 4757.470221205)
    )


def test_separate_roadmap_and_no_future_earnings_claim(audit: dict) -> None:
    assert audit["source_lists_other_project_spend_not_included"] == {
        "sarora_30mw_power_inr_crore": 150,
        "kuthrel_8mw_rooftop_solar_inr_crore": 25,
        "erw_0_15mmtpa_brownfield_inr_crore": 50,
    }
    for field in (
        "power_plant_required_for_assumed_steel_ebitda_verified",
        "incremental_power_capex_fully_funded_or_spent_verified",
        "new_plant_operational_ebitda_verified",
        "future_steel_power_synergy_ebitda_verified",
        "original_hg005_hurdle_modified",
        "company_probability_or_alpha_computed",
        "stock_price_target_or_future_return_computed",
        "independently_current_fd_shares_verified",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        assert audit[field] is False
    assert all(
        row["project_expected_stock_return"] is None
        and row["power_ebitda_savings_separately_verified"] is False
        for row in audit["two_alternative_assumptions_not_additive_payoff_estimates"]
    )


def test_input_source_values_not_mutated(originals: tuple[dict, dict, dict, dict]) -> None:
    prior = deepcopy(originals)
    build_steel_power_sensitivity(*originals[:3], provenance=originals[3])
    assert originals == prior


def test_tampered_source_receipt_or_frozen_market_cap_fails(
    originals: tuple[dict, dict, dict, dict],
) -> None:
    a, b, c, refs = deepcopy(originals)
    a["document_identity_evidence"]["source_declared_power_capex_inr_crore"] = 80
    with pytest.raises(ValueError, match="source family changed"):
        build_steel_power_sensitivity(a, b, c, provenance=refs)
    a, b, c, refs = deepcopy(originals)
    b["key_mechanical_context"]["SAMBHV"]["reported_fd_market_cap_inr_crore"] += 1
    with pytest.raises(ValueError, match="market reference changed"):
        build_steel_power_sensitivity(a, b, c, provenance=refs)
    a, b, c, refs = deepcopy(originals)
    c["key_hurdles"]["SAMBHV"]["illustrative_strong_cell"][
        "conservative_net_equity_value_to_market_cap"
    ] += 0.01
    with pytest.raises(ValueError, match="original mechanical payoff drifted"):
        build_steel_power_sensitivity(a, b, c, provenance=refs)


def test_original_issuer_pdf_blob_or_source_json_edits_fail(tmp_path: Path) -> None:
    all_paths = [path for path, _ in SOURCES.values()] + [PDF_PATH]
    for relative in all_paths:
        original = Path(relative)
        dest = tmp_path / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(original.read_bytes())
    copy_pdf = tmp_path / PDF_PATH
    copy_pdf.write_bytes(copy_pdf.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="raw SHA/size"):
        load_sambhv_pinned_sources(tmp_path)
    copy_pdf.write_bytes(Path(PDF_PATH).read_bytes())
    copy_hurdle = tmp_path / SOURCES["HG005_ORIGINAL_HURDLES"][0]
    copy_hurdle.write_bytes(copy_hurdle.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="original pinned Git blob mismatch"):
        load_sambhv_pinned_sources(tmp_path)


def test_cli_source_regeneration_and_mutation_detection(tmp_path: Path) -> None:
    destination = tmp_path / "sambhv-capex.json"
    command = [
        sys.executable, "scripts/reconcile_hg007_sambhv_steel_power.py",
        "--out", str(destination),
    ]
    run = subprocess.run(command, check=True, capture_output=True, text=True)
    summary = json.loads(run.stdout)
    assert summary["strong_conditional_steel_power_pct"] == pytest.approx(
        49.81218777654825
    )
    assert summary["strong_steel_only_pct"] == pytest.approx(52.43963459571802)
    assert summary["actual_required_power_inclusion_proven"] is False
    assert summary["stock_target_or_future_return_computed"] is False
    assert summary["live_capital_allowed"] is False
    subprocess.run(
        command + ["--verify-existing"], check=True, capture_output=True, text=True
    )
    destination.write_text(destination.read_text(encoding="utf-8") + "fake")
    failed = subprocess.run(
        command + ["--verify-existing"], check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "changed after source review" in failed.stderr
