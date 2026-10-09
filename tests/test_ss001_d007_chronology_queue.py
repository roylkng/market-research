from __future__ import annotations

import hashlib

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss001_d007_chronology_queue import (
    D003_SHA,
    ISSUERS,
    MODEL_CONFIG_SHA,
    P1_RUN_ID,
    P1_RUN_SHA,
    Q002_SHA,
    build_p2_queue,
)


def _segment(document_id: str, number: int) -> dict:
    text = f"{document_id} page {number}"
    return {
        "segment_id": f"{document_id}:pdf:page:{number:04d}",
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def _fixture() -> tuple[dict, dict, dict, dict[str, dict]]:
    packets = []
    manifests = []
    payloads: dict[str, dict] = {}
    p1_rows = []
    document_counter = 0
    announcement_counter = 0

    # 82 distinct documents: 12 P1 reuse + 70 fresh.
    # Fresh segment total: 69*17 + 67 = 1,240.
    docs_by_issuer: list[list[str]] = [[] for _ in ISSUERS]
    for issuer_index, symbol in enumerate(ISSUERS):
        reuse_id = hashlib.sha256(f"reuse-{symbol}".encode()).hexdigest()
        docs_by_issuer[issuer_index].append(reuse_id)
        document_counter += 1

    for fresh_index in range(70):
        issuer_index = fresh_index % len(ISSUERS)
        doc_id = hashlib.sha256(f"fresh-{fresh_index}".encode()).hexdigest()
        docs_by_issuer[issuer_index].append(doc_id)
        document_counter += 1
    assert document_counter == 82

    selected_doc_index = 0
    all_selected_manifest_rows = []
    for issuer_index, symbol in enumerate(ISSUERS):
        events = []
        for local_index, doc_id in enumerate(docs_by_issuer[issuer_index], start=1):
            is_reuse = local_index == 1
            if is_reuse:
                segment_count = 1
            else:
                # global fresh index is derived from document id lookup.
                fresh_no = next(
                    idx
                    for idx in range(70)
                    if hashlib.sha256(f"fresh-{idx}".encode()).hexdigest() == doc_id
                )
                segment_count = 67 if fresh_no == 69 else 17
            segments = [_segment(doc_id, n) for n in range(1, segment_count + 1)]
            manifest_sha = digest(
                {
                    "document_id": doc_id,
                    "segments": [
                        {"segment_id": s["segment_id"], "text_sha256": s["text_sha256"]}
                        for s in segments
                    ],
                }
            )
            event_id = hashlib.sha256(
                f"event-{symbol}-{local_index}".encode()
            ).hexdigest()
            url = f"https://nsearchives.nseindia.com/corporate/{doc_id}.pdf"
            manifest = {
                "document_id": doc_id,
                "source_url": url,
                "event_ids": [event_id],
                "symbols": [symbol],
                "categories": ["RIGHTS_ISSUE"],
                "extraction_state": "READY",
                "hash_reproduced": True,
                "segment_count": segment_count,
                "segment_ids": [s["segment_id"] for s in segments],
                "segment_manifest_sha256": manifest_sha,
            }
            manifests.append(manifest)
            all_selected_manifest_rows.append(manifest)
            payloads[doc_id] = {
                "document_id": doc_id,
                "source_url": url,
                "extraction_state": "READY",
                "hash_reproduced": True,
                "segment_manifest_sha256": manifest_sha,
                "segments": segments,
            }
            events.append(
                {
                    "event_id": event_id,
                    "binding_state": "TEXT_READY",
                    "document_id": doc_id,
                    "source_url": url,
                    "segment_count": segment_count,
                    "segment_ids": [s["segment_id"] for s in segments],
                    "segment_manifest_sha256": manifest_sha,
                }
            )
            announcement_counter += 1
            if is_reuse:
                p1_rows.append(
                    {
                        "issuer_packet_rank": issuer_index + 1,
                        "symbol": symbol,
                        "document_id": doc_id,
                        "source_event_id": event_id,
                        "prompt_sha256": "a" * 64,
                        "segment_manifest_sha256": manifest_sha,
                        "model_config_sha256": MODEL_CONFIG_SHA,
                        "raw_model_response_sha256": "b" * 64,
                        "validated_extraction": {
                            "document_id": doc_id,
                            "event_ids": [event_id],
                            "symbols": [symbol],
                            "validated_structured_output_sha256": "c" * 64,
                        },
                    }
                )
            selected_doc_index += 1

        packets.append(
            {
                "symbol": symbol,
                "review_queue_rank": issuer_index + 1,
                "announcement_evidence": events,
                "corporate_action_evidence": [
                    {
                        "ex_date": "2026-08-01",
                        "source_isin": f"ISIN{issuer_index}",
                        "source_raw_sha256": "d" * 64,
                        "subject": "Rights",
                    }
                ],
            }
        )

    # Add 13 duplicate announcement refs without adding new documents.
    for index in range(13):
        packet = packets[index % 12]
        original = packet["announcement_evidence"][0]
        duplicate = dict(original)
        duplicate["event_id"] = hashlib.sha256(f"duplicate-{index}".encode()).hexdigest()
        packet["announcement_evidence"].append(duplicate)
        # D003 document metadata must list the additional linked event.
        doc_id = duplicate["document_id"]
        manifest = next(row for row in manifests if row["document_id"] == doc_id)
        manifest["event_ids"].append(duplicate["event_id"])
        announcement_counter += 1
        p1_row = next(
            row for row in p1_rows if row["document_id"] == doc_id
        )
        p1_row["validated_extraction"]["event_ids"].append(duplicate["event_id"])

    assert announcement_counter == 95

    # Fill D003 manifest to its frozen 1,539 documents.
    for index in range(1539 - len(manifests)):
        filler = hashlib.sha256(f"filler-{index}".encode()).hexdigest()
        manifests.append({"document_id": filler})

    q002 = {
        "binding_id": "SS001-D007-Q002-v1",
        "binding_sha256": Q002_SHA,
        "pilot_packet_count": 50,
        "source_d003_corpus_sha256": D003_SHA,
        "feasibility_pass": True,
        "packets": packets + [
            {
                "symbol": f"EXTRA{i}",
                "review_queue_rank": 13 + i,
                "announcement_evidence": [],
                "corporate_action_evidence": [],
            }
            for i in range(38)
        ],
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    d003 = {
        "corpus_id": "SS002-D003-v1",
        "corpus_sha256": D003_SHA,
        "document_count": 1539,
        "documents": manifests,
        "llm_inference_executed": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    p1 = {
        "run_id": P1_RUN_ID,
        "run_sha256": P1_RUN_SHA,
        "model_config_sha256": MODEL_CONFIG_SHA,
        "selected_request_count": 12,
        "validated_response_count": 12,
        "rows": p1_rows,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    return q002, d003, p1, payloads


def test_complete_chronology_queue_has_exact_frozen_counts() -> None:
    q002, d003, p1, payloads = _fixture()
    queue = build_p2_queue(
        q002=q002,
        d003=d003,
        p1_run=p1,
        read_document=lambda doc_id: payloads[doc_id],
    )
    assert queue["feasibility_pass"] is True
    assert queue["issuer_count"] == 12
    assert queue["announcement_reference_count"] == 95
    assert queue["corporate_action_row_count"] == 12
    assert queue["distinct_document_count"] == 82
    assert queue["p1_reuse_document_count"] == 12
    assert queue["fresh_document_count"] == 70
    assert queue["fresh_request_count"] == 1240
    assert set(queue["shard_request_counts"]) == set(range(16))
    assert sum(queue["shard_request_counts"].values()) == 1240
    assert queue["model_inference_executed"] is False
    assert queue["share_action_clearance_proven"] is False
    assert queue["market_capitalization_calculated"] is False


def test_every_fresh_request_contains_one_original_d003_segment() -> None:
    q002, d003, p1, payloads = _fixture()
    queue = build_p2_queue(
        q002=q002,
        d003=d003,
        p1_run=p1,
        read_document=lambda doc_id: payloads[doc_id],
    )
    assert len({row["segment_id"] for row in queue["requests"]}) == 1240
    assert all(
        len(row["prompt_envelope"]["request"]["segments"]) == 1
        for row in queue["requests"]
    )
    assert all(
        row["prompt_envelope"]["request"]["segments"][0]["segment_id"]
        == row["segment_id"]
        for row in queue["requests"]
    )


def test_p1_reuse_requires_exact_segment_manifest() -> None:
    q002, d003, p1, payloads = _fixture()
    p1["rows"][0]["segment_manifest_sha256"] = "0" * 64
    with pytest.raises(AlphaContractError, match="reuse segment manifest mismatch"):
        build_p2_queue(
            q002=q002,
            d003=d003,
            p1_run=p1,
            read_document=lambda doc_id: payloads[doc_id],
        )


def test_tampered_d003_segment_fails_closed() -> None:
    q002, d003, p1, payloads = _fixture()
    fresh_doc = next(
        doc_id
        for doc_id in payloads
        if doc_id not in {row["document_id"] for row in p1["rows"]}
    )
    payloads[fresh_doc]["segments"][0]["text"] = "tampered"
    with pytest.raises(AlphaContractError, match="segment text SHA mismatch"):
        build_p2_queue(
            q002=q002,
            d003=d003,
            p1_run=p1,
            read_document=lambda doc_id: payloads[doc_id],
        )
