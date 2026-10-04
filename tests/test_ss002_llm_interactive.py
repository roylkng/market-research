from __future__ import annotations

import hashlib

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss002_llm_contract import build_prompt_envelope, extraction_template
from marketlab.ss002_llm_interactive import seal_interactive_response


def _selection():
    text="The company proposes a buyback at INR 500 per share."
    prompt=build_prompt_envelope(
        document_id="doc1",
        source_url="https://nsearchives.nseindia.com/x.pdf",
        event_ids=["event1"],
        symbols=["TEST"],
        category_hints=["BUYBACK"],
        segments=[{
            "segment_id":"doc1:pdf:page:0001",
            "text":text,
            "text_sha256":hashlib.sha256(text.encode()).hexdigest(),
        }],
        segment_manifest_sha256="c"*64,
    )
    return {
        "pilot_family":"BUYBACK",
        "symbol":"TEST",
        "announcement_id":"event1",
        "document_id":"doc1",
        "prompt_sha256":prompt["prompt_sha256"],
        "prompt_envelope":prompt,
    }


def _registration():
    return {
        "run_id":"SS002-L001-P1-GPT56SOL-INTERACTIVE-v1",
        "selection_sha256":"c040c519b8d28344a607838d2f025555b92fb9391582855e2dab7323aa805bc0",
        "contract_id":"SS002-L001-v1",
        "provider_runtime":"CHATGPT_INTERACTIVE",
        "model_id":"GPT-5.6 Sol",
        "model_configuration":{"temperature":"NOT_EXPOSED"},
        "return_outcomes_opened":False,
    }


def _raw():
    x=extraction_template(document_id="doc1",event_ids=["event1"],symbols=["TEST"])
    x.pop("provenance")
    x["economic_relevance"]="DIRECT_LISTED_SECURITY"
    x["transaction_families"]=["BUYBACK"]
    x["transaction_stage"]="PROPOSAL"
    x["facts"]["security_economics"]["offer_price_per_share"]={
        "status":"EXPLICIT",
        "value":500,
        "unit":"INR_PER_SHARE",
        "evidence_segment_ids":["doc1:pdf:page:0001"],
    }
    return x


def test_interactive_sealer_injects_bound_provenance() -> None:
    result=seal_interactive_response(
        raw_extraction=_raw(),
        selection_row=_selection(),
        registration=_registration(),
    )
    p=result["validated_extraction"]["provenance"]
    assert p["provider_runtime"]=="CHATGPT_INTERACTIVE"
    assert p["model_id"]=="GPT-5.6 Sol"
    assert len(p["raw_model_response_sha256"])==64
    assert result["portfolio_eligibility_allowed"] is False


def test_interactive_sealer_rejects_prefilled_provenance() -> None:
    raw=_raw(); raw["provenance"]={"model_id":"invented"}
    with pytest.raises(AlphaContractError,match="must not prefill provenance"):
        seal_interactive_response(
            raw_extraction=raw,
            selection_row=_selection(),
            registration=_registration(),
        )
