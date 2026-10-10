from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_casework import (
    SOURCE_BLOBS,
    build_casework_board,
    load_exact_sources,
)


def _board() -> dict:
    raw, receipts = load_exact_sources(Path("."))
    return build_casework_board(raw, receipts)


def test_frozen_cohort_all_28_symbols_stay_accounted_without_selection() -> None:
    report = _board()
    assert report["casework_id"] == "HG007-P001-EVIDENCE-ACQUISITION-BOARD-v1"
    assert report["source_membership_count"] == 28
    assert report["source_active_direct_catalyst_count"] == 7
    assert report["source_procedural_direct_review_count"] == 4
    assert report["source_nonlive_or_pending_count"] == 17
    assert len(report["casework"]) == 28
    assert len({row["symbol"] for row in report["casework"]}) == 28
    assert report["source_economic_context_case_count"] == 5
    assert report["gross_or_reverse_hurdle_surface_count"] == 4
    assert report["current_case_specific_survivor_probability_surface_count"] == 0
    assert report["newer_october_pilot_cases_needing_stage_reconciliation"] == [
        "INOXGREEN", "SAMBHV"
    ]
    assert report["approved_stock_recommendation_count"] == 0
    assert report["company_expected_returns_calculated"] is False
    assert report["return_outcomes_opened"] is False
    assert report["portfolio_eligibility_allowed"] is False
    assert report["live_capital_allowed"] is False
    assert all(
        row["stock_valuation_ready"] is False
        and row["portfolio_eligibility_allowed"] is False
        and row["live_capital_allowed"] is False
        and not row["probability_weighted_expected_return_permitted"]
        for row in report["casework"]
    )


def test_casework_hurdles_are_original_not_fabricated_target_prices() -> None:
    by_symbol = {row["symbol"]: row for row in _board()["casework"]}
    expected = {
        "ANANTRAJ", "DEVX", "INOXGREEN", "NPST", "SAMBHV",
    }
    realized = {
        symbol for symbol, item in by_symbol.items()
        if item["frozen_hg005_mechanical_hurdle"] is not None
    }
    assert realized == expected
    assert by_symbol["ANANTRAJ"]["economic_sensitivity_state"] == (
        "SENSITIVITY_READY_GROSS_EV_ONLY"
    )
    assert by_symbol["INOXGREEN"]["economic_sensitivity_state"] == (
        "PAYOFF_FRAMEWORK_BLOCKED_SOURCE_PARTIAL"
    )
    assert by_symbol["DEVX"]["frozen_hg005_mechanical_hurdle"][
        "fifty_pct_uplift_at_15x_required_incremental_annual_ebitda_inr_crore"
    ] == pytest.approx(11.847268466)
    assert by_symbol["NPST"]["frozen_hg005_mechanical_hurdle"][
        "fifty_pct_uplift_at_30x_required_incremental_annual_ebitda_inr_crore"
    ] == pytest.approx(61.42562125)
    assert by_symbol["SAMBHV"]["frozen_hg005_mechanical_hurdle"][
        "phase1_capex_inr_crore"
    ] == 810
    assert by_symbol["SAMBHV"]["frozen_hg005_mechanical_hurdle"][
        "illustrative_strong_cell"
    ]["conservative_net_equity_value_to_market_cap"] == pytest.approx(0.52439634595)
    assert all(
        row["price_reference_session"] == "2026-10-01"
        for row in by_symbol.values() if row["frozen_hg005_mechanical_hurdle"]
    )
    assert by_symbol["INOXGREEN"][
        "newer_ss002_october_pilot_exists_pending_independent_review"
    ] is True
    assert by_symbol["SAMBHV"][
        "newer_ss002_october_pilot_exists_pending_independent_review"
    ] is True
    assert by_symbol["DEVX"][
        "one_completed_issuance_is_not_full_economic_exercise"
    ] is True


