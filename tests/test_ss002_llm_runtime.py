from __future__ import annotations

import hashlib
import json

import pytest
import requests

from marketlab.ss002_llm_contract import build_prompt_envelope, extraction_template
from marketlab.ss002_llm_runtime import (
    OpenAICompatibleConfig,
    SS002LLMRuntimeError,
    build_chat_request,
    execute_l001_request,
)


def _prompt() -> dict:
    text="The company proposes a buyback at INR 500 per share."
    segments=[{
        "segment_id":"doc1:pdf:page:0001",
        "text":text,
        "text_sha256":hashlib.sha256(text.encode()).hexdigest(),
    }]
    return build_prompt_envelope(
        document_id="doc1",
        source_url="https://nsearchives.nseindia.com/x.pdf",
        event_ids=["event1"],
        symbols=["TEST"],
        category_hints=["BUYBACK"],
        segments=segments,
        segment_manifest_sha256="c"*64,
    )


def _output() -> dict:
    out=extraction_template(
        document_id="doc1",
        event_ids=["event1"],
        symbols=["TEST"],
    )
    out["economic_relevance"]="DIRECT_LISTED_SECURITY"
    out["transaction_families"]=["BUYBACK"]
    out["transaction_stage"]="PROPOSAL"
    out["facts"]["security_economics"]["offer_price_per_share"]={
        "status":"EXPLICIT",
        "value":500,
        "unit":"INR_PER_SHARE",
        "evidence_segment_ids":["doc1:pdf:page:0001"],
    }
    return out


class FakeResponse:
    def __init__(self,payload:dict,status:int=200):
        self._payload=payload
        self.status_code=status
        self.content=json.dumps(payload,sort_keys=True).encode()

    def raise_for_status(self):
        if self.status_code>=400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self,response:FakeResponse):
        self.response=response
        self.calls=[]

    def post(self,url,**kwargs):
        self.calls.append((url,kwargs))
        return self.response


def _config()->OpenAICompatibleConfig:
    return OpenAICompatibleConfig(
        provider_runtime="TEST_OPENAI_COMPATIBLE",
        base_url="http://127.0.0.1:8000",
        model_id="test-model",
        temperature=0.0,
        max_output_tokens=2048,
    )


def test_chat_request_is_deterministic_and_non_streaming() -> None:
    body=build_chat_request(prompt_envelope=_prompt(),config=_config())
    assert body["model"]=="test-model"
    assert body["temperature"]==0.0
    assert body["response_format"]=={"type":"json_object"}
    assert body["stream"] is False


def test_runtime_injects_provenance_and_validates_extraction() -> None:
    payload={
        "choices":[
            {
                "message":{
                    "content":json.dumps(_output(),sort_keys=True)
                }
            }
        ]
    }
    session=FakeSession(FakeResponse(payload))
    result=execute_l001_request(
        prompt_envelope=_prompt(),
        config=_config(),
        api_key="secret",
        session=session,
    )
    extraction=result["validated_extraction"]
    assert extraction["economic_relevance"]=="DIRECT_LISTED_SECURITY"
    assert extraction["provenance"]["model_id"]=="test-model"
    assert extraction["provenance"]["input_document_id"]=="doc1"
    assert result["portfolio_eligibility_allowed"] is False
    url,kwargs=session.calls[0]
    assert url=="http://127.0.0.1:8000/v1/chat/completions"
    assert kwargs["headers"]["Authorization"]=="Bearer secret"


def test_invalid_model_evidence_is_rejected_not_reprompted() -> None:
    output=_output()
    output["facts"]["security_economics"]["offer_price_per_share"][
        "evidence_segment_ids"
    ]=["invented"]
    payload={"choices":[{"message":{"content":json.dumps(output)}}]}
    session=FakeSession(FakeResponse(payload))
    with pytest.raises(Exception,match="unknown evidence"):
        execute_l001_request(
            prompt_envelope=_prompt(),
            config=_config(),
            api_key=None,
            session=session,
        )
    assert len(session.calls)==1


def test_transport_failure_is_explicit() -> None:
    session=FakeSession(FakeResponse({"error":"bad"},status=500))
    with pytest.raises(SS002LLMRuntimeError,match="LLM_REQUEST_FAILED"):
        execute_l001_request(
            prompt_envelope=_prompt(),
            config=_config(),
            api_key=None,
            session=session,
        )
