from __future__ import annotations

import hashlib

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss001_l001_relevance_queue import build_l001_p0_queue

Q002_SHA = "c3c28d55b98a08c91e99b76d5ae2732f2ca24406fa12752be2f0e75fa0624f36"
D003_SHA = "92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce"
D002_SHA = "eab922954ef20a12a7635107722b4e800b59cfa56ff0659da42afb3fc22218f9"


def _fixture() -> tuple[dict, dict, dict]:
    packets = []
    docs = []
    payloads = {}
    for i in range(1, 51):
        symbol = f"S{i:03d}"
        evidence = []
        if i <= 12:
            doc_id = hashlib.sha256(f"doc-{i}".encode()).hexdigest()
            event_id = f"event-{i}"
            url = f"https://nsearchives.nseindia.com/corporate/doc{i}.pdf"
            segment_id = f"{doc_id}:pdf:page:0001"
            text = f"The listed issuer {symbol} states a proposed buyback."
            segment_sha = hashlib.sha256(text.encode()).hexdigest()
            manifest_sha = hashlib.sha256(segment_id.encode()).hexdigest()
            evidence = [
                {
                    "event_id": event_id,
                    "document_id": doc_id,
                    "binding_state": "TEXT_READY",
                    "segment_ids": [segment_id],
                    "segment_count": 1,
                    "segment_manifest_sha256": manifest_sha,
                    "source_url": url,
                }
            ]
            docs.append(
                {
                    "document_id": doc_id,
                    "source_url": url,
                    "event_ids": [event_id],
                    "symbols": [symbol],
                    "categories": ["BUYBACK"],
                    "segment_ids": [segment_id],
                    "segment_manifest_sha256": manifest_sha,
                }
            )
            payloads[doc_id] = {
                "document_id": doc_id,
                "source_url": url,
                "extraction_state": "READY",
                "hash_reproduced": True,
                "segment_manifest_sha256": manifest_sha,
                "segments": [
                    {
                        "segment_id": segment_id,
                        "text": text,
                        "text_sha256": segment_sha,
                    }
                ],
            }
        packets.append(
            {
                "symbol": symbol,
                "review_queue_rank": i,
                "announcement_evidence": evidence,
            }
        )
    for j in range(1539 - len(docs)):
        docs.append({"document_id": hashlib.sha256(f"extra-{j}".encode()).hexdigest()})

    q002 = {
        "binding_id": "SS001-D007-Q002-v1",
        "binding_sha256": Q002_SHA,
        "source_d003_corpus_sha256": D003_SHA,
        "feasibility_pass": True,
        "pilot_packet_count": 50,
        "packets": packets,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    d003 = {
        "corpus_id": "SS002-D003-v1",
        "corpus_sha256": D003_SHA,
        "source_d002_corpus_sha256": D002_SHA,
        "document_count": 1539,
        "documents": docs,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    return q002, d003, payloads


def test_exact_first_12_get_complete_hash_bound_prompts() -> None:
    q002, d003, payloads = _fixture()
    result = build_l001_p0_queue(
        q002=q002,
        d003=d003,
        read_document=lambda doc_id: payloads[doc_id],
    )
    assert result["feasibility_pass"] is True
    assert result["issuer_count"] == 12
    assert result["selected_document_count"] == 12
    assert result["rows"][0]["symbol"] == "S001"
    assert result["rows"][-1]["symbol"] == "S012"
    assert len({row["document_id"] for row in result["rows"]}) == 12
    assert all(row["prompt_envelope"]["request"]["segments"] for row in result["rows"])
    assert result["model_inference_executed"] is False
    assert result["market_capitalization_calculated"] is False
    assert result["live_capital_allowed"] is False


def test_oversized_document_is_not_silently_truncated() -> None:
    q002, d003, payloads = _fixture()
    first_id = q002["packets"][0]["announcement_evidence"][0]["document_id"]
    payloads[first_id]["segments"][0]["text"] = "X" * 32001
    payloads[first_id]["segments"][0]["text_sha256"] = hashlib.sha256(
        ("X" * 32001).encode()
    ).hexdigest()
    result = build_l001_p0_queue(
        q002=q002,
        d003=d003,
        read_document=lambda doc_id: payloads[doc_id],
    )
    assert result["feasibility_pass"] is False
    assert result["selected_document_count"] == 11
    assert result["rows"][0]["selection_state"] == "SOURCE_OR_CONTEXT_LIMIT"
    assert result["rows"][0]["ignored_prior_candidates"][0]["reason"] == (
        "COMPLETE_DOCUMENT_EXCEEDS_TRANSPORT_BOUNDS"
    )


def test_tampered_d003_segment_text_fails_closed() -> None:
    q002, d003, payloads = _fixture()
    first_id = q002["packets"][0]["announcement_evidence"][0]["document_id"]
    payloads[first_id]["segments"][0]["text"] = "fabricated text"
    with pytest.raises(AlphaContractError, match="text SHA mismatch"):
        build_l001_p0_queue(
            q002=q002,
            d003=d003,
            read_document=lambda doc_id: payloads[doc_id],
        )


def test_input_with_market_cap_claim_is_rejected() -> None:
    q002, d003, payloads = _fixture()
    q002["market_capitalization_calculated"] = True
    with pytest.raises(AlphaContractError, match="refuses market capitalization"):
        build_l001_p0_queue(
            q002=q002,
            d003=d003,
            read_document=lambda doc_id: payloads[doc_id],
        )
