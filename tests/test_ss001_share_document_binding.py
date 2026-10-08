from __future__ import annotations

import hashlib

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss001_share_document_binding import build_q002_document_binding

Q001_SHA = "53aea9016adfc62abfd778a1eb7b4bd6f6de262c30d01f1b7edf91abf2dbb4be"
D002_SHA = "eab922954ef20a12a7635107722b4e800b59cfa56ff0659da42afb3fc22218f9"
D003_SHA = "92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce"


def _inputs() -> tuple[dict, dict, dict, dict]:
    packets = []
    d002_documents = []
    d003_documents = []
    counter = 0

    for rank in range(1, 51):
        symbol = f"S{rank:03d}"
        if rank <= 24:
            state, action_count, count = "BOTH_SOURCES_REVIEW_REQUIRED", 1, 8 if rank == 1 else 7
        elif rank <= 35:
            state, action_count, count = "CORPORATE_ACTION_REVIEW_REQUIRED", 1, 0
        else:
            state, action_count, count = "ANNOUNCEMENT_REVIEW_REQUIRED", 0, 5

        announcements = []
        for _ in range(count):
            counter += 1
            event_id = f"event-{counter:04d}"
            has_document = counter != 244
            url = (
                f"https://nsearchives.nseindia.com/corporate/test-{counter:04d}.pdf"
                if has_document
                else None
            )
            announcements.append(
                {
                    "event_id": event_id,
                    "source_attachment_url": url,
                    "attachment_link_state": (
                        "APPROVED_NSE_ATTACHMENT_LINK"
                        if has_document
                        else "OFFICIAL_DOCUMENT_LINK_UNAVAILABLE"
                    ),
                }
            )
            if has_document:
                doc_id = hashlib.sha256(url.encode()).hexdigest()
                segment_id = f"{doc_id}:pdf:page:0001"
                d002_documents.append(
                    {
                        "source_url": url,
                        "status": "READY",
                        "document_id": doc_id,
                        "event_ids": [event_id],
                        "symbols": [symbol],
                    }
                )
                d003_documents.append(
                    {
                        "document_id": doc_id,
                        "event_ids": [event_id],
                        "symbols": [symbol],
                        "extraction_state": "READY",
                        "hash_reproduced": True,
                        "segment_count": 1,
                        "segment_ids": [segment_id],
                        "segment_manifest_sha256": hashlib.sha256(segment_id.encode()).hexdigest(),
                    }
                )

        packets.append(
            {
                "symbol": symbol,
                "review_queue_rank": rank,
                "in_first_50_pilot": True,
                "review_state": state,
                "source_record_count": count + action_count,
                "corporate_action_evidence": [
                    {
                        "subject": "Bonus",
                        "ex_date": "2026-09-01",
                        "source_raw_sha256": "a" * 64,
                    }
                    for _ in range(action_count)
                ],
                "announcement_evidence": announcements,
                "review_questions": ["Was there a share-count change?"],
                "share_action_clearance_proven": False,
                "capitalization_calculation_allowed": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )
    assert counter == 244
    assert len(d002_documents) == 243

    source_queue = {
        "queue_id": "SS001-D007-Q001-v1",
        "queue_sha256": Q001_SHA,
        "review_packet_count": 331,
        "pilot_packet_count": 50,
        "packets": packets + [{"symbol": f"REST-{i}"} for i in range(281)],
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    pilot = {
        "queue_id": "SS001-D007-Q001-v1",
        "source_queue_sha256": Q001_SHA,
        "packet_count": 50,
        "packets": packets,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    d002 = {
        "corpus_id": "SS002-D002-v1",
        "corpus_sha256": D002_SHA,
        "documents": d002_documents,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    for i in range(1539 - len(d003_documents)):
        d003_documents.append({"document_id": hashlib.sha256(f"extra-{i}".encode()).hexdigest()})
    d003 = {
        "corpus_id": "SS002-D003-v1",
        "corpus_sha256": D003_SHA,
        "source_d002_corpus_sha256": D002_SHA,
        "documents": d003_documents,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    return source_queue, pilot, d002, d003


def test_q002_exact_link_binding_keeps_all_decisions_disabled() -> None:
    q001, pilot, d002, d003 = _inputs()
    result = build_q002_document_binding(queue=q001, pilot=pilot, d002=d002, d003=d003)
    assert result["feasibility_pass"] is True
    assert result["pilot_packet_count"] == 50
    assert result["announcement_reference_count"] == 244
    assert result["event_binding_state_counts"] == {
        "NO_OFFICIAL_ATTACHMENT": 1,
        "TEXT_READY": 243,
    }
    assert result["unique_text_ready_document_count"] == 243
    assert result["share_action_clearance_proven"] is False
    assert result["market_capitalization_calculated"] is False
    assert all(packet["capitalization_calculation_allowed"] is False for packet in result["packets"])


def test_q002_rejects_wrong_source_url_for_event() -> None:
    q001, pilot, d002, d003 = _inputs()
    d002["documents"][0]["source_url"] = "https://nsearchives.nseindia.com/WRONG.pdf"
    with pytest.raises(AlphaContractError, match="official URL mismatch"):
        build_q002_document_binding(queue=q001, pilot=pilot, d002=d002, d003=d003)


def test_q002_rejects_event_with_inconsistent_document_issuer() -> None:
    q001, pilot, d002, d003 = _inputs()
    d003["documents"][0]["symbols"] = ["OTHER"]
    with pytest.raises(AlphaContractError, match="association mismatch"):
        build_q002_document_binding(queue=q001, pilot=pilot, d002=d002, d003=d003)


def test_q002_requires_original_first_50_packet_order() -> None:
    q001, pilot, d002, d003 = _inputs()
    pilot["packets"] = list(reversed(pilot["packets"]))
    with pytest.raises(AlphaContractError, match="exact first 50"):
        build_q002_document_binding(queue=q001, pilot=pilot, d002=d002, d003=d003)


def test_q002_refuses_capitalization_in_input() -> None:
    q001, pilot, d002, d003 = _inputs()
    q001["market_capitalization_calculated"] = True
    with pytest.raises(AlphaContractError, match="cannot contain capitalizations"):
        build_q002_document_binding(queue=q001, pilot=pilot, d002=d002, d003=d003)
