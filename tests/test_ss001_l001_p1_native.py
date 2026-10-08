from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss001_l001_relevance_queue import QUEUE_ID as P0_QUEUE_ID
from marketlab.ss002_llm_contract import build_prompt_envelope

from scripts.materialize_ss001_l001_p1_native import (
    FROZEN_SYMBOLS,
    SOURCE_QUEUE_SHA,
    build_native_p1,
)

ASSERTIONS = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "ss001"
    / "ss001-d007-l001-p1-gpt6-native-assertions-v1.json"
)


def _fixture() -> tuple[dict, dict]:
    assertions = json.loads(ASSERTIONS.read_text(encoding="utf-8"))
    rows = []
    for rank, native in enumerate(assertions["responses"], start=1):
        symbol = native["symbol"]
        assert symbol == FROZEN_SYMBOLS[rank - 1]
        page_count = max(fact["page"] for fact in native["facts"])
        doc_id = hashlib.sha256(symbol.encode()).hexdigest()
        segments = []
        for page in range(1, page_count + 1):
            text = f"Mock source page {page} for {symbol}; structure-only fixture"
            segments.append(
                {
                    "segment_id": f"{doc_id}:pdf:page:{page:04d}",
                    "text": text,
                    "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                }
            )
        event_id = hashlib.sha256(f"event-{symbol}".encode()).hexdigest()
        envelope = build_prompt_envelope(
            document_id=doc_id,
            source_url=f"https://nsearchives.nseindia.com/corporate/{symbol}.pdf",
            event_ids=[event_id],
            symbols=[symbol],
            category_hints=native["families"],
            segments=segments,
            segment_manifest_sha256=hashlib.sha256(doc_id.encode()).hexdigest(),
        )
        rows.append(
            {
                "issuer_packet_rank": rank,
                "symbol": symbol,
                "selection_state": "SELECTED_COMPLETE_DOCUMENT",
                "source_event_id": event_id,
                "prompt_sha256": envelope["prompt_sha256"],
                "prompt_envelope": envelope,
            }
        )
    queue = {
        "queue_id": P0_QUEUE_ID,
        "queue_sha256": SOURCE_QUEUE_SHA,
        "feasibility_pass": True,
        "selected_document_count": 12,
        "model_inference_executed": False,
        "rows": rows,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
    }
    return queue, assertions


def test_native_model_authored_assertions_validate_against_frozen_contract() -> None:
    queue, assertions = _fixture()
    output = build_native_p1(queue, assertions)
    assert output["pilot_id"] == "SS001-D007-L001-P1-GPT6-NATIVE-v1"
    assert output["issuer_count"] == 12
    assert output["validated_response_count"] == 12
    assert output["explicit_fact_count"] >= 60
    assert output["mechanical_pass"] is True
    assert len({row["document_id"] for row in output["rows"]}) == 12
    assert output["independent_human_audit_completed"] is False
    assert output["market_capitalization_calculated"] is False
    assert output["share_action_clearance_proven"] is False
    assert output["live_capital_allowed"] is False
    assert all(
        row["validated_extraction"]["provenance"]["model_id"] == "GPT-6"
        for row in output["rows"]
    )


def test_native_assertion_cannot_cite_nonexistent_page() -> None:
    queue, assertions = _fixture()
    assertions["responses"][0]["facts"][0]["page"] = 999
    with pytest.raises(AlphaContractError, match="no unique original segment"):
        build_native_p1(queue, assertions)


def test_native_assertion_cannot_change_source_identity() -> None:
    queue, assertions = _fixture()
    assertions["responses"][0]["symbol"] = "ANOTHER"
    with pytest.raises(AlphaContractError, match="source symbol/order changed"):
        build_native_p1(queue, assertions)


def test_native_assertion_cannot_claim_independent_audit() -> None:
    queue, assertions = _fixture()
    assertions["independent_human_audit_completed"] = True
    with pytest.raises(AlphaContractError, match="cannot claim independent audit"):
        build_native_p1(queue, assertions)


def test_source_queue_cannot_claim_market_cap_or_live_capital() -> None:
    queue, assertions = _fixture()
    queue["market_capitalization_calculated"] = True
    with pytest.raises(AlphaContractError, match="market_capitalization_calculated=false"):
        build_native_p1(queue, assertions)
