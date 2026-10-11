from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_p030_underwriting_readiness import (
    BOARD_ID,
    FROZEN_FIVE,
    SOURCE_BLOBS,
    build_p030_case_readiness,
    load_pinned_underwriting_sources,
)


def _build() -> dict:
    src, prov = load_pinned_underwriting_sources(Path("."))
    return build_p030_case_readiness(src, prov)


def test_all_five_hg005_cases_with_source_pinned_non_investable_state() -> None:
    packet = _build()
    assert packet["readiness_id"] == BOARD_ID
    assert packet["assembled_as_of_ist"] == "2026-10-11"
    assert packet["original_hg005_price_session"] == "2026-10-01"
    assert packet["original_five_hg005_company_count"] == 5
    assert len(packet["evidence_source_git_blob_receipts"]) == 11
    assert [row["symbol"] for row in packet["casework"]] == list(FROZEN_FIVE)
    assert packet["separate_valuation_or_return_ready_company_count"] == 0
    assert packet["case_completion_probabilities_published"] == 0
    assert packet["economically_validated_50pct_upside_cases"] == 0
    assert packet["unverified_current_oct11_fully_diluted_company_count"] == 5
    assert packet["original_hg002_and_hg005_frozen_selection_unchanged"] is True
    for case in packet["casework"]:
        assert len(case["necessary_original_document_and_underwriting_gates"]) >= 4
        assert case["source_evidence_case"]
        assert case["current_fully_diluted_capital_and_ev_sufficient"] is False
        assert case["primary_source_economic_cashflow_sufficient"] is False
        assert case["probability_weighted_equity_expected_return"] is None
        assert case["current_price_target"] is None
        assert case["live_capital_allowed"] is False
        assert case["portfolio_eligibility_allowed"] is False
    assert packet["corporate_action_and_dividend_basis_verified"] is False
    assert packet["investment_recommendations_authorized"] is False
    assert packet["live_capital_allowed"] is False


def test_anantraj_june_qip_dated_allocation_never_newco_free_cash() -> None:
    record = {r["symbol"]: r for r in _build()["casework"]}["ANANTRAJ"]
    evidence = record["source_evidence_case"]
    assert evidence["source_publication_date"] == "2026-08-08"
    assert evidence["monitoring_cutoff"] == "2026-06-30"
    assert evidence["gross_qip_inr_crore"] == 1100
    assert evidence["net_qip_inr_crore"] == 1072.2
    assert evidence["unused_qip_earmarked_object_amount_inr_crore_not_newco_cash"] == (
        358.74
    )
    assert evidence["unreconciled_fdr_minus_qip_unused_inr_crore"] == pytest.approx(.02)
    assert evidence["newco_net_cash_or_equity_value_verified"] is False
    assert evidence["scheme_effective_date_confirmed"] is False
    assert record["original_hg005_oct1_fd_cap_inr_crore_not_current"] == pytest.approx(
        20795.48840005
    )
    assert record["original_hg005_hurdle_unmodified"][
        "equity_bridge_state"
    ] == "BLOCKED_TRANSFERRED_NET_DEBT_AND_LIABILITIES_UNQUANTIFIED"


def test_devx_no_double_count_indas_ebitda_before_cash_rent() -> None:
    case = {r["symbol"]: r for r in _build()["casework"]}["DEVX"]
    evidence = case["source_evidence_case"]
    assert evidence["fy26_standalone_reported_indas_ebitda_inr_crore"] == 103.46
    assert evidence["fy26_standalone_cash_rent_outflow_inr_crore"] == 66.92
    assert evidence["fy26_standalone_cash_ebit_after_rent_inr_crore"] == 36.55
    assert evidence["existing_ncd_coupon_pct"] == 11.75
    assert evidence["additional_50cr_ncd_not_confirmed_issued"] is True
    assert evidence["winston_incremental_cash_ebit_verified"] is False
    assert case["original_hg005_hurdle_unmodified"][
        "fifty_pct_uplift_at_15x_required_incremental_annual_ebitda_inr_crore"
    ] == pytest.approx(11.847268466000001)


def test_npst_preserve_revenue_other_income_and_unspent_not_bank_cash() -> None:
    case = {r["symbol"]: r for r in _build()["casework"]}["NPST"]
    evidence = case["source_evidence_case"]
    assert evidence["q1fy27_presentation_ebitda_inr_crore"] == 18.79
    assert evidence["q1fy27_other_income_in_total_income_inr_crore"] == 4.94
    assert evidence["other_income_fraction_of_reported_ebitda_pct"] == pytest.approx(
        100 * 4.94 / 18.79
    )
    assert evidence["reg32_unused_allocation_inr_crore_not_verified_cash"] == pytest.approx(
        264.3632
    )
    assert evidence["recurrent_core_ebitda_independently_verified"] is False
    assert case["original_hg005_hurdle_unmodified"][
        "fifty_pct_uplift_at_30x_required_incremental_annual_ebitda_inr_crore"
    ] == pytest.approx(61.42562125)


