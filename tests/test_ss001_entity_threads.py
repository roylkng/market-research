from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss001_entity_threads import validate_entity_thread_pilot

SPECIMEN = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "ss001"
    / "inoXgreen-entity-threads-p0-v1.json"
)


def _pack() -> dict:
    return json.loads(SPECIMEN.read_text(encoding="utf-8"))


def test_illustrative_entity_threads_validate_without_share_clearance() -> None:
    result = validate_entity_thread_pilot(_pack())

    assert result["structural_validation_pass"] is True
    assert result["document_count"] == 4
    assert result["entity_count"] == 4
    assert result["thread_count"] == 3
    assert result["explicit_fact_count"] == 12
    assert result["source_text_independently_reverified_by_validator"] is False
    assert result["full_d007_l002_coverage"] is False
    assert result["semantic_audit_complete"] is False
    assert result["share_action_clearance_proven"] is False
    assert result["market_capitalization_calculated"] is False
    assert result["expected_return_calculated"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False
    assert result["return_outcomes_opened"] is False


def test_irsl_allotment_cannot_be_attributed_to_inoxgreen_share_issuance() -> None:
    pack = _pack()
    pack["threads"][0]["security_issuer_entity_id"] = "INOXGREEN"
    with pytest.raises(AlphaContractError, match="other-entity shares misattributed"):
        validate_entity_thread_pilot(pack)


def test_ipp_assets_cannot_be_attributed_to_wwil_acquisition_thread() -> None:
    pack = _pack()
    pack["threads"][1]["facts"][0]["subject_entity_id"] = "INEL"
    with pytest.raises(AlphaContractError, match="cross-entity fact attributed"):
        validate_entity_thread_pilot(pack)


def test_court_approval_cannot_be_labeled_closed_without_closing_proof() -> None:
    pack = _pack()
    pack["threads"][1]["transaction_stage"] = "EXECUTED_AND_CLOSED"
    with pytest.raises(AlphaContractError, match="needs disclosed closing date"):
        validate_entity_thread_pilot(pack)


def test_proposed_consideration_cannot_be_reclassified_as_final() -> None:
    pack = _pack()
    term = next(
        row
        for row in pack["threads"][1]["facts"]
        if row["field"] == "proposed_cash_consideration_inr_crore"
    )
    term["qualifier"] = "EXPLICIT_FINAL"
    with pytest.raises(AlphaContractError, match="proposal cannot become definitive"):
        validate_entity_thread_pilot(pack)


def test_unsupported_source_page_is_rejected() -> None:
    pack = _pack()
    pack["threads"][0]["facts"][0]["evidence"][0]["segment_id"] = "not-a-source-page"
    with pytest.raises(AlphaContractError, match="unsupported document page"):
        validate_entity_thread_pilot(pack)


def test_new_document_url_or_hash_is_rejected() -> None:
    pack = _pack()
    pack["documents"][0]["source_url"] = "https://nsearchives.nseindia.com/other.pdf"
    with pytest.raises(AlphaContractError, match="official document URL mismatch"):
        validate_entity_thread_pilot(pack)


def test_later_source_date_may_not_repair_frozen_case() -> None:
    pack = _pack()
    pack["documents"][0]["published_on"] = "2026-10-09"
    with pytest.raises(AlphaContractError, match="document publication is not frozen"):
        validate_entity_thread_pilot(pack)


def test_uncited_prediction_or_market_cap_is_not_a_valid_source_fact() -> None:
    pack = _pack()
    pack["intrinsic_value_inr"] = 400
    with pytest.raises(AlphaContractError, match="top-level schema differs"):
        validate_entity_thread_pilot(pack)


def test_market_cap_and_issuer_clearance_cannot_be_switched_on() -> None:
    for field in ("market_capitalization_calculated", "share_action_clearance_proven"):
        pack = copy.deepcopy(_pack())
        pack[field] = True
        with pytest.raises(AlphaContractError, match=f"{field} must remain false"):
            validate_entity_thread_pilot(pack)


def test_issuer_approval_does_not_allow_other_entity_listed_flag() -> None:
    pack = _pack()
    pack["entities"][1]["is_listed_issuer"] = True
    with pytest.raises(AlphaContractError, match="other entity cannot be listed issuer"):
        validate_entity_thread_pilot(pack)
