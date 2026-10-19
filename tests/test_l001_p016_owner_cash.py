"""P016: cash classification is not normalized shareholder owner earnings."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.l001_p016_owner_cash_gate import (
    AUDIT_ID,
    GATES,
    build_owner_cash_falsification,
    load_original_p015,
    validate_owner_cash_falsification,
    validate_prior_original_p015,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/l001/l001-p016-owner-cash-evidence-gates-100-v1.json"


def _source():
    return load_original_p015(ROOT)


def _build():
    return build_owner_cash_falsification(_source())


def test_original_100_fy26_issuers_are_conserved_without_price_signal():
    report = _build()
    assert report["report_id"] == AUDIT_ID
    assert report["issuer_count"] == 100
    assert report["economic_cash_gate_count"] == len(GATES)
    assert len(report["company_cashflow_classification_rows"]) == 100
    assert len({
        (x["symbol"], x["isin"])
        for x in report["company_cashflow_classification_rows"]
    }) == 100
    assert report["issuer_sustainable_owner_cash_estimated_count"] == 0
    assert report["company_expected_return_estimated_count"] == 0
    assert report["live_capital_allowed"] is False
    assert report["posthoc_2026_10_19_research_not_Oct15_trading_signal"]
    assert report["acquisition_cash_flows_not_added_to_PPE_and_net_investing"]
    assert all(
        row["capital_eligible"] is False
        and row["normalized_attributable_owner_cash_cr"] is None
        and row["verified_3year_expected_total_return"] is None
        for row in report["company_cashflow_classification_rows"]
    )
    validate_owner_cash_falsification(report, original_p015=_source())


def test_suntv_original_intangibles_reverse_naive_cash_proxy():
    row = _build()["original_case_illustrations"]["SUNTV"]
    assert row["fy26_cfo_cr_reported"] == 1801.64
    assert row["fy26_ppe_cash_purchase_cr_reported"] == 83.91
    assert row["fy26_intangible_cash_purchase_cr_reported"] == 2130.31
    assert row["fy26_simple_cfo_minus_ppe_cr_not_owner_cash"] == 1717.73
    assert row["fy26_cfo_minus_ppe_intangibles_cr_not_owner_cash"] == -412.58
    assert GATES[0] in row["economic_cash_review_flags"]
    assert row["all_other_investing_cash_is_maintenance_spending"] is False
    assert row["growth_capex_fully_excludable_without_ROIC_test"] is False


def test_zero_ppe_tag_not_evidence_of_no_OIL_investment():
    row = _build()["original_case_illustrations"]["OIL"]
    assert row["fy26_ppe_cash_purchase_cr_reported"] == 0
    assert row["fy26_net_investing_cr_not_additive_to_cash_spending"] == -10381.37
    assert GATES[1] in row["economic_cash_review_flags"]
    assert row["zero_purchase_tag_proves_no_economic_reinvestment"] is False


def test_gross_investment_purchase_is_not_recurrent_ACE_or_MAYUR_capex():
    rows = _build()["original_case_illustrations"]
    for symbol in ("ACE", "MAYURUNIQ"):
        row = rows[symbol]
        assert GATES[2] in row["economic_cash_review_flags"]
        assert row["positive_additional_investing_purchase_candidates_over_simple_proxy"]
        assert all(
            item["source_amount_cr_not_verified_recurring"]
            > abs(row["fy26_simple_cfo_minus_ppe_cr_not_owner_cash"])
            for item in row[
                "positive_additional_investing_purchase_candidates_over_simple_proxy"
            ]
        )
        assert row["investments_cash_and_acquisitions_may_overlap_or_net"]
        assert row["all_other_investing_cash_is_maintenance_spending"] is False


def test_all_source_flags_are_evidence_checks_not_computed_alpha():
    report = _build()
    assert set(report["source_review_gate_counts_overlap"]).issubset(GATES)
    assert all(
        0 <= n <= 100 for n in report["source_review_gate_counts_overlap"].values()
    )
    assert report["all_original_100_issuer_identities_preserved"] is True
    assert report["prospective_oos_return_labels_not_used_for_selection"]
    assert report["financial_investment_cash_flows_not_assumed_recurring_capex"]


def test_signed_source_and_derived_payload_tampering_fails_closed():
    original = _source()
    modified = copy.deepcopy(original)
    modified["original_tag_inventory_by_company"][0][
        "fy26_reported_ppe_cash_purchase_cr"
    ] = 0
    with pytest.raises(
        AlphaContractError, match="original 100-issuer signed P015 source changed"
    ):
        validate_prior_original_p015(modified)

    derived = _build()
    derived["company_cashflow_classification_rows"][0][
        "verified_3year_expected_total_return"
    ] = 1.2
    with pytest.raises(AlphaContractError, match="diagnostic SHA changed"):
        validate_owner_cash_falsification(
            derived, original_p015=original
        )


def test_output_replays_and_direct_command_is_read_only_check():
    expected = _build()
    assert expected == json.loads(REPORT.read_text(encoding="utf-8"))
    run = subprocess.run(
        [
            sys.executable, "scripts/materialize_l001_p016_owner_cash.py",
            "--check",
        ],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    status = json.loads(run.stdout)
    assert status["state"] == "VERIFIED"
    assert status["original_issuers"] == 100
    assert status["live_capital_allowed"] is False
    assert status["signature"] == expected["report_sha256"]