def test_sambhv_power_is_extra_to_original_steel_only_hurdle() -> None:
    case = {r["symbol"]: r for r in _build()["casework"]}["SAMBHV"]
    evidence = case["source_evidence_case"]
    assert evidence["steel_only_issuer_capex_inr_crore"] == 810
    assert evidence["separate_25mw_power_capex_inr_crore"] == 125
    assert evidence["combined_steel_plus_power_capex_if_both_required_inr_crore"] == (
        935
    )
    assert evidence["capacity_addition_mmtpa"] == .36
    assert evidence["issuer_commissioning_target_not_actual"] == "Q4FY27"
    assert evidence[
        "strong_illustrative_steel_plus_power_net_increment_to_stale_oct1_cap_fraction"
    ] == pytest.approx(.4981218777654825)
    assert evidence["this_is_prospective_operational_earnings"] is False
    assert case["original_hg005_hurdle_unmodified"][
        "illustrative_strong_cell"
    ]["conservative_net_equity_value_to_market_cap"] == pytest.approx(
        .5243963459571802
    )


def test_inox_sep29_fd_pledge_no_oct1_lookahead_or_inferred_operating_income() -> None:
    case = {r["symbol"]: r for r in _build()["casework"]}["INOXGREEN"]
    proof = case["source_evidence_case"]
    assert proof["official_shares_asof_date"] == "2026-09-29"
    assert proof["first_public_broadcast_utc"] == "2026-10-08T13:24:47Z"
    assert proof["official_fd_shares_asof_sep29"] == 422070138
    assert proof["promoter_pledged_shares_asof_sep29"] == 4_900_000
    assert proof[
        "old_oct1_share_basis_may_not_use_oct8_publication_retroactively"
    ] is True
    assert proof[
        "dated_sep29_fd_shares_times_oct9_price_cap_inr_crore_not_oct11_current"
    ] == pytest.approx(5441.328219096)
    assert proof["parent_subordinated_intercompany_loan_coupon_pct"] == 12
    assert proof["parent_loan_up_to_50cr_conversion_optional"] is True
    assert proof["management_implied_post_synergy_ebitda_inr_crore_unverified"] == (
        275
    )
    assert proof["wwil_transfer_legally_completed_verified"] is False
    assert case["original_hg005_hurdle_unmodified"]["state"] == (
        "PAYOFF_FRAMEWORK_BLOCKED_SOURCE_PARTIAL"
    )


def test_historical_source_byte_tampering_fails_before_board(tmp_path: Path) -> None:
    for relative, _sha in SOURCE_BLOBS.values():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Path(relative).read_bytes())
    originals, receipts = load_pinned_underwriting_sources(tmp_path)
    assert build_p030_case_readiness(originals, receipts)[
        "original_five_hg005_company_count"
    ] == 5
    original = tmp_path / SOURCE_BLOBS["anantraj_qip"][0]
    original.write_bytes(original.read_bytes() + b" ")
    with pytest.raises(ValueError, match="original research Git blob changed"):
        load_pinned_underwriting_sources(tmp_path)


def test_cannot_silently_replace_real_facts_or_past_hg005_hurdles() -> None:
    original, prov = load_pinned_underwriting_sources(Path("."))
    preserve = deepcopy(original)
    build_p030_case_readiness(original, prov)
    assert original == preserve
    changed = deepcopy(original)
    changed["devx_cash_credit"]["fy26_standalone_issuer_reported"][
        "fy26_cash_ebit"
    ] = 103.46
    with pytest.raises(ValueError, match="source historical fact changed"):
        build_p030_case_readiness(changed, prov)

    changed = deepcopy(original)
    changed["current_company_context"]["company_cases"][0]["symbol"] = "FICTION"
    with pytest.raises(ValueError, match="original 28-case selected identity"):
        build_p030_case_readiness(changed, prov)

    changed = deepcopy(original)
    changed["anantraj_qip"]["cloud_qip_unused_is_newco_free_cash"] = True
    with pytest.raises(ValueError, match="ANANTRAJ legal effectiveness"):
        build_p030_case_readiness(changed, prov)

    changed = deepcopy(original)
    changed["current_company_context"]["company_cases"][1][
        "asof_29sep_exchange_source_update"
    ]["oct1_use_as_publicly_visible_fd_denominator_allowed"] = True
    with pytest.raises(ValueError, match="INOXGREEN corporate-action"):
        build_p030_case_readiness(changed, prov)


def test_offline_cli_reproduces_frozen_readiness_and_rejects_edits(tmp_path: Path) -> None:
    output = tmp_path / "p030.json"
    cmd = [
        sys.executable,
        "scripts/build_hg007_p030_underwriting.py",
        "--out", str(output),
    ]
    execution = subprocess.run(cmd, capture_output=True, text=True, check=True)
    counts = json.loads(execution.stdout)
    assert counts["original_five"] == list(FROZEN_FIVE)
    assert counts["source_family_count"] == len(SOURCE_BLOBS)
    assert counts["approved_equity_upside_cases"] == 0
    assert counts["valuation_ready_count"] == 0
    assert counts["live_capital_allowed"] is False
    assert json.loads(output.read_text(encoding="utf-8")) == _build()

    subprocess.run(
        cmd + ["--verify-existing"],
        capture_output=True, text=True, check=True
    )
    output.write_text(output.read_text(encoding="utf-8") + "tampered")
    rejected = subprocess.run(
        cmd + ["--verify-existing"],
        capture_output=True, text=True, check=False
    )
    assert rejected.returncode != 0
    assert "original-source five-company readiness drifted" in rejected.stderr