def test_missing_transcript_or_catalyst_never_automatically_gets_payoff() -> None:
    report = _board()
    by_symbol = {row["symbol"]: row for row in report["casework"]}
    assert by_symbol["HINDCOPPER"]["hg003_thread_state"] == "TEXT_PENDING"
    assert by_symbol["HINDCOPPER"][
        "evidence_acquisition_route"
    ] == "NONLIVE_FROZEN_COHORT_RETAINED_FOR_FUNDAMENTALS"
    assert "RETRIEVE_READABLE_ORIGINAL_EXCHANGE_ATTACHMENT" in by_symbol[
        "HINDCOPPER"
    ]["next_source_documents_to_acquire_not_asserted_as_facts"]
    assert by_symbol["BORORENEW"]["hg003_thread_state"] == (
        "CANCELLED_DIRECT_EVENT_ONLY"
    )
    assert by_symbol["BORORENEW"]["frozen_hg005_mechanical_hurdle"] is None
    assert by_symbol["AXITA"][
        "evidence_acquisition_route"
    ] == "LIVE_TRANSACTION_WITHOUT_CASE_PAYOFF_MODEL"
    assert by_symbol["AXITA"]["stock_valuation_ready"] is False


def test_original_source_byte_changes_are_rejected(tmp_path: Path) -> None:
    for path_str, _ in SOURCE_BLOBS.values():
        target = tmp_path / path_str
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(path_str).read_bytes())
    sources, receipts = load_exact_sources(tmp_path)
    assert build_casework_board(sources, receipts)["source_membership_count"] == 28
    a_source = tmp_path / SOURCE_BLOBS["HG005_PAYOFF"][0]
    a_source.write_bytes(a_source.read_bytes() + b" ")
    with pytest.raises(ValueError, match="pinned Git source blob drifted"):
        load_exact_sources(tmp_path)


def test_no_substitution_or_after_outcome_probability_elevation() -> None:
    original, receipts = load_exact_sources(Path("."))
    edited = deepcopy(original)
    edited["HG003_CURRENT_STAGE"]["active_direct_catalyst_symbols"].append("DEVX")
    with pytest.raises(ValueError, match="multiple special-situation states"):
        build_casework_board(edited, receipts)

    edited = deepcopy(original)
    edited["HG006_CURRENT_BASE_RATE"][
        "current_company_probability_surfaces_published"
    ] = 1
    with pytest.raises(ValueError, match="company probability evidence changed"):
        build_casework_board(edited, receipts)

    edited = deepcopy(original)
    edited["HG005_PAYOFF"]["key_hurdles"]["NEWSTOCK"] = {"state": "READY"}
    with pytest.raises(ValueError, match="source identities"):
        build_casework_board(edited, receipts)

    edited = deepcopy(original)
    edited["HG002_COHORT"]["symbols"][0] = "NOT_ORIGINALLY_SELECTED"
    with pytest.raises(ValueError, match="lost or substituted"):
        build_casework_board(edited, receipts)


def test_cli_materializes_complete_source_evidence_and_is_idempotent(
    tmp_path: Path,
) -> None:
    out = tmp_path / "hg007.json"
    command = [
        sys.executable,
        "scripts/build_hg007_casework.py",
        "--out",
        str(out),
    ]
    finished = subprocess.run(command, check=True, capture_output=True, text=True)
    brief = json.loads(finished.stdout)
    assert brief["source_membership_count"] == 28
    assert brief["current_publishable_company_probability_count"] == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result == _board()
    assert all(len(value["git_blob_sha"]) == 40 for value in result["source_provenance"].values())
    subprocess.run(command + ["--verify-existing"], check=True, capture_output=True, text=True)
    out.write_text(out.read_text(encoding="utf-8").replace('"live_capital_allowed": false', '"live_capital_allowed": true'))
    failure = subprocess.run(command + ["--verify-existing"], check=False, capture_output=True, text=True)
    assert failure.returncode != 0
    assert "changed from exact frozen sources" in failure.stderr
