from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss002_p005_readiness import build_transaction_readiness

RESULT = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "ss002-p004-native-result-v1.json"
)


def _source() -> dict:
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_all_eight_p004_cases_get_correct_research_routes() -> None:
    output = build_transaction_readiness(_source())
    rows = {row["symbol"]: row for row in output["cases"]}
    assert output["case_count"] == 8
    assert output["active_transaction_research_lens_count"] == 4
    assert rows["VRLLOG"]["research_lane"] == "TENDER_BUYBACK_DUE_DILIGENCE"
    assert rows["OLAELEC"]["research_lane"] == "RIGHTS_DILUTION_DUE_DILIGENCE"
    assert rows["INOXGREEN"]["research_lane"] == "ACQUISITION_DUE_DILIGENCE"
    assert rows["KOTHARIPET"]["research_lane"] == "SCHEME_DUE_DILIGENCE"
    assert rows["PVRINOX"]["research_lane"] == "COMPLETED_EVENT_IMPACT"
    assert rows["TVSSRICHAK"]["research_lane"] == "COMPLETED_EVENT_IMPACT"
    assert rows["SAMBHV"]["research_lane"] == "PROCEDURAL_MONITOR"
    assert rows["PREMEXPLN"]["research_lane"] == "SOURCE_VISUAL_REVIEW"
    assert output["underwriting_ready_count"] == 0
    assert all(not row["underwriting_ready"] for row in output["cases"])
    assert all(not row["portfolio_eligibility_allowed"] for row in output["cases"])


def test_important_missing_evidence_is_never_imputed() -> None:
    output = build_transaction_readiness(_source())
    rows = {row["symbol"]: row for row in output["cases"]}
    assert "ACCEPTANCE_RATIO_AND_DISTRIBUTION" in rows["VRLLOG"][
        "unverified_evidence_requirements"
    ]
    assert "AUDITED_TARGET_REVENUE_EBITDA_AND_CASH_CONVERSION" in rows["INOXGREEN"][
        "unverified_evidence_requirements"
    ]
    assert "APPLICATION_AND_FUTURE_PAYMENT_CALLS" in rows["OLAELEC"][
        "unverified_evidence_requirements"
    ]
    assert "ORIGINAL_NEWSPAPER_IMAGE_OR_OFFICIAL_VISUAL_NOTICE" in rows["PREMEXPLN"][
        "unverified_evidence_requirements"
    ]


def test_changed_source_identity_fails_closed() -> None:
    source = _source()
    source["pilot_sha256"] = "incorrect"
    with pytest.raises(AlphaContractError, match="pilot SHA mismatch"):
        build_transaction_readiness(source)


def test_audited_flag_cannot_be_self_declared() -> None:
    source = copy.deepcopy(_source())
    source["cases"][0]["semantic_audit_status"] = "APPROVED"
    with pytest.raises(AlphaContractError, match="not independently audited"):
        build_transaction_readiness(source)
