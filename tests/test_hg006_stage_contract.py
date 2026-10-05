from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg006_stage_contract import extraction_template,validate_extraction


def _output():
    out=extraction_template(
        document_id="doc",
        event_ids=["e1"],
        symbol="AAA",
        family="SCHEME_REORGANISATION",
    )
    out["stage_observations"]=[
        {"stage":"REGULATORY_OR_COURT_APPROVED","evidence_segment_ids":["s1"]}
    ]
    out["transaction_anchors"]=[
        {
            "anchor_type":"CASE_ORDER_REFERENCE",
            "value":"CP(CAA) 123/2025",
            "evidence_segment_ids":["s1"],
        }
    ]
    out["provenance"]={
        "provider_runtime":"TEST",
        "model_id":"TEST",
        "model_config_sha256":"a"*64,
        "prompt_contract_id":"HG006-L001-v1",
        "prompt_sha256":"b"*64,
        "input_document_id":"doc",
        "input_segment_manifest_sha256":"c"*64,
        "raw_model_response_sha256":"d"*64,
    }
    return out


def test_valid_stage_extraction_seals_without_probability():
    sealed=validate_extraction(
        _output(),
        document_id="doc",
        event_ids={"e1"},
        symbol="AAA",
        family="SCHEME_REORGANISATION",
        allowed_segment_ids={"s1"},
        segment_manifest_sha256="c"*64,
    )
    assert sealed["completion_probability_assigned"] is False
    assert sealed["portfolio_eligibility_allowed"] is False


def test_terminal_language_requires_evidence():
    out=_output()
    out["explicit_terminal_language"]="EXPLICIT_COMPLETION_LANGUAGE"
    with pytest.raises(AlphaContractError,match="explicit claim requires evidence"):
        validate_extraction(
            out,
            document_id="doc",
            event_ids={"e1"},
            symbol="AAA",
            family="SCHEME_REORGANISATION",
            allowed_segment_ids={"s1"},
            segment_manifest_sha256="c"*64,
        )


def test_unknown_evidence_segment_fails_closed():
    out=_output()
    out["transaction_anchors"][0]["evidence_segment_ids"]=["missing"]
    with pytest.raises(AlphaContractError,match="unknown evidence"):
        validate_extraction(
            out,
            document_id="doc",
            event_ids={"e1"},
            symbol="AAA",
            family="SCHEME_REORGANISATION",
            allowed_segment_ids={"s1"},
            segment_manifest_sha256="c"*64,
        )


def test_forbidden_probability_field_is_rejected():
    out=_output()
    out["completion_probability"]=0.9
    with pytest.raises(AlphaContractError,match="forbidden fields"):
        validate_extraction(
            out,
            document_id="doc",
            event_ids={"e1"},
            symbol="AAA",
            family="SCHEME_REORGANISATION",
            allowed_segment_ids={"s1"},
            segment_manifest_sha256="c"*64,
        )
