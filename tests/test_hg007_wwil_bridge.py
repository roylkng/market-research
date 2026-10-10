from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.hg007_wwil_bridge import (
    PROVISIONAL_TERMS,
    build_conditional_funding_bridge,
)


def _build(terms: dict | None = None) -> dict:
    return build_conditional_funding_bridge(
        PROVISIONAL_TERMS if terms is None else terms,
        evidence_state="SECONDARY_TRANSCRIPTION_AWAITING_ORIGINAL_PDF",
        transfer_conditions_precedent_satisfied=False,
        original_pdf_reviewed=False,
    )


def test_provisional_oct7_inox_funding_reconciles_without_valuation() -> None:
    case = _build()
    assert case["gross_purchase_consideration_inr_crore"] == 550.0
    assert case["inox_green_total_reported_funding_inr_crore"] == 450.0
    assert case["authum_external_reported_funding_inr_crore"] == 100.0
    assert case["preconversion_issuer_subsidiary_equity_ownership_fraction"] == 1.0
    assert case["hypothetical_post_both_conversions_inox_equity_interest_fraction"] == (
        pytest.approx(300.01 / 400.01)
    )
    assert case["hypothetical_post_both_conversions_authum_equity_interest_fraction"] == (
        pytest.approx(100 / 400.01)
    )
    assert case["postconversion_remaining_inox_intercompany_deposit_inr_crore"] == 150.0
    assert case["postconversion_remaining_authum_deposit_inr_crore"] == 0.0
    assert case["actual_conversion_prices_and_security_classes_verified"] is False
    assert case["original_bse_pdf_audited_verified"] is False
    assert case["purchase_transfer_legally_completed_verified"] is False
    assert case["conversions_completed_verified"] is False
    assert case["future_target_ebitda_verified"] is False
    assert case["stock_price_target_authorized"] is False
    assert case["acquisition_expected_return_calculated"] is False
    assert case["portfolio_eligibility_allowed"] is False
    assert case["live_capital_allowed"] is False


def test_rejects_550cr_cash_uses_that_do_not_reconcile() -> None:
    wrong = deepcopy(PROVISIONAL_TERMS)
    wrong["authum_external_intercompany_deposit_inr_crore"] = 50
    with pytest.raises(ValueError, match="do not reconcile"):
        _build(wrong)


def test_rejects_conversion_exceeding_deposit_and_negative_funding() -> None:
    wrong = deepcopy(PROVISIONAL_TERMS)
    wrong["inox_green_deposit_planned_equity_conversion_inr_crore"] = 300
    with pytest.raises(ValueError, match="do not reconcile"):
        _build(wrong)

    wrong = deepcopy(PROVISIONAL_TERMS)
    wrong["gross_wwil_purchase_consideration_inr_crore"] = -10
    with pytest.raises(ValueError, match="cannot be negative"):
        _build(wrong)


def test_cannot_promote_secondary_transcription_to_verified_original_pdf() -> None:
    with pytest.raises(ValueError, match="cannot be promoted"):
        build_conditional_funding_bridge(
            PROVISIONAL_TERMS,
            evidence_state="INDEPENDENT_OFFICIAL_DOCUMENT_VERIFIED",
            transfer_conditions_precedent_satisfied=False,
            original_pdf_reviewed=False,
        )
    with pytest.raises(ValueError, match="cannot certify legal close"):
        build_conditional_funding_bridge(
            PROVISIONAL_TERMS,
            evidence_state="SECONDARY_TRANSCRIPTION_AWAITING_ORIGINAL_PDF",
            transfer_conditions_precedent_satisfied=True,
            original_pdf_reviewed=False,
        )
    with pytest.raises(ValueError, match="cannot certify legal close"):
        build_conditional_funding_bridge(
            PROVISIONAL_TERMS,
            evidence_state="SECONDARY_TRANSCRIPTION_AWAITING_ORIGINAL_PDF",
            transfer_conditions_precedent_satisfied=False,
            original_pdf_reviewed=True,
        )


def test_cli_produces_provisional_research_only_artifact(tmp_path: Path) -> None:
    output = tmp_path / "wwil.json"
    finished = subprocess.run(
        [sys.executable, "scripts/build_hg007_wwil_bridge.py", "--out", str(output)],
        capture_output=True,
        text=True,
        check=True,
    )
    metadata = json.loads(finished.stdout)
    case = json.loads(output.read_text(encoding="utf-8"))
    assert metadata["gross_purchase_crore"] == 550
    assert metadata["expected_return_calculated"] is False
    assert case == _build()
    assert case["original_bse_pdf_audited_verified"] is False
    assert case["source"]["original_source_pdf_sha256_verified"] is False
